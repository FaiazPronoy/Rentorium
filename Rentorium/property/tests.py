"""Tests for the property app."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authentication.models import UserProfile
from property.models import (
    AllProperty, Amenity, Booking, CommercialProperty, Conversation, Favourite,
    LandProperty, Message, PropertyReport, PropertyReview, RecentSearch,
    ResidentialProperty, SavedSearch,
)

PASSWORD = 'Rentorium@2026'


def make_user(email, name, role=UserProfile.Role.RENTER, agent=False):
    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    profile = user.UserProfile
    profile.name = name
    profile.email = email
    profile.role = UserProfile.Role.AGENT if agent else role
    profile.is_agent = agent
    profile.save()
    return user, profile


def make_listing(owner, **kwargs):
    defaults = dict(
        user=owner,
        Property_Name='A perfectly ordinary three bedroom flat',
        Property_Description='Somewhere to live.',
        Property_type='residential', Property_on='rent',
        Price=30000, Total_area_in_sqft=1200,
        City='Dhaka', Area='Gulshan',
        status=AllProperty.Status.APPROVED, needs_approval=False,
        Bedrooms=3, Bathrooms=2,
    )
    defaults.update(kwargs)
    return ResidentialProperty.objects.create(**defaults)


class ModelTests(TestCase):
    def setUp(self):
        _, self.owner = make_user('owner@test.com', 'Owner One', UserProfile.Role.OWNER)

    def test_a_profile_is_created_with_every_user(self):
        user = User.objects.create_user(username='new@test.com', password=PASSWORD)
        self.assertTrue(hasattr(user, 'UserProfile'))

    def test_slug_is_generated_and_unique(self):
        a = make_listing(self.owner)
        b = make_listing(self.owner)
        self.assertTrue(a.slug)
        self.assertNotEqual(a.slug, b.slug)

    def test_approving_clears_the_needs_approval_flag(self):
        listing = make_listing(self.owner, status=AllProperty.Status.PENDING)
        self.assertTrue(listing.needs_approval)
        listing.status = AllProperty.Status.APPROVED
        listing.save()
        self.assertFalse(listing.needs_approval)
        self.assertIsNotNone(listing.approved_at)

    def test_price_per_square_foot(self):
        listing = make_listing(self.owner, Price=30000, Total_area_in_sqft=1000)
        self.assertEqual(listing.price_per_sqft, 30.0)

    def test_land_road_width_is_a_real_column(self):
        """Road_size_in_sqft is a real column, not a bare field reference."""
        plot = LandProperty.objects.create(
            user=self.owner, Property_Name='A plot with a wide road',
            Property_type='land', Property_on='sale', Price=1000000,
            City='Dhaka', Area='Uttara', Road_size_in_sqft=40,
        )
        self.assertEqual(LandProperty.objects.get(pk=plot.pk).Road_size_in_sqft, 40)

    def test_live_queryset_hides_pending_and_archived(self):
        make_listing(self.owner)
        make_listing(self.owner, status=AllProperty.Status.PENDING)
        make_listing(self.owner, is_archived=True)
        self.assertEqual(AllProperty.objects.live().count(), 1)

    def test_the_subtype_is_reachable_from_the_base_row(self):
        listing = make_listing(self.owner)
        base = AllProperty.objects.get(pk=listing.pk)
        self.assertIsInstance(base.specific, ResidentialProperty)
        self.assertEqual(base.specific.Bedrooms, 3)

    def test_a_person_can_only_review_a_property_once(self):
        _, other = make_user('r@test.com', 'Reviewer')
        listing = make_listing(self.owner)
        PropertyReview.objects.create(property=listing, author=other,
                                      rating=5, comment='Very good indeed.')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PropertyReview.objects.create(property=listing, author=other,
                                              rating=1, comment='Changed my mind.')

    def test_a_property_cannot_be_saved_twice_by_one_person(self):
        _, other = make_user('f@test.com', 'Fan')
        listing = make_listing(self.owner)
        Favourite.objects.create(profile=other, property=listing)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Favourite.objects.create(profile=other, property=listing)

    def test_rating_is_the_average_of_the_reviews(self):
        listing = make_listing(self.owner)
        for i, score in enumerate([5, 4, 3]):
            _, person = make_user(f'p{i}@test.com', f'Person {i}')
            PropertyReview.objects.create(property=listing, author=person,
                                          rating=score, comment='A fine place to live.')
        self.assertEqual(listing.rating, 4.0)
        self.assertEqual(listing.rating_count, 3)


class AccessControlTests(TestCase):
    """Who is allowed to see and change what."""

    def setUp(self):
        self.owner_user, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        self.other_user, self.other = make_user('other@test.com', 'Somebody Else')
        self.agent_user, self.agent = make_user('agent@test.com', 'Agent', agent=True)
        self.listing = make_listing(self.owner, Property_Documents='property_documents/deed.pdf')

    # ---- private documents ------------------------------------------
    def test_a_stranger_cannot_read_the_ownership_papers(self):
        self.client.login(username='other@test.com', password=PASSWORD)
        r = self.client.get(reverse('view_property_documents', args=[self.listing.pk]))
        self.assertEqual(r.status_code, 404)

    def test_the_owner_can_read_their_own_papers(self):
        self.client.login(username='owner@test.com', password=PASSWORD)
        r = self.client.get(reverse('view_property_documents', args=[self.listing.pk]))
        self.assertEqual(r.status_code, 200)

    def test_an_agent_can_read_the_papers(self):
        self.client.login(username='agent@test.com', password=PASSWORD)
        r = self.client.get(reverse('view_property_documents', args=[self.listing.pk]))
        self.assertEqual(r.status_code, 200)

    def test_signed_out_visitors_are_sent_to_sign_in(self):
        r = self.client.get(reverse('view_property_documents', args=[self.listing.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('signin', r.url)

    # ---- editing -----------------------------------------------------
    def test_a_stranger_cannot_open_the_edit_page(self):
        self.client.login(username='other@test.com', password=PASSWORD)
        r = self.client.get(reverse('update_property', args=[self.listing.pk]))
        self.assertEqual(r.status_code, 404)

    def test_the_edit_page_opens_for_a_listing_that_has_a_document(self):
        """The ownership paper has no public URL by design.

        Django's default file widget renders a link to `value.url`, so it
        asked the private storage for one and the page returned a 500. The
        form uses a plain file input for that field now.
        """
        self.listing.Property_Documents.save(
            'deed.pdf', ContentFile(b'%PDF-1.4 test'), save=True)
        self.client.login(username='owner@test.com', password=PASSWORD)
        r = self.client.get(reverse('update_property', args=[self.listing.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIn('On record', r.content.decode())

    def test_a_new_listing_form_does_not_prefill_the_price_with_zero(self):
        """`default=0` on the model showed a 0 the price check then rejected."""
        self.client.login(username='owner@test.com', password=PASSWORD)
        r = self.client.get(reverse('add_property_data', args=['residential']))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context['form'].initial.get('Price'))

    def test_a_stranger_cannot_post_an_edit(self):
        self.client.login(username='other@test.com', password=PASSWORD)
        r = self.client.post(reverse('update_property', args=[self.listing.pk]),
                             {'Property_Name': 'I have taken this over'})
        self.assertEqual(r.status_code, 404)
        self.listing.refresh_from_db()
        self.assertNotEqual(self.listing.Property_Name, 'I have taken this over')

    # ---- deleting ----------------------------------------------------
    def test_a_stranger_cannot_delete_a_listing(self):
        self.client.login(username='other@test.com', password=PASSWORD)
        r = self.client.post(reverse('delete_property', args=[self.listing.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(AllProperty.objects.filter(pk=self.listing.pk).exists())

    def test_the_owner_can_delete_their_own_listing(self):
        self.client.login(username='owner@test.com', password=PASSWORD)
        r = self.client.post(reverse('delete_property', args=[self.listing.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(AllProperty.objects.filter(pk=self.listing.pk).exists())

    def test_deleting_is_refused_on_a_get(self):
        self.client.login(username='owner@test.com', password=PASSWORD)
        self.client.get(reverse('delete_property', args=[self.listing.pk]))
        self.assertTrue(AllProperty.objects.filter(pk=self.listing.pk).exists())

    # ---- unapproved listings ------------------------------------------
    def test_a_pending_listing_is_hidden_from_the_public(self):
        pending = make_listing(self.owner, status=AllProperty.Status.PENDING)
        r = self.client.get(reverse('property_detail', args=[pending.pk]))
        self.assertEqual(r.status_code, 404)

    def test_the_owner_can_still_see_their_pending_listing(self):
        pending = make_listing(self.owner, status=AllProperty.Status.PENDING)
        self.client.login(username='owner@test.com', password=PASSWORD)
        r = self.client.get(reverse('property_detail', args=[pending.pk]))
        self.assertEqual(r.status_code, 200)

    # ---- messaging ----------------------------------------------------
    def test_a_stranger_cannot_read_someone_elses_conversation(self):
        thread = Conversation.objects.create(
            property=self.listing, renter=self.other, owner=self.owner)
        _, outsider = make_user('nosy@test.com', 'Nosy Person')
        self.client.login(username='nosy@test.com', password=PASSWORD)
        r = self.client.get(reverse('conversation', args=[thread.pk]))
        self.assertEqual(r.status_code, 404)

    # ---- agent only areas ----------------------------------------------
    def test_a_normal_user_cannot_open_the_agent_console(self):
        self.client.login(username='other@test.com', password=PASSWORD)
        r = self.client.get(reverse('agent_dashboard'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('page-not-found', r.url)

    def test_a_normal_user_cannot_approve_a_listing(self):
        pending = make_listing(self.owner, status=AllProperty.Status.PENDING)
        self.client.login(username='other@test.com', password=PASSWORD)
        self.client.post(reverse('approve_property', args=[pending.pk]))
        pending.refresh_from_db()
        self.assertEqual(pending.status, AllProperty.Status.PENDING)


class BookingTests(TestCase):
    def setUp(self):
        self.owner_user, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        self.renter_user, self.renter = make_user('renter@test.com', 'Renter')
        self.other_user, self.other = make_user('other@test.com', 'Another Renter')
        self.listing = make_listing(self.owner)
        self.day = timezone.localdate() + timedelta(days=2)

    def _book(self, client_email, hour=11):
        self.client.login(username=client_email, password=PASSWORD)
        return self.client.post(reverse('book_property', args=[self.listing.pk]), {
            'visit_date': self.day.isoformat(),
            'visit_time': f'{hour}:00',
            'message': 'Would this time suit?',
        })

    def test_a_visit_can_be_requested(self):
        self._book('renter@test.com')
        self.assertEqual(Booking.objects.count(), 1)
        booking = Booking.objects.first()
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertTrue(booking.reference.startswith('RV'))

    def test_an_owner_cannot_book_their_own_property(self):
        self._book('owner@test.com')
        self.assertEqual(Booking.objects.count(), 0)

    def test_a_visit_in_the_past_is_refused(self):
        self.client.login(username='renter@test.com', password=PASSWORD)
        self.client.post(reverse('book_property', args=[self.listing.pk]), {
            'visit_date': (timezone.localdate() - timedelta(days=1)).isoformat(),
            'visit_time': '11:00',
        })
        self.assertEqual(Booking.objects.count(), 0)

    def test_a_visit_outside_working_hours_is_refused(self):
        self._book('renter@test.com', hour=3)
        self.assertEqual(Booking.objects.count(), 0)

    def test_two_people_cannot_hold_the_same_accepted_slot(self):
        self._book('renter@test.com')
        first = Booking.objects.first()
        first.status = Booking.Status.ACCEPTED
        first.save()

        Booking.objects.create(
            property=self.listing, renter=self.other, owner=self.owner,
            visit_date=self.day,
            visit_time=first.visit_time, status=Booking.Status.PENDING,
        )
        second = Booking.objects.exclude(pk=first.pk).first()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                second.status = Booking.Status.ACCEPTED
                second.save()

    def test_the_second_request_for_a_taken_slot_is_refused_by_the_form(self):
        self._book('renter@test.com')
        booking = Booking.objects.first()
        booking.status = Booking.Status.ACCEPTED
        booking.save()
        self.client.logout()
        self._book('other@test.com')
        self.assertEqual(Booking.objects.count(), 1)

    def test_only_the_owner_can_accept(self):
        self._book('renter@test.com')
        booking = Booking.objects.first()
        self.client.logout()
        self.client.login(username='other@test.com', password=PASSWORD)
        self.client.post(reverse('booking_action', args=[booking.pk, 'accept']))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.PENDING)

    def test_the_owner_can_accept(self):
        self._book('renter@test.com')
        booking = Booking.objects.first()
        self.client.logout()
        self.client.login(username='owner@test.com', password=PASSWORD)
        self.client.post(reverse('booking_action', args=[booking.pk, 'accept']))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.ACCEPTED)

    def test_the_renter_can_cancel_their_own_request(self):
        self._book('renter@test.com')
        booking = Booking.objects.first()
        self.client.post(reverse('booking_action', args=[booking.pk, 'cancel']))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)


class SearchTests(TestCase):
    def setUp(self):
        _, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        self.lift = Amenity.objects.create(name='Lift')
        self.pool = Amenity.objects.create(name='Swimming pool')

        self.cheap = make_listing(
            self.owner, Property_Name='Small flat in Mirpur for a small budget',
            Price=15000, Area='Mirpur', Bedrooms=1, Bathrooms=1,
            Total_area_in_sqft=600)
        self.mid = make_listing(
            self.owner, Property_Name='Comfortable flat in Dhanmondi by the lake',
            Price=45000, Area='Dhanmondi', Bedrooms=3, Bathrooms=2,
            Total_area_in_sqft=1400)
        self.mid.amenities.add(self.lift)
        self.posh = make_listing(
            self.owner, Property_Name='Large flat in Gulshan with a pool',
            Price=150000, Area='Gulshan', Bedrooms=4, Bathrooms=4,
            Total_area_in_sqft=2600)
        self.posh.amenities.add(self.lift, self.pool)
        self.shop = CommercialProperty.objects.create(
            user=self.owner, Property_Name='A shop on a busy corner in Banani',
            Property_type='commercial', Property_on='rent', Price=90000,
            City='Dhaka', Area='Banani', status=AllProperty.Status.APPROVED,
            needs_approval=False, Business_type='shop', Has_security_system=True,
        )

    def get(self, **params):
        r = self.client.get(reverse('property_list'), params)
        self.assertEqual(r.status_code, 200)
        return list(r.context['filtered_properties'])

    def test_everything_live_shows_by_default(self):
        self.assertEqual(len(self.get()), 4)

    def test_keyword_search_looks_at_the_title_and_the_area(self):
        self.assertEqual([p.pk for p in self.get(q='Dhanmondi')], [self.mid.pk])

    def test_price_range(self):
        found = self.get(min_price=20000, max_price=100000)
        self.assertCountEqual([p.pk for p in found], [self.mid.pk, self.shop.pk])

    def test_bedrooms_is_at_least_not_exactly(self):
        found = self.get(bedrooms=3)
        self.assertCountEqual([p.pk for p in found], [self.mid.pk, self.posh.pk])

    def test_type_filter(self):
        self.assertEqual([p.pk for p in self.get(property_type='commercial')], [self.shop.pk])

    def test_minimum_area(self):
        self.assertEqual([p.pk for p in self.get(min_area=2000)], [self.posh.pk])

    def test_amenities_are_combined_with_and_not_or(self):
        found = self.get(amenities=[self.lift.pk, self.pool.pk])
        self.assertEqual([p.pk for p in found], [self.posh.pk])

    def test_ordering_by_price(self):
        found = self.get(ordering='price_asc')
        self.assertEqual([p.pk for p in found][0], self.cheap.pk)
        found = self.get(ordering='price_desc')
        self.assertEqual([p.pk for p in found][0], self.posh.pk)

    def test_a_junk_filter_value_does_not_crash_or_filter(self):
        self.assertEqual(len(self.get(property_type='nonsense')), 4)

    def test_a_pending_listing_never_appears_in_search(self):
        make_listing(self.owner, status=AllProperty.Status.PENDING)
        self.assertEqual(len(self.get()), 4)


class FavouriteAndCompareTests(TestCase):
    def setUp(self):
        _, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        self.user, self.profile = make_user('me@test.com', 'Me')
        self.listing = make_listing(self.owner)
        self.client.login(username='me@test.com', password=PASSWORD)

    def test_saving_and_unsaving(self):
        url = reverse('toggle_favourite', args=[self.listing.pk])
        self.client.post(url)
        self.assertEqual(Favourite.objects.count(), 1)
        self.client.post(url)
        self.assertEqual(Favourite.objects.count(), 0)

    def test_saving_returns_json_for_a_background_request(self):
        r = self.client.post(reverse('toggle_favourite', args=[self.listing.pk]),
                             HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.json()['saved'], True)

    def test_compare_holds_at_most_four(self):
        for i in range(6):
            listing = make_listing(self.owner, Property_Name=f'Another decent flat number {i}')
            self.client.post(reverse('toggle_compare', args=[listing.pk]))
        self.assertEqual(len(self.client.session['compare']), 4)

    def test_compare_can_be_cleared(self):
        self.client.post(reverse('toggle_compare', args=[self.listing.pk]))
        self.client.post(reverse('clear_compare'))
        self.assertEqual(self.client.session['compare'], [])

    def test_a_stranger_cannot_compare_a_pending_listing(self):
        hidden = make_listing(self.owner, status=AllProperty.Status.PENDING)
        r = self.client.post(reverse('toggle_compare', args=[hidden.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.client.session.get('compare', []), [])


class ReviewTests(TestCase):
    def setUp(self):
        self.owner_user, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        self.user, self.profile = make_user('me@test.com', 'Me')
        self.listing = make_listing(self.owner)

    def test_a_review_can_be_written_and_then_edited(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        url = reverse('write_review', args=[self.listing.pk])
        self.client.post(url, {'rating': 5, 'title': 'Great',
                               'comment': 'A really good place to live in, no complaints.'})
        self.assertEqual(PropertyReview.objects.count(), 1)
        self.client.post(url, {'rating': 3, 'title': 'On reflection',
                               'comment': 'Second thoughts about the water pressure here.'})
        self.assertEqual(PropertyReview.objects.count(), 1)
        self.assertEqual(PropertyReview.objects.first().rating, 3)

    def test_an_owner_cannot_review_their_own_listing(self):
        self.client.login(username='owner@test.com', password=PASSWORD)
        self.client.post(reverse('write_review', args=[self.listing.pk]),
                         {'rating': 5, 'comment': 'My own place is wonderful, obviously.'})
        self.assertEqual(PropertyReview.objects.count(), 0)

    def test_a_very_short_review_is_refused(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        self.client.post(reverse('write_review', args=[self.listing.pk]),
                         {'rating': 5, 'comment': 'Nice'})
        self.assertEqual(PropertyReview.objects.count(), 0)


class MessagingTests(TestCase):
    def setUp(self):
        self.owner_user, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        self.user, self.profile = make_user('me@test.com', 'Me')
        self.listing = make_listing(self.owner)

    def test_one_thread_per_person_per_property(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        url = reverse('start_conversation', args=[self.listing.pk])
        self.client.post(url, {'body': 'Is this still available?'})
        self.client.post(url, {'body': 'Hello again, any news?'})
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 2)

    def test_reading_a_thread_marks_the_other_sides_messages_as_read(self):
        thread = Conversation.objects.create(
            property=self.listing, renter=self.profile, owner=self.owner)
        Message.objects.create(conversation=thread, sender=self.owner, body='Yes it is.')
        self.client.login(username='me@test.com', password=PASSWORD)
        self.client.get(reverse('conversation', args=[thread.pk]))
        self.assertEqual(thread.messages.filter(is_read=False).count(), 0)

    def test_an_owner_cannot_message_themselves(self):
        self.client.login(username='owner@test.com', password=PASSWORD)
        self.client.post(reverse('start_conversation', args=[self.listing.pk]),
                         {'body': 'Talking to myself.'})
        self.assertEqual(Conversation.objects.count(), 0)


class ViewCountTests(TestCase):
    def setUp(self):
        _, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        self.listing = make_listing(self.owner)

    def test_one_view_is_counted_per_visitor_per_day(self):
        url = reverse('property_detail', args=[self.listing.pk])
        self.client.get(url)
        self.client.get(url)
        self.client.get(url)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.view_count, 1)




class PrivateDocumentTests(TestCase):
    """The papers are private: no URL reaches them, only the document view."""

    def setUp(self):
        _, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        _, self.stranger = make_user('nosy@test.com', 'Nosy Parker')
        _, self.agent = make_user('agent@test.com', 'Agent', agent=True)
        self.listing = make_listing(self.owner)
        self.listing.Property_Documents.save(
            'deed.pdf', ContentFile(b'%PDF-1.4 the ownership deed'), save=True)

    def tearDown(self):
        self.listing.Property_Documents.delete(save=False)

    def test_guessing_the_media_url_gets_nothing(self):
        name = self.listing.Property_Documents.name
        r = self.client.get(f'{settings.MEDIA_URL}{name}')
        self.assertEqual(r.status_code, 404)

    def test_a_stranger_cannot_stream_the_file(self):
        self.client.login(username='nosy@test.com', password=PASSWORD)
        r = self.client.get(reverse('property_document_file', args=[self.listing.pk]))
        self.assertEqual(r.status_code, 404)

    def test_the_owner_can_stream_the_file(self):
        self.client.login(username='owner@test.com', password=PASSWORD)
        r = self.client.get(reverse('property_document_file', args=[self.listing.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b''.join(r.streaming_content), b'%PDF-1.4 the ownership deed')
        self.assertEqual(r['X-Content-Type-Options'], 'nosniff')

class PaginationTests(TestCase):
    """Paging through a search must not repeat or lose a listing."""

    def setUp(self):
        _, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        for i in range(15):
            make_listing(self.owner, Property_Name=f'Flat number {i:02d}',
                         Price=10000 + i * 1000)

    def _pks(self, **params):
        r = self.client.get(reverse('property_list'), params)
        self.assertEqual(r.status_code, 200)
        return [p.pk for p in r.context['filtered_properties']]

    def test_page_one_and_page_two_never_overlap(self):
        one, two = self._pks(page=1), self._pks(page=2)
        self.assertTrue(one and two)
        self.assertEqual(set(one) & set(two), set())

class BookingLifecycleTests(TestCase):
    """A visit can only move on from the status it is actually in."""

    def setUp(self):
        _, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        _, self.renter = make_user('renter@test.com', 'Renter')
        self.listing = make_listing(self.owner)
        self.booking = Booking.objects.create(
            property=self.listing, renter=self.renter, owner=self.owner,
            visit_date=(timezone.localdate() + timedelta(days=3)),
            visit_time='11:00', status=Booking.Status.PENDING,
        )

    def _act(self, action, who='owner@test.com'):
        self.client.login(username=who, password=PASSWORD)
        return self.client.post(
            reverse('booking_action', args=[self.booking.pk, action]))

    def _set(self, status):
        self.booking.status = status
        self.booking.save(update_fields=['status'])

    def test_a_cancelled_visit_cannot_be_accepted_back_to_life(self):
        self._set(Booking.Status.CANCELLED)
        self._act('accept')
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CANCELLED)

    def test_a_pending_visit_still_accepts_normally(self):
        self._act('accept')
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.ACCEPTED)

    def test_a_stranger_cannot_touch_the_visit(self):
        make_user('nosy@test.com', 'Nosy')
        r = self._act('accept', who='nosy@test.com')
        self.assertEqual(r.status_code, 404)


class SavedSearchTests(TestCase):
    """Saving a search, listing the saved ones, and deleting them."""

    def setUp(self):
        _, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        self.user, self.me = make_user('me@test.com', 'Me')
        make_listing(self.owner, Area='Gulshan', Price=30000)
        make_listing(self.owner, Area='Banani', Price=90000,
                     Property_Name='A flat in Banani that costs more')
        self.client.login(username='me@test.com', password=PASSWORD)

    def test_a_search_can_be_saved(self):
        r = self.client.post(reverse('save_search'),
                             {'label': 'Cheap in Gulshan', 'query_string': '?q=Gulshan'})
        self.assertEqual(r.status_code, 302)
        row = SavedSearch.objects.get(profile=self.me)
        self.assertEqual(row.label, 'Cheap in Gulshan')
        self.assertEqual(row.query_string, 'q=Gulshan')   # the '?' is stripped

    def test_the_list_page_counts_real_matches_not_zero(self):
        SavedSearch.objects.create(profile=self.me, label='Gulshan',
                                   query_string='q=Gulshan')
        SavedSearch.objects.create(profile=self.me, label='Everything',
                                   query_string='')
        r = self.client.get(reverse('saved_searches'))
        self.assertEqual(r.status_code, 200)
        counts = {row['search'].label: row['matches'] for row in r.context['rows']}
        self.assertEqual(counts['Gulshan'], 1)
        self.assertEqual(counts['Everything'], 2)

    def test_a_saved_search_can_be_deleted(self):
        row = SavedSearch.objects.create(profile=self.me, label='Gulshan',
                                         query_string='q=Gulshan')
        self.client.post(reverse('delete_saved_search', args=[row.pk]))
        self.assertFalse(SavedSearch.objects.filter(pk=row.pk).exists())

    def test_you_cannot_delete_someone_elses_saved_search(self):
        _, other = make_user('other@test.com', 'Other')
        row = SavedSearch.objects.create(profile=other, label='Theirs',
                                         query_string='q=Banani')
        self.client.post(reverse('delete_saved_search', args=[row.pk]))
        self.assertTrue(SavedSearch.objects.filter(pk=row.pk).exists())



class SearchSuggestionTests(TestCase):
    """The box under the search field: live suggestions and recent searches."""

    def setUp(self):
        _, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        _, self.me = make_user('me@test.com', 'Me')
        self.flat = make_listing(
            self.owner, Property_Name='Bright flat near Gulshan 2 circle',
            Area='Gulshan', landmark='Beside the lake')
        make_listing(self.owner, Property_Name='Shop on Dhanmondi road 27',
                     Area='Dhanmondi')
        make_listing(self.owner, Property_Name='A hidden one', Area='Banani',
                     status=AllProperty.Status.PENDING)

    def suggest(self, term=''):
        r = self.client.get(reverse('search_suggest'), {'q': term})
        self.assertEqual(r.status_code, 200)
        return r.json()

    def flat_items(self, data):
        out = []
        for group in data['groups']:
            out += group['items']
        return out

    def test_typing_suggests_an_area_and_a_listing(self):
        items = self.flat_items(self.suggest('gul'))
        kinds = {i['kind'] for i in items}
        self.assertIn('area', kinds)
        self.assertIn('listing', kinds)
        labels = [i['label'] for i in items]
        self.assertIn('Gulshan', labels)
        self.assertIn('Bright flat near Gulshan 2 circle', labels)

    def test_a_listing_that_is_not_live_is_never_suggested(self):
        labels = [i['label'] for i in self.flat_items(self.suggest('hidden'))]
        self.assertNotIn('A hidden one', labels)

    def test_there_is_always_a_plain_search_fallback(self):
        items = self.flat_items(self.suggest('nothing matches this'))
        self.assertEqual([i['kind'] for i in items], ['search'])

    def test_a_signed_out_visitor_gets_no_recent_searches(self):
        self.assertEqual(self.suggest('')['groups'], [])

    def test_searching_records_it_and_it_comes_back_as_a_suggestion(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        self.client.get(reverse('property_list'), {'q': 'Gulshan'})
        row = RecentSearch.objects.get(profile=self.me)
        self.assertEqual(row.term, 'Gulshan')
        self.assertEqual(row.hits, 1)

        items = self.flat_items(self.suggest(''))
        self.assertEqual([i['kind'] for i in items], ['recent'])
        self.assertEqual(items[0]['label'], 'Gulshan')

    def test_an_empty_search_is_not_recorded(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        self.client.get(reverse('property_list'), {'q': '   '})
        self.assertFalse(RecentSearch.objects.exists())

    def test_paging_through_results_does_not_record_the_search_again(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        self.client.get(reverse('property_list'), {'q': 'Gulshan'})
        first = RecentSearch.objects.get(profile=self.me).searched_at
        self.client.get(reverse('property_list'), {'q': 'Gulshan', 'page': '2'})
        self.assertEqual(RecentSearch.objects.get(profile=self.me).searched_at, first)

    def test_the_same_search_twice_makes_one_row(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        self.client.get(reverse('property_list'), {'q': 'Gulshan'})
        self.client.get(reverse('property_list'), {'q': 'Gulshan'})
        self.assertEqual(RecentSearch.objects.filter(profile=self.me).count(), 1)

    def test_only_the_newest_few_are_kept(self):
        for n in range(RecentSearch.KEEP + 4):
            RecentSearch.remember(self.me, f'term {n}')
        self.assertEqual(RecentSearch.objects.filter(profile=self.me).count(),
                         RecentSearch.KEEP)
        newest = RecentSearch.objects.filter(profile=self.me).first()
        self.assertEqual(newest.term, f'term {RecentSearch.KEEP + 3}')

    def test_recent_searches_are_private_to_one_person(self):
        _, other = make_user('other@test.com', 'Other')
        RecentSearch.remember(other, 'their private search')
        self.client.login(username='me@test.com', password=PASSWORD)
        labels = [i['label'] for i in self.flat_items(self.suggest(''))]
        self.assertNotIn('their private search', labels)

    def test_clearing_removes_only_your_own(self):
        _, other = make_user('other@test.com', 'Other')
        RecentSearch.remember(self.me, 'mine')
        RecentSearch.remember(other, 'theirs')
        self.client.login(username='me@test.com', password=PASSWORD)
        self.client.post(reverse('clear_recent_searches'))
        self.assertFalse(RecentSearch.objects.filter(profile=self.me).exists())
        self.assertTrue(RecentSearch.objects.filter(profile=other).exists())


class ReportListingTests(TestCase):
    def setUp(self):
        _, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        _, self.me = make_user('me@test.com', 'Me')
        self.listing = make_listing(self.owner)

    def report(self, **data):
        payload = {'reason': PropertyReport.Reason.FAKE, 'detail': 'It is not real.'}
        payload.update(data)
        return self.client.post(
            reverse('report_property', args=[self.listing.pk]), payload)

    def test_a_signed_out_visitor_is_sent_to_sign_in(self):
        self.report()
        self.assertFalse(PropertyReport.objects.exists())

    def test_a_signed_in_person_can_report(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        self.report()
        row = PropertyReport.objects.get()
        self.assertEqual(row.property_id, self.listing.pk)
        self.assertEqual(row.reporter, self.me)
        self.assertEqual(row.status, PropertyReport.Status.OPEN)

    def test_an_owner_cannot_report_their_own_listing(self):
        self.client.login(username='owner@test.com', password=PASSWORD)
        self.report()
        self.assertFalse(PropertyReport.objects.exists())

    def test_a_made_up_reason_is_refused(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        self.report(reason='because-i-say-so')
        self.assertFalse(PropertyReport.objects.exists())

    def test_the_same_person_cannot_pile_on(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        self.report()
        self.report(reason=PropertyReport.Reason.TAKEN)
        self.assertEqual(PropertyReport.objects.count(), 1)

    def test_a_second_person_can_still_report_the_same_listing(self):
        _, other = make_user('other@test.com', 'Other')
        self.client.login(username='me@test.com', password=PASSWORD)
        self.report()
        self.client.login(username='other@test.com', password=PASSWORD)
        self.report()
        self.assertEqual(PropertyReport.objects.count(), 2)

    def test_reporting_again_is_allowed_once_the_first_is_settled(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        self.report()
        PropertyReport.objects.update(status=PropertyReport.Status.DISMISSED)
        self.report(reason=PropertyReport.Reason.TAKEN)
        self.assertEqual(PropertyReport.objects.count(), 2)

    def test_the_detail_page_shows_the_report_link_and_the_reasons(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        r = self.client.get(self.listing.get_absolute_url())
        self.assertContains(r, 'Something wrong with this listing?')
        self.assertContains(r, 'reportModal')

    def test_the_owner_sees_no_report_link_on_their_own_listing(self):
        self.client.login(username='owner@test.com', password=PASSWORD)
        r = self.client.get(self.listing.get_absolute_url())
        self.assertNotContains(r, 'Something wrong with this listing?')
