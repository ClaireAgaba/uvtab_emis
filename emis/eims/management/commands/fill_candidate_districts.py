from django.core.management.base import BaseCommand
from django.db import transaction, OperationalError, connection
import time

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

        # Reduce likelihood of "database is locked" on SQLite by setting busy timeout
        # Safe no-op on non-SQLite backends
        try:
            with connection.cursor() as cur:
                cur.execute("PRAGMA busy_timeout = 5000")  # 5 seconds
        except Exception:
            pass

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
        """
        Bulk update with retry/backoff to handle SQLite 'database is locked'.
        Fallback to per-row saves if bulk update continues to fail.
        """
        if not candidates:
            return
        max_retries = 5
        delay = 0.5
        for attempt in range(1, max_retries + 1):
            try:
                with transaction.atomic():
                    Candidate.objects.bulk_update(candidates, ["district"]) 
                return
            except OperationalError as exc:
                # Typical for SQLite when another writer holds the lock
                if "locked" in str(exc).lower() and attempt < max_retries:
                    time.sleep(delay)
                    delay *= 2  # exponential backoff
                    continue
                # Fallback: per-row update to make progress
                for cand in candidates:
                    try:
                        with transaction.atomic():
                            Candidate.objects.filter(pk=cand.pk).update(district=cand.district)
                    except OperationalError:
                        # Last resort: small sleep then try save()
                        time.sleep(0.1)
                        cand.save(update_fields=["district"]) 
                return
