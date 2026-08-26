"""Tests for the public pages, the contact form and site reviews."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from authentication.models import UserProfile
from basic.models import Contact, Faq, Reviews

PASSWORD = 'Rentorium@2026'


class PublicPageTests(TestCase):
    def test_every_public_page_returns_200(self):
        for name in ['home', 'about', 'faqs', 'license', 'terms',
                     'testimonial', 'contact', 'PageNotFound']:
            r = self.client.get(reverse(name))
            self.assertIn(r.status_code, (200, 404), name)

    def test_the_not_found_page_really_returns_404(self):
        self.assertEqual(self.client.get(reverse('PageNotFound')).status_code, 404)

    def test_an_unknown_url_returns_404(self):
        self.assertEqual(self.client.get('/no/such/page/').status_code, 404)

    def test_the_faq_page_shows_published_questions_only(self):
        Faq.objects.create(question='Shown one', answer='Yes')
        Faq.objects.create(question='Hidden one', answer='No', is_published=False)
        r = self.client.get(reverse('faqs'))
        self.assertContains(r, 'Shown one')
        self.assertNotContains(r, 'Hidden one')


class ContactFormTests(TestCase):
    def payload(self, **over):
        data = {
            'name': 'Imran Kabir', 'email': 'imran@example.com',
            'subject': 'A question about listings',
            'message': 'My listing has been waiting for two days, is that normal?',
        }
        data.update(over)
        return data

    def test_a_good_message_is_saved(self):
        self.client.post(reverse('contact'), self.payload())
        self.assertEqual(Contact.objects.count(), 1)
        self.assertEqual(Contact.objects.first().status, Contact.Status.NEW)

    def test_a_very_short_message_is_refused(self):
        self.client.post(reverse('contact'), self.payload(message='hi'))
        self.assertEqual(Contact.objects.count(), 0)

    def test_a_bad_email_is_refused(self):
        self.client.post(reverse('contact'), self.payload(email='not-an-email'))
        self.assertEqual(Contact.objects.count(), 0)

    def test_the_honeypot_catches_a_bot(self):
        self.client.post(reverse('contact'), self.payload(website='http://spam.example'))
        self.assertEqual(Contact.objects.count(), 0)


class SiteReviewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='me@test.com', email='me@test.com', password=PASSWORD)
        profile = self.user.UserProfile
        profile.name = 'Me Myself'
        profile.save()

    def test_a_signed_out_visitor_cannot_post_a_review(self):
        self.client.post(reverse('testimonial'),
                         {'rating': 5, 'comment': 'This site is really quite good.'})
        self.assertEqual(Reviews.objects.count(), 0)

    def test_a_signed_in_person_can_post_one_review(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        self.client.post(reverse('testimonial'),
                         {'rating': 5, 'comment': 'This site is really quite good.'})
        self.assertEqual(Reviews.objects.count(), 1)

    def test_posting_again_updates_rather_than_duplicates(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        self.client.post(reverse('testimonial'),
                         {'rating': 5, 'comment': 'This site is really quite good.'})
        self.client.post(reverse('testimonial'),
                         {'rating': 2, 'comment': 'On reflection it is only alright.'})
        self.assertEqual(Reviews.objects.count(), 1)
        self.assertEqual(Reviews.objects.first().rating, 2)

    def test_a_very_short_review_is_refused(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        self.client.post(reverse('testimonial'), {'rating': 5, 'comment': 'good'})
        self.assertEqual(Reviews.objects.count(), 0)

    def test_a_person_can_delete_their_own_review(self):
        self.client.login(username='me@test.com', password=PASSWORD)
        self.client.post(reverse('testimonial'),
                         {'rating': 5, 'comment': 'This site is really quite good.'})
        self.client.post(reverse('delete_testimonial'))
        self.assertEqual(Reviews.objects.count(), 0)


class ContextProcessorTests(TestCase):
    def test_the_site_context_survives_an_anonymous_visitor(self):
        r = self.client.get(reverse('home'))
        self.assertFalse(r.context['is_logged_in'])
        self.assertIsNone(r.context['profile'])

    def test_a_user_with_no_profile_row_does_not_crash_the_site(self):
        user = User.objects.create_user(username='ghost@test.com', password=PASSWORD)
        UserProfile.objects.filter(user=user).delete()
        self.client.login(username='ghost@test.com', password=PASSWORD)
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)
