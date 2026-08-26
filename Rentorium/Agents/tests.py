"""Tests for the agent console and the decision log."""
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from Agents.models import AgentAction
from authentication.models import Notification, UserProfile
from basic.models import Contact
from property.models import AllProperty
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
