from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal

from eims.models import (
    Candidate,
    AssessmentCenter,
    AssessmentSeries,
)

# Optional imports – these models may not exist in all installs
try:
    from eims.models import CenterSeriesPayment
except Exception:  # pragma: no cover
    CenterSeriesPayment = None

try:
    from eims.models import CandidateLevel, CandidateModule, CandidatePaper
except Exception:  # pragma: no cover
    CandidateLevel = CandidateModule = CandidatePaper = None


class Command(BaseCommand):
    help = (
        "Reset a center's enrollments and invoices without deleting candidates.\n"
        "- Deletes CandidateLevel/CandidateModule/CandidatePaper in scope\n"
        "- Resets candidate.assessment_series to NULL (or only for series when specified)\n"
        "- Resets fees_balance to 0 and clears all payment flags\n"
        "- Optionally deletes CenterSeriesPayment rows\n"
        "Dry-run by default; use --force to execute."
    )

    def add_arguments(self, parser):
        grp = parser.add_mutually_exclusive_group(required=True)
        grp.add_argument('--center-id', type=int, help='AssessmentCenter ID')
        grp.add_argument('--center-number', type=str, help='AssessmentCenter center_number (e.g., UVT185)')

        parser.add_argument('--series-id', type=int, default=None, help='Restrict to a specific AssessmentSeries ID')
        parser.add_argument('--delete-payments', action='store_true', help='Also delete CenterSeriesPayment rows for the scope')
        parser.add_argument('--include-paid', action='store_true', help='Include candidates marked as payment_cleared=True')
        parser.add_argument('--limit', type=int, default=None, help='Limit candidates processed (testing)')
        parser.add_argument('--force', action='store_true', help='Actually perform the reset (otherwise DRY-RUN)')

    def _get_center(self, center_id=None, center_number=None):
        qs = AssessmentCenter.objects.all()
        if center_id is not None:
            return qs.get(id=center_id)
        return qs.get(center_number=center_number)

    def handle(self, *args, **opts):
        center_id = opts.get('center_id')
        center_number = opts.get('center_number')
        series_id = opts.get('series_id')
        delete_payments = opts.get('delete_payments', False)
        include_paid = opts.get('include_paid', False)
        limit = opts.get('limit')
        force = opts.get('force', False)

        try:
            center = self._get_center(center_id=center_id, center_number=center_number)
        except AssessmentCenter.DoesNotExist:
            raise CommandError('Center not found with the provided identifier')

        scope = Candidate.objects.select_related('assessment_series').filter(assessment_center=center)
        if not include_paid:
            scope = scope.filter(payment_cleared=False)
        total = scope.count()
        if limit:
            scope = scope.order_by('id')[:limit]
        ids = list(scope.values_list('id', flat=True))

        self.stdout.write(self.style.WARNING('================== DRY RUN ==================' if not force else '================== EXECUTION =================='))
        self.stdout.write(f"Center: {center.center_number} - {center.center_name}")
        if series_id:
            try:
                series = AssessmentSeries.objects.get(id=series_id)
                self.stdout.write(f"Series filter: {series.id} - {series.name}")
            except AssessmentSeries.DoesNotExist:
                raise CommandError('Invalid --series-id provided')
        self.stdout.write(f"Candidates matched: {total} | to process: {len(ids)}")
        self.stdout.write(f"Delete CenterSeriesPayment: {'YES' if delete_payments else 'NO'} | Include paid: {'YES' if include_paid else 'NO'}")

        if not force:
            self.stdout.write(self.style.WARNING('Dry-run complete. Re-run with --force to execute.'))
            return

        with transaction.atomic():
            # Delete scoped CenterSeriesPayment rows first (if requested)
            if delete_payments and CenterSeriesPayment is not None:
                pay_qs = CenterSeriesPayment.objects.filter(assessment_center=center)
                if series_id:
                    pay_qs = pay_qs.filter(assessment_series_id=series_id)
                removed = pay_qs.count()
                pay_qs.delete()
                self.stdout.write(self.style.SUCCESS(f"Deleted {removed} CenterSeriesPayment row(s)."))

            # Reset each candidate
            for cand in Candidate.objects.filter(id__in=ids).iterator(chunk_size=500):
                # Delete enrollments
                if CandidateLevel is not None:
                    qs = CandidateLevel.objects.filter(candidate=cand)
                    if series_id:
                        qs = qs.filter(assessment_series_id=series_id)
                    qs.delete()
                if CandidateModule is not None:
                    qs = CandidateModule.objects.filter(candidate=cand)
                    if series_id:
                        qs = qs.filter(assessment_series_id=series_id)
                    qs.delete()
                if CandidatePaper is not None:
                    qs = CandidatePaper.objects.filter(candidate=cand)
                    if series_id:
                        qs = qs.filter(assessment_series_id=series_id)
                    qs.delete()

                # Reset invoice/billing flags
                cand.fees_balance = Decimal('0.00')
                cand.payment_cleared = False
                cand.payment_cleared_date = None
                cand.payment_cleared_by = None
                cand.payment_amount_cleared = None
                cand.payment_center_series_ref = None

                # Clear cached modular billing hints if present
                if hasattr(cand, 'modular_module_count'):
                    cand.modular_module_count = None
                if hasattr(cand, 'modular_billing_amount'):
                    cand.modular_billing_amount = None

                # Reset assessment_series
                if series_id:
                    # Only clear if matches filter
                    if cand.assessment_series_id == series_id:
                        cand.assessment_series = None
                else:
                    cand.assessment_series = None

                cand.save(update_fields=[
                    'fees_balance', 'payment_cleared', 'payment_cleared_date', 'payment_cleared_by',
                    'payment_amount_cleared', 'payment_center_series_ref', 'assessment_series',
                    'modular_module_count', 'modular_billing_amount',
                ])

        self.stdout.write(self.style.SUCCESS('Reset complete.'))
