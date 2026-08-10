from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

APPS = ["cars", "inquiries", "imports", "payments", "purchases"]

# Sales look after listings, customers and shipments.
# They can see money but never decide it.
SALES = [
    "view_car", "add_car", "change_car",
    "view_carimage", "add_carimage", "change_carimage",
    "view_inquiry",
    "view_importorder", "add_importorder", "change_importorder",
    "view_importmilestone", "add_importmilestone", "change_importmilestone",
    "view_payment",
    "view_purchaserequest",
]

# Managers additionally decide amounts, approve purchases, and can remove
# listings. Nobody, at any level, gets delete_payment.
MANAGER = SALES + [
    "delete_car", "delete_carimage",
    "delete_inquiry",
    "delete_importorder", "delete_importmilestone",
    "add_payment", "change_payment",
    "change_purchaserequest",
]

CUSTOMER = []

ROLES = [("Sales", SALES), ("Manager", MANAGER), ("Customer", CUSTOMER)]


class Command(BaseCommand):
    help = "Create the Sales, Manager and Customer groups with their permissions"

    def handle(self, *args, **options):
        for name, codenames in ROLES:
            group, created = Group.objects.get_or_create(name=name)

            perms = Permission.objects.filter(
                codename__in=codenames,
                content_type__app_label__in=APPS,
            )
            group.permissions.set(perms)

            state = "created" if created else "updated"
            self.stdout.write(
                self.style.SUCCESS(f"{name}: {state}, {perms.count()} permissions")
            )