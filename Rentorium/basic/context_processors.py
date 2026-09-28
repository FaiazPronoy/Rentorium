from django.conf import settings


def site_context(request):
    """
    Values every template needs. Written so it can never raise: the first
    version crashed the whole site when a user had no profile row.
    """
    compare = []
    if hasattr(request, 'session'):
        try:
            compare = request.session.get('compare', []) or []
        except Exception:
            compare = []

    profile = None
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        profile = getattr(user, 'UserProfile', None)

    # The nav shows agents how many reports are waiting. One small count, and
    # only for the handful of people who can act on it.
    open_reports = 0
    if profile is not None and profile.is_agent:
        try:
            from property.models import PropertyReport
            open_reports = PropertyReport.objects.filter(
                status=PropertyReport.Status.OPEN).count()
        except Exception:
            open_reports = 0

    return {
        'open_reports': open_reports,
        'SITE_NAME': settings.SITE_NAME,
        'SITE_LEGAL_NAME': settings.SITE_LEGAL_NAME,
        'SITE_TAGLINE': settings.SITE_TAGLINE,
        'SITE_ADDRESS': settings.SITE_ADDRESS,
        'SITE_PHONE': settings.SITE_PHONE,
        'SITE_EMAIL': settings.SITE_EMAIL,
        'SITE_HOURS': settings.SITE_HOURS,
        'CURRENCY_SIGN': settings.CURRENCY_SIGN,
        'ASSET_VERSION': settings.ASSET_VERSION,
        'profile': profile,
        'name': profile.name if profile else '',
        'is_logged_in': profile is not None,
        'is_agent': bool(profile and profile.is_agent),
        'unread_notifications': profile.unread_notifications() if profile else 0,
        'unread_messages': profile.unread_messages() if profile else 0,
        # supplied globally so every page that renders a property card can
        # show the right state, not only the browse page
        'compare_ids': compare,
        'compare_count': len(compare),
    }
