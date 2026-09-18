from django.contrib import admin

from .models import (
    AllProperty, Amenity, Booking, CommercialProperty, Conversation, Favourite,
    LandProperty, Message, PropertyImage, PropertyReview, PropertyView,
    ResidentialProperty, SavedSearch,
)


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1


class BasePropertyAdmin(admin.ModelAdmin):
    list_display = ('Property_Name', 'user', 'Property_type', 'Property_on',
                    'Price', 'Area', 'status', 'is_featured', 'view_count')
    list_filter = ('status', 'Property_type', 'Property_on', 'Area', 'is_featured')
    search_fields = ('Property_Name', 'Property_Description', 'Area', 'user__name')
    readonly_fields = ('slug', 'view_count', 'created_at', 'updated_at')
    filter_horizontal = ('amenities',)
    inlines = [PropertyImageInline]
    list_select_related = ('user',)


@admin.register(AllProperty)
class AllPropertyAdmin(BasePropertyAdmin):
    pass


@admin.register(ResidentialProperty)
class ResidentialPropertyAdmin(BasePropertyAdmin):
    pass


@admin.register(CommercialProperty)
class CommercialPropertyAdmin(BasePropertyAdmin):
    pass


@admin.register(LandProperty)
class LandPropertyAdmin(BasePropertyAdmin):
    pass


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'icon')
    list_filter = ('group',)


@admin.register(PropertyReview)
class PropertyReviewAdmin(admin.ModelAdmin):
    list_display = ('property', 'author', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('comment', 'property__Property_Name', 'author__name')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('reference', 'property', 'renter', 'visit_date',
                    'visit_time', 'status')
    list_filter = ('status', 'visit_date')
    search_fields = ('reference', 'property__Property_Name', 'renter__name')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('property', 'renter', 'owner', 'last_message_at')
    search_fields = ('property__Property_Name', 'renter__name', 'owner__name')


admin.site.register([Favourite, Message, SavedSearch, PropertyView, PropertyImage])
