from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from .decorators import login_required_message, post_required, profile_of
from .forms import ChangePasswordForm, EditProfileForm, SignInForm, SignUpForm
from .models import LoginAttempt, Notification, UserProfile

MAX_LOGIN_FAILURES = 6
LOCK_MINUTES = 15


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()[:45]
    return request.META.get('REMOTE_ADDR', '')[:45]


def _safe_next(request, fallback='/'):
    """Never redirect to another site, and never back to a sign in page."""
    target = request.POST.get('next') or request.GET.get('next') or ''
    if not target or not target.startswith('/') or target.startswith('//'):
        return fallback
    if any(bit in target for bit in ('/signin', '/signup', '/login')):
        return fallback
    return target


# signup

def signup(request):
    if request.user.is_authenticated:
        messages.info(request, 'You are already signed in.')
        return redirect('home')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                user = User.objects.create_user(
                    username=data['email'],
                    email=data['email'],
                    password=data['password'],
                )
                # the post_save signal has already made the profile
                profile = user.UserProfile
                profile.name = data['name']
                profile.email = data['email']
                profile.contact_no = data.get('contact_no') or ''
                profile.nid = data.get('nid') or None
                profile.role = data['role']
                profile.save()

            Notification.push(
                profile,
                f'Welcome to {settings.SITE_NAME}',
                'Complete your profile so owners know who they are talking to.',
                reverse('edit_profile'),
                Notification.Kind.SYSTEM,
            )
            messages.success(request, 'Account created. Please sign in.')
            return redirect('signin')
        messages.error(request, 'Please fix the highlighted fields.')
    else:
        form = SignUpForm()

    return render(request, 'signup.html', {'form': form})


# signin

def signin(request):
    if request.user.is_authenticated:
        messages.info(request, 'You are already signed in.')
        return redirect('home')

    locked = False
    form = SignInForm(request)

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip().lower()
        failures = LoginAttempt.recent_failures(username, LOCK_MINUTES)

        if failures >= MAX_LOGIN_FAILURES:
            locked = True
            messages.error(
                request,
                f'Too many failed attempts. Try again in {LOCK_MINUTES} minutes.',
            )
            form = SignInForm(request, data=request.POST)
        else:
            form = SignInForm(request, data=request.POST)
            if form.is_valid():
                user = form.get_user()
                LoginAttempt.objects.create(
                    username=username, ip=client_ip(request), successful=True
                )
                login(request, user)
                request.session.cycle_key()
                messages.success(request, f'Welcome back, {user.UserProfile.first_name}.')
                return redirect(_safe_next(request, '/'))

            LoginAttempt.objects.create(
                username=username, ip=client_ip(request), successful=False
            )
            # A suspended account is deactivated, so Django's own check fails
            # with the same wording as a wrong password. Say what actually
            # happened instead, or the person keeps retrying a good password.
            held = UserProfile.objects.filter(
                user__username__iexact=username, is_suspended=True).first()
            if held:
                # Drop the form's own "wrong email or password", which is not
                # what happened and reads as a contradiction beside this.
                form.errors.clear()
                messages.error(
                    request,
                    'This account is suspended. {}Write to {} if you think that '
                    'is a mistake.'.format(
                        f'Reason given: {held.suspended_reason} '
                        if held.suspended_reason else '',
                        settings.SITE_EMAIL,
                    ),
                )
                return render(request, 'signin.html', {
                    'form': form, 'locked': False,
                    'next': _safe_next(request, ''),
                })

            left = MAX_LOGIN_FAILURES - failures - 1
            if 0 < left <= 2:
                messages.warning(request, f'{left} attempt(s) left before a lockout.')

    return render(request, 'signin.html', {
        'form': form,
        'locked': locked,
        'next': _safe_next(request, ''),
    })


@login_required_message
@post_required
def signout(request):
    target = _safe_next(request, '/')
    logout(request)
    messages.success(request, 'Signed out.')
    return redirect(target)


# profile

@login_required_message
def profile(request):
    me = profile_of(request)
    from django.db.models import Sum
    stats = {
        'listings': me.properties.count(),
        'live': me.properties.filter(status='approved', is_archived=False).count(),
        'favourites': me.favourites.count(),
        'bookings': me.bookings_made.count(),
        'reviews_written': me.property_reviews.count(),
        'views': me.properties.aggregate(v=Sum('view_count'))['v'] or 0,
    }
    return render(request, 'profile.html', {
        'me': me,
        'stats': stats,
        'recent_logins': LoginAttempt.objects.filter(
            username=request.user.username)[:6],
        'active': 'profile',
    })


def public_profile(request, pk):
    """What other people see: listings and reputation, no private details."""
    from property.views import annotate_saved

    person = get_object_or_404(UserProfile, pk=pk)
    listings = list(person.properties.live().with_cards()[:12])
    annotate_saved(listings, profile_of(request))
    rating = person.properties.aggregate(v=Avg('reviews__rating'))['v']
    return render(request, 'public_profile.html', {
        'person': person,
        'listings': listings,
        'listing_count': person.properties.live().count(),
        'rating': round(rating, 1) if rating else None,
    })


@login_required_message
def edit_profile(request):
    me = profile_of(request)
    if request.method == 'POST':
        form = EditProfileForm(request.POST, request.FILES, instance=me)
        if form.is_valid():
            with transaction.atomic():
                updated = form.save()
                request.user.email = updated.email
                request.user.username = updated.email
                request.user.save(update_fields=['email', 'username'])
            messages.success(request, 'Profile updated.')
            return redirect('profile')
        messages.error(request, 'Please fix the highlighted fields.')
    else:
        form = EditProfileForm(instance=me)

    return render(request, 'edit_profile.html', {'form': form, 'active': 'profile'})


@login_required_message
def change_password(request):
    if request.method == 'POST':
        form = ChangePasswordForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, request.user)
            Notification.push(
                profile_of(request), 'Password changed',
                'Your password was changed just now.', reverse('profile'),
                Notification.Kind.ALERT,
            )
            messages.success(request, 'Password changed.')
            return redirect('profile')
        messages.error(request, 'Please fix the highlighted fields.')
    else:
        form = ChangePasswordForm(request.user)
    return render(request, 'change_password.html', {'form': form, 'active': 'profile'})


@login_required_message
def become_owner(request):
    me = profile_of(request)
    if request.method == 'POST' and me.role == UserProfile.Role.RENTER:
        me.role = UserProfile.Role.OWNER
        me.save(update_fields=['role', 'is_agent'])
        messages.success(request, 'You can list properties now.')
    return redirect('add_property')


@login_required_message
@post_required
def delete_account(request):
    password = request.POST.get('password', '')
    user = authenticate(username=request.user.username, password=password)
    if user is None:
        messages.error(request, 'That password is wrong. Nothing was deleted.')
        return redirect('profile')

    user.delete()
    logout(request)
    messages.success(request, 'Your account and everything on it has been deleted.')
    return redirect('home')


# dashboard

@login_required_message
def dashboard(request):
    """One page that answers: what is happening with my account right now."""
    from property.models import AllProperty, Booking, Conversation

    me = profile_of(request)
    from django.db.models import Sum

    my_properties = me.properties.with_cards()
    # separate calls: joining favourites in makes Sum count a property once
    # per favourite, which inflated the view total on this page only
    view_total = me.properties.aggregate(n=Sum('view_count'))['n'] or 0
    save_total = me.properties.aggregate(n=Count('favourited_by'))['n'] or 0

    stats = {
        'listings': me.properties.count(),
        'live': me.properties.filter(status=AllProperty.Status.APPROVED,
                                     is_archived=False).count(),
        'pending': me.properties.filter(status=AllProperty.Status.PENDING).count(),
        'views': view_total,
        'favourites_received': save_total,
        'saved': me.favourites.count(),
    }

    incoming = me.bookings_received.exclude(
        status__in=[Booking.Status.CANCELLED, Booking.Status.DECLINED]
    ).select_related('property', 'renter')[:5]
    outgoing = me.bookings_made.select_related('property', 'owner')[:5]

    threads = Conversation.objects.filter(
        Q(renter=me) | Q(owner=me)
    ).select_related('property', 'renter', 'owner')[:5]

    # 14 day view chart across everything the user owns
    from property.models import PropertyView
    since = timezone.localdate() - timezone.timedelta(days=13)
    rows = (PropertyView.objects
            .filter(property__user=me, viewed_on__gte=since)
            .values('viewed_on').annotate(n=Count('id')))
    by_day = {r['viewed_on']: r['n'] for r in rows}
    chart = []
    for i in range(13, -1, -1):
        day = timezone.localdate() - timezone.timedelta(days=i)
        # built from the date parts: strftime('%-d') is not portable to Windows
        chart.append({'label': f'{day.day}/{day.month}',
                      'value': by_day.get(day, 0)})
    chart_max = max([c['value'] for c in chart] + [1])

    return render(request, 'dashboard.html', {
        'me': me,
        'stats': stats,
        'my_properties': list(my_properties[:6]),
        'incoming': incoming,
        'outgoing': outgoing,
        'threads': threads,
        'chart': chart,
        'chart_max': chart_max,
        'notifications': me.notifications.all()[:6],
        'active': 'dashboard',
    })


# notifications

@login_required_message
def notifications(request):
    me = profile_of(request)
    show = request.GET.get('show', 'all')
    rows = me.notifications.all()
    if show == 'unread':
        rows = rows.filter(is_read=False)
    return render(request, 'notifications.html', {
        'rows': rows[:100],
        'show': show,
        'unread': me.notifications.filter(is_read=False).count(),
        'active': 'notifications',
    })


@login_required_message
@post_required
def read_notification(request, pk):
    me = profile_of(request)
    note = get_object_or_404(Notification, pk=pk, profile=me)
    note.is_read = True
    note.save(update_fields=['is_read'])
    if note.link:
        return redirect(note.link)
    return redirect('notifications')


@login_required_message
@post_required
def read_all_notifications(request):
    profile_of(request).notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, 'All caught up.')
    return redirect('notifications')


# password reset

def password_reset_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(request, 'That password reset link is invalid or has expired.')
        return redirect('password_reset')

    if request.method == 'POST':
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your password has been reset. Please sign in.')
            return redirect('signin')
    else:
        form = SetPasswordForm(user)

    return render(request, 'password_reset_confirm.html', {'form': form})
