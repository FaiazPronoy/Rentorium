from django import forms
from django.core.exceptions import ValidationError

from .models import Contact, Reviews


class ReviewForm(forms.ModelForm):
    """A review of Rentorium itself."""

    class Meta:
        model = Reviews
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.RadioSelect(choices=[(i, i) for i in range(1, 6)]),
            'comment': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'How did Rentorium work out for you?',
            }),
        }

    def clean_comment(self):
        comment = self.cleaned_data['comment'].strip()
        if len(comment) < 15:
            raise ValidationError('Write a little more, at least 15 characters.')
        return comment


class ContactForm(forms.ModelForm):
    """The contact form. A ModelForm this time, so it actually validates."""

    website = forms.CharField(required=False, widget=forms.HiddenInput)  # honeypot

    class Meta:
        model = Contact
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Your name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
            'subject': forms.TextInput(attrs={'placeholder': 'What is this about?'}),
            'message': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Tell us more…'}),
        }

    def clean_message(self):
        message = self.cleaned_data['message'].strip()
        if len(message) < 15:
            raise ValidationError('Please describe it in a little more detail.')
        return message

    def clean_website(self):
        """Bots fill hidden fields. People do not."""
        if self.cleaned_data.get('website'):
            raise ValidationError('Something went wrong. Please try again.')
        return ''
