import os

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone


class UserProfile(models.Model):
    """
    Everything about a person that Django's own User model does not hold.

    One profile per user, created automatically by a signal, so a user can
    never exist without one. That single guarantee removes a whole class of
    crashes the first version had.
    """

    GENDER_CHOICES = [
        (1, 'Male'),
        (2, 'Female'),
        (3, 'Other'),
    ]

    class Role(models.TextChoices):
        RENTER = 'renter', 'Renter'
        OWNER = 'owner', 'Property owner'
        AGENT = 'agent', 'Agent'

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='UserProfile'
    )
    name = models.CharField(max_length=50)
    email = models.EmailField(max_length=100)
    contact_no = models.CharField(max_length=20, blank=True, default='')
    gender = models.IntegerField(choices=GENDER_CHOICES, null=True, blank=True)
    nid = models.CharField(max_length=18, unique=True, null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True, default='')
    bio = models.TextField(max_length=500, blank=True, default='')
    profile_picture = models.ImageField(upload_to='profile_picture', null=True, blank=True)

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.RENTER)
    is_agent = models.BooleanField(default=False)          # mirrors role
    is_verified = models.BooleanField(default=False)
    avatar_color = models.CharField(max_length=7, default='#009C6B')

    # --- moderation -------------------------------------------------------
    # A suspended person keeps their account and their data; they simply
    # cannot sign in or act until an agent lifts it. Nothing is deleted, so a
    # mistake can be undone, and their listings come back with them.
    is_suspended = models.BooleanField(default=False)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_reason = models.CharField(max_length=200, blank=True, default='')
    suspended_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='suspensions_made',
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['is_agent']),
            models.Index(fields=['is_suspended']),
        ]

    def __str__(self):
        return self.name or self.email

    def save(self, *args, **kwargs):
        # role and is_agent are two views of the same fact, so keep them in step
        if self.role == self.Role.AGENT:
            self.is_agent = True
        elif self.is_agent and self.role != self.Role.AGENT:
            self.role = self.Role.AGENT
        super().save(*args, **kwargs)

    # helpers
    @property
    def initials(self):
        parts = [p for p in (self.name or self.email).split() if p]
        if not parts:
            return '?'
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    @property
    def first_name(self):
        return (self.name or '').split(' ')[0]

    @property
    def display_role(self):
        return self.get_role_display()

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER or self.properties.exists()

    def suspend(self, by=None, reason=''):
        """Lock the account and hide everything they have listed."""
        from property.models import AllProperty
        self.is_suspended = True
        self.suspended_at = timezone.now()
        self.suspended_reason = (reason or '')[:200]
        self.suspended_by = by
        self.save(update_fields=['is_suspended', 'suspended_at',
                                 'suspended_reason', 'suspended_by'])
        # Their listings come off the site with them, but stay in the database
        # so lifting the suspension puts everything back untouched.
        self.properties.filter(is_archived=False).update(is_archived=True)
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])

    def lift_suspension(self, by=None):
        self.is_suspended = False
        self.suspended_at = None
        self.suspended_reason = ''
        self.suspended_by = by
        self.save(update_fields=['is_suspended', 'suspended_at',
                                 'suspended_reason', 'suspended_by'])
        self.properties.filter(is_archived=True).update(is_archived=False)
        self.user.is_active = True
        self.user.save(update_fields=['is_active'])

    @property
    def masked_nid(self):
        if not self.nid:
            return ''
        return '*' * max(0, len(self.nid) - 4) + self.nid[-4:]

    @property
    def listing_count(self):
        return self.properties.count()

    @property
    def member_since(self):
        return self.created_at

    def get_absolute_url(self):
        return reverse('public_profile', args=[self.pk])

    def unread_messages(self):
        from property.models import Message
        return Message.objects.filter(
            conversation__in=self.conversations_as_renter.all() | self.conversations_as_owner.all(),
            is_read=False,
        ).exclude(sender=self).count()

    def unread_notifications(self):
        return self.notifications.filter(is_read=False).count()


# signals

@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    """A user without a profile broke half of the first version. Not any more."""
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                'name': (instance.get_full_name() or instance.username or '').strip()[:50],
                'email': instance.email or '',
            },
        )


@receiver(pre_delete, sender=UserProfile)
def delete_profile_picture(sender, instance, **kwargs):
    if instance.profile_picture:
        try:
            if os.path.isfile(instance.profile_picture.path):
                os.remove(instance.profile_picture.path)
        except (ValueError, OSError):
            pass


class Notification(models.Model):
    """In app notifications: a booking request, a reply, an approval."""

    class Kind(models.TextChoices):
        BOOKING = 'booking', 'Booking'
        MESSAGE = 'message', 'Message'
        APPROVAL = 'approval', 'Approval'
        REVIEW = 'review', 'Review'
        ALERT = 'alert', 'Alert'
        SYSTEM = 'system', 'System'

    profile = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='notifications'
    )
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.SYSTEM)
    title = models.CharField(max_length=120)
    body = models.CharField(max_length=300, blank=True, default='')
    link = models.CharField(max_length=300, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['profile', 'is_read', '-created_at'])]

    def __str__(self):
        return f'{self.profile}: {self.title}'

    @staticmethod
    def push(profile, title, body='', link='', kind=Kind.SYSTEM):
        """Fire and forget. Never let a notification failure break a request."""
        if profile is None:
            return None
        try:
            return Notification.objects.create(
                profile=profile, title=title, body=body[:300],
                link=link, kind=kind,
            )
        except Exception:
            return None


class LoginAttempt(models.Model):
    """Sign in attempts, so brute force can be throttled and shown to the user."""

    username = models.CharField(max_length=150)
    ip = models.CharField(max_length=45, blank=True, default='')
    successful = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-attempted_at']
        indexes = [models.Index(fields=['username', '-attempted_at'])]

    def __str__(self):
        return f'{self.username} {"ok" if self.successful else "failed"}'

    @classmethod
    def recent_failures(cls, username, minutes=15):
        since = timezone.now() - timezone.timedelta(minutes=minutes)
        return cls.objects.filter(
            username=username, successful=False, attempted_at__gte=since
        ).count()
