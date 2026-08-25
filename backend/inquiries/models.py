from django.conf import settings
from django.db import models
from cars.models import Car

class Inquiry(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inquiries",
    )
    # PROTECT, like the purchase requests and orders that also point at a
    # car. An enquiry is the same kind of record: somebody asked, somebody
    # answered, and that exchange outlives the listing. On CASCADE, deleting
    # a listing took every enquiry about it with it - question, reply, who
    # sent it and the ticket - and returned 204 as though nothing had
    # happened.
    car = models.ForeignKey(Car, on_delete=models.PROTECT, related_name='inquiries')
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- the reply -------------------------------------------------------
    # An enquiry is answered once. These three fields are the record of that,
    # and `replied_at` is what settles the ticket: an enquiry has no status
    # column, so the presence of a reply is the status.
    reply = models.TextField(blank=True)
    replied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replied_inquiries",
    )
    replied_at = models.DateTimeField(null=True, blank=True)
    # False when there was no address to write to and an agent rang instead.
    reply_emailed = models.BooleanField(default=False)

    def __str__(self):
         return f"{self.name} about {self.car}"
