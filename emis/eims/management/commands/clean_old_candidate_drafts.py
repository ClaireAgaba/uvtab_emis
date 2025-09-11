from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from eims.models import CandidateDraft


class Command(BaseCommand):
    help = (
        "Delete CandidateDraft entries. By default, removes records older than the specified age\n"
        "(default: 2 hours). Use --all to delete ALL drafts regardless of age.\n"
        "Use --dry-run to preview the deletions without applying them."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=2,
            help="Age threshold in hours. Drafts older than this will be deleted (default: 2).",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Alternative to --hours. If provided, overrides hours (e.g., --days 2 == 48 hours).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting.",
        )
        parser.add_argument(
            "--verbose-list",
            action="store_true",
            help="List individual draft IDs and owners that match the threshold.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            dest="delete_all",
            help="Delete ALL drafts with status='draft' regardless of creation/update time.",
        )

    def handle(self, *args, **options):
        delete_all = options.get("delete_all")

        dry_run = options["dry_run"]
        verbose_list = options["verbose_list"]

        if delete_all:
            # Delete ALL CandidateDraft rows regardless of status or timestamps
            qs = CandidateDraft.objects.all()
            total = qs.count()

            if total == 0:
                self.stdout.write(self.style.SUCCESS("No CandidateDraft records found (table already empty)."))
                return

            self.stdout.write(
                self.style.WARNING(
                    f"Found {total} CandidateDraft record(s) in total. These will be deleted."
                )
            )
        else:
            # Determine threshold (age-based cleanup)
            if options.get("days") is not None:
                threshold = timezone.now() - timedelta(days=options["days"])
                threshold_readable = f"{options['days']} day(s)"
            else:
                hours = options["hours"]
                threshold = timezone.now() - timedelta(hours=hours)
                threshold_readable = f"{hours} hour(s)"

            qs = CandidateDraft.objects.filter(updated_at__lt=threshold)
            total = qs.count()

            if total == 0:
                self.stdout.write(self.style.SUCCESS(
                    f"No CandidateDraft records older than {threshold_readable} (threshold: {threshold:%Y-%m-%d %H:%M:%S %Z})."
                ))
                return

            self.stdout.write(
                self.style.WARNING(
                    f"Found {total} CandidateDraft record(s) older than {threshold_readable} (threshold: {threshold:%Y-%m-%d %H:%M:%S %Z})."
                )
            )

        if verbose_list:
            for d in qs.select_related("user", "assessment_center"):
                user_str = getattr(d.user, "username", "<deleted user>")
                center_str = getattr(d.assessment_center, "center_name", "—")
                self.stdout.write(f" - Draft #{d.pk} | user={user_str} | center={center_str} | updated_at={d.updated_at:%Y-%m-%d %H:%M}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run enabled: no deletions performed."))
            return

        deleted_count, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_count} CandidateDraft record(s)."))
