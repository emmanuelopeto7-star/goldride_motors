"""The whole staff surface, pinned by role.

A probe rather than a set of hand-written cases: every staff endpoint, every
method, as every role. A 401/403 means the permission layer refused; anything
else - 400 or 404 included - means it let the caller through, because DRF
checks permissions before it validates a body or looks an object up.

The point is regression protection. Adding an endpoint without a permission
class, or loosening one by accident, is silent in every other test; here it
fails immediately.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.authtoken.models import Token

User = get_user_model()

REFUSED = (401, 403)

# Real UUID, no such payment. The reference routes take <uuid:reference>, and
# a path that does not resolve answers 404 to everybody - which would sail
# through this probe while proving nothing about who may call it.
NO_SUCH_PAYMENT = "00000000-0000-0000-0000-000000000000"

# Everything Sales may reach, which includes collecting money: raising an
# invoice and chasing it is the job. Deletes, approvals and the rates are the
# decisions about the money, and those are not on this list - see MANAGER_ONLY.
SALES_MAY = [
    ("staff/cars/", "get"), ("staff/cars/", "post"),
    ("staff/cars/1/", "get"), ("staff/cars/1/", "patch"),
    ("staff/cars/1/extend/", "post"),
    ("staff/car-images/", "get"), ("staff/car-images/", "post"),
    ("staff/hero-banners/", "get"), ("staff/hero-banners/", "post"),
    ("staff/hero-banners/1/", "patch"),
    ("staff/orders/", "get"), ("staff/orders/1/", "get"),
    ("staff/orders/1/", "patch"), ("staff/orders/1/reactivate/", "post"),
    ("staff/milestones/", "post"),
    ("staff/import-rates/", "get"),
    ("staff/import-requests/", "get"), ("staff/import-requests/1/", "get"),
    ("staff/import-requests/1/", "patch"),
    ("staff/import-requests/1/notify/", "post"),
    ("staff/sourced-units/", "get"), ("staff/sourced-units/", "post"),
    ("staff/sourced-units/1/", "patch"),
    ("staff/sourced-units/1/push-to-stock/", "post"),
    ("staff/payments/", "get"), ("staff/payments/", "post"),
    (f"staff/payments/{NO_SUCH_PAYMENT}/dispatch/", "post"),
    (f"staff/payments/{NO_SUCH_PAYMENT}/reconcile/", "post"),
    ("staff/payments/reconcile/", "post"),
    ("staff/tickets/", "get"), ("staff/tickets/1/", "get"),
    ("staff/tickets/1/claim/", "post"), ("staff/tickets/1/release/", "post"),
    ("staff/tickets/1/close/", "post"), ("staff/tickets/1/reply/", "post"),
    ("purchases/staff/", "get"), ("purchases/staff/1/", "get"),
    ("inquiries/all/", "get"), ("inquiries/1/", "get"),
    ("staff/chats/", "get"), ("staff/chats/1/", "get"),
    ("staff/chats/1/", "post"), ("staff/chats/1/read/", "post"),
]

# Sales must be refused these. Deleting is a supervisor's act; approving moves
# money; the rates decide what every future quote charges.
MANAGER_ONLY = [
    ("staff/cars/1/", "delete"),
    ("staff/car-images/1/", "delete"),
    ("staff/hero-banners/1/", "delete"),
    ("staff/orders/1/", "delete"),
    ("staff/sourced-units/1/", "delete"),
    ("staff/import-rates/", "post"),
    (f"staff/payments/{NO_SUCH_PAYMENT}/record/", "post"),
    ("staff/team/", "get"),
    ("staff/team/", "post"),
    ("staff/team/1/", "get"),
    ("staff/team/1/", "patch"),
    ("purchases/staff/1/approve/", "post"),
    ("purchases/staff/1/reject/", "post"),
]



class StaffPermissionSurfaceTests(TestCase):
    def setUp(self):
        self.tokens = {"anonymous": None}
        for label, groups in [
            ("customer", ["Customer"]),
            ("sales", ["Sales"]),
            ("manager", ["Manager"]),
        ]:
            user = User.objects.create_user(f"perm_{label}", f"perm_{label}@x.com", "pw")
            for name in groups:
                Group.objects.get_or_create(name=name)[0].user_set.add(user)
            self.tokens[label] = Token.objects.create(user=user).key

    def probe(self, path, method, role):
        token = self.tokens[role]
        headers = {"HTTP_AUTHORIZATION": f"Token {token}"} if token else {}
        response = getattr(self.client, method)(
            f"/api/{path}", data={}, content_type="application/json", **headers
        )
        return response.status_code

    def test_nothing_staff_is_open_to_the_public(self):
        for path, method in SALES_MAY + MANAGER_ONLY:
            with self.subTest(path=path, method=method):
                self.assertIn(self.probe(path, method, "anonymous"), REFUSED)

    def test_a_customer_reaches_none_of_it(self):
        """A signed-in buyer is not a member of staff."""
        for path, method in SALES_MAY + MANAGER_ONLY:
            with self.subTest(path=path, method=method):
                self.assertIn(self.probe(path, method, "customer"), REFUSED)

    def test_sales_reaches_everything_meant_for_sales(self):
        for path, method in SALES_MAY:
            with self.subTest(path=path, method=method):
                self.assertNotIn(self.probe(path, method, "sales"), REFUSED)

    def test_sales_is_refused_what_belongs_to_a_manager(self):
        for path, method in MANAGER_ONLY:
            with self.subTest(path=path, method=method):
                self.assertIn(self.probe(path, method, "sales"), REFUSED)

    def test_a_manager_reaches_all_of_it(self):
        for path, method in SALES_MAY + MANAGER_ONLY:
            with self.subTest(path=path, method=method):
                self.assertNotIn(self.probe(path, method, "manager"), REFUSED)
