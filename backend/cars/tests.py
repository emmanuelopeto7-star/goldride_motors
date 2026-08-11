import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from django.contrib.auth import get_user_model

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
