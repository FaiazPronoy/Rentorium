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

    return {
        'SITE_NAME': settings.SITE_NAME,
        'SITE_TAGLINE': settings.SITE_TAGLINE,
        'CURRENCY_SIGN': settings.CURRENCY_SIGN,
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
