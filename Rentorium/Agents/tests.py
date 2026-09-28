"""Tests for the agent console and the decision log."""
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from Agents.models import AgentAction
from authentication.models import Notification, UserProfile
from basic.models import Contact
from property.models import AllProperty, PropertyReport
from property.tests import PASSWORD, make_listing, make_user


class AgentConsoleTests(TestCase):
    def setUp(self):
        self.agent_user, self.agent = make_user('agent@test.com', 'Agent', agent=True)
        self.owner_user, self.owner = make_user('owner@test.com', 'Owner',
                                                UserProfile.Role.OWNER)
        self.pending = make_listing(self.owner, status=AllProperty.Status.PENDING)

    def signin_agent(self):
        self.client.login(username='agent@test.com', password=PASSWORD)

    def test_the_console_lists_what_is_waiting(self):
        self.signin_agent()
        r = self.client.get(reverse('agent_dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([x.pk for x in r.context['pending_properties']], [self.pending.pk])

    def test_approving_publishes_and_records_the_decision(self):
        self.signin_agent()
        self.client.post(reverse('approve_property', args=[self.pending.pk]))
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, AllProperty.Status.APPROVED)
        self.assertFalse(self.pending.needs_approval)
        self.assertEqual(self.pending.Approval_by_Agent, 'Agent')
        self.assertEqual(
            AgentAction.objects.filter(action=AgentAction.Action.APPROVED).count(), 1)

    def test_the_owner_is_told_when_a_listing_goes_live(self):
        self.signin_agent()
        self.client.post(reverse('approve_property', args=[self.pending.pk]))
        self.assertTrue(
            Notification.objects.filter(profile=self.owner,
                                        kind=Notification.Kind.APPROVAL).exists())

    def test_rejecting_needs_a_reason(self):
        self.signin_agent()
        self.client.post(reverse('reject_property', args=[self.pending.pk]), {'reason': ''})
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, AllProperty.Status.PENDING)

    def test_rejecting_with_a_reason_sends_it_back(self):
        self.signin_agent()
        self.client.post(reverse('reject_property', args=[self.pending.pk]),
                         {'reason': 'Please add photos and the ownership paper.'})
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, AllProperty.Status.REJECTED)
        self.assertIn('photos', self.pending.rejection_reason)

    def test_approval_can_be_withdrawn(self):
        self.signin_agent()
        self.client.post(reverse('approve_property', args=[self.pending.pk]))
        self.client.post(reverse('cancel_approval', args=[self.pending.pk]),
                         {'reason': 'Another look needed.'})
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, AllProperty.Status.PENDING)

    def test_the_decision_history_is_kept_not_overwritten(self):
        self.signin_agent()
        self.client.post(reverse('approve_property', args=[self.pending.pk]))
        self.client.post(reverse('cancel_approval', args=[self.pending.pk]),
                         {'reason': 'Another look needed.'})
        self.client.post(reverse('approve_property', args=[self.pending.pk]))
        self.assertEqual(AgentAction.objects.filter(property=self.pending).count(), 3)

    def test_verifying_the_papers_verifies_the_owner(self):
        self.signin_agent()
        self.pending.Property_Documents.save(
            'deed.pdf', ContentFile(b'%PDF-1.4 ownership deed'), save=True)
        self.client.post(reverse('verify_documents', args=[self.pending.pk]))
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_verified)

    def test_nothing_is_verified_when_there_is_no_document(self):
        self.signin_agent()
        self.client.post(reverse('verify_documents', args=[self.pending.pk]))
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_verified)
        self.assertEqual(
            AgentAction.objects.filter(action=AgentAction.Action.VERIFIED).count(), 0)

    def test_featuring_can_be_toggled(self):
        self.signin_agent()
        self.client.post(reverse('toggle_feature', args=[self.pending.pk]))
        self.pending.refresh_from_db()
        self.assertTrue(self.pending.is_featured)
        self.client.post(reverse('toggle_feature', args=[self.pending.pk]))
        self.pending.refresh_from_db()
        self.assertFalse(self.pending.is_featured)

    def test_a_decision_cannot_be_made_with_a_get(self):
        self.signin_agent()
        self.client.get(reverse('approve_property', args=[self.pending.pk]))
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, AllProperty.Status.PENDING)

    def test_all_the_agent_pages_render(self):
        self.signin_agent()
        for name in ['agent_dashboard', 'agent_stats', 'agent_log',
                     'agent_users', 'agent_enquiries']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)


class AgentLogFilterTests(TestCase):
    """Filtering the decision log."""

    def setUp(self):
        self.agent_user, self.agent = make_user('agent@test.com', 'Agent', agent=True)
        self.owner_user, self.owner = make_user('owner@test.com', 'Owner',
                                                UserProfile.Role.OWNER)
        self.listing = make_listing(self.owner, status=AllProperty.Status.PENDING)
        self.client.login(username='agent@test.com', password=PASSWORD)
        self.client.post(reverse('approve_property', args=[self.listing.pk]))

    def test_junk_in_the_action_filter_does_not_crash(self):
        r = self.client.get(reverse('agent_log'), {'action': 'nonsense'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context['rows']), 1)

    def test_a_real_agent_id_actually_filters(self):
        r = self.client.get(reverse('agent_log'), {'agent': self.agent.pk})
        self.assertEqual(len(r.context['rows']), 1)

class EnquiryReplyTests(TestCase):
    """Answering an enquiry from the console."""

    def setUp(self):
        make_user('agent@test.com', 'Agent', agent=True)
        self.enquiry = Contact.objects.create(
            name='Someone', email='someone@test.com',
            subject='Is the Gulshan flat still free?',
            message='Asking about the three bedroom one.',
        )
        self.client.login(username='agent@test.com', password=PASSWORD)

    def test_an_enquiry_can_be_answered(self):
        self.client.post(reverse('agent_enquiries'),
                         {'id': self.enquiry.pk, 'reply': 'Yes, still free.'})
        self.enquiry.refresh_from_db()
        self.assertEqual(self.enquiry.status, Contact.Status.ANSWERED)
        self.assertEqual(self.enquiry.reply, 'Yes, still free.')


class ReportQueueTests(TestCase):
    """The queue of listings people have flagged, and what an agent does with it."""

    def setUp(self):
        self.agent_user, self.agent = make_user('agent@test.com', 'Agent', agent=True)
        self.owner_user, self.owner = make_user('owner@test.com', 'Owner',
                                                UserProfile.Role.OWNER)
        self.reporter_user, self.reporter = make_user('renter@test.com', 'Renter')
        self.listing = make_listing(self.owner)
        self.report = PropertyReport.objects.create(
            property=self.listing, reporter=self.reporter,
            reason=PropertyReport.Reason.FAKE, detail='Photos are from a hotel site.',
        )

    def signin_agent(self):
        self.client.login(username='agent@test.com', password=PASSWORD)

    def test_only_an_agent_can_open_the_queue(self):
        self.client.login(username='renter@test.com', password=PASSWORD)
        r = self.client.get(reverse('agent_reports'))
        self.assertNotEqual(r.status_code, 200)

    def test_the_queue_shows_an_open_report(self):
        self.signin_agent()
        r = self.client.get(reverse('agent_reports'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([x.pk for x in r.context['rows']], [self.report.pk])

    def test_upholding_takes_the_listing_down_and_logs_it(self):
        self.signin_agent()
        self.client.post(reverse('resolve_report', args=[self.report.pk]),
                         {'decision': 'uphold', 'outcome': 'The address does not exist.'})
        self.report.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(self.report.status, PropertyReport.Status.UPHELD)
        self.assertEqual(self.report.handled_by, self.agent)
        self.assertEqual(self.listing.status, AllProperty.Status.REJECTED)
        self.assertTrue(AgentAction.objects.filter(
            action=AgentAction.Action.REPORT_UPHELD).exists())

    def test_dismissing_leaves_the_listing_alone(self):
        self.signin_agent()
        self.client.post(reverse('resolve_report', args=[self.report.pk]),
                         {'decision': 'dismiss', 'outcome': 'Checked, it is fine.'})
        self.report.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(self.report.status, PropertyReport.Status.DISMISSED)
        self.assertEqual(self.listing.status, AllProperty.Status.APPROVED)

    def test_upholding_settles_every_other_open_report_on_the_same_listing(self):
        _, second = make_user('second@test.com', 'Second')
        other = PropertyReport.objects.create(
            property=self.listing, reporter=second,
            reason=PropertyReport.Reason.TAKEN)
        self.signin_agent()
        self.client.post(reverse('resolve_report', args=[self.report.pk]),
                         {'decision': 'uphold'})
        other.refresh_from_db()
        self.assertEqual(other.status, PropertyReport.Status.UPHELD)

    def test_a_report_cannot_be_decided_twice(self):
        self.signin_agent()
        self.client.post(reverse('resolve_report', args=[self.report.pk]),
                         {'decision': 'dismiss'})
        self.client.post(reverse('resolve_report', args=[self.report.pk]),
                         {'decision': 'uphold'})
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, PropertyReport.Status.DISMISSED)

    def test_the_person_who_reported_is_told_the_outcome(self):
        self.signin_agent()
        self.client.post(reverse('resolve_report', args=[self.report.pk]),
                         {'decision': 'dismiss'})
        self.assertTrue(Notification.objects.filter(profile=self.reporter).exists())

    def test_a_report_cannot_be_resolved_by_a_get(self):
        self.signin_agent()
        self.client.get(reverse('resolve_report', args=[self.report.pk]))
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, PropertyReport.Status.OPEN)


class BulkDecisionTests(TestCase):
    def setUp(self):
        self.agent_user, self.agent = make_user('agent@test.com', 'Agent', agent=True)
        self.owner_user, self.owner = make_user('owner@test.com', 'Owner',
                                                UserProfile.Role.OWNER)
        self.rows = [make_listing(self.owner, status=AllProperty.Status.PENDING)
                     for _ in range(3)]
        self.client.login(username='agent@test.com', password=PASSWORD)

    def pks(self):
        return [r.pk for r in self.rows]

    def test_several_listings_can_be_approved_at_once(self):
        self.client.post(reverse('bulk_decide'),
                         {'picked': self.pks(), 'bulk_action': 'approve'})
        for row in self.rows:
            row.refresh_from_db()
            self.assertEqual(row.status, AllProperty.Status.APPROVED)
        self.assertEqual(AgentAction.objects.filter(
            action=AgentAction.Action.APPROVED).count(), 3)

    def test_every_owner_is_told_individually(self):
        self.client.post(reverse('bulk_decide'),
                         {'picked': self.pks(), 'bulk_action': 'approve'})
        self.assertEqual(Notification.objects.filter(profile=self.owner).count(), 3)

    def test_sending_back_in_bulk_needs_a_reason(self):
        self.client.post(reverse('bulk_decide'),
                         {'picked': self.pks(), 'bulk_action': 'reject'})
        for row in self.rows:
            row.refresh_from_db()
            self.assertEqual(row.status, AllProperty.Status.PENDING)

    def test_sending_back_in_bulk_passes_the_reason_on(self):
        self.client.post(reverse('bulk_decide'), {
            'picked': self.pks(), 'bulk_action': 'reject',
            'bulk_reason': 'No ownership paper on any of these.',
        })
        for row in self.rows:
            row.refresh_from_db()
            self.assertEqual(row.status, AllProperty.Status.REJECTED)
            self.assertEqual(row.rejection_reason,
                             'No ownership paper on any of these.')

    def test_a_listing_someone_else_already_decided_is_left_alone(self):
        settled = self.rows[0]
        settled.status = AllProperty.Status.APPROVED
        settled.save()
        AgentAction.objects.all().delete()
        self.client.post(reverse('bulk_decide'), {
            'picked': self.pks(), 'bulk_action': 'reject',
            'bulk_reason': 'Not good enough.',
        })
        settled.refresh_from_db()
        self.assertEqual(settled.status, AllProperty.Status.APPROVED)
        self.assertEqual(AgentAction.objects.count(), 2)

    def test_rubbish_ids_are_ignored(self):
        self.client.post(reverse('bulk_decide'),
                         {'picked': ['abc', '-1', '0'], 'bulk_action': 'approve'})
        for row in self.rows:
            row.refresh_from_db()
            self.assertEqual(row.status, AllProperty.Status.PENDING)

    def test_a_renter_cannot_bulk_approve(self):
        _, _ = make_user('renter@test.com', 'Renter')
        self.client.login(username='renter@test.com', password=PASSWORD)
        self.client.post(reverse('bulk_decide'),
                         {'picked': self.pks(), 'bulk_action': 'approve'})
        for row in self.rows:
            row.refresh_from_db()
            self.assertEqual(row.status, AllProperty.Status.PENDING)


class SuspensionTests(TestCase):
    def setUp(self):
        self.agent_user, self.agent = make_user('agent@test.com', 'Agent', agent=True)
        self.owner_user, self.owner = make_user('owner@test.com', 'Owner',
                                                UserProfile.Role.OWNER)
        self.listing = make_listing(self.owner)
        self.client.login(username='agent@test.com', password=PASSWORD)

    def suspend(self, reason='Three listings for flats that do not exist.'):
        return self.client.post(reverse('suspend_user', args=[self.owner.pk]),
                                {'reason': reason})

    def test_suspending_locks_the_account_and_hides_their_listings(self):
        self.suspend()
        self.owner.refresh_from_db()
        self.owner_user.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertTrue(self.owner.is_suspended)
        self.assertFalse(self.owner_user.is_active)
        self.assertTrue(self.listing.is_archived)
        self.assertEqual(AllProperty.objects.live().count(), 0)

    def test_a_suspension_needs_a_reason(self):
        self.suspend(reason='   ')
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_suspended)

    def test_the_person_is_told_why(self):
        self.suspend()
        note = Notification.objects.filter(profile=self.owner).last()
        self.assertIn('do not exist', note.body)

    def test_the_decision_is_in_the_log_against_the_person(self):
        self.suspend()
        row = AgentAction.objects.get(action=AgentAction.Action.SUSPENDED)
        self.assertEqual(row.subject, self.owner)
        self.assertIsNone(row.property)

    def test_a_suspended_person_cannot_sign_in(self):
        self.suspend()
        self.client.logout()
        self.assertFalse(
            self.client.login(username='owner@test.com', password=PASSWORD))

    def test_a_suspended_person_is_thrown_out_of_a_session_they_already_had(self):
        """Deactivating the account ends the session at the next request.

        Django's auth backend refuses to load an inactive user, so the
        already-signed-in browser becomes anonymous rather than carrying on
        until the cookie expires.
        """
        self.client.logout()
        self.client.login(username='owner@test.com', password=PASSWORD)
        self.owner.suspend(by=self.agent, reason='Caught out.')
        r = self.client.get(reverse('posted_properties'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('signin', r.url)

    def test_the_reason_is_shown_when_they_try_to_sign_in_again(self):
        self.suspend()
        self.client.logout()
        r = self.client.post(reverse('signin'), {
            'username': 'owner@test.com', 'password': PASSWORD,
        })
        self.assertContains(r, 'This account is suspended')
        self.assertNotContains(r, 'Wrong email or password')

    def test_the_guard_also_catches_a_suspension_set_without_deactivating(self):
        """A row edited straight in the admin, say."""
        self.client.logout()
        self.client.login(username='owner@test.com', password=PASSWORD)
        UserProfile.objects.filter(pk=self.owner.pk).update(
            is_suspended=True, suspended_reason='Set by hand.')
        r = self.client.get(reverse('posted_properties'), follow=True)
        self.assertContains(r, 'suspended')

    def test_an_agent_cannot_be_suspended_from_here(self):
        _, other_agent = make_user('agent2@test.com', 'Agent Two', agent=True)
        self.client.post(reverse('suspend_user', args=[other_agent.pk]),
                         {'reason': 'Nope.'})
        other_agent.refresh_from_db()
        self.assertFalse(other_agent.is_suspended)

    def test_an_agent_cannot_suspend_themselves(self):
        self.client.post(reverse('suspend_user', args=[self.agent.pk]),
                         {'reason': 'Oops.'})
        self.agent.refresh_from_db()
        self.assertFalse(self.agent.is_suspended)

    def test_lifting_puts_everything_back(self):
        self.suspend()
        self.client.post(reverse('lift_suspension', args=[self.owner.pk]))
        self.owner.refresh_from_db()
        self.owner_user.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertFalse(self.owner.is_suspended)
        self.assertTrue(self.owner_user.is_active)
        self.assertFalse(self.listing.is_archived)
        self.assertEqual(AllProperty.objects.live().count(), 1)
        self.client.logout()
        self.assertTrue(
            self.client.login(username='owner@test.com', password=PASSWORD))

    def test_a_renter_cannot_suspend_anyone(self):
        _, _ = make_user('renter@test.com', 'Renter')
        self.client.login(username='renter@test.com', password=PASSWORD)
        self.client.post(reverse('suspend_user', args=[self.owner.pk]),
                         {'reason': 'I do not like them.'})
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_suspended)


class CsvExportTests(TestCase):
    def setUp(self):
        self.agent_user, self.agent = make_user('agent@test.com', 'Agent', agent=True)
        self.owner_user, self.owner = make_user('owner@test.com', 'Owner',
                                                UserProfile.Role.OWNER)
        self.listing = make_listing(self.owner, Property_Name='A flat in Gulshan')
        Contact.objects.create(name='Nusrat', email='n@example.com',
                               subject='A question', message='Is it free?')
        PropertyReport.objects.create(property=self.listing, reporter=self.owner,
                                      reason=PropertyReport.Reason.WRONG)
        AgentAction.objects.create(agent=self.agent, property=self.listing,
                                   action=AgentAction.Action.APPROVED)
        self.client.login(username='agent@test.com', password=PASSWORD)

    def rows(self, what, **params):
        r = self.client.get(reverse('agent_export', args=[what]), params)
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])
        self.assertIn('attachment', r['Content-Disposition'])
        body = r.content.decode('utf-8-sig')
        return [line for line in body.splitlines() if line.strip()]

    def test_every_export_has_a_header_and_at_least_one_row(self):
        for what in ('listings', 'users', 'enquiries', 'reports', 'log'):
            with self.subTest(what=what):
                self.assertGreaterEqual(len(self.rows(what)), 2)

    def test_the_listings_export_names_the_listing(self):
        self.assertIn('A flat in Gulshan', '\n'.join(self.rows('listings')))

    def test_the_listings_export_can_be_filtered_by_status(self):
        make_listing(self.owner, Property_Name='Still waiting',
                     status=AllProperty.Status.PENDING)
        body = '\n'.join(self.rows('listings', status='pending'))
        self.assertIn('Still waiting', body)
        self.assertNotIn('A flat in Gulshan', body)

    def test_it_starts_with_a_byte_order_mark_so_excel_reads_it(self):
        r = self.client.get(reverse('agent_export', args=['users']))
        self.assertTrue(r.content.startswith('﻿'.encode()))

    def test_an_unknown_export_is_a_404(self):
        r = self.client.get('/agents/export/passwords.csv')
        self.assertEqual(r.status_code, 404)

    def test_a_renter_cannot_export_anything(self):
        _, _ = make_user('renter@test.com', 'Renter')
        self.client.login(username='renter@test.com', password=PASSWORD)
        r = self.client.get(reverse('agent_export', args=['users']))
        self.assertNotEqual(r.status_code, 200)
