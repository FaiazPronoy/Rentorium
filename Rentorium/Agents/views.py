from django.contrib import messages
from django.http import Http404
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from authentication.decorators import agent_required, post_required, profile_of
from authentication.models import Notification, UserProfile
from basic.models import Contact
from property.views import safe_back
from property.models import (
    AllProperty, Booking, Conversation, Favourite, PropertyReview, PropertyView,
)

from .models import AgentAction


def as_pk(raw):
    """An id from a query string, or None if it is not a usable one."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    # a huge number is not a missing row, it overflows the id column
    return value if 0 < value < 10 ** 12 else None


# dashboard

@agent_required
def agent_dashboard(request):
    """The approval queue, plus everything an agent needs to decide quickly."""
    pending = (AllProperty.objects
               .filter(status=AllProperty.Status.PENDING)
               .select_related('user')
               .prefetch_related('images')
               .order_by('created_at'))

    search = (request.GET.get('q') or '').strip()
    if search:
        pending = pending.filter(
            Q(Property_Name__icontains=search)
            | Q(Area__icontains=search)
            | Q(user__name__icontains=search)
        )

    pending_total = pending.count()
    pending = pending.with_cards()[:40]

    counts = {
        'pending': AllProperty.objects.filter(status=AllProperty.Status.PENDING).count(),
        'approved': AllProperty.objects.filter(status=AllProperty.Status.APPROVED).count(),
        'rejected': AllProperty.objects.filter(status=AllProperty.Status.REJECTED).count(),
        'total': AllProperty.objects.count(),
    }
    me = profile_of(request)

    return render(request, 'agent_dashboard.html', {
        'pending_properties': pending,
        'pending_total': pending_total,
        'counts': counts,
        'search': search,
        'my_actions_today': AgentAction.objects.filter(
            agent=me, created_at__date=timezone.localdate()).count(),
        'recent_actions': AgentAction.objects.select_related('agent', 'property')[:8],
        'active': 'agent',
    })


# the decisions

def _decide(request, listing, action, status, reason=''):
    me = profile_of(request)
    listing.status = status
    listing.Approval_by_Agent = me.name if status == AllProperty.Status.APPROVED else (
        'Cancel' if status == AllProperty.Status.REJECTED else listing.Approval_by_Agent
    )
    if status == AllProperty.Status.PENDING:
        # back in the queue, so it must not still read as approved by someone
        listing.Approval_by_Agent = None
    listing.rejection_reason = reason if status == AllProperty.Status.REJECTED else ''
    listing.save()

    AgentAction.objects.create(agent=me, property=listing, action=action, reason=reason)

    if listing.user:
        if status == AllProperty.Status.APPROVED:
            Notification.push(
                listing.user, 'Your listing is live',
                f'"{listing.Property_Name}" has been approved and is now searchable.',
                listing.get_absolute_url(), Notification.Kind.APPROVAL,
            )
        elif status == AllProperty.Status.REJECTED:
            Notification.push(
                listing.user, 'Your listing needs changes',
                reason or 'An agent asked for changes before it can go live.',
                reverse('update_property', args=[listing.pk]),
                Notification.Kind.APPROVAL,
            )


@agent_required
@post_required
def approve_property(request, property_id):
    listing = get_object_or_404(AllProperty, pk=property_id)
    _decide(request, listing, AgentAction.Action.APPROVED, AllProperty.Status.APPROVED)
    messages.success(request, f'"{listing.Property_Name}" is live.')
    return safe_back(request, reverse('agent_dashboard'))


@agent_required
@post_required
def reject_property(request, property_id):
    listing = get_object_or_404(AllProperty, pk=property_id)
    reason = (request.POST.get('reason') or '').strip()[:200]
    if not reason:
        messages.error(request, 'Say why, so the owner can fix it.')
        return redirect('agent_dashboard')
    _decide(request, listing, AgentAction.Action.REJECTED,
            AllProperty.Status.REJECTED, reason)
    messages.success(request, 'The owner has been told what to change.')
    return safe_back(request, reverse('agent_dashboard'))


@agent_required
@post_required
def cancel_approval(request, property_id):
    """Pulls a live listing back into the approval queue."""
    listing = get_object_or_404(AllProperty, pk=property_id)
    reason = (request.POST.get('reason') or 'Sent back for another look').strip()[:200]
    _decide(request, listing, AgentAction.Action.REVERTED,
            AllProperty.Status.PENDING, reason)
    messages.success(request, 'Approval withdrawn and the owner told.')
    return safe_back(request, reverse('agent_dashboard'))


@agent_required
@post_required
def verify_documents(request, property_id):
    listing = get_object_or_404(AllProperty, pk=property_id)
    me = profile_of(request)
    if not listing.Property_Documents:
        messages.error(request, 'There is no document on this listing to check.')
        return redirect('agent_dashboard')
    AgentAction.objects.create(
        agent=me, property=listing, action=AgentAction.Action.VERIFIED,
        reason=(request.POST.get('reason') or '')[:200],
    )
    if listing.user and not listing.user.is_verified:
        listing.user.is_verified = True
        listing.user.save(update_fields=['is_verified'])
        Notification.push(
            listing.user, 'You are verified',
            'An agent checked your ownership papers. A verified badge now shows '
            'on your listings.',
            reverse('profile'), Notification.Kind.APPROVAL,
        )
    messages.success(request, 'Documents marked as checked.')
    return safe_back(request, reverse('agent_dashboard'))


@agent_required
@post_required
def toggle_feature(request, property_id):
    listing = get_object_or_404(AllProperty, pk=property_id)
    listing.is_featured = not listing.is_featured
    listing.save(update_fields=['is_featured'])
    AgentAction.objects.create(
        agent=profile_of(request), property=listing,
        action=AgentAction.Action.FEATURED if listing.is_featured
        else AgentAction.Action.UNFEATURED,
    )
    if listing.is_featured and listing.user:
        Notification.push(
            listing.user, 'Your listing is featured',
            f'"{listing.Property_Name}" now shows on the front page.',
            listing.get_absolute_url(), Notification.Kind.APPROVAL,
        )
    messages.success(
        request, 'Featured on the front page.' if listing.is_featured else 'No longer featured.'
    )
    return safe_back(request, reverse('agent_dashboard'))


# stats

@agent_required
def agent_stats(request):
    live = AllProperty.objects.live()

    by_type = []
    for key, label in AllProperty.PROPERTY_TYPES:
        rows = live.filter(Property_type=key)
        by_type.append({
            'label': label,
            'count': rows.count(),
            'avg_price': rows.aggregate(v=Avg('Price'))['v'] or 0,
            'colour': {'residential': '#009C6B', 'commercial': '#0FB5AE',
                       'land': '#2E8FB8'}[key],
        })

    by_area = (live.values('Area')
               .annotate(n=Count('id'), avg=Avg('Price'))
               .order_by('-n')[:10])

    since = timezone.localdate() - timezone.timedelta(days=13)
    view_rows = (PropertyView.objects.filter(viewed_on__gte=since)
                 .values('viewed_on').annotate(n=Count('id')))
    by_day = {r['viewed_on']: r['n'] for r in view_rows}
    chart = []
    for i in range(13, -1, -1):
        day = timezone.localdate() - timezone.timedelta(days=i)
        chart.append({'label': day.strftime('%d/%m'), 'value': by_day.get(day, 0)})
    chart_max = max([c['value'] for c in chart] + [1])

    # walk back a calendar month at a time, not 30 days
    signup_rows = []
    month_start = timezone.localdate().replace(day=1)
    months = []
    for _ in range(6):
        months.append(month_start)
        month_start = (month_start - timezone.timedelta(days=1)).replace(day=1)
    for start in reversed(months):
        next_month = (start + timezone.timedelta(days=32)).replace(day=1)
        signup_rows.append({
            'label': start.strftime('%b'),
            'value': UserProfile.objects.filter(
                created_at__date__gte=start,
                created_at__date__lt=next_month).count(),
        })
    signup_max = max([r['value'] for r in signup_rows] + [1])

    return render(request, 'agent_stats.html', {
        'totals': {
            'listings': AllProperty.objects.count(),
            'live': live.count(),
            'users': UserProfile.objects.count(),
            'owners': UserProfile.objects.filter(properties__isnull=False)
                                         .distinct().count(),
            'views': PropertyView.objects.count(),
            'bookings': Booking.objects.count(),
            'accepted': Booking.objects.filter(status=Booking.Status.ACCEPTED).count(),
            'enquiries': Conversation.objects.count(),
            'saves': Favourite.objects.count(),
            'reviews': PropertyReview.objects.count(),
            'avg_rating': PropertyReview.objects.aggregate(v=Avg('rating'))['v'],
            'open_contacts': Contact.objects.filter(status=Contact.Status.NEW).count(),
        },
        'by_type': by_type,
        'by_area': by_area,
        'chart': chart,
        'chart_max': chart_max,
        'signups': signup_rows,
        'signup_max': signup_max,
        'busiest': live.order_by('-view_count')[:8],
        'active': 'agentstats',
    })


@agent_required
def agent_log(request):
    rows = AgentAction.objects.select_related('agent', 'property')
    who = (request.GET.get('agent') or '').strip()
    agent_id = as_pk(who)
    if agent_id is None:
        who = ''
    else:
        rows = rows.filter(agent_id=agent_id)
    action = request.GET.get('action')
    if action in dict(AgentAction.Action.choices):
        rows = rows.filter(action=action)

    return render(request, 'agent_log.html', {
        'rows': rows[:200],
        'agents': UserProfile.objects.filter(is_agent=True),
        'who': who,
        'action': action,
        'actions': AgentAction.Action.choices,
        'active': 'agentlog',
    })


@agent_required
def agent_users(request):
    rows = UserProfile.objects.annotate(
        listings=Count('properties', distinct=True),
        bookings=Count('bookings_made', distinct=True),
    ).select_related('user')

    search = (request.GET.get('q') or '').strip()
    if search:
        rows = rows.filter(
            Q(name__icontains=search) | Q(email__icontains=search)
            | Q(contact_no__icontains=search)
        )
    role = request.GET.get('role')
    if role in dict(UserProfile.Role.choices):
        rows = rows.filter(role=role)

    return render(request, 'agent_users.html', {
        'rows': rows[:200],
        'search': search,
        'role': role,
        'roles': UserProfile.Role.choices,
        'active': 'agentusers',
    })


@agent_required
def agent_enquiries(request):
    rows = Contact.objects.all()
    status = request.GET.get('status', Contact.Status.NEW)
    if status in dict(Contact.Status.choices):
        rows = rows.filter(status=status)

    if request.method == 'POST':
        enquiry_id = as_pk(request.POST.get('id'))
        if enquiry_id is None:
            raise Http404('No such enquiry.')
        enquiry = get_object_or_404(Contact, pk=enquiry_id)
        enquiry.reply = (request.POST.get('reply') or '')[:4000]
        enquiry.status = Contact.Status.ANSWERED
        enquiry.save(update_fields=['reply', 'status'])
        messages.success(request, 'Marked as answered.')
        return redirect('agent_enquiries')

    return render(request, 'agent_enquiries.html', {
        'rows': rows[:100],
        'status': status,
        'statuses': Contact.Status.choices,
        'counts': {
            'new': Contact.objects.filter(status=Contact.Status.NEW).count(),
            'answered': Contact.objects.filter(status=Contact.Status.ANSWERED).count(),
        },
        'active': 'agentenquiries',
    })
