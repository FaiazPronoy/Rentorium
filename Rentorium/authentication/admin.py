from django.contrib import admin

from .models import LoginAttempt, Notification, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'role', 'is_agent', 'is_verified', 'created_at')
    list_filter = ('role', 'is_agent', 'is_verified', 'gender')
    search_fields = ('name', 'email', 'contact_no', 'nid')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('user',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('profile', 'kind', 'title', 'is_read', 'created_at')
    list_filter = ('kind', 'is_read')
    search_fields = ('title', 'body', 'profile__name')


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('username', 'ip', 'successful', 'attempted_at')
    list_filter = ('successful',)
    search_fields = ('username', 'ip')
