"""
One inline SVG icon set for the whole site.

Emoji were doing this job before. They render differently on every operating
system, they carry a colour we do not control, and half of them were only
loosely related to what they labelled. These are drawn on the same 24 unit
grid with the same stroke weight, they inherit `currentColor`, and they cost
nothing extra to load because they are part of the HTML.

Registered as a template builtin (see settings), so `{% icon "home" %}` works
in any template without a load tag.
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


ICONS = {
    # navigation and chrome
    'home': '<path d="M3 10.2 12 3l9 7.2V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>'
            '<path d="M9.5 21v-6.5h5V21"/>',
    'search': '<circle cx="11" cy="11" r="7"/><path d="m20.5 20.5-4-4"/>',
    'menu': '<path d="M4 7h16M4 12h16M4 17h16"/>',
    'close': '<path d="M6 6l12 12M18 6 6 18"/>',
    'chevron-down': '<path d="m6 9.5 6 6 6-6"/>',
    'chevron-left': '<path d="m14.5 5.5-6.5 6.5 6.5 6.5"/>',
    'chevron-right': '<path d="m9.5 5.5 6.5 6.5-6.5 6.5"/>',
    'arrow-right': '<path d="M4 12h15"/><path d="m13 6 6 6-6 6"/>',
    'arrow-left': '<path d="M20 12H5"/><path d="m11 6-6 6 6 6"/>',
    'arrow-up': '<path d="M12 20V5"/><path d="m6 11 6-6 6 6"/>',
    'flag': '<path d="M5 21V4"/>'
            '<path d="M5 4.5h9l-1.4 3.4a1 1 0 0 0 0 .8L14 12H5"/>',
    'history': '<path d="M3.5 9.5A9 9 0 1 1 3 13"/><path d="M3 4.5v5h5"/>'
               '<path d="M12 7.5V12l3 2"/>',
    'ban': '<circle cx="12" cy="12" r="8.5"/><path d="m6.2 6.2 11.6 11.6"/>',
    'undo': '<path d="M4 9.5h9a5.5 5.5 0 0 1 0 11H8"/><path d="M8 5 3.5 9.5 8 14"/>',
    'table': '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/>'
             '<path d="M3.5 9.5h17"/><path d="M9.5 9.5v10"/>',
    'external': '<path d="M14 4h6v6"/><path d="M20 4 11.5 12.5"/>'
                '<path d="M18 14.5V19a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h4.5"/>',
    'sun': '<circle cx="12" cy="12" r="4"/>'
           '<path d="M12 2v2.2M12 19.8V22M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6'
           'M2 12h2.2M19.8 12H22M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6"/>',
    'moon': '<path d="M20.5 14.8A8.6 8.6 0 0 1 9.2 3.5a8.6 8.6 0 1 0 11.3 11.3z"/>',
    'filter': '<path d="M4 6.5h16M7 12h10M10 17.5h4"/>',
    'refresh': '<path d="M20.5 11.5a8.5 8.5 0 1 0-1 5"/><path d="M20.5 5.5v6h-6"/>',
    'logout': '<path d="M15 4h3.5A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5H15"/>'
              '<path d="m9.5 8-4 4 4 4"/><path d="M5.5 12h10"/>',

    # people
    'user': '<circle cx="12" cy="8" r="3.6"/><path d="M4.8 20a7.2 7.2 0 0 1 14.4 0"/>',
    'users': '<circle cx="9" cy="8" r="3.4"/><path d="M2.6 20a6.4 6.4 0 0 1 12.8 0"/>'
             '<path d="M16.2 5.2a3.4 3.4 0 0 1 0 5.6"/>'
             '<path d="M17.8 14.4A6.4 6.4 0 0 1 21.4 20"/>',
    'user-check': '<circle cx="10" cy="8" r="3.6"/><path d="M3 20a7 7 0 0 1 11.5-5.4"/>'
                  '<path d="m15.5 17.5 2 2 4-4"/>',

    # property
    'building': '<rect x="4.5" y="3" width="15" height="18" rx="1.6"/>'
                '<path d="M8.5 7h2M13.5 7h2M8.5 11h2M13.5 11h2M8.5 15h2M13.5 15h2"/>'
                '<path d="M10 21v-2.5h4V21"/>',
    'land': '<path d="M3 20.5h18"/><path d="M12 20.5V10"/>'
            '<path d="M12 9.5 7.6 15h8.8z"/><path d="M12 4 8.4 9.5h7.2z"/>',
    'bed': '<path d="M3 19.5V9"/><path d="M3 13.5h15.5a2.5 2.5 0 0 1 2.5 2.5v3.5"/>'
           '<circle cx="7.4" cy="10.6" r="1.9"/>',
    'bath': '<path d="M3.5 12h17v3.2a4 4 0 0 1-4 4h-9a4 4 0 0 1-4-4z"/>'
            '<path d="M6.5 12V6.4a2.2 2.2 0 0 1 3.8-1.5"/><path d="m5 21 1-1.4M19 21l-1-1.4"/>',
    'area': '<rect x="3" y="8" width="18" height="8" rx="1.5"/>'
            '<path d="M7 8v3M11 8v4.5M15 8v3M19 8v4.5"/>',
    'balcony': '<path d="M3.5 12.5h17"/><path d="M6.5 12.5V21M10 12.5V21M14 12.5V21M17.5 12.5V21"/>'
               '<path d="M6.5 12.5V8a5.5 5.5 0 0 1 11 0v4.5"/>',
    'floors': '<path d="m12 3 9 4.8-9 4.8-9-4.8z"/><path d="m3 12.4 9 4.8 9-4.8"/>',
    'key': '<circle cx="7.8" cy="15.2" r="3.8"/>'
           '<path d="m10.6 12.5 8.2-8.2 2 2-1.6 1.6 1.6 1.6-2 2-1.6-1.6-1.7 1.7-1.7-1.7"/>',
    'tag': '<path d="M3.5 11.5V4h7.5l9.5 9.5-7.5 7.5z"/><circle cx="7.8" cy="7.8" r="1.4"/>',

    # amenities
    'lift': '<rect x="5" y="3" width="14" height="18" rx="2"/>'
            '<path d="M9.4 9.6 12 6.6l2.6 3M9.4 14.4l2.6 3 2.6-3"/>',
    'power': '<path d="M13.2 3 5.5 14h5.5l-.9 7 7.7-11h-5.5z"/>',
    'parking': '<rect x="4" y="4" width="16" height="16" rx="3.2"/>'
               '<path d="M10 16.5v-9h3.2a2.7 2.7 0 0 1 0 5.4H10"/>',
    'wifi': '<path d="M4.6 11.6a10.5 10.5 0 0 1 14.8 0"/>'
            '<path d="M8.1 15.1a5.6 5.6 0 0 1 7.8 0"/><circle cx="12" cy="18.4" r="1.1"/>',
    'cctv': '<path d="m3 7.4 13.4-3.2 1.4 5.4L4.4 12.8z"/>'
            '<path d="M6.6 12.4V15a3 3 0 0 0 3 3h2.2"/><path d="m18.2 9.4 3-.8"/>',
    'shield': '<path d="M12 3.2 5 6v6.2c0 4.5 3 7.7 7 8.8 4-1.1 7-4.3 7-8.8V6z"/>',
    'shield-check': '<path d="M12 3.2 5 6v6.2c0 4.5 3 7.7 7 8.8 4-1.1 7-4.3 7-8.8V6z"/>'
                    '<path d="m9.2 12 2 2 3.6-3.6"/>',
    'pool': '<path d="M3 17.2c1.6 0 1.6 1.3 3.2 1.3s1.6-1.3 3.2-1.3 1.6 1.3 3.2 1.3'
            ' 1.6-1.3 3.2-1.3 1.6 1.3 3.2 1.3"/>'
            '<path d="M7.4 15.5V5.8a2.1 2.1 0 0 1 4.2 0v9.7M12.4 15.5V5.8a2.1 2.1 0 0 1 4.2 0v9.7"/>',
    'gym': '<path d="M6.4 8v8M3.8 10.2v3.6M17.6 8v8M20.2 10.2v3.6M6.4 12h11.2"/>',
    'ac': '<path d="M12 3v18M4.2 7.5l15.6 9M19.8 7.5l-15.6 9"/>',
    'flame': '<path d="M12 21a6.2 6.2 0 0 0 6.2-6.2c0-4.2-4.2-5.2-4.2-9.3 0 0-3.1 1.5-3.1 5.2'
             ' 0 1.6-1.6 1-1.6-1-2.5 2.7-3.5 3.8-3.5 5.1A6.2 6.2 0 0 0 12 21z"/>',
    'water': '<path d="M12 3.4S5.8 10.2 5.8 14a6.2 6.2 0 0 0 12.4 0c0-3.8-6.2-10.6-6.2-10.6z"/>',
    'sofa': '<path d="M5.5 11.5V8.2A2.2 2.2 0 0 1 7.7 6h8.6a2.2 2.2 0 0 1 2.2 2.2v3.3"/>'
            '<path d="M3 13.2a2.2 2.2 0 0 1 4.4 0v2.3h9.2v-2.3a2.2 2.2 0 0 1 4.4 0V19H3z"/>',
    'prayer': '<path d="M4.5 20.5V11c0-4 3.4-7 7.5-7s7.5 3 7.5 7v9.5"/>'
              '<path d="M4.5 20.5h15"/><path d="M9.5 20.5v-4.2a2.5 2.5 0 0 1 5 0v4.2"/>',
    'pet': '<circle cx="7.2" cy="9.4" r="1.8"/><circle cx="12" cy="7.4" r="1.8"/>'
           '<circle cx="16.8" cy="9.4" r="1.8"/>'
           '<path d="M12 12.6c-3 0-5.2 2.2-5.2 4.4S9 20.6 12 20.6s5.2-1.4 5.2-3.6-2.2-4.4-5.2-4.4z"/>',
    'rooftop': '<path d="m3 12.5 9-7 9 7"/><path d="M6 12.5V20h12v-7.5"/>'
               '<path d="M9.5 20v-4.5h5V20"/>',

    # actions and status
    'check': '<path d="m4.5 12.5 5 5 10-11"/>',
    'check-circle': '<circle cx="12" cy="12" r="9"/><path d="m8 12.2 2.6 2.6L16 9.4"/>',
    'plus': '<path d="M12 5v14M5 12h14"/>',
    'edit': '<path d="M12 20.5h8.5"/>'
            '<path d="M16.6 3.4a2.2 2.2 0 0 1 3.1 3.1L8.2 18l-4.2 1.1L5.1 15z"/>',
    'trash': '<path d="M4 6.8h16"/><path d="M9.4 6.8V4.6h5.2v2.2"/>'
             '<path d="m6.6 6.8 1 13.2h8.8l1-13.2"/>',
    'camera': '<path d="M4 8.2h3.2L8.8 5.8h6.4l1.6 2.4H20a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4'
              'a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.6" r="3.4"/>',
    'image': '<rect x="3" y="4.5" width="18" height="15" rx="2.2"/>'
             '<circle cx="8.4" cy="10" r="1.6"/><path d="m4 17.4 4.6-4.6 3.4 3.4 3.2-3.2L20 17"/>',
    'file': '<path d="M13.2 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.8z"/>'
            '<path d="M13.2 3v5.8H19"/>',
    'link': '<path d="M10.2 13.4a4.8 4.8 0 0 0 6.8 0l2-2a4.8 4.8 0 1 0-6.8-6.8l-1 1"/>'
            '<path d="M13.8 10.6a4.8 4.8 0 0 0-6.8 0l-2 2a4.8 4.8 0 1 0 6.8 6.8l1-1"/>',
    'heart': '<path d="M12 20.2s-7.3-4.5-7.3-9.6A4.2 4.2 0 0 1 12 7.2a4.2 4.2 0 0 1 7.3 3.4'
             'c0 5.1-7.3 9.6-7.3 9.6z"/>',
    'star': '<path d="m12 3.4 2.7 5.7 6.3.8-4.6 4.3 1.2 6.2L12 17.4l-5.6 3 1.2-6.2L3 9.9l6.3-.8z"/>',
    'compare': '<path d="M6 4v16M18 4v16"/><path d="M6 8.5h6.5M17.5 15.5H11"/>'
               '<path d="m10 6 2.5 2.5L10 11M14 13l-2.5 2.5L14 18"/>',
    'calendar': '<rect x="3.5" y="5" width="17" height="16" rx="2.2"/>'
                '<path d="M8.5 3v4M15.5 3v4M3.5 10h17"/>',
    'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7.2V12l3.2 2"/>',
    'mail': '<rect x="3" y="5.2" width="18" height="13.6" rx="2.2"/>'
            '<path d="m3.6 7 8.4 5.8L20.4 7"/>',
    'bell': '<path d="M18 9.4a6 6 0 1 0-12 0c0 5.2-2.2 6.2-2.2 6.2h16.4S18 14.6 18 9.4"/>'
            '<path d="M10.2 19.6a2.2 2.2 0 0 0 3.6 0"/>',
    'chat': '<path d="M20.5 12.4c0 4-3.8 7.2-8.5 7.2a9.9 9.9 0 0 1-2.8-.4L4.5 21l1.4-3.7'
            'a6.9 6.9 0 0 1-2.4-5c0-4 3.8-7.2 8.5-7.2s8.5 3.2 8.5 7.3z"/>',
    'pin': '<path d="M20 10.2c0 6-8 11.8-8 11.8S4 16.2 4 10.2a8 8 0 1 1 16 0z"/>'
           '<circle cx="12" cy="10.1" r="2.8"/>',
    'phone': '<path d="M6.2 3h3l2 5-2.3 1.4a12.2 12.2 0 0 0 5.7 5.7L16 12.8l5 2v3.1'
             'A2.1 2.1 0 0 1 18.7 20 16.9 16.9 0 0 1 4 5.3 2.1 2.1 0 0 1 6.2 3z"/>',
    'chart': '<path d="M3.5 20.5h17"/><path d="M6.5 20.5v-6M11 20.5V8M15.5 20.5v-9M20 20.5v-4"/>',
    'trend': '<path d="M3.5 16.5 9 11l4 4 7.5-7.5"/><path d="M15.5 7.5h5v5"/>',
    'eye': '<path d="M2.6 12S6.2 5.6 12 5.6 21.4 12 21.4 12 17.8 18.4 12 18.4 2.6 12 2.6 12z"/>'
           '<circle cx="12" cy="12" r="3.1"/>',
    'eye-off': '<path d="M4 4l16 16"/>'
               '<path d="M9.6 5.9A9.7 9.7 0 0 1 12 5.6c5.8 0 9.4 6.4 9.4 6.4a17.4 17.4 0 0 1-3.5 4.3"/>'
               '<path d="M6.3 7.7A17.2 17.2 0 0 0 2.6 12S6.2 18.4 12 18.4a9.5 9.5 0 0 0 3.4-.6"/>'
               '<path d="M9.9 10a3.1 3.1 0 0 0 4.2 4.3"/>',
    'lock': '<rect x="4.6" y="10" width="14.8" height="10.4" rx="2.2"/>'
            '<path d="M8.2 10V7.6a3.8 3.8 0 0 1 7.6 0V10"/>',
    'award': '<circle cx="12" cy="9" r="5.4"/><path d="M8.6 13.4 7.2 21l4.8-2.5L16.8 21l-1.4-7.6"/>',
    'info': '<circle cx="12" cy="12" r="9"/><path d="M12 11.2v5M12 7.9v.1"/>',
    'alert': '<path d="M12 4.2 2.8 20.2h18.4z"/><path d="M12 10.2v4M12 17.3v.1"/>',
    'inbox': '<rect x="3" y="4.6" width="18" height="14.8" rx="2.2"/>'
             '<path d="M3 13.4h4.4l1.4 2.4h6.4l1.4-2.4H21"/>',
    'sliders': '<path d="M5 20V13M5 9V4M12 20v-9M12 7V4M19 20v-5M19 11V4"/>'
               '<path d="M2.6 13h4.8M9.6 11h4.8M16.6 15h4.8"/>',
    'download': '<path d="M12 4v11"/><path d="m7.5 10.5 4.5 4.5 4.5-4.5"/><path d="M4.5 19.5h15"/>',
    'dot': '<circle cx="12" cy="12" r="3.4"/>',
}


@register.simple_tag
def icon(name, cls=''):
    """`{% icon "home" %}` or `{% icon "home" "lg" %}`."""
    body = ICONS.get(name, ICONS['dot'])
    classes = 'ico-svg' + (' ' + cls if cls else '')
    # data-icon lets the front end reuse a glyph the page already carries,
    # instead of shipping a second copy of the set to JavaScript.
    return mark_safe(
        f'<svg class="{classes}" data-icon="{name}" viewBox="0 0 24 24" '
        f'aria-hidden="true" focusable="false">{body}</svg>'
    )


# Amenity rows are typed in by hand in the admin, so the icon is chosen by
# looking at the words in the name rather than by a fixed id.
_AMENITY_WORDS = (
    ('cctv', 'cctv'), ('camera', 'cctv'),
    ('generator', 'power'), ('power', 'power'), ('solar', 'power'),
    ('lift', 'lift'), ('elevator', 'lift'),
    ('parking', 'parking'), ('garage', 'parking'),
    ('internet', 'wifi'), ('wifi', 'wifi'), ('broadband', 'wifi'),
    ('security', 'shield'), ('guard', 'shield'), ('intercom', 'shield'),
    ('pool', 'pool'), ('swim', 'pool'),
    ('gym', 'gym'), ('fitness', 'gym'),
    ('air condition', 'ac'), ('ac', 'ac'), ('cooling', 'ac'),
    ('gas', 'flame'),
    ('water', 'water'), ('reserve', 'water'),
    ('furnish', 'sofa'), ('community', 'users'), ('hall', 'users'),
    ('prayer', 'prayer'), ('mosque', 'prayer'),
    ('pet', 'pet'),
    ('roof', 'rooftop'), ('terrace', 'rooftop'),
    ('balcony', 'balcony'),
    ('lawn', 'land'), ('garden', 'land'),
    ('cctv camera', 'cctv'),
)


@register.filter
def amenity_icon(name):
    key = str(name or '').lower()
    for word, icon_name in _AMENITY_WORDS:
        if word in key:
            return icon(icon_name)
    return icon('check')


# The three property types, and the six notification kinds, each get one.
_TYPE_ICON = {'residential': 'home', 'commercial': 'building', 'land': 'land'}
_KIND_ICON = {
    'booking': 'calendar', 'message': 'chat', 'approval': 'check-circle',
    'review': 'star', 'alert': 'bell', 'system': 'info',
}


@register.filter
def type_icon(key):
    return icon(_TYPE_ICON.get(str(key), 'home'))


@register.filter
def kind_icon(key):
    return icon(_KIND_ICON.get(str(key), 'info'))


# A compact relative time. `timesince` gives "10 hours, 5 minutes", and the
# templates were cutting that with truncatewords, which produced "10 …".
from django.utils import timezone as _tz

@register.filter
def since(value):
    if not value:
        return ''
    now = _tz.now() if _tz.is_aware(value) else _tz.datetime.now()
    seconds = (now - value).total_seconds()
    if seconds < 0:
        seconds = 0
    minutes = seconds / 60
    if minutes < 1:
        return 'just now'
    if minutes < 60:
        return f'{int(minutes)}m ago'
    hours = minutes / 60
    if hours < 24:
        return f'{int(hours)}h ago'
    days = hours / 24
    if days < 7:
        return f'{int(days)}d ago'
    if days < 31:
        return f'{int(days / 7)}w ago'
    if days < 365:
        return f'{int(days / 30)}mo ago'
    return f'{int(days / 365)}y ago'
