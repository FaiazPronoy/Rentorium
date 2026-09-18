from django import template

register = template.Library()


@register.filter
def format_field_name(value):
    return str(value).replace('_', ' ').capitalize()


@register.filter
def add_class(field, css):
    """Adds a CSS class to a form widget from inside a template."""
    try:
        return field.as_widget(attrs={**field.field.widget.attrs, 'class': css})
    except AttributeError:
        return field


@register.filter
def initials(name):
    parts = [p for p in str(name or '').split() if p]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()
