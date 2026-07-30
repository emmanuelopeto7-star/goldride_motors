from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

APPS = ["cars", "inquiries", "imports", "payments"]

SALES = [
    "view_car", "add_car", "change_car",
    "view_carimage", "add_carimage", "change_carimage",
    "view_inquiry",
    "view_importorder", "add_importorder", "change_importorder",
    "view_importmilestone", "add_importmilestone", "change_importmilestone",
    "view_payment",
]

MANAGER = SALES + [
    "delete_car", "delete_carimage",
    "delete_inquiry",
    "delete_importorder", "delete_importmilestone",
    "add_payment", "change_payment",
]

class Command(BaseCommand):
    help = "Create the Sales and Manager groups with their permissions"

    def handle(self, *args, **options):
        for name, codenames in [("Sales", SALES), ("Manager", MANAGER)]:
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