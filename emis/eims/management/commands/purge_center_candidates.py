from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from django.utils import timezone
from decimal import Decimal
import os

from eims.models import (
    Candidate,
    AssessmentCenter,
    AssessmentSeries,
)

# Optional import: payments model may not exist in all installations
try:
    from eims.models import CenterSeriesPayment
except Exception:  # pragma: no cover
    CenterSeriesPayment = None


class Command(BaseCommand):
    help = (
        "Purge candidates from a center (optionally restricted to an assessment series). "
        "This tool can delete even 'paid' candidates, and will optionally remove "
        "CenterSeriesPayment rows and media files. Defaults to DRY-RUN."
    )

    def add_arguments(self, parser):
        grp = parser.add_mutually_exclusive_group(required=True)
        grp.add_argument('--center-id', type=int, help='AssessmentCenter ID')
        grp.add_argument('--center-number', type=str, help='AssessmentCenter center_number (e.g., UVT001)')

        parser.add_argument('--series-id', type=int, default=None, help='Restrict to a specific AssessmentSeries ID')
        parser.add_argument('--limit', type=int, default=None, help='Delete at most N candidates (for testing)')
        parser.add_argument('--include-paid', action='store_true', help='Allow deleting candidates with payment_cleared=True')
        parser.add_argument('--delete-payments', action='store_true', help='Also delete CenterSeriesPayment rows for the scope')
        parser.add_argument('--delete-media', action='store_true', help='Delete candidate photo and document files from storage')
        parser.add_argument('--force', action='store_true', help='Actually perform deletion (otherwise DRY-RUN)')

    def _get_center(self, center_id=None, center_number=None):
        qs = AssessmentCenter.objects.all()
        if center_id is not None:
            return qs.get(id=center_id)
        return qs.get(center_number=center_number)

    def _delete_file_field(self, file_field):
        try:
            if file_field and hasattr(file_field, 'path') and os.path.isfile(file_field.path):
                os.remove(file_field.path)
        except Exception:
            # Ignore file deletion errors to avoid aborting a purge
            pass

    def handle(self, *args, **options):
        center_id = options.get('center_id')
        center_number = options.get('center_number')
        series_id = options.get('series_id')
        include_paid = options.get('include_paid', False)
        delete_payments = options.get('delete_payments', False)
        delete_media = options.get('delete_media', False)
        limit = options.get('limit')
        force = options.get('force', False)

        try:
            center = self._get_center(center_id=center_id, center_number=center_number)
        except AssessmentCenter.DoesNotExist:
            raise CommandError('Center not found with the provided identifier')

        candidates_qs = Candidate.objects.filter(assessment_center=center)
        if series_id:
            candidates_qs = candidates_qs.filter(assessment_series_id=series_id)

        protected_paid_qs = candidates_qs.filter(payment_cleared=True)
        if protected_paid_qs.exists() and not include_paid:
            raise CommandError(
                f"Refusing to purge: {protected_paid_qs.count()} candidates are marked as paid. "
                f"Re-run with --include-paid to override."
            )

        total_candidates = candidates_qs.count()
        if limit:
            candidates_qs = candidates_qs.order_by('id')[:limit]
        target_ids = list(candidates_qs.values_list('id', flat=True))

        # Summaries
        paid_sum = candidates_qs.aggregate(total=models.Sum('payment_amount_cleared'))['total'] or Decimal('0.00')
        paid_count = candidates_qs.filter(payment_cleared=True).count()

        self.stdout.write(self.style.WARNING('================== DRY RUN ==================' if not force else '================== EXECUTION =================='))
        self.stdout.write(f"Center: {center.center_number} - {center.center_name}")
        if series_id:
            try:
                series = AssessmentSeries.objects.get(id=series_id)
                self.stdout.write(f"Series: {series.id} - {series.name}")
            except AssessmentSeries.DoesNotExist:
                raise CommandError('Invalid --series-id provided')
        self.stdout.write(f"Total candidates in scope: {total_candidates}")
        self.stdout.write(f"Will purge: {len(target_ids)} candidates")
        self.stdout.write(f"Paid candidates in scope: {paid_count} | Sum payment_amount_cleared: {paid_sum}")
        self.stdout.write(f"Delete payments rows: {'YES' if delete_payments else 'NO'} | Delete media files: {'YES' if delete_media else 'NO'}")

        if not force:
            self.stdout.write(self.style.WARNING('Dry-run complete. Re-run with --force to execute.'))
            return

        with transaction.atomic():
            # Optionally delete CenterSeriesPayment rows for scope
            if delete_payments and CenterSeriesPayment is not None:
                pay_qs = CenterSeriesPayment.objects.filter(assessment_center=center)
                if series_id:
                    pay_qs = pay_qs.filter(assessment_series_id=series_id)
                removed = pay_qs.count()
                pay_qs.delete()
                self.stdout.write(self.style.SUCCESS(f"Deleted {removed} CenterSeriesPayment rows."))

            # Delete candidates (and related via cascade). Clean media if requested
            batch = Candidate.objects.filter(id__in=target_ids)

            if delete_media:
                for c in batch:
                    self._delete_file_field(c.passport_photo_with_regno)
                    self._delete_file_field(c.passport_photo)
                    self._delete_file_field(c.identification_document)
                    self._delete_file_field(c.qualification_document)

            deleted_info = batch.delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted candidates and related objects: {deleted_info}"))

        # After deletion, recommend syncing payment records to recalc center totals
        self.stdout.write(self.style.WARNING('Run: python manage.py sync_payment_records'))
        self.stdout.write(self.style.SUCCESS('Purge complete.'))
