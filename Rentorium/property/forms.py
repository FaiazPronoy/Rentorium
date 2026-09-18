from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    AllProperty, Amenity, Booking, CommercialProperty, LandProperty, Message,
    PropertyReview, ResidentialProperty, SavedSearch,
)

SHARED_FIELDS = [
    'Property_Name', 'Property_Description', 'Property_on',
    'Price', 'service_charge', 'security_deposit_months', 'negotiable',
    'Total_area_in_sqft', 'furnishing', 'available_from',
    'City', 'Area', 'Road_No', 'Block', 'Postal_code', 'landmark',
    'Property_Pictures', 'Property_Documents', 'amenities',
]

class PrivateFileInput(forms.FileInput):
    """A file box for a document that has no public URL.

    The default for a FileField is ClearableFileInput, which renders
    "Currently: <a href="{{ value.url }}">" for a file that is already saved.
    Ownership papers live outside MEDIA_ROOT and their storage refuses to
    produce a URL, so that widget raised ValueError and the edit page of every
    listing that had a document returned a 500. A plain file input never asks
    for the URL; the name of the file on record goes in the help text below,
    and the only way to open it stays the permission-checked document view.
    """


SHARED_WIDGETS = {
    'Property_Documents': PrivateFileInput,
    'Property_Documents': PrivateFileInput,
    'Property_Name': forms.TextInput(
        attrs={'placeholder': 'Bright 3 bedroom flat near Gulshan 2 circle'}),
    'Property_Description': forms.Textarea(
        attrs={'rows': 5, 'placeholder': 'What makes this place good to live in?'}),
    'available_from': forms.DateInput(attrs={'type': 'date'}),
    'landmark': forms.TextInput(attrs={'placeholder': 'Beside Gulshan Society Mosque'}),
    'amenities': forms.CheckboxSelectMultiple,
}


class BasePropertyForm(forms.ModelForm):
    """Validation every listing shares, whatever its type."""

    class Meta:
        widgets = SHARED_WIDGETS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('Block', 'Postal_code', 'Road_No', 'landmark',
                     'Property_Documents', 'Property_Pictures', 'amenities'):
            if name in self.fields:
                self.fields[name].required = False
        if 'Block' in self.fields:
            self.fields['Block'].label = 'Block or sector'
        if 'amenities' in self.fields:
            self.fields['amenities'].queryset = Amenity.objects.all()
        if 'available_from' in self.fields and not self.instance.pk:
            self.fields['available_from'].initial = timezone.localdate()

        # These carry `default=0` on the model, so a brand new form arrived
        # showing a 0 in every money box — a filled-in field that the price
        # check then rejects. Start them empty with a hint instead, and let
        # the two optional ones fall back to 0 on save.
        if not self.instance.pk:
            for name, hint in (('Price', 'e.g. 45000'),
                               ('service_charge', '0 if there is none'),
                               ('security_deposit_months', '0 if there is none')):
                if name in self.fields:
                    self.fields[name].initial = None
                    self.fields[name].widget.attrs.setdefault('placeholder', hint)
        for name in ('service_charge', 'security_deposit_months'):
            if name in self.fields:
                self.fields[name].required = False

        # Say which paper is already on record, since the box itself cannot
        # link to it.
        doc = getattr(self.instance, 'Property_Documents', None)
        if 'Property_Documents' in self.fields and doc:
            self.fields['Property_Documents'].help_text = (
                'On record: %s. Upload a new file to replace it.'
                % (doc.name or '').rsplit('/', 1)[-1]
            )

    def clean_service_charge(self):
        return self.cleaned_data.get('service_charge') or 0

    def clean_security_deposit_months(self):
        return self.cleaned_data.get('security_deposit_months') or 0

    def clean_Property_Name(self):
        title = ' '.join(self.cleaned_data['Property_Name'].split())
        if len(title) < 10:
            raise ValidationError('Give the listing a real title, at least 10 characters.')
        return title

    def clean_Price(self):
        price = self.cleaned_data['Price']
        if price is None or price <= 0:
            raise ValidationError('Enter the asking price.')
        if price > 999999999:
            raise ValidationError('That price looks wrong.')
        return price

    def clean_Postal_code(self):
        code = (self.cleaned_data.get('Postal_code') or '').strip()
        if code and (not code.isdigit() or len(code) != 4):
            raise ValidationError('A Bangladeshi postal code is 4 digits.')
        return code

    def clean_Property_Pictures(self):
        image = self.cleaned_data.get('Property_Pictures')
        if image and getattr(image, 'size', 0) > 5 * 1024 * 1024:
            raise ValidationError('Keep each picture under 5 MB.')
        return image

    def clean_Property_Documents(self):
        doc = self.cleaned_data.get('Property_Documents')
        if doc and getattr(doc, 'size', 0) > 10 * 1024 * 1024:
            raise ValidationError('Keep the document under 10 MB.')
        return doc

    def clean_available_from(self):
        when = self.cleaned_data.get('available_from')
        if when and when < timezone.localdate() - timedelta(days=365):
            raise ValidationError('That date is more than a year in the past.')
        return when

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('Property_on') == 'sale':
            cleaned['service_charge'] = 0
            cleaned['security_deposit_months'] = 0
        return cleaned


class ResidentialPropertyForm(BasePropertyForm):
    class Meta(BasePropertyForm.Meta):
        model = ResidentialProperty
        fields = SHARED_FIELDS + [
            'House_No', 'floor_number', 'Floor_count', 'Bedrooms', 'Bathrooms',
            'Number_of_Balcony', 'Garage_spaces_Per_Sqft', 'has_lift',
            'Has_Pool', 'Has_Garden', 'Year',
        ]
        widgets = dict(SHARED_WIDGETS, Year=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        cleaned = super().clean()
        floor = cleaned.get('floor_number')
        total = cleaned.get('Floor_count')
        if floor and total and floor > total:
            self.add_error('floor_number',
                           'The flat cannot be on a floor above the top of the building.')
        return cleaned


class CommercialPropertyForm(BasePropertyForm):
    class Meta(BasePropertyForm.Meta):
        model = CommercialProperty
        fields = SHARED_FIELDS + [
            'House_No', 'Business_type', 'Parking_spaces', 'Has_elevator',
            'Has_security_system', 'Has_conference_room', 'has_generator', 'Year',
        ]
        widgets = dict(SHARED_WIDGETS, Year=forms.DateInput(attrs={'type': 'date'}))


class LandPropertyForm(BasePropertyForm):
    class Meta(BasePropertyForm.Meta):
        model = LandProperty
        fields = SHARED_FIELDS + [
            'Land_type', 'Road_size_in_sqft', 'Is_fenced',
            'has_water_connection', 'has_gas_connection',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # land has no furnishing
        self.fields.pop('furnishing', None)


FORM_FOR_TYPE = {
    'residential': ResidentialPropertyForm,
    'commercial': CommercialPropertyForm,
    'land': LandPropertyForm,
}


class PropertyTypeForm(forms.Form):
    Type = forms.ChoiceField(
        choices=AllProperty.PROPERTY_TYPES, widget=forms.RadioSelect, label='',
    )


class MultiFileInput(forms.ClearableFileInput):
    """Django 5 refuses `multiple` on the stock widget, so allow it here."""
    allow_multiple_selected = True


class MultiImageField(forms.FileField):
    """Returns a list of files rather than only the last one."""

    widget = MultiFileInput

    def clean(self, data, initial=None):
        if not isinstance(data, (list, tuple)):
            data = [data] if data else []
        cleaned = []
        for one in data:
            if one:
                cleaned.append(super().clean(one, initial))
        return cleaned


class PropertyImageForm(forms.Form):
    """Several gallery images at once."""

    images = MultiImageField(
        widget=MultiFileInput(attrs={'multiple': True, 'accept': 'image/*'}),
        required=False, label='Add photos',
    )

    def clean_images(self):
        files = self.files.getlist('images') if hasattr(self.files, 'getlist') else []
        if len(files) > 8:
            raise ValidationError('Up to 8 photos at a time.')
        for f in files:
            if f.size > 5 * 1024 * 1024:
                raise ValidationError(f'"{f.name}" is over 5 MB.')
            if not (f.content_type or '').startswith('image/'):
                raise ValidationError(f'"{f.name}" is not an image.')
        return files


# filters

ORDERINGS = [
    ('', 'Most relevant'),
    ('newest', 'Newest first'),
    ('price_asc', 'Price: low to high'),
    ('price_desc', 'Price: high to low'),
    ('area_desc', 'Largest first'),
    ('rating', 'Best rated'),
    ('popular', 'Most viewed'),
]


class PropertyFilterForm(forms.Form):
    q = forms.CharField(
        required=False, label='Search',
        widget=forms.TextInput(attrs={
            'placeholder': 'Title, area, landmark or description',
            # picked up by the suggestion panel in static/js/app.js
            'data-suggest': '/property/suggest/',
        }),
    )
    property_type = forms.ChoiceField(
        choices=[('', 'Any type')] + list(AllProperty.PROPERTY_TYPES), required=False
    )
    property_on = forms.ChoiceField(
        choices=[('', 'Rent or buy')] + list(AllProperty.Action), required=False
    )
    area = forms.ChoiceField(
        choices=[('', 'Anywhere')] + list(AllProperty.AREA_CHOICES), required=False
    )
    city = forms.ChoiceField(
        choices=[('', 'Any city')] + list(AllProperty.CITY_CHOICES), required=False
    )
    min_price = forms.DecimalField(required=False, min_value=0,
                                   widget=forms.NumberInput(attrs={'placeholder': 'Min'}))
    max_price = forms.DecimalField(required=False, min_value=0,
                                   widget=forms.NumberInput(attrs={'placeholder': 'Max'}))
    min_area = forms.IntegerField(required=False, min_value=0,
                                  widget=forms.NumberInput(attrs={'placeholder': 'Min sq ft'}))
    furnishing = forms.ChoiceField(
        choices=[('', 'Any furnishing')] + list(AllProperty.Furnishing.choices), required=False
    )

    bedrooms = forms.IntegerField(required=False, min_value=0, label='Beds, at least')
    bathrooms = forms.IntegerField(required=False, min_value=0, label='Baths, at least')

    business_type = forms.ChoiceField(
        choices=[('', 'Any use')] + list(CommercialProperty.Business_types), required=False
    )
    has_conference = forms.BooleanField(required=False, label='Conference room')
    has_security = forms.BooleanField(required=False, label='Security')

    land_type = forms.ChoiceField(
        choices=[('', 'Any land')] + list(LandProperty.Land_types), required=False
    )

    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.all(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    ordering = forms.ChoiceField(choices=ORDERINGS, required=False)

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get('min_price'), cleaned.get('max_price')
        if low and high and low > high:
            cleaned['min_price'], cleaned['max_price'] = high, low
        return cleaned

    @property
    def active_count(self):
        """
        How many filters the user actually set, for the 'clear' button.

        The amenity field cleans to an empty queryset when nothing is ticked,
        and an empty queryset is not equal to [], so the old membership test
        counted it as a live filter on every visit and the page always claimed
        the results were filtered.
        """
        if not self.is_bound or not self.is_valid():
            return 0
        skip = {'ordering'}

        def is_set(value):
            if value is None or value is False or value == '':
                return False
            if hasattr(value, 'exists'):            # a queryset
                return value.exists()
            if isinstance(value, (list, tuple, set, dict)):
                return bool(value)
            return True

        return sum(1 for k, v in self.cleaned_data.items()
                   if k not in skip and is_set(v))


class SavedSearchForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ['label', 'alert_enabled']
        widgets = {'label': forms.TextInput(
            attrs={'placeholder': 'Three bed flats in Dhanmondi under 40k'})}


# reviews

class PropertyReviewForm(forms.ModelForm):
    class Meta:
        model = PropertyReview
        fields = ['rating', 'title', 'comment']
        widgets = {
            'rating': forms.RadioSelect(choices=[(i, i) for i in range(1, 6)]),
            'title': forms.TextInput(attrs={'placeholder': 'Sum it up in a few words'}),
            'comment': forms.Textarea(
                attrs={'rows': 4, 'placeholder': 'What was the place and the owner like?'}),
        }

    def clean_comment(self):
        comment = self.cleaned_data['comment'].strip()
        if len(comment) < 20:
            raise ValidationError('Write a little more, at least 20 characters.')
        return comment


# bookings

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['visit_date', 'visit_time', 'message']
        widgets = {
            'visit_date': forms.DateInput(attrs={'type': 'date'}),
            'visit_time': forms.TimeInput(attrs={'type': 'time'}),
            'message': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'Anything the owner should know?'}),
        }

    def __init__(self, *args, **kwargs):
        self.property = kwargs.pop('property', None)
        self.renter = kwargs.pop('renter', None)
        super().__init__(*args, **kwargs)
        # The three month window is enforced in clean_visit_date; mirroring it
        # onto the widget means the date picker itself will not offer a day the
        # server is going to refuse.
        self.fields['visit_date'].widget.attrs['min'] = timezone.localdate().isoformat()
        self.fields['visit_date'].widget.attrs['max'] = (
            timezone.localdate() + timedelta(days=90)).isoformat()
        self.fields['visit_date'].initial = timezone.localdate() + timedelta(days=1)
        self.fields['message'].required = False

    def clean_visit_date(self):
        when = self.cleaned_data['visit_date']
        if when < timezone.localdate():
            raise ValidationError('Pick a date in the future.')
        if when > timezone.localdate() + timedelta(days=90):
            raise ValidationError('Visits can be booked up to three months ahead.')
        return when

    def clean_visit_time(self):
        at = self.cleaned_data['visit_time']
        if not (8 <= at.hour < 21):
            raise ValidationError('Visits run between 8 in the morning and 9 at night.')
        return at

    def clean(self):
        cleaned = super().clean()
        day, at = cleaned.get('visit_date'), cleaned.get('visit_time')
        if not (day and at and self.property):
            return cleaned

        taken = Booking.objects.filter(
            property=self.property, visit_date=day, visit_time=at,
            status=Booking.Status.ACCEPTED,
        ).exists()
        if taken:
            raise ValidationError('Someone else already has that slot. Please pick another.')

        if self.renter:
            duplicate = Booking.objects.filter(
                property=self.property, renter=self.renter,
                visit_date=day, visit_time=at,
            ).exclude(pk=self.instance.pk or 0).exists()
            if duplicate:
                raise ValidationError('You have already asked for that slot.')
        return cleaned


# messaging

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['body']
        widgets = {'body': forms.Textarea(
            attrs={'rows': 3, 'placeholder': 'Write a message…'})}

    def clean_body(self):
        body = self.cleaned_data['body'].strip()
        if not body:
            raise ValidationError('Type something first.')
        return body
