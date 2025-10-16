from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal

from eims.models import Candidate, AssessmentCenter

class Command(BaseCommand):
    help = (
        "Clear 'payment cleared' badges for candidates in a center without touching enrollments or assessment series.\n"
        "- Targets candidates with payment_cleared=True (and optionally non-null payment_amount_cleared/ref).\n"
        "- Resets payment flags and keeps existing fees_balance and enrollments intact.\n"
        "Dry-run by default; use --force to persist."
    )

    def add_arguments(self, parser):
        grp = parser.add_mutually_exclusive_group(required=True)
        grp.add_argument('--center-id', type=int, help='AssessmentCenter ID')
        grp.add_argument('--center-number', type=str, help='AssessmentCenter center_number (e.g., UVT454)')
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
        force = opts.get('force', False)
        limit = opts.get('limit')

        try:
            center = self._get_center(center_id=center_id, center_number=center_number)
        except AssessmentCenter.DoesNotExist:
            raise CommandError('Center not found with the provided identifier')

        qs = Candidate.objects.filter(assessment_center=center, payment_cleared=True)
        total = qs.count()
        if limit:
            qs = qs.order_by('id')[:limit]
        ids = list(qs.values_list('id', flat=True))

        self.stdout.write(self.style.WARNING('================== DRY RUN ==================' if not force else '================== EXECUTION =================='))
        self.stdout.write(f"Center: {center.center_number} - {center.center_name}")
        self.stdout.write(f"Candidates with payment_cleared=True: {total} | to update now: {len(ids)}")

        if not force:
            self.stdout.write(self.style.WARNING('Dry-run complete. Re-run with --force to execute.'))
            return

        updated = 0
        with transaction.atomic():
            for cand in Candidate.objects.filter(id__in=ids).iterator(chunk_size=500):
                cand.payment_cleared = False
                cand.payment_cleared_date = None
                cand.payment_cleared_by = None
                cand.payment_amount_cleared = None
                cand.payment_center_series_ref = None
                # Keep fees_balance as-is and do not touch enrollments/series
                cand.save(update_fields=[
                    'payment_cleared','payment_cleared_date','payment_cleared_by','payment_amount_cleared','payment_center_series_ref'
                ])
                updated += 1
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} candidate(s).'))
