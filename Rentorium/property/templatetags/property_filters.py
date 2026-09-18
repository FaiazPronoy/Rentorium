from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def format_field_name(value):
    """Turns a model field name into something a person can read."""
    if value == 'Block':
        return 'Block or sector'
    return str(value).replace('_', ' ').capitalize()


@register.filter
def get_type(value):
    return type(value).__name__


@register.filter
def money(value):
    """Formats a number the way a price should look."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if number >= 10000000:
        return f'{number / 10000000:.2f} crore'.replace('.00 ', ' ')
    if number >= 100000:
        return f'{number / 100000:.2f} lakh'.replace('.00 ', ' ')
    return f'{number:,.0f}'


@register.filter
def stars(rating):
    """Five stars, filled to the rating."""
    try:
        value = round(float(rating or 0))
    except (TypeError, ValueError):
        value = 0
    filled = '★' * value
    empty = f'<span class="off">{"☆" * (5 - value)}</span>' if value < 5 else ''
    return mark_safe(f'<span class="stars">{filled}{empty}</span>')


@register.filter
def querystring_without(querydict, key):
    params = querydict.copy()
    params.pop(key, None)
    return params.urlencode()


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """Keeps the current query string and changes only what is passed in."""
    params = context['request'].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ''):
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()


@register.filter
def index(sequence, position):
    try:
        return sequence[position]
    except (IndexError, TypeError, KeyError):
        return ''
