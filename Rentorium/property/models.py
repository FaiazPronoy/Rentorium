import os
import uuid
# `property` is a field name on several models below, which shadows the builtin
# inside those class bodies. This alias keeps the decorator usable there.
from builtins import property as computed

from django.core.validators import (
    FileExtensionValidator, MaxValueValidator, MinValueValidator,
)
from django.db import models
from django.db.models import Avg, Count, Q
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from authentication.models import UserProfile

from .storage import private_storage


# reference data

class Amenity(models.Model):
    """Lift, generator, gym, parking. Kept as rows so the admin can add more."""

    name = models.CharField(max_length=50, unique=True)
    # Legacy: the site draws an SVG picked from the name now, so this is only
    # here for rows created before that change. Safe to leave blank.
    icon = models.CharField(max_length=8, blank=True, default='')
    group = models.CharField(max_length=30, default='General')

    class Meta:
        ordering = ['group', 'name']
        verbose_name_plural = 'amenities'

    def __str__(self):
        return self.name


# property

class PropertyQuerySet(models.QuerySet):
    """Reusable filters, so a view never has to remember what 'live' means."""

    def live(self):
        return self.filter(status=AllProperty.Status.APPROVED, is_archived=False)

    def pending(self):
        return self.filter(status=AllProperty.Status.PENDING)

    def with_stats(self):
        return self.annotate(
            avg_rating=Avg('reviews__rating'),
            review_count=Count('reviews', distinct=True),
            favourite_count=Count('favourited_by', distinct=True),
        )

    def owned_by(self, profile):
        return self.filter(user=profile)

    def with_cards(self):
        """Everything a property card needs, in one round trip."""
        return (self.select_related(
                    'user',
                    'residentialproperty', 'commercialproperty', 'landproperty')
                .prefetch_related('images', 'amenities')
                .with_stats())


class AllProperty(models.Model):
    """
    The base listing. Residential, commercial and land each extend it, which
    keeps the shared columns in one table and the specific ones in their own.
    """

    PROPERTY_TYPES = (
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('land', 'Land'),
    )
    Action = (
        ('rent', 'Rent'),
        ('sale', 'Sale'),
    )
    CITY_CHOICES = (
        ('Dhaka', 'Dhaka'),
        ('Chattogram', 'Chattogram'),
        ('Sylhet', 'Sylhet'),
        ('Khulna', 'Khulna'),
        ('Rajshahi', 'Rajshahi'),
    )
    AREA_CHOICES = (
        ('Gulshan', 'Gulshan'),
        ('Banani', 'Banani'),
        ('Dhanmondi', 'Dhanmondi'),
        ('Bashundhara R/A', 'Bashundhara R/A'),
        ('Uttara', 'Uttara'),
        ('Mirpur', 'Mirpur'),
        ('Mohakhali', 'Mohakhali'),
        ('Badda', 'Badda'),
        ('Motijheel', 'Motijheel'),
        ('Agrabad', 'Agrabad'),
        ('Zindabazar', 'Zindabazar'),
        ('Other', 'Other'),
    )

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING = 'pending', 'Waiting for approval'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        RENTED = 'rented', 'Rented or sold'

    class Furnishing(models.TextChoices):
        UNFURNISHED = 'unfurnished', 'Unfurnished'
        SEMI = 'semi', 'Semi furnished'
        FULL = 'full', 'Fully furnished'

    # --- ownership ------------------------------------------------------
    user = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='properties', null=True
    )

    # --- the listing ----------------------------------------------------
    Property_Name = models.CharField('title', max_length=200)
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    Property_Description = models.TextField(blank=True, default='')
    Total_area_in_sqft = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(1)],
    )
    Price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    service_charge = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
        help_text='Monthly service charge, on top of the rent.',
    )
    security_deposit_months = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(24)],
    )
    negotiable = models.BooleanField(default=False)

    Property_Pictures = models.ImageField(upload_to='pics', null=True, blank=True)

    # --- where ----------------------------------------------------------
    Road_No = models.CharField(max_length=10, blank=True, default='')
    Block = models.CharField('block or sector', max_length=20, blank=True, default='')
    City = models.CharField(max_length=100, choices=CITY_CHOICES, default='Dhaka')
    Postal_code = models.CharField(max_length=6, blank=True, default='')
    Area = models.CharField(max_length=100, choices=AREA_CHOICES)
    landmark = models.CharField(max_length=120, blank=True, default='')

    # --- classification --------------------------------------------------
    Property_on = models.CharField(max_length=20, choices=Action, default='rent')
    Property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES)
    furnishing = models.CharField(
        max_length=12, choices=Furnishing.choices, default=Furnishing.UNFURNISHED
    )
    available_from = models.DateField(null=True, blank=True)
    amenities = models.ManyToManyField(Amenity, blank=True, related_name='properties')

    # --- moderation -------------------------------------------------------
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    Approval_by_Agent = models.CharField(max_length=50, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=200, blank=True, default='')
    needs_approval = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)

    Property_Documents = models.FileField(
        upload_to='property_documents', null=True, blank=True,
        storage=private_storage,          # never served straight off a URL
        validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])],
        help_text='Ownership paper or deed. Only you and a verified agent can open it.',
    )

    # --- counters ---------------------------------------------------------
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PropertyQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'properties'
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['Property_type', 'Property_on']),
            models.Index(fields=['Area', 'City']),
            models.Index(fields=['Price']),
            models.Index(fields=['slug']),
        ]
        constraints = [
            models.CheckConstraint(check=Q(Price__gte=0), name='price_not_negative'),
        ]

    def __str__(self):
        return self.Property_Name

    # saving
    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.Property_Name)[:180] or 'property'
            candidate = base
            n = 2
            while AllProperty.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f'{base}-{n}'
                n += 1
            self.slug = candidate
        # status and the two legacy flags describe the same thing, keep them true
        if self.status == self.Status.APPROVED:
            self.needs_approval = False
            if not self.approved_at:
                self.approved_at = timezone.now()
        elif self.status == self.Status.PENDING:
            self.needs_approval = True
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        # the readable form when there is a slug, the bare id otherwise
        if self.slug:
            return reverse('property_detail', args=[self.pk, self.slug])
        return reverse('property_detail', args=[self.pk])

    # behaviour
    @property
    def is_live(self):
        return self.status == self.Status.APPROVED and not self.is_archived

    @property
    def is_rental(self):
        return self.Property_on == 'rent'

    @property
    def price_label(self):
        return 'per month' if self.is_rental else 'total'

    @property
    def full_address(self):
        bits = [b for b in [
            f'House {self.house_no}' if self.house_no else '',
            f'Road {self.Road_No}' if self.Road_No else '',
            self.Block, self.Area, self.City,
        ] if b]
        return ', '.join(bits)

    @property
    def house_no(self):
        """Land has no house number, the other two do."""
        for attr in ('residentialproperty', 'commercialproperty'):
            sub = getattr(self, attr, None)
            if sub is not None:
                return sub.House_No
        return ''

    @property
    def specific(self):
        """
The subtype row for this listing, or None."""
        for attr in ('residentialproperty', 'commercialproperty', 'landproperty'):
            try:
                return getattr(self, attr)
            except (AttributeError, models.ObjectDoesNotExist):
                continue
        return None

    @property
    def price_per_sqft(self):
        if self.Total_area_in_sqft and self.Total_area_in_sqft > 0:
            return round(float(self.Price) / float(self.Total_area_in_sqft), 2)
        return None

    @property
    def monthly_total(self):
        return float(self.Price) + float(self.service_charge)

    @property
    def cover_image(self):
        for image in self.images.all():
            return image.image
        return self.Property_Pictures or None

    @property
    def rating(self):
        if hasattr(self, 'avg_rating'):
            value = self.avg_rating
        else:
            value = self.reviews.aggregate(v=Avg('rating'))['v']
        return round(value, 1) if value else None

    @property
    def rating_count(self):
        if hasattr(self, 'review_count'):
            return self.review_count
        return self.reviews.count()

    @property
    def stars(self):
        """A list of 5 booleans, so the template does not have to do maths."""
        r = self.rating or 0
        return [i <= round(r) for i in range(1, 6)]

    def headline_facts(self):
        """
        The three numbers shown on a card, whatever the type.

        A card shows the first three, so size goes in before the nice-to-know
        ones: a listing that told you bedrooms, bathrooms and balconies but
        not the floor area was the least useful of the possible three.
        """
        sub = self.specific
        size = ((f'{int(self.Total_area_in_sqft):,}', 'sq ft')
                if self.Total_area_in_sqft else None)
        facts = []
        if isinstance(sub, ResidentialProperty):
            facts = [
                (f'{sub.Bedrooms}', 'bed'),
                (f'{sub.Bathrooms}', 'bath'),
            ]
            if size:
                facts.append(size)
            facts.append((f'{sub.Number_of_Balcony}', 'balcony'))
        elif isinstance(sub, CommercialProperty):
            facts = [(sub.get_Business_type_display() or 'Commercial', 'use')]
            if size:
                facts.append(size)
            facts.append((f'{sub.Parking_spaces}', 'parking'))
        elif isinstance(sub, LandProperty):
            facts = [(sub.get_Land_type_display() or 'Land', 'type')]
            if size:
                facts.append(size)
            facts.append(('Fenced' if sub.Is_fenced else 'Open', 'boundary'))
        elif size:
            facts = [size]
        return facts

    def can_be_seen_by(self, profile):
        if self.is_live:
            return True
        if profile is None:
            return False
        return profile == self.user or profile.is_agent

    def can_be_edited_by(self, profile):
        return profile is not None and (profile == self.user or profile.is_agent)

    def can_documents_be_seen_by(self, profile):
        """Private papers: the owner and a verified agent, nobody else."""
        return profile is not None and (profile == self.user or profile.is_agent)

    def register_view(self, profile=None, session_key=''):
        """One view per person per day, so the counter means something."""
        today = timezone.now().date()
        already = PropertyView.objects.filter(
            property=self, viewed_on=today,
        ).filter(
            Q(profile=profile) if profile else Q(session_key=session_key)
        ).exists()
        if already:
            return False
        PropertyView.objects.create(
            property=self, profile=profile, session_key=session_key[:40], viewed_on=today
        )
        AllProperty.objects.filter(pk=self.pk).update(view_count=models.F('view_count') + 1)
        return True


@receiver(pre_delete, sender=AllProperty)
def delete_property_files(sender, instance, **kwargs):
    for field in (instance.Property_Pictures, instance.Property_Documents):
        if field:
            try:
                if os.path.isfile(field.path):
                    os.remove(field.path)
            except (ValueError, OSError):
                pass


# the subtypes

class ResidentialProperty(AllProperty):
    House_No = models.CharField(max_length=10, blank=True, default='')
    Floor_count = models.PositiveIntegerField(default=1, validators=[MaxValueValidator(200)])
    floor_number = models.PositiveIntegerField(default=1, validators=[MaxValueValidator(200)])
    Bedrooms = models.PositiveIntegerField(default=1, validators=[MaxValueValidator(30)])
    Bathrooms = models.PositiveIntegerField(default=1, validators=[MaxValueValidator(30)])
    Garage_spaces_Per_Sqft = models.PositiveIntegerField('garage spaces', default=0)
    Has_Pool = models.BooleanField('has a pool', default=False)
    Has_Garden = models.BooleanField('has a garden', default=False)
    Number_of_Balcony = models.PositiveIntegerField('balconies', default=1)
    has_lift = models.BooleanField('has a lift', default=False)
    Year = models.DateField('built in', null=True, blank=True)

    class Meta:
        verbose_name_plural = 'residential properties'


class CommercialProperty(AllProperty):
    Business_types = (
        ('office', 'Office'),
        ('community_center', 'Community centre'),
        ('shop', 'Shop'),
        ('restaurant', 'Restaurant'),
        ('warehouse', 'Warehouse'),
        ('other', 'Other'),
    )

    House_No = models.CharField(max_length=10, blank=True, default='')
    Business_type = models.CharField(max_length=20, choices=Business_types, default='office')
    Parking_spaces = models.PositiveIntegerField(default=0)
    Has_elevator = models.BooleanField('has a lift', default=False)
    Has_security_system = models.BooleanField('has security', default=False)
    Has_conference_room = models.BooleanField('has a conference room', default=False)
    has_generator = models.BooleanField('has a generator', default=False)
    Year = models.DateField('built in', null=True, blank=True)

    class Meta:
        verbose_name_plural = 'commercial properties'


class LandProperty(AllProperty):
    Land_types = (
        ('Farmland', 'Farmland'),
        ('Playground', 'Playground'),
        ('warehouse', 'Warehouse plot'),
        ('residential_plot', 'Residential plot'),
        ('commercial_plot', 'Commercial plot'),
    )

    Land_type = models.CharField(max_length=100, choices=Land_types, default='residential_plot')
    Road_size_in_sqft = models.PositiveIntegerField('road width in feet', default=0)
    Is_fenced = models.BooleanField('is fenced', default=False)
    has_water_connection = models.BooleanField(default=False)
    has_gas_connection = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'land properties'


# gallery

class PropertyImage(models.Model):
    property = models.ForeignKey(
        AllProperty, on_delete=models.CASCADE, related_name='images'
    )
    image = models.ImageField(upload_to='pics')
    caption = models.CharField(max_length=120, blank=True, default='')
    position = models.PositiveSmallIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'id']

    def __str__(self):
        return f'{self.property.Property_Name} image {self.pk}'


@receiver(pre_delete, sender=PropertyImage)
def delete_image_file(sender, instance, **kwargs):
    if instance.image:
        try:
            if os.path.isfile(instance.image.path):
                os.remove(instance.image.path)
        except (ValueError, OSError):
            pass


# favourites

class Favourite(models.Model):
    profile = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='favourites'
    )
    property = models.ForeignKey(
        AllProperty, on_delete=models.CASCADE, related_name='favourited_by'
    )
    note = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['profile', 'property'], name='unique_favourite'),
        ]

    def __str__(self):
        return f'{self.profile} saved {self.property}'


# reviews

class PropertyReview(models.Model):
    """A review of one property, by someone who is not its owner."""

    property = models.ForeignKey(
        AllProperty, on_delete=models.CASCADE, related_name='reviews'
    )
    author = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='property_reviews'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=120, blank=True, default='')
    comment = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['property', 'author'], name='one_review_per_person'),
        ]
        indexes = [models.Index(fields=['property', '-created_at'])]

    def __str__(self):
        return f'{self.author} rated {self.property} {self.rating}/5'

    def stars(self):
        return [i <= self.rating for i in range(1, 6)]


# bookings

class Booking(models.Model):
    """
    A request to view a property at a given time. The owner accepts or
    declines. Two accepted bookings can never share the same slot.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Waiting for the owner'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'

    reference = models.CharField(max_length=12, unique=True, blank=True)
    property = models.ForeignKey(
        AllProperty, on_delete=models.CASCADE, related_name='bookings'
    )
    renter = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='bookings_made'
    )
    owner = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='bookings_received'
    )
    visit_date = models.DateField()
    visit_time = models.TimeField()
    message = models.CharField(max_length=300, blank=True, default='')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    owner_response = models.CharField(max_length=300, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['visit_date', 'visit_time']
        constraints = [
            # one accepted visit per property per slot
            models.UniqueConstraint(
                fields=['property', 'visit_date', 'visit_time'],
                condition=Q(status='accepted'),
                name='one_accepted_visit_per_slot',
            ),
            # and one open request per person per property per slot
            models.UniqueConstraint(
                fields=['property', 'renter', 'visit_date', 'visit_time'],
                name='no_duplicate_request',
            ),
        ]
        indexes = [
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['renter', 'status']),
        ]

    def __str__(self):
        return f'{self.reference} {self.property} on {self.visit_date}'

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = 'RV' + uuid.uuid4().hex[:8].upper()
        super().save(*args, **kwargs)

    def is_past(self):
        return self.visit_date < timezone.localdate()

    def badge_class(self):
        return {
            self.Status.PENDING: 'badge-pending',
            self.Status.ACCEPTED: 'badge-ok',
            self.Status.DECLINED: 'badge-fail',
            self.Status.CANCELLED: 'badge-fail',
            self.Status.COMPLETED: 'badge-ok',
        }.get(self.status, '')


# messaging

class Conversation(models.Model):
    """One thread per renter, per property."""

    property = models.ForeignKey(
        AllProperty, on_delete=models.CASCADE, related_name='conversations'
    )
    renter = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='conversations_as_renter'
    )
    owner = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='conversations_as_owner'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-last_message_at']
        constraints = [
            models.UniqueConstraint(
                fields=['property', 'renter'], name='one_thread_per_renter_per_property'
            ),
        ]

    def __str__(self):
        return f'{self.renter} about {self.property}'

    def other_party(self, profile):
        return self.owner if profile == self.renter else self.renter

    def unread_for(self, profile):
        return self.messages.filter(is_read=False).exclude(sender=profile).count()

    def involves(self, profile):
        return profile in (self.renter, self.owner)


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='messages_sent'
    )
    body = models.TextField(max_length=2000)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['conversation', 'created_at'])]

    def __str__(self):
        return f'{self.sender}: {self.body[:40]}'


# saved searches

class SavedSearch(models.Model):
    """A filter set the user wants to keep, with a count of new matches."""

    profile = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='saved_searches'
    )
    label = models.CharField(max_length=60)
    query_string = models.CharField(max_length=400)
    alert_enabled = models.BooleanField(default=True)
    last_checked = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.profile}: {self.label}'


# analytics

class PropertyView(models.Model):
    """One row per person per property per day. Feeds the owner dashboard."""

    property = models.ForeignKey(
        AllProperty, on_delete=models.CASCADE, related_name='view_log'
    )
    profile = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='property_views',
    )
    session_key = models.CharField(max_length=40, blank=True, default='')
    viewed_on = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['property', 'viewed_on'])]

    def __str__(self):
        return f'{self.property} viewed on {self.viewed_on}'


# search history

class RecentSearch(models.Model):
    """The last few things a signed in person searched for.

    Kept server side rather than in the browser so the list follows the person
    from their phone to their laptop. One row per person per phrase: searching
    the same thing again moves it back to the top instead of filling the list.
    """

    profile = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='recent_searches'
    )
    term = models.CharField(max_length=80)
    query_string = models.CharField(max_length=400, blank=True, default='')
    hits = models.PositiveIntegerField(default=0)
    searched_at = models.DateTimeField(default=timezone.now)

    KEEP = 8

    class Meta:
        ordering = ['-searched_at']
        constraints = [
            models.UniqueConstraint(fields=['profile', 'term'],
                                    name='one_row_per_person_per_term'),
        ]
        indexes = [models.Index(fields=['profile', '-searched_at'])]

    def __str__(self):
        return f'{self.profile}: {self.term}'

    @classmethod
    def remember(cls, profile, term, query_string='', hits=0):
        """Record a search, then trim the list back to the newest few."""
        term = ' '.join((term or '').split())[:80]
        if not profile or not term:
            return None
        row, _ = cls.objects.update_or_create(
            profile=profile, term=term,
            defaults={'query_string': query_string[:400],
                      'hits': hits, 'searched_at': timezone.now()},
        )
        stale = list(cls.objects.filter(profile=profile)
                     .values_list('pk', flat=True)[cls.KEEP:])
        if stale:
            cls.objects.filter(pk__in=stale).delete()
        return row


# reports

class PropertyReport(models.Model):
    """Someone telling us a listing is wrong, fake or already gone.

    Anyone signed in can file one; it lands in the agent queue. The same
    person cannot report the same listing twice while their first report is
    still open, so one annoyed user cannot bury the queue.
    """

    class Reason(models.TextChoices):
        FAKE = 'fake', 'The listing looks fake'
        TAKEN = 'taken', 'Already rented or sold'
        WRONG = 'wrong', 'Details or photos are wrong'
        PRICE = 'price', 'The price is misleading'
        DUPLICATE = 'duplicate', 'Posted more than once'
        OFFENSIVE = 'offensive', 'Offensive or spam content'
        OTHER = 'other', 'Something else'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        UPHELD = 'upheld', 'Upheld'
        DISMISSED = 'dismissed', 'Dismissed'

    property = models.ForeignKey(
        AllProperty, on_delete=models.CASCADE, related_name='reports'
    )
    reporter = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reports_filed',
    )
    reason = models.CharField(max_length=12, choices=Reason.choices)
    detail = models.CharField(max_length=500, blank=True, default='')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    handled_by = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reports_handled',
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['property', 'reporter'],
                condition=Q(status='open'),
                name='one_open_report_per_person_per_listing',
            ),
        ]
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['property', 'status']),
        ]

    def __str__(self):
        return f'{self.get_reason_display()} on {self.property}'

    @computed
    def badge_class(self):
        return {
            self.Status.OPEN: 'badge-pending',
            self.Status.UPHELD: 'badge-fail',
            self.Status.DISMISSED: 'badge-ok',
        }.get(self.status, '')
