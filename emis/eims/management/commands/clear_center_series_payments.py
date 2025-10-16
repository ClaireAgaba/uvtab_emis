from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal

from eims.models import Candidate, AssessmentCenter, AssessmentSeries

# Optional import: may not exist in all installs
try:
    from eims.models import CenterSeriesPayment
except Exception:  # pragma: no cover
    CenterSeriesPayment = None

class Command(BaseCommand):
    help = (
        "Clear center-level paid totals without touching enrollments or fees balance.\n"
        "- Deletes CenterSeriesPayment rows for the specified center (optionally a specific series).\n"
        "- Resets candidate payment flags (payment_cleared, payment_* fields) in the same scope.\n"
        "- Does NOT change candidate enrollments, assessment_series, or fees_balance.\n"
        "Dry-run by default; use --force to execute."
    )

    def add_arguments(self, parser):
        grp = parser.add_mutually_exclusive_group(required=True)
        grp.add_argument('--center-id', type=int, help='AssessmentCenter ID')
        grp.add_argument('--center-number', type=str, help='AssessmentCenter center_number (e.g., UVT454)')

        parser.add_argument('--series-id', type=int, default=None, help='Restrict to a specific AssessmentSeries ID')
        parser.add_argument('--limit', type=int, default=None, help='Limit candidates processed (testing)')
        parser.add_argument('--force', action='store_true', help='Actually perform the updates (otherwise DRY-RUN)')

    def _get_center(self, center_id=None, center_number=None):
        qs = AssessmentCenter.objects.all()
        if center_id is not None:
            return qs.get(id=center_id)
        return qs.get(center_number=center_number)

    def handle(self, *args, **opts):
        center_id = opts.get('center_id')
        center_number = opts.get('center_number')
        series_id = opts.get('series_id')
        force = opts.get('force', False)
        limit = opts.get('limit')

        if CenterSeriesPayment is None:
            raise CommandError('CenterSeriesPayment model not available in this installation.')

        try:
            center = self._get_center(center_id=center_id, center_number=center_number)
        except AssessmentCenter.DoesNotExist:
            raise CommandError('Center not found with the provided identifier')

        # Build scoped candidates
        cand_qs = Candidate.objects.filter(assessment_center=center)
        if series_id:
            cand_qs = cand_qs.filter(assessment_series_id=series_id)
        total_cands = cand_qs.count()
        if limit:
            cand_qs = cand_qs.order_by('id')[:limit]
        cand_ids = list(cand_qs.values_list('id', flat=True))

        # Payments rows to delete
        pay_qs = CenterSeriesPayment.objects.filter(assessment_center=center)
        if series_id:
            pay_qs = pay_qs.filter(assessment_series_id=series_id)
        pay_count = pay_qs.count()

        self.stdout.write(self.style.WARNING('================== DRY RUN ==================' if not force else '================== EXECUTION =================='))
        self.stdout.write(f"Center: {center.center_number} - {center.center_name}")
        if series_id:
            try:
                s = AssessmentSeries.objects.get(id=series_id)
                self.stdout.write(f"Series: {s.id} - {s.name}")
            except AssessmentSeries.DoesNotExist:
                raise CommandError('Invalid --series-id provided')
        self.stdout.write(f"Candidates in scope: {total_cands} | Payment rows to delete: {pay_count}")

        if not force:
            self.stdout.write(self.style.WARNING('Dry-run complete. Re-run with --force to execute.'))
            return

        updated = 0
        with transaction.atomic():
            # Delete payment rows
            removed = pay_qs.delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted CenterSeriesPayment rows: {removed}"))

            # Reset payment flags on candidates
            for cand in Candidate.objects.filter(id__in=cand_ids).iterator(chunk_size=500):
                if any([
                    cand.payment_cleared,
                    cand.payment_amount_cleared,
                    cand.payment_center_series_ref,
                ]):
                    cand.payment_cleared = False
                    cand.payment_cleared_date = None
                    cand.payment_cleared_by = None
                    cand.payment_amount_cleared = None
                    cand.payment_center_series_ref = None
                    cand.save(update_fields=[
                        'payment_cleared','payment_cleared_date','payment_cleared_by','payment_amount_cleared','payment_center_series_ref'
                    ])
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f'Reset payment flags for {updated} candidate(s).'))
