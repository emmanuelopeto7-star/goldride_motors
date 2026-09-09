"""Where uploaded files go.

The rule is one line in settings - Cloudinary when a cloud name is configured,
the filesystem when it is not - and the cost of getting it wrong is invisible
until somebody uploads a photograph in production and it 404s. That happened
twice: the home page hero, then a car's photographs.

These tests reload the settings module under each condition rather than
asserting on the value it happened to load at import.
"""

import importlib
import os
from unittest.mock import patch

from django.test import SimpleTestCase

CLOUD = "cloudinary_storage.storage.MediaCloudinaryStorage"
LOCAL = "django.core.files.storage.FileSystemStorage"


def storage_backend_with(env):
    """The default STORAGES backend settings.py would pick, given `env`."""
    with patch.dict(os.environ, env, clear=False):
        import goldride_project.settings as settings_module

        # decouple reads os.environ at call time, so re-executing the module is
        # what makes the environment above take effect.
        reloaded = importlib.reload(settings_module)
        return reloaded.STORAGES["default"]["BACKEND"]


class UploadStorageTests(SimpleTestCase):
    def test_uses_cloudinary_when_a_cloud_name_is_set(self):
        backend = storage_backend_with(
            {
                "CLOUDINARY_CLOUD_NAME": "goldride",
                "CLOUDINARY_API_KEY": "key",
                "CLOUDINARY_API_SECRET": "secret",
            }
        )

        self.assertEqual(backend, CLOUD)

    def test_falls_back_to_the_filesystem_when_it_is_not(self):
        # Development, and any deploy where the credentials were forgotten.
        # Falling back is deliberate: the alternative is a site that will not
        # boot, which is worse than one whose uploads do not persist.
        backend = storage_backend_with({"CLOUDINARY_CLOUD_NAME": ""})

        self.assertEqual(backend, LOCAL)

    def test_a_key_without_a_cloud_name_is_not_enough(self):
        # Half-configured is the state a deploy actually lands in, and it must
        # not select a backend that cannot address a bucket.
        backend = storage_backend_with(
            {"CLOUDINARY_CLOUD_NAME": "", "CLOUDINARY_API_KEY": "key"}
        )

        self.assertEqual(backend, LOCAL)

    def tearDown(self):
        # Leave the module as the rest of the suite expects to find it.
        import goldride_project.settings as settings_module

        importlib.reload(settings_module)


class PaperworkStaysPrivateTests(SimpleTestCase):
    """Dealer documents must never follow car photographs to a public CDN.

    A logbook, a national ID and a KRA PIN certificate are personal documents.
    Cloudinary delivers by public URL - unlisted, but readable by anyone who
    has it - and nothing in the app ever emits that URL, which is exactly what
    would make such a leak quiet.
    """

    def test_documents_are_pinned_to_the_local_filesystem(self):
        from django.core.files.storage import FileSystemStorage
        from dealers.models import DealerDocument

        storage = DealerDocument._meta.get_field("file").storage

        self.assertIsInstance(storage, FileSystemStorage)

    def test_car_photographs_are_not_pinned(self):
        # The other half of the rule: photographs *should* follow the default,
        # which is what puts them on Cloudinary in production.
        from cars.models import Car, CarImage

        for model, field in ((Car, "image"), (CarImage, "image")):
            with self.subTest(model=model.__name__):
                storage = model._meta.get_field(field).storage
                self.assertEqual(type(storage).__name__, "DefaultStorage")
