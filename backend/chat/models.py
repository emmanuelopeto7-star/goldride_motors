from django.conf import settings
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    """The conversation about one ticket.

    Attached to the work rather than to the person: an agent reading a
    sourcing request sees what was said about *that* request, not a single
    stream mixing it with an unrelated enquiry from March. The cost is that a
    customer with three tickets has three threads, which is why their side
    lists them rather than opening one.

    A conversation outlives its ticket. Closing a ticket ends the work, not
    the talking - somebody replying to a settled matter still reaches us, and
    the inbox sorts by who spoke last precisely so that message is not
    invisible behind a closed status.

    Nobody owns a conversation the way an agent owns a ticket. Whoever is on
    shift answers, which is why the unread marks below are per side rather
    than per person.
    """

    ticket = models.OneToOneField(
        "tickets.Ticket",
        on_delete=models.CASCADE,
        related_name="conversation",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Denormalised so the staff inbox can sort by it without touching every
    # message. A list of conversations is read constantly and written rarely.
    last_message_at = models.DateTimeField(null=True, blank=True)

    # "Everything before this moment has been seen by that side." Timestamps
    # rather than counters: a counter has to be kept correct on every write
    # from both ends, and drifts the first time one is missed.
    customer_read_at = models.DateTimeField(null=True, blank=True)
    staff_read_at = models.DateTimeField(null=True, blank=True)

    # When we last emailed the customer to say something was waiting. Compared
    # against customer_read_at rather than counted: one alert per unread run,
    # so a burst of five replies is one email and the next one only comes
    # after they have actually looked.
    customer_alerted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_message_at", "-created_at"]

    @property
    def customer(self):
        """Whose conversation it is - the ticket's customer, always."""
        return self.ticket.customer

    def __str__(self):
        return f"Conversation about {self.ticket}"

    def unread_for_staff(self):
        return self._unread(self.staff_read_at, from_staff=False)

    def unread_for_customer(self):
        return self._unread(self.customer_read_at, from_staff=True)

    def _unread(self, seen_at, from_staff):
        messages = self.messages.filter(from_staff=from_staff)
        if seen_at is not None:
            messages = messages.filter(created_at__gt=seen_at)
        return messages.count()

    def mark_read(self, by_staff):
        field = "staff_read_at" if by_staff else "customer_read_at"
        Conversation.objects.filter(pk=self.pk).update(**{field: timezone.now()})
        self.refresh_from_db()


class Message(models.Model):
    """One thing somebody said.

    `from_staff` is stored rather than worked out from the sender's groups.
    Roles change - a salesperson becomes a manager, somebody leaves - and a
    transcript that re-reads its own history through today's permissions is
    a transcript you cannot trust. Same reasoning as pinning a dollar rate
    onto a quote.
    """

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_messages",
    )
    from_staff = models.BooleanField()
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self):
        who = "staff" if self.from_staff else "customer"
        return f"{who}: {self.body[:40]}"

    def save(self, *args, **kwargs):
        new = self._state.adding
        super().save(*args, **kwargs)
        if new:
            # Keeps the inbox sortable without a query over every message.
            Conversation.objects.filter(pk=self.conversation_id).update(
                last_message_at=self.created_at
            )
