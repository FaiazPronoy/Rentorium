from django import forms
from .models import *

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Reviews
        fields = ['comment', 'rating']

class ContactForm(forms.Form):
    class Meta:
        model = Contact
        fields = "__all__"
