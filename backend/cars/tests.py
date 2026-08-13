import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.utils import IntegrityError
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from .models import Car, Favourite, HeroBanner

# Uploads in tests must not land in the real media folder - without this every
# run leaves another hero_XXXX.jpg behind next to genuine content.
MEDIA_OVERRIDE = override_settings(MEDIA_ROOT=tempfile.mkdtemp())


def make_car(make="Toyota", model="Prado", availability="available"):
    return Car.objects.create(
        make=make,
        model=model,
        year=2019,
        price=Decimal("4250000.00"),
        description="A car.",
        availability=availability,
    )


class CarMakesTests(APITestCase):
    url = "/api/cars/makes/"

    def test_returns_each_make_once_with_a_count(self):
        make_car(make="Toyota", model="Prado")
        make_car(make="Toyota", model="Hilux")
        make_car(make="Mazda", model="Demio")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            [{"make": "Toyota", "count": 2}, {"make": "Mazda", "count": 1}],
        )

    def test_is_not_paginated(self):
        """The brand strip needs every make, not the first page of them."""
        for index in range(15):
            make_car(make=f"Make{index:02d}")

        response = self.client.get(self.url)

        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 15)

    def test_counts_match_filtering_the_car_list_by_that_make(self):
        make_car(make="Toyota", model="Prado")
        make_car(make="Toyota", model="Hilux", availability="sold")

        makes = self.client.get(self.url).data
        listed = self.client.get("/api/cars/", {"make": "Toyota"}).data

        self.assertEqual(makes[0]["count"], listed["count"])

    def test_empty_lot_returns_an_empty_list(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_makes_is_not_read_as_a_car_id(self):
        """`makes/` sits before `<int:pk>/`, so it must not 404 as a lookup."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_is_public(self):
        make_car()

        self.assertEqual(self.client.get(self.url).status_code, 200)


class CarModelsTests(APITestCase):
    url = "/api/cars/models/"

    def test_groups_by_make_and_model_with_counts(self):
        make_car(make="Toyota", model="Prado")
        make_car(make="Toyota", model="Prado")
        make_car(make="Toyota", model="Hilux")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(row["make"], row["model"], row["count"]) for row in response.data],
            [("Toyota", "Prado", 2), ("Toyota", "Hilux", 1)],
        )

    def test_is_not_paginated(self):
        for index in range(15):
            make_car(model=f"Model{index:02d}")

        response = self.client.get(self.url)

        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 15)

    def test_image_is_null_when_no_car_of_that_model_has_one(self):
        make_car(make="Mazda", model="Demio")

        response = self.client.get(self.url)

        self.assertIsNone(response.data[0]["image"])

    def test_is_public(self):
        make_car()

        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_models_is_not_read_as_a_car_id(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)


class FavouriteTests(APITestCase):
    url = "/api/favourites/"

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("saver", password="pw-for-tests-1")
        self.other = User.objects.create_user("stranger", password="pw-for-tests-2")
        self.car = make_car()

    def test_requires_signing_in(self):
        """There is nobody to save a car against otherwise."""
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.client.post(self.url, {"car": self.car.pk}).status_code, 401)

    def test_saves_a_car(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(self.url, {"car": self.car.pk})

        self.assertEqual(response.status_code, 201)
        self.assertTrue(Favourite.objects.filter(user=self.user, car=self.car).exists())

    def test_saving_twice_is_a_no_op(self):
        self.client.force_authenticate(self.user)
        self.client.post(self.url, {"car": self.car.pk})

        response = self.client.post(self.url, {"car": self.car.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Favourite.objects.filter(user=self.user).count(), 1)

    def test_lists_only_your_own(self):
        Favourite.objects.create(user=self.other, car=self.car)
        mine = make_car(make="Mazda", model="Demio")
        Favourite.objects.create(user=self.user, car=mine)

        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)

        results = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["car"], mine.pk)

    def test_returns_the_whole_car_for_the_grid(self):
        Favourite.objects.create(user=self.user, car=self.car)
        self.client.force_authenticate(self.user)

        response = self.client.get(self.url)
        results = response.data["results"] if "results" in response.data else response.data

        self.assertEqual(results[0]["car_detail"]["make"], "Toyota")
        self.assertIn("images", results[0]["car_detail"])

    def test_removes_by_car_id(self):
        Favourite.objects.create(user=self.user, car=self.car)
        self.client.force_authenticate(self.user)

        response = self.client.delete(f"{self.url}{self.car.pk}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Favourite.objects.filter(user=self.user).exists())

    def test_cannot_remove_someone_elses(self):
        Favourite.objects.create(user=self.other, car=self.car)
        self.client.force_authenticate(self.user)

        response = self.client.delete(f"{self.url}{self.car.pk}/")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Favourite.objects.filter(user=self.other).exists())


@MEDIA_OVERRIDE
class HeroBannerTests(APITestCase):
    url = "/api/hero/"

    def banner(self, headline="Arrivals", is_active=True):
        return HeroBanner.objects.create(
            image=SimpleUploadedFile("hero.jpg", b"not-a-real-jpeg"),
            headline=headline,
            subline="Hand picked",
            is_active=is_active,
        )

    def test_returns_null_when_nothing_is_active(self):
        """The home page must render without a banner, not error."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data)

    def test_returns_the_active_banner(self):
        self.banner(headline="Latest arrivals")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["headline"], "Latest arrivals")
        self.assertEqual(response.data["subline"], "Hand picked")

    def test_ignores_drafts(self):
        self.banner(headline="Draft", is_active=False)

        self.assertIsNone(self.client.get(self.url).data)

    def test_serves_the_most_recent_of_several_active_banners(self):
        self.banner(headline="Older")
        newer = self.banner(headline="Newer")

        response = self.client.get(self.url)

        self.assertEqual(response.data["headline"], newer.headline)

    def test_image_is_an_absolute_url(self):
        """The React app is on another origin, so a relative path is useless."""
        self.banner()

        response = self.client.get(self.url)

        self.assertTrue(response.data["image"].startswith("http"))

    def test_is_read_only(self):
        response = self.client.post(self.url, {"headline": "Nope"})

        self.assertEqual(response.status_code, 405)

    def test_video_is_optional_and_empty_when_absent(self):
        """A still-only banner is the normal case, not a degraded one."""
        self.banner()

        response = self.client.get(self.url)

        self.assertIn("video", response.data)
        self.assertFalse(response.data["video"])

    def test_video_is_served_when_present(self):
        banner = self.banner()
        banner.video = SimpleUploadedFile("hero.mp4", b"not-a-real-mp4")
        banner.save(update_fields=["video"])

        response = self.client.get(self.url)

        self.assertTrue(response.data["video"].endswith(".mp4"))
        self.assertTrue(response.data["video"].startswith("http"))

    def test_poster_is_still_served_alongside_a_video(self):
        """The poster is the fallback, so it must never be replaced by the video."""
        banner = self.banner()
        banner.video = SimpleUploadedFile("hero.mp4", b"not-a-real-mp4")
        banner.save(update_fields=["video"])

        response = self.client.get(self.url)

        self.assertTrue(response.data["image"])
        self.assertNotEqual(response.data["image"], response.data["video"])


class VinUniquenessTests(APITestCase):
    """Doc gap 3.1 (HIGH): listings were matched by make/model/year alone, so
    nothing stopped the same physical car being listed twice."""

    def staff_client(self):
        User = get_user_model()
        user = User.objects.create_user("sales", "sales@goldride.co.ke", "pw")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(user)
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_two_listings_cannot_share_a_vin(self):
        make_car()
        Car.objects.filter(make="Toyota").update(vin="JTEBH9FJ40K123456")

        with self.assertRaises(IntegrityError):
            Car.objects.create(
                make="Toyota",
                model="Prado",
                year=2019,
                price=Decimal("4250000.00"),
                description="The same car again.",
                vin="JTEBH9FJ40K123456",
            )

    def test_many_listings_may_have_no_vin(self):
        """Blank is the normal state before the logbook arrives - the constraint
        must not turn that into a collision."""
        make_car(model="Prado")
        make_car(model="Hilux")
        make_car(model="Demio")

        self.assertEqual(Car.objects.filter(vin="").count(), 3)

    def test_vin_is_stored_uppercase_and_trimmed(self):
        car = make_car()
        car.vin = "  jtebh9fj40k123456 "
        car.save()

        car.refresh_from_db()
        self.assertEqual(car.vin, "JTEBH9FJ40K123456")

    def test_differently_cased_vins_still_collide(self):
        """Normalising on save is what makes the plain constraint case-blind."""
        car = make_car()
        car.vin = "JTEBH9FJ40K123456"
        car.save()

        with self.assertRaises(IntegrityError):
            second = make_car(model="Land Cruiser")
            second.vin = "jtebh9fj40k123456"
            second.save()

    def test_staff_api_rejects_a_duplicate_vin_with_400(self):
        """A database IntegrityError would be a 500. Staff need the field name."""
        first = make_car()
        first.vin = "JTEBH9FJ40K123456"
        first.save()
        self.staff_client()

        response = self.client.post(
            "/api/staff/cars/",
            {
                "make": "Toyota",
                "model": "Prado",
                "year": 2019,
                "price": "4250000.00",
                "description": "Duplicate.",
                "vin": "jtebh9fj40k123456",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("vin", response.data)

    def test_staff_api_accepts_a_fresh_vin(self):
        self.staff_client()

        response = self.client.post(
            "/api/staff/cars/",
            {
                "make": "Toyota",
                "model": "Hilux",
                "year": 2020,
                "price": "3950000.00",
                "description": "A pickup.",
                "vin": "mr0fz29g001234567"[:17],
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["vin"], "MR0FZ29G001234567")

    def test_editing_a_car_may_keep_its_own_vin(self):
        """Excluding self from the clash check - otherwise no car with a VIN
        could ever be edited again."""
        car = make_car()
        car.vin = "JTEBH9FJ40K123456"
        car.save()
        self.staff_client()

        response = self.client.patch(
            f"/api/staff/cars/{car.pk}/",
            {"vin": "JTEBH9FJ40K123456", "price": "4100000.00"},
        )

        self.assertEqual(response.status_code, 200)

    def test_staff_can_search_by_chassis_number(self):
        car = make_car()
        car.vin = "JTEBH9FJ40K123456"
        car.save()
        make_car(model="Demio")
        self.staff_client()

        response = self.client.get("/api/staff/cars/?search=JTEBH9FJ40K123456")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], car.pk)


class ListingExpiryTests(APITestCase):
    """Doc gap 3.1 (MEDIUM): listings stayed active indefinitely, so cars sold
    months earlier kept answering searches."""

    def staff_client(self):
        User = get_user_model()
        user = User.objects.create_user("sales2", "sales2@goldride.co.ke", "pw")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(user)
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def expired_car(self, **kwargs):
        car = make_car(**kwargs)
        car.expires_at = timezone.now() - timedelta(days=1)
        car.save(update_fields=["expires_at"])
        return car

    def test_a_new_listing_gets_an_expiry_without_being_asked(self):
        car = make_car()

        self.assertIsNotNone(car.expires_at)
        self.assertFalse(car.is_expired)

    def test_expired_listings_are_absent_from_the_public_list(self):
        live = make_car(model="Prado")
        self.expired_car(model="Demio")

        response = self.client.get("/api/cars/")

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], live.pk)

    def test_an_expired_listing_404s_rather_than_rendering(self):
        """A stale search result must not turn into an enquiry."""
        car = self.expired_car()

        response = self.client.get(f"/api/cars/{car.pk}/")

        self.assertEqual(response.status_code, 404)

    def test_make_counts_ignore_expired_listings(self):
        """Counts have to match what filtering by that make returns."""
        make_car(make="Toyota", model="Prado")
        self.expired_car(make="Toyota", model="Hilux")

        response = self.client.get("/api/cars/makes/")

        self.assertEqual(response.data, [{"make": "Toyota", "count": 1}])

    def test_model_carousel_ignores_expired_listings(self):
        make_car(make="Toyota", model="Prado")
        self.expired_car(make="Mazda", model="Demio")

        response = self.client.get("/api/cars/models/")

        self.assertEqual([row["model"] for row in response.data], ["Prado"])

    def test_a_listing_with_no_expiry_never_lapses(self):
        """The escape hatch for a unit that should stay up regardless."""
        car = make_car()
        car.expires_at = None
        car.save(update_fields=["expires_at"])

        self.assertFalse(car.is_expired)
        self.assertEqual(self.client.get("/api/cars/").data["count"], 1)

    def test_saving_an_existing_car_does_not_revive_it(self):
        """Only inserts get a default - otherwise any edit would silently renew."""
        car = self.expired_car()

        car.price = Decimal("3999000.00")
        car.save()

        car.refresh_from_db()
        self.assertTrue(car.is_expired)

    def test_extend_renews_from_now_not_from_the_old_expiry(self):
        car = self.expired_car()

        car.extend()

        self.assertFalse(car.is_expired)
        self.assertGreater(car.expires_at, timezone.now() + timedelta(days=40))

    def test_staff_can_renew_a_lapsed_listing(self):
        car = self.expired_car()
        self.staff_client()

        response = self.client.post(f"/api/staff/cars/{car.pk}/extend/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_expired"])
        self.assertEqual(self.client.get("/api/cars/").data["count"], 1)

    def test_staff_can_renew_for_a_chosen_number_of_days(self):
        car = make_car()
        self.staff_client()

        response = self.client.post(f"/api/staff/cars/{car.pk}/extend/", {"days": 7})

        self.assertEqual(response.status_code, 200)
        car.refresh_from_db()
        self.assertLess(car.expires_at, timezone.now() + timedelta(days=8))

    def test_a_nonsense_renewal_window_is_refused(self):
        car = make_car()
        self.staff_client()

        response = self.client.post(f"/api/staff/cars/{car.pk}/extend/", {"days": 0})

        self.assertEqual(response.status_code, 400)

    def test_renewing_requires_staff(self):
        car = make_car()

        response = self.client.post(f"/api/staff/cars/{car.pk}/extend/")

        self.assertIn(response.status_code, (401, 403))

    def test_staff_still_see_expired_listings(self):
        """They are the only people who can renew one."""
        self.expired_car()
        self.staff_client()

        response = self.client.get("/api/staff/cars/")

        self.assertEqual(len(response.data["results"]), 1)

    def test_staff_can_filter_down_to_the_renewal_worklist(self):
        make_car(model="Prado")
        lapsed = self.expired_car(model="Demio")
        self.staff_client()

        response = self.client.get("/api/staff/cars/?expired=true")

        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], lapsed.pk)
