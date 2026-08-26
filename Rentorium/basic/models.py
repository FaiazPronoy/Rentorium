from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from authentication.models import UserProfile


class Reviews(models.Model):
    """A review of the platform itself, shown on the testimonial page."""

    user = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='site_reviews'
    )
    comment = models.TextField(max_length=1000)
    rating = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    date = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'reviews'
        constraints = [
            models.UniqueConstraint(fields=['user'], name='one_site_review_per_user'),
        ]

    def __str__(self):
        return f'{self.user} rated the site {self.rating}/5'

    @property
    def stars(self):
        return [i <= self.rating for i in range(1, 6)]


class Contact(models.Model):
    """A message from the contact form."""

    class Status(models.TextChoices):
        NEW = 'new', 'New'
        ANSWERED = 'answered', 'Answered'
        CLOSED = 'closed', 'Closed'

    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField(max_length=4000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    reply = models.TextField(max_length=4000, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', '-created_at'])]

    def __str__(self):
        return self.subject


class Faq(models.Model):
    """Editable FAQ, so the page is not hard coded into a template."""

    question = models.CharField(max_length=200)
    answer = models.TextField(max_length=2000)
    position = models.PositiveSmallIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['position', 'id']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'

    def __str__(self):
        return self.question
