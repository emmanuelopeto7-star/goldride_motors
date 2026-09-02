from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .pay_link import pay_link

from .models import Payment, PaymentEvent, ReconciliationRun


class InitiatePaymentRequestSerializer(serializers.Serializer):
    reference = serializers.UUIDField(help_text="The payment reference given to the customer.")
    email = serializers.EmailField()


class DispatchRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(
        required=False, allow_blank=True,
        help_text="M-PESA number as 2547XXXXXXXX. Defaults to the order's phone.",
    )
    email = serializers.EmailField(required=False, allow_blank=True)


class CheckoutResponseSerializer(serializers.Serializer):
    checkout_url = serializers.URLField(required=False)
    detail = serializers.CharField(required=False)


class PaymentSerializer(serializers.ModelSerializer):
    order_display = serializers.StringRelatedField(source="order", read_only=True)
    # Withheld once it has expired rather than sent and struck through: a link
    # on the screen is one somebody will click, and the honest offer at that
    # point is a fresh one.
    checkout_url = serializers.SerializerMethodField()
    checkout_is_live = serializers.BooleanField(read_only=True)
    pay_url = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "reference",
            "order",
            "order_display",
            "amount",
            "method",
            "status",
            "provider_ref",
            "checkout_url",
            "checkout_is_live",
            "pay_url",
            "checkout_expires_at",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_checkout_url(self, payment):
        return payment.checkout_url if payment.checkout_is_live else None

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_pay_url(self, payment):
        """The link worth showing anywhere durable.

        `checkout_url` is a Paystack session and goes stale in minutes; this
        one lasts as long as the invoice does and mints a fresh session when
        it is opened.
        """
        if payment.method != "card" or payment.status != "pending":
            return None
        return pay_link(payment)


class PaymentEventSerializer(serializers.ModelSerializer):
    """One line of a payment's history, as staff read it."""

    source_label = serializers.CharField(source="get_source_display", read_only=True)
    actor_name = serializers.CharField(
        source="actor.get_username", read_only=True, default=None
    )

    class Meta:
        model = PaymentEvent
        fields = [
            "id",
            "from_status",
            "to_status",
            "source",
            "source_label",
            "detail",
            "actor_name",
            "created_at",
        ]


class ReconciliationRunSerializer(serializers.ModelSerializer):
    trigger_label = serializers.CharField(
        source="get_trigger_display", read_only=True
    )
    seconds = serializers.FloatField(read_only=True)

    class Meta:
        model = ReconciliationRun
        fields = [
            "id",
            "state",
            "trigger",
            "trigger_label",
            "started_at",
            "finished_at",
            "seconds",
            "checked",
            "updated",
            "error",
        ]


class CorrectionSerializer(serializers.Serializer):
    """Putting a payment right by hand.

    The reason is required and has a floor on its length. A correction is the
    one place a person overrides what a provider said, and "fixed" six months
    later tells whoever is reading the history nothing at all.
    """

    status = serializers.ChoiceField(choices=Payment.STATUS_CHOICES)
    reason = serializers.CharField(min_length=8, max_length=300)
