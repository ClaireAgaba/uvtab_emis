from django.core.management.base import BaseCommand
from django.db import transaction

from eims.models import Candidate


class Command(BaseCommand):
    help = (
        "Backfill Candidate.district using the district of their assessment_center. "
        "Only candidates with a null district and a non-null assessment_center that has a district will be updated."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without saving changes.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Optional maximum number of candidates to process (useful for testing).",
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=500,
            help="How many records to bulk update per transaction chunk.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        chunk_size = max(1, options["chunk_size"])  # ensure positive

        qs = (
            Candidate.objects
            .filter(district__isnull=True)
            .filter(assessment_center__isnull=False)
            .filter(assessment_center__district__isnull=False)
            .select_related("assessment_center__district")
            .order_by("id")
        )

        total_candidates = qs.count()
        if limit is not None:
            qs = qs[:limit]

        self.stdout.write(self.style.NOTICE(
            f"Found {total_candidates} candidate(s) missing district with a usable assessment center. "
            + (f"Processing only first {limit}." if limit else "Processing all.")
        ))

        to_update = []
        processed = 0
        updated = 0

        for cand in qs.iterator(chunk_size=1000):
            ac = cand.assessment_center
            if not ac or not getattr(ac, "district", None):
                continue
            cand.district = ac.district
            to_update.append(cand)
            processed += 1
            # Bulk flush per chunk_size
            if not dry_run and len(to_update) >= chunk_size:
                self._bulk_update(to_update)
                updated += len(to_update)
                to_update.clear()

        # Final flush
        if not dry_run and to_update:
            self._bulk_update(to_update)
            updated += len(to_update)
            to_update.clear()

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"[DRY RUN] Would update {len(to_update) + processed if processed else 0} candidate(s). No changes saved."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated {updated} candidate(s)."))

    @staticmethod
    def _bulk_update(candidates):
        if not candidates:
            return
        # Use a transaction per bulk chunk
        with transaction.atomic():
            Candidate.objects.bulk_update(candidates, ["district"]) 
