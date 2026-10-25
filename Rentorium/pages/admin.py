from django.contrib import admin

from .models import Contact, Faq, Reviews


@admin.register(Reviews)
class ReviewsAdmin(admin.ModelAdmin):
    list_display = ('user', 'rating', 'is_published', 'date')
    list_filter = ('rating', 'is_published')
    search_fields = ('comment', 'user__name')


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'email', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('subject', 'message', 'name', 'email')


@admin.register(Faq)
class FaqAdmin(admin.ModelAdmin):
    list_display = ('question', 'position', 'is_published')
    list_editable = ('position', 'is_published')
