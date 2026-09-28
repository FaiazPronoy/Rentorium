import json
import mimetypes
from urllib.parse import quote_plus, urlparse

from django.conf import settings
from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.http import FileResponse, Http404, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin

from authentication.decorators import (
    login_required_message, post_required, profile_of,
)
from authentication.models import Notification

from .templatetags.property_filters import money
from .forms import (
    FORM_FOR_TYPE, BookingForm, MessageForm, PropertyFilterForm,
    PropertyImageForm, PropertyReviewForm, PropertyTypeForm, SavedSearchForm,
)
from .models import (
    AllProperty, Booking, Conversation, Favourite, Message, PropertyImage,
    PropertyReport, PropertyReview, PropertyView, RecentSearch, SavedSearch,
)


def safe_back(request, fallback):
    """
    Go back where the user came from, but only if that is somewhere on this
    site. A raw Referer header is attacker controlled, so it can point at
    anywhere at all.
    """
    referer = request.META.get('HTTP_REFERER', '')
    if referer:
        parsed = urlparse(referer)
        if not parsed.netloc or parsed.netloc == request.get_host():
            target = parsed.path + (f'?{parsed.query}' if parsed.query else '')
            if target.startswith('/') and not target.startswith('//'):
                return redirect(target)
    return redirect(fallback)


# the search

def apply_filters(request, queryset):
    """
    Turns the query string into a filtered, ordered queryset.

    Everything goes through the form first, so a value that is not one of the
    allowed choices simply does not filter anything, and no raw input ever
    reaches the ORM as a field name.
    """
    # bound even when the query string is empty, so the ordering below is
    # applied on every page
    form = PropertyFilterForm(request.GET)
    if not form.is_valid():
        return queryset.with_cards().order_by('-is_featured', '-created_at'), form

    return _order(_apply_cleaned(queryset, form.cleaned_data), form.cleaned_data), form


def _apply_cleaned(queryset, d):
    """The filtering half, split out so a saved search can re-run it."""

    if d.get('q'):
        term = d['q']
        queryset = queryset.filter(
            Q(Property_Name__icontains=term)
            | Q(Property_Description__icontains=term)
            | Q(Area__icontains=term)
            | Q(City__icontains=term)
            | Q(landmark__icontains=term)
            | Q(Block__icontains=term)
        )

    for key, field in (
        ('property_type', 'Property_type'),
        ('property_on', 'Property_on'),
        ('area', 'Area'),
        ('city', 'City'),
        ('furnishing', 'furnishing'),
    ):
        if d.get(key):
            queryset = queryset.filter(**{field: d[key]})

    if d.get('min_price'):
        queryset = queryset.filter(Price__gte=d['min_price'])
    if d.get('max_price'):
        queryset = queryset.filter(Price__lte=d['max_price'])
    if d.get('min_area'):
        queryset = queryset.filter(Total_area_in_sqft__gte=d['min_area'])

    if d.get('bedrooms'):
        queryset = queryset.filter(residentialproperty__Bedrooms__gte=d['bedrooms'])
    if d.get('bathrooms'):
        queryset = queryset.filter(residentialproperty__Bathrooms__gte=d['bathrooms'])

    if d.get('business_type'):
        queryset = queryset.filter(commercialproperty__Business_type=d['business_type'])
    if d.get('has_conference'):
        queryset = queryset.filter(commercialproperty__Has_conference_room=True)
    if d.get('has_security'):
        queryset = queryset.filter(commercialproperty__Has_security_system=True)

    if d.get('land_type'):
        queryset = queryset.filter(landproperty__Land_type=d['land_type'])

    for amenity in d.get('amenities') or []:
        # AND, not OR: every ticked amenity must be present
        queryset = queryset.filter(amenities=amenity)

    return queryset.distinct()


def _order(queryset, d):
    """The ordering half."""
    queryset = queryset.with_cards()
    ordering = {
        'newest': '-created_at',
        'price_asc': 'Price',
        'price_desc': '-Price',
        'area_desc': '-Total_area_in_sqft',
        'rating': '-avg_rating',
        'popular': '-view_count',
    }.get(d.get('ordering'), '-is_featured')

    if ordering == '-is_featured':
        queryset = queryset.order_by('-is_featured', '-created_at')
    else:
        queryset = queryset.order_by(ordering, '-created_at')

    return queryset


def paginate(request, queryset, per_page=None):
    per_page = per_page or settings.PROPERTIES_PER_PAGE
    paginator = Paginator(queryset, per_page)
    try:
        return paginator.page(request.GET.get('page'))
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def query_without_page(request):
    params = request.GET.copy()
    params.pop('page', None)
    encoded = params.urlencode()
    return f'&{encoded}' if encoded else ''


def annotate_saved(page, profile):
    """Marks which of the listings on this page the viewer has already saved."""
    if profile is None:
        return page
    saved = set(
        Favourite.objects.filter(profile=profile,
                                 property__in=[p.pk for p in page])
        .values_list('property_id', flat=True)
    )
    for item in page:
        item.is_saved = item.pk in saved
    return page


# browsing

def property_list(request):
    profile = profile_of(request)
    base = AllProperty.objects.live().select_related('user')
    results, form = apply_filters(request, base)

    total = results.count()

    # Remember what they searched for, but only the first page of a real
    # search: paging through the same results should not re-record it, and an
    # empty box is not a search.
    term = (request.GET.get('q') or '').strip()
    if term and profile and request.GET.get('page') in (None, '', '1'):
        # query_without_page() is built for appending to a URL, so it starts
        # with '&'; a saved search needs it as a bare query string.
        RecentSearch.remember(
            profile, term, query_without_page(request).lstrip('&'), total)

    page = paginate(request, results)
    annotate_saved(page, profile)

    return render(request, 'property_list.html', {
        'filtered_properties': page,
        'filter_form': form,
        'total': total,
        'querystring': query_without_page(request),
        'view_mode': 'list' if request.GET.get('view') == 'list' else 'grid',
        'compare_ids': request.session.get('compare', []),
        'active': 'browse',
    })


def property_type(request):
    live = AllProperty.objects.live()
    groups = []
    for key, label in AllProperty.PROPERTY_TYPES:
        groups.append({
            'key': key,
            'label': label,
            'count': live.filter(Property_type=key).count(),
            'rent': live.filter(Property_type=key, Property_on='rent').count(),
            'sale': live.filter(Property_type=key, Property_on='sale').count(),
        })
    areas = (live.values('Area').annotate(n=Count('id')).order_by('-n'))
    return render(request, 'property_type.html', {
        'groups': groups, 'areas': areas, 'active': 'types',
    })


def property_detail(request, pk, slug=None):
    listing = get_object_or_404(
        AllProperty.objects.select_related('user').prefetch_related('images', 'amenities'),
        pk=pk,
    )
    profile = profile_of(request)

    if not listing.can_be_seen_by(profile):
        raise Http404('That listing is not available.')

    if not request.session.session_key:
        request.session.save()
    listing.register_view(profile, request.session.session_key or '')
    listing.refresh_from_db(fields=['view_count'])

    specific = listing.specific
    reviews = listing.reviews.select_related('author')
    my_review = reviews.filter(author=profile).first() if profile else None

    similar = list(AllProperty.objects.live()
                   .filter(Area=listing.Area, Property_type=listing.Property_type)
                   .exclude(pk=listing.pk).with_cards()[:3])
    if not similar:
        similar = list(AllProperty.objects.live()
                       .filter(Property_type=listing.Property_type)
                       .exclude(pk=listing.pk).with_cards()[:3])
    annotate_saved(similar, profile)

    can_review = bool(profile and profile != listing.user and not my_review)

    # every photo, in gallery order, for the tiles and the lightbox
    photos = [i.image.url for i in listing.images.all() if i.image]
    if not photos and listing.Property_Pictures:
        photos = [listing.Property_Pictures.url]

    return render(request, 'property_detail.html', {
        'listing': listing,
        'photos': photos,
        'photos_json': json.dumps(photos),
        'facts': _detail_facts(listing, specific),
        'reviews': reviews[:10],
        'my_review': my_review,
        'can_review': can_review,
        'review_form': PropertyReviewForm(instance=my_review),
        'booking_form': BookingForm(property=listing, renter=profile),
        'message_form': MessageForm(),
        'is_saved': bool(profile and Favourite.objects.filter(
            profile=profile, property=listing).exists()),
        'is_owner': profile == listing.user,
        'can_see_documents': listing.can_documents_be_seen_by(profile),
        'in_compare': listing.pk in request.session.get('compare', []),
        'report_reasons': PropertyReport.Reason.choices,
        'my_open_report': bool(profile and PropertyReport.objects.filter(
            property=listing, reporter=profile,
            status=PropertyReport.Status.OPEN).exists()),
        'similar': similar,
        'booked_slots': list(
            listing.bookings.filter(status=Booking.Status.ACCEPTED,
                                    visit_date__gte=timezone.localdate())
            .values_list('visit_date', 'visit_time')
        ),
        'active': 'browse',
    })


def _detail_facts(listing, specific):
    """A tidy list of label and value pairs for whichever type this is."""
    facts = [
        ('Listed for', listing.get_Property_on_display()),
        ('Type', listing.get_Property_type_display()),
        ('Area', f'{listing.Area}, {listing.City}'),
    ]
    if listing.Total_area_in_sqft:
        facts.append(('Size', f'{int(listing.Total_area_in_sqft):,} sq ft'))
    if listing.price_per_sqft:
        facts.append(('Price per sq ft', f'{settings.CURRENCY_SIGN} {listing.price_per_sqft:,.2f}'))
    if listing.Property_type != 'land':
        facts.append(('Furnishing', listing.get_furnishing_display()))
    if listing.available_from:
        facts.append(('Available from', listing.available_from.strftime('%d %b %Y')))

    from .models import CommercialProperty, LandProperty, ResidentialProperty
    if isinstance(specific, ResidentialProperty):
        facts += [
            ('Bedrooms', specific.Bedrooms),
            ('Bathrooms', specific.Bathrooms),
            ('Balconies', specific.Number_of_Balcony),
            ('Floor', f'{specific.floor_number} of {specific.Floor_count}'),
            ('Garage spaces', specific.Garage_spaces_Per_Sqft),
            ('Lift', 'Yes' if specific.has_lift else 'No'),
            ('Pool', 'Yes' if specific.Has_Pool else 'No'),
            ('Garden', 'Yes' if specific.Has_Garden else 'No'),
        ]
        if specific.Year:
            facts.append(('Built', specific.Year.strftime('%Y')))
    elif isinstance(specific, CommercialProperty):
        facts += [
            ('Use', specific.get_Business_type_display()),
            ('Parking spaces', specific.Parking_spaces),
            ('Lift', 'Yes' if specific.Has_elevator else 'No'),
            ('Security', 'Yes' if specific.Has_security_system else 'No'),
            ('Conference room', 'Yes' if specific.Has_conference_room else 'No'),
            ('Generator', 'Yes' if specific.has_generator else 'No'),
        ]
        if specific.Year:
            facts.append(('Built', specific.Year.strftime('%Y')))
    elif isinstance(specific, LandProperty):
        facts += [
            ('Land type', specific.get_Land_type_display()),
            ('Road width', f'{specific.Road_size_in_sqft} ft'),
            ('Fenced', 'Yes' if specific.Is_fenced else 'No'),
            ('Water line', 'Yes' if specific.has_water_connection else 'No'),
            ('Gas line', 'Yes' if specific.has_gas_connection else 'No'),
        ]
    return facts


# listing

@login_required_message
def add_property(request):
    if request.method == 'POST':
        form = PropertyTypeForm(request.POST)
        if form.is_valid():
            return redirect('add_property_data',
                            property_type=form.cleaned_data['Type'])
        messages.error(request, 'Pick one of the three types.')
    else:
        form = PropertyTypeForm()

    return render(request, 'add_property.html', {
        'form': form,
        'my_count': profile_of(request).properties.count(),
        'active': 'add',
    })


@login_required_message
def add_property_data(request, property_type):
    form_class = FORM_FOR_TYPE.get(property_type)
    if form_class is None:
        messages.error(request, 'Unknown property type.')
        return redirect('add_property')

    me = profile_of(request)

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES)
        image_form = PropertyImageForm(request.POST, request.FILES)
        if form.is_valid() and image_form.is_valid():
            with transaction.atomic():
                listing = form.save(commit=False)
                listing.user = me
                listing.Property_type = property_type
                listing.status = AllProperty.Status.PENDING
                listing.needs_approval = True
                listing.save()
                form.save_m2m()
                _save_gallery(listing, image_form.cleaned_data.get('images') or [])

            _notify_agents(
                'A listing is waiting for approval',
                f'{listing.Property_Name} in {listing.Area}',
                reverse('agent_dashboard'),
            )
            messages.success(
                request,
                'Listing submitted. An agent will review it, usually within a day.'
            )
            return redirect('property_detail', pk=listing.pk)
        messages.error(request, 'Please fix the highlighted fields.')
    else:
        form = form_class()
        image_form = PropertyImageForm()

    return render(request, 'add_property_data.html', {
        'form': form,
        'image_form': image_form,
        'property_type': property_type,
        'type_label': dict(AllProperty.PROPERTY_TYPES)[property_type],
        'active': 'add',
    })


def _save_gallery(listing, files):
    existing = listing.images.count()
    room = max(0, settings.MAX_IMAGES_PER_PROPERTY - existing)
    for i, f in enumerate(files[:room]):
        PropertyImage.objects.create(property=listing, image=f, position=existing + i)


def _notify_agents(title, body, link):
    from authentication.models import UserProfile
    for agent in UserProfile.objects.filter(is_agent=True):
        Notification.push(agent, title, body, link, Notification.Kind.APPROVAL)


@login_required_message
def update_property(request, property_id):
    listing = get_object_or_404(AllProperty, pk=property_id)
    me = profile_of(request)

    if not listing.can_be_edited_by(me):
        messages.error(request, 'That listing is not yours to edit.')
        raise Http404('Not yours.')

    form_class = FORM_FOR_TYPE.get(listing.Property_type)
    specific = listing.specific
    if form_class is None or specific is None:
        messages.error(request, 'That listing cannot be edited.')
        return redirect('property_detail', pk=listing.pk)

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=specific)
        image_form = PropertyImageForm(request.POST, request.FILES)
        if form.is_valid() and image_form.is_valid():
            with transaction.atomic():
                updated = form.save(commit=False)
                # an edit sends it back to the queue, unless an agent made it
                if not me.is_agent:
                    updated.status = AllProperty.Status.PENDING
                    updated.needs_approval = True
                    updated.Approval_by_Agent = None
                updated.save()
                form.save_m2m()
                _save_gallery(updated, image_form.cleaned_data.get('images') or [])

            if not me.is_agent:
                _notify_agents(
                    'An edited listing is waiting again',
                    f'{updated.Property_Name} in {updated.Area}',
                    reverse('agent_dashboard'),
                )
            messages.success(
                request,
                'Listing updated.' + ('' if me.is_agent else ' It goes back for approval.')
            )
            return redirect('property_detail', pk=listing.pk)
        messages.error(request, 'Please fix the highlighted fields.')
    else:
        form = form_class(instance=specific)
        image_form = PropertyImageForm()

    return render(request, 'update_property.html', {
        'form': form,
        'image_form': image_form,
        'listing': listing,
        'active': 'mylistings',
    })


@login_required_message
@post_required
def delete_property(request, property_id):
    listing = get_object_or_404(AllProperty, pk=property_id)
    me = profile_of(request)
    if not listing.can_be_edited_by(me):
        messages.error(request, 'That listing is not yours to delete.')
        raise Http404('Not yours.')

    name = listing.Property_Name
    listing.delete()
    messages.success(request, f'"{name}" has been deleted.')
    return redirect('posted_properties')


@login_required_message
def posted_properties(request):
    me = profile_of(request)
    base = AllProperty.objects.owned_by(me)

    status = request.GET.get('status', '')
    if status in dict(AllProperty.Status.choices):
        base = base.filter(status=status)

    results, form = apply_filters(request, base)
    page = paginate(request, results)

    counts = {
        'all': AllProperty.objects.owned_by(me).count(),
        'approved': AllProperty.objects.owned_by(me).filter(status='approved').count(),
        'pending': AllProperty.objects.owned_by(me).filter(status='pending').count(),
        'rejected': AllProperty.objects.owned_by(me).filter(status='rejected').count(),
        'rented': AllProperty.objects.owned_by(me).filter(status='rented').count(),
    }

    from django.db.models import Sum
    return render(request, 'posted_properties.html', {
        'filtered_properties': page,
        'filter_form': form,
        'counts': counts,
        'status': status,
        'querystring': query_without_page(request),
        'total_views': (AllProperty.objects.owned_by(me)
                        .aggregate(v=Sum('view_count'))['v'] or 0),
        'compare_ids': request.session.get('compare', []),
        'active': 'mylistings',
    })


@login_required_message
@post_required
def change_status(request, property_id):
    listing = get_object_or_404(AllProperty, pk=property_id)
    me = profile_of(request)
    if not listing.can_be_edited_by(me):
        raise Http404('Not yours.')

    action = request.POST.get('action')
    if action in ('rented', 'archive') and listing.status not in (
            AllProperty.Status.APPROVED, AllProperty.Status.RENTED):
        messages.error(request, 'Only a live listing can be hidden or marked taken.')
        return redirect('posted_properties')

    if action == 'archive':
        listing.is_archived = True
        listing.save(update_fields=['is_archived'])
        messages.success(request, 'Listing hidden from search.')
    elif action == 'unarchive':
        listing.is_archived = False
        listing.save(update_fields=['is_archived'])
        messages.success(request, 'Listing is visible again.')
    elif action == 'rented':
        listing.status = AllProperty.Status.RENTED
        listing.save()
        messages.success(request, 'Marked as rented or sold. Well done.')
    elif action == 'relist':
        listing.status = AllProperty.Status.PENDING
        listing.is_archived = False
        listing.save()
        messages.success(request, 'Sent back to the approval queue.')
    return redirect('posted_properties')


# images

@login_required_message
def manage_images(request, property_id):
    listing = get_object_or_404(AllProperty, pk=property_id)
    me = profile_of(request)
    if not listing.can_be_edited_by(me):
        raise Http404('Not yours.')

    if request.method == 'POST':
        form = PropertyImageForm(request.POST, request.FILES)
        if form.is_valid():
            files = form.cleaned_data.get('images') or []
            room = settings.MAX_IMAGES_PER_PROPERTY - listing.images.count()
            if room <= 0:
                messages.error(
                    request,
                    f'A listing can hold {settings.MAX_IMAGES_PER_PROPERTY} photos.'
                )
            else:
                _save_gallery(listing, files)
                messages.success(request, f'{min(len(files), room)} photo(s) added.')
            return redirect('manage_images', property_id=listing.pk)
        messages.error(request, 'Those files could not be used.')
    else:
        form = PropertyImageForm()

    return render(request, 'manage_images.html', {
        'listing': listing,
        'form': form,
        'images': listing.images.all(),
        'room': settings.MAX_IMAGES_PER_PROPERTY - listing.images.count(),
        'active': 'mylistings',
    })


@login_required_message
@post_required
def delete_image(request, image_id):
    image = get_object_or_404(PropertyImage.objects.select_related('property'), pk=image_id)
    if not image.property.can_be_edited_by(profile_of(request)):
        raise Http404('Not yours.')
    listing_id = image.property_id
    image.delete()
    messages.success(request, 'Photo removed.')
    return redirect('manage_images', property_id=listing_id)


@login_required_message
@post_required
def make_cover(request, image_id):
    image = get_object_or_404(PropertyImage.objects.select_related('property'), pk=image_id)
    listing = image.property
    if not listing.can_be_edited_by(profile_of(request)):
        raise Http404('Not yours.')
    with transaction.atomic():
        PropertyImage.objects.filter(property=listing).update(position=F('position') + 1)
        image.position = 0
        image.save(update_fields=['position'])
    messages.success(request, 'Cover photo changed.')
    return redirect('manage_images', property_id=listing.pk)


# documents

@login_required_message
@xframe_options_sameorigin   # the papers page previews it in an iframe
def property_document_file(request, property_id):
    """
    Sends the file itself, after checking who is asking.

    It lives outside MEDIA_ROOT (see property/storage.py), so this view is the
    only way to reach it.
    """
    listing = get_object_or_404(AllProperty, pk=property_id)
    if not listing.can_documents_be_seen_by(profile_of(request)):
        raise Http404('Private.')
    if not listing.Property_Documents:
        raise Http404('No document.')

    try:
        handle = listing.Property_Documents.open('rb')
    except (FileNotFoundError, ValueError):
        raise Http404('The file is missing.')

    name = listing.Property_Documents.name.rsplit('/', 1)[-1]
    kind = mimetypes.guess_type(name)[0] or 'application/octet-stream'
    response = FileResponse(handle, content_type=kind)
    response['Content-Disposition'] = f'inline; filename="{name}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required_message
def view_property_documents(request, property_id):
    """The papers page. Only the owner and an agent can open it."""
    listing = get_object_or_404(AllProperty, pk=property_id)
    me = profile_of(request)

    if not listing.can_documents_be_seen_by(me):
        messages.error(request, 'Those documents are private.')
        raise Http404('Private.')

    document = listing.Property_Documents
    return render(request, 'view_property_documents.html', {
        'listing': listing,
        'property_documents': document,
        'document_url': (reverse('property_document_file', args=[listing.pk])
                         if document else ''),
        'document_name': document.name.rsplit('/', 1)[-1] if document else '',
        'is_pdf': bool(document) and document.name.lower().endswith('.pdf'),
        'agent_actions': listing.agent_actions.select_related('agent')[:10],
        'active': 'mylistings',
    })


# favourites

@login_required_message
def favourites(request):
    me = profile_of(request)
    rows = list(Favourite.objects.filter(profile=me)
                .select_related('property', 'property__user',
                                'property__residentialproperty',
                                'property__commercialproperty',
                                'property__landproperty')
                .prefetch_related('property__images'))
    for row in rows:
        row.property.is_saved = True      # by definition, it is on this page
    return render(request, 'favourites.html', {
        'favourites': rows,
        'compare_ids': request.session.get('compare', []),
        'active': 'favourites',
    })


@login_required_message
@post_required
def toggle_favourite(request, property_id):
    listing = get_object_or_404(AllProperty, pk=property_id)
    me = profile_of(request)

    existing = Favourite.objects.filter(profile=me, property=listing).first()
    if existing:
        existing.delete()
        saved = False
    else:
        Favourite.objects.get_or_create(profile=me, property=listing)
        saved = True
        if listing.user and listing.user != me:
            Notification.push(
                listing.user, 'Someone saved your listing',
                f'{me.name} saved "{listing.Property_Name}".',
                listing.get_absolute_url(), Notification.Kind.ALERT,
            )

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'saved': saved,
            'count': listing.favourited_by.count(),
        })
    messages.success(request, 'Saved.' if saved else 'Removed from saved.')
    return safe_back(request, listing.get_absolute_url())


# compare

@post_required
def toggle_compare(request, property_id):
    listing = get_object_or_404(AllProperty, pk=property_id)
    # A listing waiting for approval is not public, and the comparison page
    # rendered its price, size and amenities to anyone who asked.
    if not listing.can_be_seen_by(profile_of(request)):
        raise Http404('Not available.')
    ids = request.session.get('compare', [])
    added = False
    if listing.pk in ids:
        ids.remove(listing.pk)
        note = 'Removed from the comparison.'
    elif len(ids) >= settings.MAX_COMPARE:
        note = f'You can compare up to {settings.MAX_COMPARE} at once.'
    else:
        ids.append(listing.pk)
        added = True
        note = 'Added to the comparison.'
    request.session['compare'] = ids

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'added': added, 'count': len(ids), 'message': note})

    if added:
        messages.success(request, note)
    else:
        messages.info(request, note)
    return safe_back(request, listing.get_absolute_url())


def compare(request):
    ids = request.session.get('compare', [])
    profile = profile_of(request)
    listings = [
        p for p in AllProperty.objects.filter(pk__in=ids).with_cards()
        if p.can_be_seen_by(profile)
    ]
    listings.sort(key=lambda p: ids.index(p.pk))
    # drop anything that has since been unpublished, so the bar stays honest
    if len(listings) != len(ids):
        request.session['compare'] = [p.pk for p in listings]

    rows = []
    if listings:
        keys = [
            ('Price', lambda p: f'{settings.CURRENCY_SIGN} {money(p.Price)}'),
            ('Listed for', lambda p: p.get_Property_on_display()),
            ('Type', lambda p: p.get_Property_type_display()),
            ('Area', lambda p: f'{p.Area}, {p.City}'),
            ('Size', lambda p: f'{int(p.Total_area_in_sqft):,} sq ft' if p.Total_area_in_sqft else '-'),
            ('Price per sq ft', lambda p: (f'{settings.CURRENCY_SIGN} {p.price_per_sqft:,.2f}'
                                           if p.price_per_sqft else '-')),
            ('Service charge', lambda p: f'{settings.CURRENCY_SIGN} {money(p.service_charge)}'),
            ('Furnishing', lambda p: p.get_furnishing_display()),
            ('Bedrooms', lambda p: getattr(p.specific, 'Bedrooms', '-')),
            ('Bathrooms', lambda p: getattr(p.specific, 'Bathrooms', '-')),
            ('Rating', lambda p: f'{p.rating} / 5' if p.rating else 'Not rated'),
            ('Views', lambda p: p.view_count),
            ('Amenities', lambda p: p.amenities.count()),
        ]
        for label, fn in keys:
            rows.append({'label': label, 'values': [fn(p) for p in listings]})

    return render(request, 'compare.html', {
        'listings': listings, 'rows': rows, 'active': 'browse',
    })


@post_required
def clear_compare(request):
    request.session['compare'] = []
    messages.info(request, 'Comparison cleared.')
    return safe_back(request, reverse('property_list'))


# reviews

@login_required_message
@post_required
def write_review(request, property_id):
    listing = get_object_or_404(AllProperty, pk=property_id)
    me = profile_of(request)

    if me == listing.user:
        messages.error(request, 'You cannot review your own listing.')
        return redirect('property_detail', pk=listing.pk)

    existing = PropertyReview.objects.filter(property=listing, author=me).first()
    form = PropertyReviewForm(request.POST, instance=existing)
    if form.is_valid():
        review = form.save(commit=False)
        review.property = listing
        review.author = me
        review.save()
        if listing.user:
            Notification.push(
                listing.user, 'New review on your listing',
                f'{me.name} gave "{listing.Property_Name}" {review.rating} out of 5.',
                listing.get_absolute_url(), Notification.Kind.REVIEW,
            )
        messages.success(request, 'Review updated.' if existing else 'Thanks for the review.')
    else:
        messages.error(request, form.errors.as_text().replace('*', '').strip()[:200]
                       or 'Please check the review and try again.')
    return redirect('property_detail', pk=listing.pk)


@login_required_message
@post_required
def delete_review(request, review_id):
    review = get_object_or_404(PropertyReview.objects.select_related('property'), pk=review_id)
    me = profile_of(request)
    if review.author != me and not me.is_agent:
        raise Http404('Not yours.')
    listing_id = review.property_id
    review.delete()
    messages.success(request, 'Review removed.')
    return redirect('property_detail', pk=listing_id)


# bookings

@login_required_message
def book_property(request, property_id):
    listing = get_object_or_404(AllProperty.objects.select_related('user'), pk=property_id)
    me = profile_of(request)

    if listing.user == me:
        messages.error(request, 'You do not need to book a visit to your own property.')
        return redirect('property_detail', pk=listing.pk)
    if not listing.is_live:
        messages.error(request, 'That listing is not taking visits right now.')
        return redirect('property_detail', pk=listing.pk)

    if request.method != 'POST':
        return redirect('property_detail', pk=listing.pk)

    form = BookingForm(request.POST, property=listing, renter=me)
    if form.is_valid():
        booking = form.save(commit=False)
        booking.property = listing
        booking.renter = me
        booking.owner = listing.user
        try:
            booking.save()
        except IntegrityError:
            messages.error(request, 'That slot has just been taken. Please pick another.')
            return redirect('property_detail', pk=listing.pk)

        Notification.push(
            listing.user, 'New viewing request',
            f'{me.name} asked to see "{listing.Property_Name}" on '
            f'{booking.visit_date:%d %b} at {booking.visit_time:%H:%M}.',
            reverse('bookings'), Notification.Kind.BOOKING,
        )
        messages.success(
            request,
            f'Request sent. Reference {booking.reference}. '
            'The owner will confirm or suggest another time.'
        )
        return redirect('bookings')

    for error in form.non_field_errors():
        messages.error(request, error)
    for field, errors in form.errors.items():
        if field != '__all__':
            for error in errors:
                messages.error(request, f'{field.replace("_", " ").title()}: {error}')
    return redirect('property_detail', pk=listing.pk)


@login_required_message
def bookings(request):
    me = profile_of(request)

    # An accepted visit whose date has passed is finished, whether or not
    # anyone remembered to press the button. Leaving them "accepted" for ever
    # made the list unreadable after a few weeks.
    Booking.objects.filter(
        Q(owner=me) | Q(renter=me),
        status=Booking.Status.ACCEPTED,
        visit_date__lt=timezone.localdate(),
    ).update(status=Booking.Status.COMPLETED)

    tab = request.GET.get('tab', 'incoming' if me.properties.exists() else 'mine')

    incoming = (me.bookings_received
                .select_related('property', 'renter')
                .order_by('-created_at'))
    mine = (me.bookings_made
            .select_related('property', 'owner')
            .order_by('-created_at'))

    return render(request, 'bookings.html', {
        'incoming': incoming,
        'mine': mine,
        'tab': tab,
        'pending_count': incoming.filter(status=Booking.Status.PENDING).count(),
        'active': 'bookings',
    })


@login_required_message
@post_required
def booking_action(request, booking_id, action):
    booking = get_object_or_404(
        Booking.objects.select_related('property', 'renter', 'owner'), pk=booking_id
    )
    me = profile_of(request)
    response = (request.POST.get('owner_response') or '').strip()[:300]

    is_owner = me == booking.owner
    is_renter = me == booking.renter
    if not (is_owner or is_renter):
        raise Http404('Not yours.')

    # Checking who is asking is not enough: without this, a declined or
    # cancelled visit could be brought back to life by POSTing to the accept
    # endpoint directly, and the renter would be told it was confirmed.
    allowed_from = {
        'accept':   {Booking.Status.PENDING},
        'decline':  {Booking.Status.PENDING},
        'complete': {Booking.Status.ACCEPTED},
        'cancel':   {Booking.Status.PENDING, Booking.Status.ACCEPTED},
    }
    if booking.status not in allowed_from.get(action, set()):
        messages.error(
            request,
            f'That visit is already {booking.get_status_display().lower()}.'
        )
        return redirect('bookings')

    if action == 'accept' and is_owner:
        clash = Booking.objects.filter(
            property=booking.property, visit_date=booking.visit_date,
            visit_time=booking.visit_time, status=Booking.Status.ACCEPTED,
        ).exclude(pk=booking.pk).exists()
        if clash:
            messages.error(request, 'You have already accepted a visit at that time.')
            return redirect('bookings')
        booking.status = Booking.Status.ACCEPTED
        booking.owner_response = response
        booking.save()
        Notification.push(
            booking.renter, 'Visit confirmed',
            f'{booking.owner.name} confirmed your visit to '
            f'"{booking.property.Property_Name}" on {booking.visit_date:%d %b}.',
            reverse('bookings'), Notification.Kind.BOOKING,
        )
        messages.success(request, 'Visit confirmed.')

    elif action == 'decline' and is_owner:
        booking.status = Booking.Status.DECLINED
        booking.owner_response = response
        booking.save()
        Notification.push(
            booking.renter, 'Visit declined',
            (response or 'The owner cannot make that time.'),
            reverse('bookings'), Notification.Kind.BOOKING,
        )
        messages.success(request, 'Visit declined.')

    elif action == 'complete' and is_owner:
        booking.status = Booking.Status.COMPLETED
        booking.save()
        messages.success(request, 'Marked as done.')

    elif action == 'cancel' and is_renter:
        booking.status = Booking.Status.CANCELLED
        booking.save()
        Notification.push(
            booking.owner, 'Visit cancelled',
            f'{booking.renter.name} cancelled the visit on {booking.visit_date:%d %b}.',
            reverse('bookings'), Notification.Kind.BOOKING,
        )
        messages.success(request, 'Visit cancelled.')

    else:
        messages.error(request, 'That action is not available to you.')

    return redirect('bookings')


# messaging

@login_required_message
def inbox(request):
    me = profile_of(request)
    threads = (Conversation.objects
               .filter(Q(renter=me) | Q(owner=me))
               .select_related('property', 'renter', 'owner')
               .prefetch_related('messages', 'messages__sender'))
    rows = []
    for thread in threads:
        chat = list(thread.messages.all())
        rows.append({
            'thread': thread,
            'other': thread.other_party(me),
            'last': chat[-1] if chat else None,
            'unread': sum(1 for m in chat if not m.is_read and m.sender_id != me.pk),
        })
    return render(request, 'inbox.html', {'rows': rows, 'active': 'inbox'})


@login_required_message
@post_required
def start_conversation(request, property_id):
    listing = get_object_or_404(AllProperty.objects.select_related('user'), pk=property_id)
    me = profile_of(request)

    if listing.user == me:
        messages.error(request, 'That is your own listing.')
        return redirect('property_detail', pk=listing.pk)

    form = MessageForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Type a message first.')
        return redirect('property_detail', pk=listing.pk)

    with transaction.atomic():
        thread, _ = Conversation.objects.get_or_create(
            property=listing, renter=me, defaults={'owner': listing.user}
        )
        Message.objects.create(conversation=thread, sender=me,
                               body=form.cleaned_data['body'])
        thread.last_message_at = timezone.now()
        thread.save(update_fields=['last_message_at'])

    Notification.push(
        listing.user, 'New enquiry',
        f'{me.name} asked about "{listing.Property_Name}".',
        reverse('conversation', args=[thread.pk]), Notification.Kind.MESSAGE,
    )
    messages.success(request, 'Message sent.')
    return redirect('conversation', conversation_id=thread.pk)


@login_required_message
def conversation(request, conversation_id):
    thread = get_object_or_404(
        Conversation.objects.select_related('property', 'renter', 'owner'),
        pk=conversation_id,
    )
    me = profile_of(request)
    if not thread.involves(me):
        raise Http404('Not yours.')

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            Message.objects.create(conversation=thread, sender=me,
                                   body=form.cleaned_data['body'])
            thread.last_message_at = timezone.now()
            thread.save(update_fields=['last_message_at'])
            Notification.push(
                thread.other_party(me), 'New message',
                f'{me.name}: {form.cleaned_data["body"][:80]}',
                reverse('conversation', args=[thread.pk]), Notification.Kind.MESSAGE,
            )
            return redirect('conversation', conversation_id=thread.pk)
        messages.error(request, 'Type a message first.')
    else:
        form = MessageForm()

    thread.messages.filter(is_read=False).exclude(sender=me).update(is_read=True)

    return render(request, 'conversation.html', {
        'thread': thread,
        'other': thread.other_party(me),
        'chat': thread.messages.select_related('sender'),
        'form': form,
        'me': me,
        'active': 'inbox',
    })


# saved searches

def run_saved_search(search):
    """Re-runs one saved search. Returns (total matches, matches since last look)."""
    params = QueryDict(search.query_string)
    form = PropertyFilterForm(params)
    results = AllProperty.objects.live()
    if form.is_valid():
        results = _apply_cleaned(results, form.cleaned_data)
    results = results.distinct()
    fresh = 0
    if search.alert_enabled and search.last_checked:
        fresh = results.filter(created_at__gt=search.last_checked).count()
    return results.count(), fresh, {k: v for k, v in params.items() if v}


def new_saved_search_matches(profile):
    """How many new properties are waiting across every saved search."""
    total = 0
    for search in profile.saved_searches.filter(alert_enabled=True):
        total += run_saved_search(search)[1]
    return total


@login_required_message
def saved_searches(request):
    """
    Each saved search is re-run, so both counts on the page are real: how many
    match now, and how many of those appeared since the last time this page was
    opened. Looking at the page is what marks them as seen.
    """
    me = profile_of(request)
    rows = []
    for search in me.saved_searches.all():
        matches, fresh, params = run_saved_search(search)
        rows.append({
            'search': search, 'matches': matches, 'new': fresh, 'params': params,
        })

    # they have now seen them
    if rows:
        me.saved_searches.all().update(last_checked=timezone.now())

    return render(request, 'saved_searches.html', {
        'rows': rows,
        'new_total': sum(r['new'] for r in rows),
        'active': 'saved',
    })


@login_required_message
@post_required
def save_search(request):
    me = profile_of(request)
    form = SavedSearchForm(request.POST)
    query = (request.POST.get('query_string') or '').lstrip('?')[:400]
    if form.is_valid():
        if me.saved_searches.count() >= 12:
            messages.error(request, 'You can keep up to 12 saved searches.')
        else:
            search = form.save(commit=False)
            search.profile = me
            search.query_string = query
            search.save()
            messages.success(request, 'Search saved. We will keep an eye on it.')
    else:
        messages.error(request, 'Give the search a name first.')
    return safe_back(request, reverse('property_list'))


@login_required_message
@post_required
def delete_saved_search(request, search_id):
    SavedSearch.objects.filter(pk=search_id, profile=profile_of(request)).delete()
    messages.success(request, 'Saved search removed.')
    return redirect('saved_searches')


# search suggestions

SUGGEST_LIMIT = 8


def search_suggest(request):
    """
    What the box under the search field offers.

    With nothing typed it answers with the person's own last few searches;
    once they start typing it answers with places and listings that actually
    exist, so a suggestion never leads to an empty results page. Read only,
    so it needs no CSRF token and no sign in.
    """
    term = ' '.join((request.GET.get('q') or '').split())[:60]
    profile = profile_of(request)
    live = AllProperty.objects.live()
    out = []

    if not term:
        if profile:
            for row in profile.recent_searches.all()[:SUGGEST_LIMIT]:
                out.append({
                    'kind': 'recent',
                    'label': row.term,
                    'note': ('no matches' if row.hits == 0
                             else f'{row.hits} match{"" if row.hits == 1 else "es"}'),
                    'url': f"{reverse('property_list')}?{row.query_string}"
                           if row.query_string else
                           f"{reverse('property_list')}?q={quote_plus(row.term)}",
                })
        return JsonResponse({'term': term, 'groups': [
            {'title': 'Recent searches', 'items': out}] if out else []})

    # areas and cities, ranked by how much there is to see there
    places = (live.filter(Q(Area__icontains=term) | Q(City__icontains=term))
              .values('Area', 'City').annotate(n=Count('id')).order_by('-n')[:4])
    place_items = [{
        'kind': 'area',
        'label': p['Area'],
        'note': f"{p['City']} · {p['n']} listing{'' if p['n'] == 1 else 's'}",
        'url': f"{reverse('property_list')}?area={quote_plus(p['Area'])}",
    } for p in places]

    listings = (live.filter(Q(Property_Name__icontains=term)
                            | Q(landmark__icontains=term))
                .order_by('-is_featured', '-created_at')[:5])
    listing_items = [{
        'kind': 'listing',
        'label': row.Property_Name,
        'note': f'{row.Area}, {row.City} · {settings.CURRENCY_SIGN} {money(row.Price)}',
        'url': row.get_absolute_url(),
    } for row in listings]

    groups = []
    if place_items:
        groups.append({'title': 'Areas', 'items': place_items})
    if listing_items:
        groups.append({'title': 'Listings', 'items': listing_items})
    groups.append({'title': '', 'items': [{
        'kind': 'search',
        'label': f'Search everything for “{term}”',
        'note': '',
        'url': f"{reverse('property_list')}?q={quote_plus(term)}",
    }]})
    return JsonResponse({'term': term, 'groups': groups})


@login_required_message
@post_required
def clear_recent_searches(request):
    RecentSearch.objects.filter(profile=profile_of(request)).delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'cleared': True})
    messages.success(request, 'Recent searches cleared.')
    return safe_back(request, reverse('property_list'))


# reporting a listing

@login_required_message
@post_required
def report_property(request, property_id):
    """Anyone signed in can flag a listing. It lands in the agent queue."""
    listing = get_object_or_404(AllProperty, pk=property_id)
    me = profile_of(request)

    if listing.user == me:
        messages.error(request, 'You cannot report your own listing.')
        return safe_back(request, listing.get_absolute_url())

    reason = request.POST.get('reason')
    if reason not in dict(PropertyReport.Reason.choices):
        messages.error(request, 'Pick a reason for the report.')
        return safe_back(request, listing.get_absolute_url())

    detail = ' '.join((request.POST.get('detail') or '').split())[:500]
    try:
        with transaction.atomic():
            PropertyReport.objects.create(
                property=listing, reporter=me, reason=reason, detail=detail,
            )
    except IntegrityError:
        # the unique constraint, so they have one open already
        messages.info(request, 'You have already reported this listing. '
                               'An agent is looking at it.')
        return safe_back(request, listing.get_absolute_url())

    messages.success(request, 'Thank you. An agent will look at this listing.')
    return safe_back(request, listing.get_absolute_url())


# analytics

@login_required_message
def property_analytics(request, property_id):
    listing = get_object_or_404(AllProperty, pk=property_id)
    me = profile_of(request)
    if not listing.can_be_edited_by(me):
        raise Http404('Not yours.')

    since = timezone.localdate() - timezone.timedelta(days=29)
    rows = (PropertyView.objects.filter(property=listing, viewed_on__gte=since)
            .values('viewed_on').annotate(n=Count('id')))
    by_day = {r['viewed_on']: r['n'] for r in rows}
    chart = []
    for i in range(29, -1, -1):
        day = timezone.localdate() - timezone.timedelta(days=i)
        chart.append({'label': day.strftime('%d/%m'), 'value': by_day.get(day, 0)})
    chart_max = max([c['value'] for c in chart] + [1])

    return render(request, 'property_analytics.html', {
        'listing': listing,
        'chart': chart,
        'chart_max': chart_max,
        'views_30d': sum(c['value'] for c in chart),
        'saves': listing.favourited_by.count(),
        'enquiries': listing.conversations.count(),
        'visits': listing.bookings.count(),
        'accepted_visits': listing.bookings.filter(status=Booking.Status.ACCEPTED).count(),
        'reviews': listing.reviews.count(),
        'recent_savers': listing.favourited_by.select_related('profile')[:8],
        'active': 'mylistings',
    })
