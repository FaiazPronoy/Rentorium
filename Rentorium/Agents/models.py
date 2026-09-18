from builtins import property as computed

from django.db import models

from authentication.models import UserProfile
from property.models import AllProperty


class AgentAction(models.Model):
    """
    Every moderation decision an agent makes, kept forever.

    The first version overwrote a single text column with the agent's name and
    lost the history. Now an owner can be told exactly who decided what, when,
    and why, and a wrong decision can be traced.
    """

    class Action(models.TextChoices):
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        REVERTED = 'reverted', 'Sent back for changes'
        VERIFIED = 'verified', 'Documents verified'
        FEATURED = 'featured', 'Featured'
        UNFEATURED = 'unfeatured', 'Unfeatured'
        REPORT_UPHELD = 'rpt_upheld', 'Report upheld'
        REPORT_DISMISSED = 'rpt_ok', 'Report dismissed'
        SUSPENDED = 'suspended', 'Account suspended'
        LIFTED = 'lifted', 'Suspension lifted'

    agent = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, related_name='agent_actions'
    )
    # Null for a decision that is about a person rather than a listing — a
    # suspension, for instance. `subject` below names them.
    property = models.ForeignKey(
        AllProperty, on_delete=models.CASCADE, related_name='agent_actions',
        null=True, blank=True,
    )
    action = models.CharField(max_length=12, choices=Action.choices)
    # A moderation entry that is not about one listing (a suspension, say)
    # names the person instead.
    subject = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='actions_against',
    )
    reason = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property', '-created_at']),
            models.Index(fields=['agent', '-created_at']),
        ]

    def __str__(self):
        who = self.agent.name if self.agent else 'a removed agent'
        return f'{who} {self.get_action_display().lower()} {self.target}'

    @computed
    def target(self):
        """Whatever this decision was about, for the log."""
        return self.property or self.subject or 'a removed record'

    @computed
    def badge_class(self):
        return {
            self.Action.APPROVED: 'badge-ok',
            self.Action.VERIFIED: 'badge-ok',
            self.Action.FEATURED: 'badge-ok',
            self.Action.REPORT_DISMISSED: 'badge-ok',
            self.Action.LIFTED: 'badge-ok',
            self.Action.REJECTED: 'badge-fail',
            self.Action.SUSPENDED: 'badge-fail',
            self.Action.REPORT_UPHELD: 'badge-fail',
            self.Action.REVERTED: 'badge-pending',
            self.Action.UNFEATURED: 'badge-pending',
        }.get(self.action, '')
