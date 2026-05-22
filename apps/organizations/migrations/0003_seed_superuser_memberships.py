"""Auto-assign all existing superusers to the oldest Organization as owner.

This lets Faz 1 superusers see their data after Faz 2 login enforcement.
Safe to run multiple times (get_or_create).
"""
from django.db import migrations


def assign_superusers(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Organization = apps.get_model("organizations", "Organization")
    Membership = apps.get_model("organizations", "OrganizationMembership")

    org = Organization.objects.order_by("created_at").first()
    if not org:
        return

    for su in User.objects.filter(is_superuser=True):
        Membership.objects.get_or_create(
            user=su, organization=org, defaults={"role": "owner"}
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0002_organizationmembership"),
    ]

    operations = [
        migrations.RunPython(assign_superusers, noop),
    ]
