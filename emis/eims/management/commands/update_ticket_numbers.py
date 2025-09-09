from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from eims.models import Complaint


class Command(BaseCommand):
    help = "Backfill Complaint.ticket_no to new format TKTyy#### using the CURRENT year."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the changes without saving them",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        year_short = timezone.now().strftime("%y")
        self.stdout.write(self.style.MIGRATE_HEADING(f"Using year yy={year_short}"))

        complaints = Complaint.objects.order_by("id").only("id", "ticket_no")
        total = complaints.count()
        if total == 0:
            self.stdout.write("No complaints found.")
            return

        changes = []
        for c in complaints:
            new_no = f"TKT{year_short}{c.id:04d}"
            if c.ticket_no != new_no:
                changes.append((c.id, c.ticket_no, new_no))

        self.stdout.write(f"Computed {len(changes)} updates out of {total} complaints.")
        if dry_run:
            for cid, old, new in changes[:20]:  # preview first 20
                self.stdout.write(f"#{cid}: {old} -> {new}")
            if len(changes) > 20:
                self.stdout.write(f"... and {len(changes) - 20} more")
            self.stdout.write(self.style.WARNING("Dry-run complete. No changes saved."))
            return

        with transaction.atomic():
            for cid, old, new in changes:
                Complaint.objects.filter(id=cid).update(ticket_no=new)
        self.stdout.write(self.style.SUCCESS(f"Updated {len(changes)} complaint ticket numbers to new format."))
