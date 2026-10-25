import hashlib

AREA_CENTRES = {
    'Gulshan': (23.7925, 90.4078),
    'Banani': (23.7940, 90.4043),
    'Dhanmondi': (23.7461, 90.3742),
    'Bashundhara R/A': (23.8193, 90.4526),
    'Uttara': (23.8759, 90.3795),
    'Mirpur': (23.8223, 90.3654),
    'Mohakhali': (23.7780, 90.4050),
    'Badda': (23.7806, 90.4265),
    'Motijheel': (23.7330, 90.4172),
    'Agrabad': (22.3252, 91.8123),
    'Zindabazar': (24.8949, 91.8687),
}

CITY_CENTRES = {
    'Dhaka': (23.8103, 90.4125),
    'Chattogram': (22.3569, 91.7832),
    'Sylhet': (24.8949, 91.8687),
    'Khulna': (22.8456, 89.5403),
    'Rajshahi': (24.3745, 88.6042),
}

SPREAD = 0.006


def place(listing):
    lat, lng = AREA_CENTRES.get(listing.Area) or CITY_CENTRES.get(listing.City, CITY_CENTRES['Dhaka'])
    digest = hashlib.md5(str(listing.pk).encode()).digest()
    dx = (digest[0] / 255 - 0.5) * 2 * SPREAD
    dy = (digest[1] / 255 - 0.5) * 2 * SPREAD
    return round(lat + dy, 5), round(lng + dx, 5)
