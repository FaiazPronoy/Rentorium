import csv

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.http import Http404, HttpResponse
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from authentication.decorators import agent_required, post_required, profile_of
from authentication.models import Notification, UserProfile
from basic.models import Contact
from property.views import safe_back
from property.models import (
    AllProperty, Booking, Conversation, Favourite, PropertyReport,
    PropertyReview, PropertyView,
)

from .models import AgentAction


def _send_reply(enquiry):
    """Emails an agent's answer back to whoever wrote in."""
    if not enquiry.reply or not enquiry.email:
        return False
    body = (
        f'Hello {enquiry.name},\n\n'
        f'{enquiry.reply}\n\n'
        f'---\nYou wrote to us about: {enquiry.subject}\n\n'
        f'{enquiry.message}\n\n'
        f'- The {settings.SITE_NAME} team'
    )
    try:
        return bool(send_mail(
            f'Re: {enquiry.subject}', body,
            settings.DEFAULT_FROM_EMAIL, [enquiry.email], fail_silently=True,
        ))
    except Exception:
        return False


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
        'reports': PropertyReport.objects.filter(
            status=PropertyReport.Status.OPEN).count(),
        'suspended': UserProfile.objects.filter(is_suspended=True).count(),
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
    else:
        role = ''

    held = request.GET.get('held')
    if held == 'suspended':
        rows = rows.filter(is_suspended=True)
    elif held == 'active':
        rows = rows.filter(is_suspended=False)
    else:
        held = ''

    total = rows.count()
    return render(request, 'agent_users.html', {
        'rows': rows[:200],
        'total': total,
        'search': search,
        'role': role,
        'held': held,
        'roles': UserProfile.Role.choices,
        'counts': {
            'suspended': UserProfile.objects.filter(is_suspended=True).count(),
        },
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
        enquiry.reply = (request.POST.get('reply') or '').strip()[:4000]
        enquiry.status = Contact.Status.ANSWERED
        enquiry.save(update_fields=['reply', 'status'])
        # Writing the reply into the database and calling it answered was the
        # whole of it before: the person who wrote in never heard back.
        sent = _send_reply(enquiry)
        messages.success(
            request,
            'Reply sent to {}.'.format(enquiry.email) if sent
            else 'Saved as answered, but the email could not be sent.'
        )
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


# bulk actions

MAX_BULK = 50


@agent_required
@post_required
def bulk_decide(request):
    """Approve or send back several listings at once.

    The queue often fills with a dozen listings from the same estate, and
    deciding them one page load at a time is what made agents batch their
    work. Everything still goes through `_decide`, so each one is logged and
    each owner is still told individually.
    """
    ids = request.POST.getlist('picked')
    action = request.POST.get('bulk_action')
    reason = (request.POST.get('bulk_reason') or '').strip()[:200]

    picked = [pk for pk in (as_pk(i) for i in ids) if pk is not None][:MAX_BULK]
    if not picked:
        messages.error(request, 'Tick the listings you want to act on first.')
        return redirect('agent_dashboard')

    if action == 'approve':
        decision = (AgentAction.Action.APPROVED, AllProperty.Status.APPROVED, '')
        done_word = 'approved and now live'
    elif action == 'reject':
        if not reason:
            messages.error(request, 'Sending listings back needs a reason the '
                                    'owners can act on.')
            return redirect('agent_dashboard')
        decision = (AgentAction.Action.REJECTED, AllProperty.Status.REJECTED, reason)
        done_word = 'sent back with your note'
    else:
        messages.error(request, 'Pick approve or send back.')
        return redirect('agent_dashboard')

    # Only ever act on what is actually still waiting: a listing another agent
    # decided while this page was open must not be silently overruled.
    rows = list(AllProperty.objects.filter(
        pk__in=picked, status=AllProperty.Status.PENDING))
    for listing in rows:
        _decide(request, listing, decision[0], decision[1], decision[2])

    skipped = len(picked) - len(rows)
    note = f' {skipped} had already been decided.' if skipped else ''
    if rows:
        messages.success(request, f'{len(rows)} listing'
                                  f'{"" if len(rows) == 1 else "s"} {done_word}.{note}')
    else:
        messages.info(request, f'Nothing to do.{note}')
    return redirect('agent_dashboard')


# reports

@agent_required
def agent_reports(request):
    """The queue of listings people have flagged."""
    rows = (PropertyReport.objects
            .select_related('property', 'property__user', 'reporter', 'handled_by'))

    status = request.GET.get('status', PropertyReport.Status.OPEN)
    if status in dict(PropertyReport.Status.choices):
        rows = rows.filter(status=status)
    else:
        status = ''

    reason = request.GET.get('reason')
    if reason in dict(PropertyReport.Reason.choices):
        rows = rows.filter(reason=reason)
    else:
        reason = ''

    return render(request, 'agent_reports.html', {
        'rows': rows[:200],
        'status': status,
        'reason': reason,
        'statuses': PropertyReport.Status.choices,
        'reasons': PropertyReport.Reason.choices,
        'counts': {
            'open': PropertyReport.objects.filter(
                status=PropertyReport.Status.OPEN).count(),
            'upheld': PropertyReport.objects.filter(
                status=PropertyReport.Status.UPHELD).count(),
            'dismissed': PropertyReport.objects.filter(
                status=PropertyReport.Status.DISMISSED).count(),
        },
        'active': 'agentreports',
    })


@agent_required
@post_required
def resolve_report(request, report_id):
    """Uphold a report (which pulls the listing) or dismiss it."""
    report = get_object_or_404(
        PropertyReport.objects.select_related('property'), pk=report_id)
    if report.status != PropertyReport.Status.OPEN:
        messages.info(request, 'That report has already been dealt with.')
        return safe_back(request, reverse('agent_reports'))

    me = profile_of(request)
    outcome = (request.POST.get('outcome') or '').strip()[:200]
    uphold = request.POST.get('decision') == 'uphold'

    report.status = (PropertyReport.Status.UPHELD if uphold
                     else PropertyReport.Status.DISMISSED)
    report.handled_by = me
    report.handled_at = timezone.now()
    report.outcome = outcome
    report.save(update_fields=['status', 'handled_by', 'handled_at', 'outcome'])

    AgentAction.objects.create(
        agent=me, property=report.property,
        action=(AgentAction.Action.REPORT_UPHELD if uphold
                else AgentAction.Action.REPORT_DISMISSED),
        reason=outcome or report.get_reason_display(),
    )

    if uphold:
        # An upheld report takes the listing off the site and tells the owner
        # what to fix, using the same path as a normal rejection.
        if report.property.status != AllProperty.Status.REJECTED:
            _decide(request, report.property, AgentAction.Action.REJECTED,
                    AllProperty.Status.REJECTED,
                    outcome or f'Reported: {report.get_reason_display().lower()}')
        # Every other open report on the same listing is now settled too.
        PropertyReport.objects.filter(
            property=report.property, status=PropertyReport.Status.OPEN
        ).update(status=PropertyReport.Status.UPHELD, handled_by=me,
                 handled_at=timezone.now(),
                 outcome=outcome or 'Handled with an earlier report.')
        messages.success(request, 'Report upheld and the listing taken down.')
    else:
        messages.success(request, 'Report dismissed. The listing stays up.')

    if report.reporter:
        Notification.push(
            report.reporter,
            'Thanks for the report' if not uphold else 'We acted on your report',
            ('We looked at "{}" and left it up.'.format(
                report.property.Property_Name)
             if not uphold else
             'We took "{}" down after your report.'.format(
                 report.property.Property_Name)),
            kind=Notification.Kind.SYSTEM,
        )
    return safe_back(request, reverse('agent_reports'))


# accounts

@agent_required
@post_required
def suspend_user(request, profile_id):
    target = get_object_or_404(UserProfile, pk=profile_id)
    me = profile_of(request)

    if target == me:
        messages.error(request, 'You cannot suspend your own account.')
        return safe_back(request, reverse('agent_users'))
    if target.is_agent:
        messages.error(request, 'An agent account cannot be suspended from here.')
        return safe_back(request, reverse('agent_users'))
    if target.is_suspended:
        messages.info(request, f'{target.name} is already suspended.')
        return safe_back(request, reverse('agent_users'))

    reason = (request.POST.get('reason') or '').strip()[:200]
    if not reason:
        messages.error(request, 'Say why. The person is told the reason.')
        return safe_back(request, reverse('agent_users'))

    hidden = target.properties.filter(is_archived=False).count()
    target.suspend(by=me, reason=reason)
    AgentAction.objects.create(
        agent=me, subject=target, action=AgentAction.Action.SUSPENDED, reason=reason,
    )
    Notification.push(
        target, 'Your account has been suspended', reason,
        kind=Notification.Kind.ALERT,
    )
    messages.success(
        request,
        f'{target.name} is suspended'
        + (f' and {hidden} listing{"" if hidden == 1 else "s"} taken off the site.'
           if hidden else '.'),
    )
    return safe_back(request, reverse('agent_users'))


@agent_required
@post_required
def lift_suspension(request, profile_id):
    target = get_object_or_404(UserProfile, pk=profile_id)
    if not target.is_suspended:
        messages.info(request, f'{target.name} is not suspended.')
        return safe_back(request, reverse('agent_users'))

    me = profile_of(request)
    back = target.properties.filter(is_archived=True).count()
    target.lift_suspension(by=me)
    AgentAction.objects.create(
        agent=me, subject=target, action=AgentAction.Action.LIFTED,
        reason=(request.POST.get('reason') or '')[:200],
    )
    Notification.push(
        target, 'Your account is active again',
        'An agent lifted the suspension. Everything you had listed is back.',
        kind=Notification.Kind.SYSTEM,
    )
    messages.success(
        request,
        f'{target.name} can sign in again'
        + (f', and {back} listing{"" if back == 1 else "s"} are back on the site.'
           if back else '.'),
    )
    return safe_back(request, reverse('agent_users'))


# csv export

def _csv(name, header, rows):
    """A download, streamed straight out of the queryset."""
    stamp = timezone.localdate().isoformat()
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="rentorium-{name}-{stamp}.csv"'
    # Excel opens a UTF-8 file as Latin-1 unless it sees the byte order mark,
    # which turns every Bengali name and every ৳ into mojibake.
    response.write('﻿')
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response


EXPORTS = ('listings', 'users', 'enquiries', 'reports', 'log')


@agent_required
def agent_export(request, what):
    if what not in EXPORTS:
        raise Http404('Nothing to export by that name.')

    if what == 'listings':
        rows = (AllProperty.objects.select_related('user')
                .annotate(saves=Count('favourited_by', distinct=True),
                          reviews_n=Count('reviews', distinct=True))
                .order_by('pk'))
        status = request.GET.get('status')
        if status in dict(AllProperty.Status.choices):
            rows = rows.filter(status=status)
        return _csv('listings', [
            'ID', 'Title', 'Type', 'Listed for', 'Status', 'Featured',
            'Price', 'Service charge', 'Area', 'City', 'Size (sq ft)',
            'Owner', 'Owner email', 'Views', 'Saves', 'Reviews',
            'Created', 'Approved',
        ], [[
            r.pk, r.Property_Name, r.get_Property_type_display(),
            r.get_Property_on_display(), r.get_status_display(),
            'yes' if r.is_featured else 'no',
            r.Price, r.service_charge, r.Area, r.City,
            r.Total_area_in_sqft or '',
            r.user.name if r.user else '', r.user.email if r.user else '',
            r.view_count, r.saves, r.reviews_n,
            timezone.localtime(r.created_at).strftime('%Y-%m-%d %H:%M'),
            timezone.localtime(r.approved_at).strftime('%Y-%m-%d %H:%M')
            if r.approved_at else '',
        ] for r in rows])

    if what == 'users':
        rows = (UserProfile.objects.select_related('user')
                .annotate(listings=Count('properties', distinct=True),
                          bookings=Count('bookings_made', distinct=True))
                .order_by('pk'))
        return _csv('users', [
            'ID', 'Name', 'Email', 'Phone', 'Role', 'Verified', 'Suspended',
            'Suspended reason', 'Listings', 'Viewings booked', 'Joined',
            'Last login',
        ], [[
            r.pk, r.name, r.email, r.contact_no, r.get_role_display(),
            'yes' if r.is_verified else 'no',
            'yes' if r.is_suspended else 'no', r.suspended_reason,
            r.listings, r.bookings,
            timezone.localtime(r.created_at).strftime('%Y-%m-%d'),
            timezone.localtime(r.user.last_login).strftime('%Y-%m-%d %H:%M')
            if r.user and r.user.last_login else '',
        ] for r in rows])

    if what == 'enquiries':
        rows = Contact.objects.order_by('pk')
        return _csv('enquiries', [
            'ID', 'Name', 'Email', 'Subject', 'Message', 'Status', 'Reply',
            'Received',
        ], [[
            r.pk, r.name, r.email, r.subject, r.message,
            r.get_status_display(), r.reply,
            timezone.localtime(r.created_at).strftime('%Y-%m-%d %H:%M'),
        ] for r in rows])

    if what == 'reports':
        rows = (PropertyReport.objects
                .select_related('property', 'reporter', 'handled_by').order_by('pk'))
        return _csv('reports', [
            'ID', 'Listing ID', 'Listing', 'Reason', 'Detail', 'Reported by',
            'Status', 'Handled by', 'Outcome', 'Reported', 'Handled',
        ], [[
            r.pk, r.property_id, r.property.Property_Name,
            r.get_reason_display(), r.detail,
            r.reporter.name if r.reporter else 'removed account',
            r.get_status_display(),
            r.handled_by.name if r.handled_by else '', r.outcome,
            timezone.localtime(r.created_at).strftime('%Y-%m-%d %H:%M'),
            timezone.localtime(r.handled_at).strftime('%Y-%m-%d %H:%M')
            if r.handled_at else '',
        ] for r in rows])

    rows = AgentAction.objects.select_related('agent', 'property', 'subject').order_by('pk')
    return _csv('moderation-log', [
        'ID', 'When', 'Agent', 'Action', 'Listing', 'Account', 'Reason',
    ], [[
        r.pk, timezone.localtime(r.created_at).strftime('%Y-%m-%d %H:%M'),
        r.agent.name if r.agent else 'removed agent',
        r.get_action_display(),
        r.property.Property_Name if r.property else '',
        r.subject.name if r.subject else '',
        r.reason,
    ] for r in rows])
