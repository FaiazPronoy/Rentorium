from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


def profile_of(request):
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        return getattr(user, 'UserProfile', None)
    return None


def _suspended(request, profile):
    from django.contrib.auth import logout
    logout(request)
    messages.error(
        request,
        'This account has been suspended. {}Write to us if you think that is '
        'a mistake.'.format(
            f'Reason given: {profile.suspended_reason}. '
            if profile.suspended_reason else ''
        ),
    )
    return redirect('home')


def login_required_message(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, 'Please sign in to continue.')
            return redirect(f"{reverse('signin')}?next={request.get_full_path()}")
        profile = profile_of(request)
        if profile is None:
            messages.error(request, 'Your profile could not be loaded.')
            return redirect('home')
        if profile.is_suspended:
            return _suspended(request, profile)
        return view(request, *args, **kwargs)

    return wrapper


def agent_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, 'Please sign in to continue.')
            return redirect(f"{reverse('signin')}?next={request.get_full_path()}")
        profile = profile_of(request)
        if profile is not None and profile.is_suspended:
            return _suspended(request, profile)
        if profile is None or not profile.is_agent:
            messages.error(request, 'That area is for agents only.')
            return redirect('PageNotFound')
        return view(request, *args, **kwargs)

    return wrapper


def post_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.method != 'POST':
            messages.error(request, 'That action has to be submitted, not visited.')
            return redirect('/')
        return view(request, *args, **kwargs)

    return wrapper
