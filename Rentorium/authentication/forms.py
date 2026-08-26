import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import UserProfile

SPECIAL = set('$@#%*^!&?.-_')


def check_password_strength(password):
    """One place for the password rules, used by signup and by change password."""
    errors = []
    if len(password) < 8:
        errors.append('Use at least 8 characters.')
    if not any(c.isdigit() for c in password):
        errors.append('Include at least one number.')
    if not any(c.isupper() for c in password):
        errors.append('Include at least one capital letter.')
    if not any(c.islower() for c in password):
        errors.append('Include at least one small letter.')
    if not any(c in SPECIAL for c in password):
        errors.append('Include one special character, for example @ # ! or ?')
    if errors:
        raise ValidationError(errors)
    return password


class SignUpForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='At least 8 characters, with a capital, a number and a symbol.',
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'})
    )
    role = forms.ChoiceField(
        choices=[
            (UserProfile.Role.RENTER, 'I am looking for a place'),
            (UserProfile.Role.OWNER, 'I want to list my property'),
        ],
        initial=UserProfile.Role.RENTER,
        widget=forms.RadioSelect,
    )
    agree = forms.BooleanField(
        label='I agree to the terms and the privacy policy', required=True
    )

    class Meta:
        model = UserProfile
        fields = ['name', 'email', 'contact_no', 'nid']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Faiaz Abrar'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
            'contact_no': forms.TextInput(attrs={'placeholder': '01XXXXXXXXX'}),
            'nid': forms.TextInput(attrs={'placeholder': '10, 13 or 17 digits'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('That email is already registered.')
        return email

    def clean_name(self):
        name = ' '.join(self.cleaned_data['name'].split())
        if len(name) < 3:
            raise ValidationError('Please enter your full name.')
        return name.title()

    def clean_contact_no(self):
        contact = (self.cleaned_data.get('contact_no') or '').strip()
        if contact and not re.fullmatch(r'01[3-9]\d{8}', contact):
            raise ValidationError('Enter a valid 11 digit Bangladeshi number.')
        return contact

    def clean_nid(self):
        nid = (self.cleaned_data.get('nid') or '').strip()
        if not nid:
            return nid
        if not nid.isdigit() or len(nid) not in (10, 13, 17, 18):
            raise ValidationError('NID must be 10, 13, 17 or 18 digits.')
        if UserProfile.objects.filter(nid=nid).exists():
            raise ValidationError('That NID is already registered.')
        return nid

    def clean_password(self):
        return check_password_strength(self.cleaned_data['password'])

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        confirm = cleaned.get('confirm_password')
        if password and confirm and password != confirm:
            self.add_error('confirm_password', 'The two passwords do not match.')
        return cleaned


class SignInForm(AuthenticationForm):
    error_messages = {
        'invalid_login': 'Wrong email or password. Please try again.',
        'inactive': 'This account has been disabled.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Email'
        self.fields['username'].widget.attrs.update({
            'placeholder': 'you@example.com', 'autocomplete': 'username', 'autofocus': True,
        })
        self.fields['password'].widget.attrs.update({'autocomplete': 'current-password'})

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()


class EditProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'name', 'email', 'contact_no', 'gender', 'nid', 'dob',
            'address', 'bio', 'profile_picture', 'role',
        ]
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'bio': forms.Textarea(attrs={'rows': 3,
                                         'placeholder': 'A line or two about you.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = [
            (UserProfile.Role.RENTER, 'Renter'),
            (UserProfile.Role.OWNER, 'Property owner'),
        ]
        if self.instance and self.instance.is_agent:
            # an agent cannot demote themselves through this form
            self.fields['role'].disabled = True
            self.fields['role'].choices = [(UserProfile.Role.AGENT, 'Agent')]

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.user_id:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise ValidationError('That email belongs to another account.')
        return email

    def clean_nid(self):
        nid = (self.cleaned_data.get('nid') or '').strip()
        if not nid:
            return None
        qs = UserProfile.objects.filter(nid=nid).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('That NID belongs to another account.')
        return nid

    def clean_contact_no(self):
        contact = (self.cleaned_data.get('contact_no') or '').strip()
        if contact and not re.fullmatch(r'01[3-9]\d{8}', contact):
            raise ValidationError('Enter a valid 11 digit Bangladeshi number.')
        return contact

    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if picture and getattr(picture, 'size', 0) > 5 * 1024 * 1024:
            raise ValidationError('Keep the picture under 5 MB.')
        return picture


class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput)
    new_password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current = self.cleaned_data['current_password']
        if not self.user.check_password(current):
            raise ValidationError('That is not your current password.')
        return current

    def clean_new_password(self):
        new = self.cleaned_data['new_password']
        check_password_strength(new)
        validate_password(new, self.user)
        return new

    def clean(self):
        cleaned = super().clean()
        new = cleaned.get('new_password')
        confirm = cleaned.get('confirm_password')
        if new and confirm and new != confirm:
            self.add_error('confirm_password', 'The two passwords do not match.')
        if new and self.user.check_password(new):
            self.add_error('new_password', 'Choose something different from the old one.')
        return cleaned

    def save(self):
        self.user.set_password(self.cleaned_data['new_password'])
        self.user.save()
        return self.user
