"""Adding and removing staff from the dashboard."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

User = get_user_model()
URL = "/api/staff/team/"


def staff(username, role, active=True):
    user = User.objects.create_user(username, f"{username}@goldride.co.ke", "pw")
    user.is_active = active
    user.save()
    Group.objects.get_or_create(name=role)[0].user_set.add(user)
    return user


class TeamTests(APITestCase):
    def setUp(self):
        self.boss = staff("boss", "Manager")
        self.sales = staff("asha", "Sales")

    def sign_in(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )

    def new_member(self, **overrides):
        fields = {
            "username": "brian",
            "email": "brian@goldride.co.ke",
            "first_name": "Brian",
            "last_name": "Otieno",
            "role": "Sales",
            "password": "a-long-enough-passphrase",
        }
        fields.update(overrides)
        return fields

    # --- who may look ------------------------------------------------------

    def test_a_manager_sees_the_team(self):
        self.sign_in(self.boss)

        response = self.client.get(URL)

        self.assertEqual(response.status_code, 200)
        by_name = {row["username"]: row for row in response.data}
        self.assertEqual(by_name["asha"]["role"], "Sales")
        self.assertEqual(by_name["boss"]["role"], "Manager")

    def test_sales_cannot(self):
        self.sign_in(self.sales)

        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_customers_are_not_listed(self):
        buyer = User.objects.create_user("buyer", "buyer@x.com", "pw")
        Group.objects.get_or_create(name="Customer")[0].user_set.add(buyer)
        self.sign_in(self.boss)

        usernames = [row["username"] for row in self.client.get(URL).data]

        self.assertNotIn("buyer", usernames)

    # --- adding ------------------------------------------------------------

    def test_a_manager_can_add_a_colleague(self):
        self.sign_in(self.boss)

        response = self.client.post(URL, self.new_member())

        self.assertEqual(response.status_code, 201)
        added = User.objects.get(username="brian")
        self.assertTrue(added.groups.filter(name="Sales").exists())
        self.assertEqual(response.data["full_name"], "Brian Otieno")

    def test_the_new_account_can_sign_in(self):
        """The point of setting a password at all."""
        self.sign_in(self.boss)
        self.client.post(URL, self.new_member())
        self.client.credentials()

        response = self.client.post(
            "/api/auth/login/",
            {"username": "brian", "password": "a-long-enough-passphrase"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)

    def test_a_weak_password_is_refused(self):
        self.sign_in(self.boss)

        response = self.client.post(URL, self.new_member(password="pw"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)

    def test_a_password_is_required(self):
        self.sign_in(self.boss)
        fields = self.new_member()
        del fields["password"]

        response = self.client.post(URL, fields)

        self.assertEqual(response.status_code, 400)

    def test_sales_cannot_add_anyone(self):
        self.sign_in(self.sales)

        self.assertEqual(self.client.post(URL, self.new_member()).status_code, 403)

    # --- changing ----------------------------------------------------------

    def test_a_manager_can_promote_someone(self):
        self.sign_in(self.boss)

        response = self.client.patch(f"{URL}{self.sales.pk}/", {"role": "Manager"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.sales.groups.filter(name="Manager").exists())
        self.assertFalse(self.sales.groups.filter(name="Sales").exists())

    def test_removing_someone_deactivates_rather_than_deletes(self):
        """Their name is on decisions, and those have to stay readable."""
        self.sign_in(self.boss)

        response = self.client.patch(f"{URL}{self.sales.pk}/", {"is_active": False})

        self.assertEqual(response.status_code, 200)
        self.sales.refresh_from_db()
        self.assertFalse(self.sales.is_active)
        self.assertTrue(User.objects.filter(pk=self.sales.pk).exists())

    def test_a_deactivated_colleague_cannot_sign_in(self):
        self.sign_in(self.boss)
        self.client.patch(f"{URL}{self.sales.pk}/", {"is_active": False})
        self.client.credentials()

        response = self.client.post(
            "/api/auth/login/", {"username": "asha", "password": "pw"}
        )

        self.assertEqual(response.status_code, 400)

    def test_they_can_be_brought_back(self):
        gone = staff("returner", "Sales", active=False)
        self.sign_in(self.boss)

        self.client.patch(f"{URL}{gone.pk}/", {"is_active": True})

        gone.refresh_from_db()
        self.assertTrue(gone.is_active)

    def test_nobody_may_act_on_their_own_account(self):
        """What stops the last manager locking everyone out, themselves
        included."""
        self.sign_in(self.boss)

        response = self.client.patch(f"{URL}{self.boss.pk}/", {"is_active": False})

        self.assertEqual(response.status_code, 403)
        self.boss.refresh_from_db()
        self.assertTrue(self.boss.is_active)

    def test_the_owners_account_is_left_alone(self):
        owner = User.objects.create_user("owner", "owner@x.com", "pw")
        owner.is_superuser = True
        owner.save()
        self.sign_in(self.boss)

        response = self.client.patch(f"{URL}{owner.pk}/", {"role": "Sales"})

        self.assertEqual(response.status_code, 403)

    def test_an_owner_reads_as_a_manager(self):
        owner = User.objects.create_user("owner2", "owner2@x.com", "pw")
        owner.is_superuser = True
        owner.save()
        self.sign_in(self.boss)

        rows = {row["username"]: row for row in self.client.get(URL).data}

        self.assertEqual(rows["owner2"]["role"], "Manager")

    def test_deleting_is_not_offered(self):
        self.sign_in(self.boss)

        response = self.client.delete(f"{URL}{self.sales.pk}/")

        self.assertEqual(response.status_code, 405)

    def test_a_new_colleague_is_active_even_when_the_form_omits_it(self):
        """DRF reads a missing BooleanField in form data as False. Without an
        explicit default that created colleagues who could not sign in."""
        self.sign_in(self.boss)

        response = self.client.post(URL, self.new_member(), format="multipart")

        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.get(username="brian").is_active)
