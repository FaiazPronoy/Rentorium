from django.contrib.auth.models import User

DEMO_PASSWORD = 'Rentorium@2026'
AGENT_PASSWORD = 'Agent@2026'

KEYS = [
    ('Renter', 'rafid@rentorium.test', DEMO_PASSWORD),
    ('Owner', 'faiaz@rentorium.test', DEMO_PASSWORD),
    ('Agent', 'agent@rentorium.test', AGENT_PASSWORD),
]


def demo_keys():
    users = {u.username: u for u in User.objects.filter(
        username__in=[k[1] for k in KEYS], is_active=True).select_related('UserProfile')}
    keys = []
    for role, email, password in KEYS:
        user = users.get(email)
        if user is None:
            continue
        profile = getattr(user, 'UserProfile', None)
        name = (profile.first_name if profile and profile.first_name else role)
        keys.append({'role': role, 'email': email, 'password': password, 'name': name})
    return keys
