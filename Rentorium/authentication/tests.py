import re

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authentication.models import EmailCode, LoginAttempt, Notification, UserProfile

PASSWORD = 'Rentorium@2026'


class SignUpTests(TestCase):
    def payload(self, **over):
        data = {
            'name': 'Faiaz Abrar', 'email': 'faiaz@test.com',
            'contact_no': '01711111111', 'nid': '1234567890',
            'password': PASSWORD, 'confirm_password': PASSWORD,
            'role': UserProfile.Role.RENTER, 'agree': 'on',
        }
        data.update(over)
        return data

    def test_a_good_signup_creates_a_user_and_a_profile(self):
        r = self.client.post(reverse('signup'), self.payload())
        self.assertRedirects(r, reverse('signin'))
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(UserProfile.objects.count(), 1)
        profile = UserProfile.objects.first()
        self.assertEqual(profile.name, 'Faiaz Abrar')
        self.assertEqual(profile.role, UserProfile.Role.RENTER)

    def test_the_password_is_hashed_not_stored(self):
        self.client.post(reverse('signup'), self.payload())
        user = User.objects.first()
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.password.startswith('pbkdf2_'))
        self.assertTrue(user.check_password(PASSWORD))

    def test_a_weak_password_is_refused(self):
        for weak in ['short1!', 'nocapital1!', 'NOLOWER1!', 'NoDigits!!', 'NoSymbol123']:
            self.client.post(reverse('signup'),
                             self.payload(password=weak, confirm_password=weak,
                                          email=f'{weak}@test.com', nid=''))
        self.assertEqual(User.objects.count(), 0)

    def test_mismatched_passwords_are_refused(self):
        self.client.post(reverse('signup'), self.payload(confirm_password='Different@2026'))
        self.assertEqual(User.objects.count(), 0)

    def test_a_duplicate_email_is_refused(self):
        self.client.post(reverse('signup'), self.payload())
        self.client.post(reverse('signup'), self.payload(nid='9999999999'))
        self.assertEqual(User.objects.count(), 1)

    def test_a_duplicate_nid_is_refused(self):
        self.client.post(reverse('signup'), self.payload())
        self.client.post(reverse('signup'), self.payload(email='other@test.com'))
        self.assertEqual(User.objects.count(), 1)

    def test_a_bad_phone_number_is_refused(self):
        self.client.post(reverse('signup'), self.payload(contact_no='12345'))
        self.assertEqual(User.objects.count(), 0)

    def test_the_terms_box_has_to_be_ticked(self):
        data = self.payload()
        data.pop('agree')
        self.client.post(reverse('signup'), data)
        self.assertEqual(User.objects.count(), 0)

    def test_a_welcome_notification_is_created(self):
        self.client.post(reverse('signup'), self.payload())
        self.assertEqual(Notification.objects.count(), 1)


class SignInTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='faiaz@test.com', email='faiaz@test.com', password=PASSWORD)
        profile = self.user.UserProfile
        profile.name = 'Faiaz Abrar'
        profile.save()

    def test_signing_in_works(self):
        r = self.client.post(reverse('signin'),
                             {'username': 'faiaz@test.com', 'password': PASSWORD})
        self.assertRedirects(r, '/')

    def test_a_wrong_password_is_refused_and_recorded(self):
        self.client.post(reverse('signin'),
                         {'username': 'faiaz@test.com', 'password': 'wrong'})
        self.assertEqual(LoginAttempt.objects.filter(successful=False).count(), 1)

    def test_six_wrong_attempts_lock_the_address(self):
        for _ in range(6):
            self.client.post(reverse('signin'),
                             {'username': 'faiaz@test.com', 'password': 'wrong'})
        r = self.client.post(reverse('signin'),
                             {'username': 'faiaz@test.com', 'password': PASSWORD})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Too many failed attempts')

    def test_the_next_parameter_cannot_send_you_to_another_site(self):
        r = self.client.post(reverse('signin'), {
            'username': 'faiaz@test.com', 'password': PASSWORD,
            'next': 'https://example.com/evil',
        })
        self.assertRedirects(r, '/')

    def test_a_relative_next_is_honoured(self):
        r = self.client.post(reverse('signin'), {
            'username': 'faiaz@test.com', 'password': PASSWORD,
            'next': reverse('property_list'),
        })
        self.assertRedirects(r, reverse('property_list'))


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='me@test.com', email='me@test.com', password=PASSWORD)
        profile = self.user.UserProfile
        profile.name = 'Me Myself'
        profile.email = 'me@test.com'
        profile.save()
        self.client.login(username='me@test.com', password=PASSWORD)

    def test_the_profile_page_loads(self):
        self.assertEqual(self.client.get(reverse('profile')).status_code, 200)

    def test_editing_the_email_also_moves_the_username(self):
        self.client.post(reverse('edit_profile'), {
            'name': 'Me Myself', 'email': 'new@test.com', 'contact_no': '01711111111',
            'role': UserProfile.Role.RENTER, 'address': '', 'bio': '',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'new@test.com')
        self.assertEqual(self.user.email, 'new@test.com')

    def test_you_cannot_take_an_email_that_belongs_to_someone_else(self):
        User.objects.create_user(username='taken@test.com', email='taken@test.com',
                                 password=PASSWORD)
        self.client.post(reverse('edit_profile'), {
            'name': 'Me Myself', 'email': 'taken@test.com',
            'role': UserProfile.Role.RENTER, 'address': '', 'bio': '',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'me@test.com')

    def test_changing_the_password_needs_the_current_one(self):
        self.client.post(reverse('change_password'), {
            'current_password': 'wrong',
            'new_password': 'Brandnew@2026', 'confirm_password': 'Brandnew@2026',
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_changing_the_password_works_with_the_right_one(self):
        self.client.post(reverse('change_password'), {
            'current_password': PASSWORD,
            'new_password': 'Brandnew@2026', 'confirm_password': 'Brandnew@2026',
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Brandnew@2026'))

    def test_deleting_an_account_needs_the_password(self):
        self.client.post(reverse('delete_account'), {'password': 'wrong'})
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_deleting_an_account_works_with_the_password(self):
        self.client.post(reverse('delete_account'), {'password': PASSWORD})
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_the_account_cannot_be_deleted_on_a_get(self):
        self.client.get(reverse('delete_account'))
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())


class GuardTests(TestCase):
    PROTECTED = [
        'dashboard', 'profile', 'edit_profile', 'change_password', 'notifications',
        'favourites', 'bookings', 'inbox', 'saved_searches', 'posted_properties',
        'add_property',
    ]

    def test_signed_out_visitors_are_redirected_not_shown(self):
        for name in self.PROTECTED:
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn('signin', r.url, name)

    def test_public_pages_do_not_need_a_session(self):
        for name in ['home', 'about', 'faqs', 'terms', 'license', 'testimonial',
                     'contact', 'property_list', 'property_type', 'signin', 'signup']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)


class DashboardTests(TestCase):
    def setUp(self):
        from property.models import PropertyView
        from property.tests import make_listing, make_user
        from django.utils import timezone

        _, self.owner = make_user('owner@test.com', 'Owner', UserProfile.Role.OWNER)
        _, self.viewer = make_user('viewer@test.com', 'Viewer')
        self.listing = make_listing(self.owner)
        today = timezone.localdate()
        for offset in (0, 1, 5, 13, 20):
            PropertyView.objects.create(
                property=self.listing, profile=self.viewer,
                viewed_on=today - timezone.timedelta(days=offset),
            )
        self.client.login(username='owner@test.com', password=PASSWORD)

    def test_the_dashboard_renders_with_real_view_data(self):
        r = self.client.get(reverse('dashboard'))
        self.assertEqual(r.status_code, 200)

    def test_a_brand_new_user_sees_an_empty_dashboard_not_a_crash(self):
        self.client.logout()
        self.client.login(username='viewer@test.com', password=PASSWORD)
        r = self.client.get(reverse('dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(sum(c['value'] for c in r.context['chart']), 0)


class DemoKeyTests(TestCase):
    def test_no_keys_on_an_empty_database(self):
        self.assertEqual(self.client.get(reverse('signin')).context['demo'], [])

    def test_a_key_signs_in_as_that_person(self):
        from authentication.demo import DEMO_PASSWORD
        user = User.objects.create_user(username='rafid@rentorium.test',
                                        email='rafid@rentorium.test', password=DEMO_PASSWORD)
        profile = user.UserProfile
        profile.name = 'Rafid Hasan'
        profile.save()

        keys = self.client.get(reverse('signin')).context['demo']
        self.assertEqual([(k['role'], k['name']) for k in keys], [('Renter', 'Rafid')])

        r = self.client.post(reverse('signin'),
                             {'username': keys[0]['email'], 'password': keys[0]['password']})
        self.assertRedirects(r, '/')

    def test_a_suspended_demo_person_gets_no_key(self):
        from authentication.demo import DEMO_PASSWORD
        User.objects.create_user(username='faiaz@rentorium.test', email='faiaz@rentorium.test',
                                 password=DEMO_PASSWORD, is_active=False)
        self.assertEqual(self.client.get(reverse('signin')).context['demo'], [])


class TwoStepTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='faiaz@test.com', email='faiaz@test.com', password=PASSWORD)

    def code(self):
        return re.search(r'\b(\d{6})\b', mail.outbox[-1].subject).group(1)

    def sign_in(self, **extra):
        return self.client.post(reverse('signin'),
                                {'username': 'faiaz@test.com', 'password': PASSWORD, **extra})

    def turn_on(self):
        self.client.force_login(self.user)
        self.client.post(reverse('two_step_on'))
        self.client.post(reverse('two_step_confirm'), {'code': self.code()})
        self.client.logout()

    def test_it_is_off_until_turned_on(self):
        self.assertRedirects(self.sign_in(), '/')
        self.assertEqual(len(mail.outbox), 0)

    def test_turning_it_on_needs_the_emailed_code(self):
        self.client.force_login(self.user)
        self.client.post(reverse('two_step_on'))
        self.assertEqual(mail.outbox[-1].to, ['faiaz@test.com'])
        self.client.post(reverse('two_step_confirm'), {'code': '000000' if self.code() != '000000' else '111111'})
        self.user.UserProfile.refresh_from_db()
        self.assertFalse(self.user.UserProfile.two_step)
        self.client.post(reverse('two_step_confirm'), {'code': self.code()})
        self.user.UserProfile.refresh_from_db()
        self.assertTrue(self.user.UserProfile.two_step)

    def test_the_password_alone_does_not_sign_in(self):
        self.turn_on()
        self.assertRedirects(self.sign_in(), reverse('signin_verify'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_the_code_finishes_signing_in_and_keeps_next(self):
        self.turn_on()
        self.sign_in(next=reverse('property_list'))
        r = self.client.post(reverse('signin_verify'), {'code': self.code()})
        self.assertRedirects(r, reverse('property_list'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_a_code_works_once(self):
        self.turn_on()
        self.sign_in()
        code = self.code()
        self.client.post(reverse('signin_verify'), {'code': code})
        self.client.post(reverse('signout'))
        self.sign_in()
        mail.outbox.clear()
        self.client.post(reverse('signin_verify'), {'code': code})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_the_code_is_stored_hashed(self):
        self.turn_on()
        self.sign_in()
        entry = EmailCode.objects.filter(user=self.user, purpose=EmailCode.Purpose.SIGN_IN).first()
        self.assertNotIn(self.code(), entry.code_hash)

    def test_an_old_code_is_refused(self):
        self.turn_on()
        self.sign_in()
        EmailCode.objects.update(created_at=timezone.now() - timezone.timedelta(minutes=11))
        r = self.client.post(reverse('signin_verify'), {'code': self.code()})
        self.assertRedirects(r, reverse('signin'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_five_wrong_codes_end_the_attempt(self):
        self.turn_on()
        self.sign_in()
        right = self.code()
        wrong = '111111' if right != '111111' else '222222'
        for _ in range(EmailCode.MAX_TRIES):
            r = self.client.post(reverse('signin_verify'), {'code': wrong})
        self.assertRedirects(r, reverse('signin'))
        self.client.post(reverse('signin_verify'), {'code': right})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_the_code_page_needs_a_password_first(self):
        self.assertRedirects(self.client.get(reverse('signin_verify')), reverse('signin'))

    def test_turning_it_off_needs_the_password(self):
        self.turn_on()
        self.client.force_login(self.user)
        self.client.post(reverse('two_step_off'), {'password': 'Wrong@2026'})
        self.user.UserProfile.refresh_from_db()
        self.assertTrue(self.user.UserProfile.two_step)
        self.client.post(reverse('two_step_off'), {'password': PASSWORD})
        self.user.UserProfile.refresh_from_db()
        self.assertFalse(self.user.UserProfile.two_step)

    def test_demo_accounts_cannot_turn_it_on(self):
        demo = User.objects.create_user(username='rafid@rentorium.test', email='rafid@rentorium.test',
                                        password=PASSWORD)
        self.client.force_login(demo)
        self.client.post(reverse('two_step_on'))
        self.assertEqual(len(mail.outbox), 0)

