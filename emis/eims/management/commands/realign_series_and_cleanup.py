from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone
from decimal import Decimal
from pathlib import Path
import csv
from datetime import date

from eims.models import Candidate, AssessmentSeries

class Command(BaseCommand):
    help = (
        "Realign candidates without an assigned assessment series and clean bad enrollments.\n"
        "Rules:\n"
        " - Consider only candidates with an invoice set (any enrollment OR fees_balance>0).\n"
        " - If candidate.assessment_series is NULL and assessment_date falls within an existing series window\n"
        "   for the same month/year (typically Mar..Oct 2025), assign that series.\n"
        " - If candidate.assessment_series is NULL and assessment_date month is Nov or Dec 2025,\n"
        "   clean up: delete enrollments (levels/modules), reset billing to zero, and clear payment flags.\n"
        "Dry-run by default; use --apply to persist."
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Persist changes')
        parser.add_argument('--year', type=int, help='Target assessment year (omit to include all years)')
        parser.add_argument('--center', type=int, help='Filter by assessment center id')
        parser.add_argument('--export', type=str, help='Export CSV audit to this path')
        parser.add_argument('--limit', type=int, help='Limit candidates for testing')
        parser.add_argument('--include-unbilled', action='store_true', help='Include candidates with fees_balance>0 but no enrollments')

    def _find_series_for_date(self, d: date):
        # 1) Exact month/year match, pick series whose start_date month/year equals d
        s = (
            AssessmentSeries.objects
            .filter(start_date__year=d.year, start_date__month=d.month)
            .order_by('start_date')
            .first()
        )
        if s:
            return s
        # 2) Fallback: date window coverage
        return AssessmentSeries.objects.filter(start_date__lte=d, end_date__gte=d).order_by('start_date').first()

    def handle(self, *args, **opts):
        apply = opts.get('apply')
        target_year = opts.get('year')
        center_id = opts.get('center')
        export = opts.get('export')
        limit = opts.get('limit')
        include_unbilled = opts.get('include_unbilled')

        # Base queryset: series missing
        qs = (
            Candidate.objects
            .select_related('assessment_center', 'assessment_series', 'occupation')
            .annotate(level_count=Count('candidatelevel'), module_count=Count('candidatemodule', distinct=True))
            .filter(assessment_series__isnull=True)
        )
        # Scope: enrolled candidates by default (center invoices focus)
        enrolled_q = Q(level_count__gt=0) | Q(module_count__gt=0)
        if include_unbilled:
            qs = qs.filter(enrolled_q | Q(fees_balance__gt=0))
        else:
            qs = qs.filter(enrolled_q)
        if target_year:
            qs = qs.filter(assessment_date__year=target_year)
        if center_id:
            qs = qs.filter(assessment_center_id=center_id)
        if limit:
            qs = qs.order_by('id')[:limit]

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No candidates require realignment.'))
            return

        self.stdout.write(self.style.WARNING(f'Targeting {total} candidate(s) for assessment-series realignment... apply={apply}'))

        writer = None
        f = None
        if export:
            out_path = Path(export)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            f = out_path.open('w', newline='', encoding='utf-8')
            writer = csv.DictWriter(f, fieldnames=[
                'id','reg_number','name','center','assessment_date','action','series_assigned','notes'
            ])
            writer.writeheader()

        assigned = 0
        cleaned = 0

        for cand in qs.iterator(chunk_size=1000):
            month = cand.assessment_date.month
            yr = cand.assessment_date.year
            action = ''
            series_assigned = ''
            notes = ''

            if month in (11, 12):
                # November/December: clean up anomalous enrollments
                action = 'CLEANUP_NOV_DEC'
                notes = 'Deleted enrollments; reset invoice to zero; cleared payment flags.'
                if apply:
                    # Delete enrollments
                    cand.candidatelevel_set.all().delete()
                    cand.candidatemodule_set.all().delete()
                    # Reset billing/payment
                    cand.fees_balance = Decimal('0.00')
                    cand.payment_cleared = False
                    cand.payment_cleared_date = None
                    cand.payment_cleared_by = None
                    cand.payment_amount_cleared = None
                    cand.payment_center_series_ref = None
                    cand.save(update_fields=['fees_balance','payment_cleared','payment_cleared_date','payment_cleared_by','payment_amount_cleared','payment_center_series_ref'])
                cleaned += 1
            else:
                # Try to assign the series that covers the assessment_date
                s = self._find_series_for_date(cand.assessment_date)
                if s:
                    action = 'ASSIGN_SERIES'
                    series_assigned = s.name
                    if apply:
                        cand.assessment_series = s
                        cand.save(update_fields=['assessment_series'])
                    assigned += 1
                else:
                    action = 'NO_SERIES_FOUND'
                    notes = 'No AssessmentSeries found by month/year or window for this assessment_date.'

            if writer:
                writer.writerow({
                    'id': cand.id,
                    'reg_number': cand.reg_number or '',
                    'name': cand.full_name,
                    'center': cand.assessment_center.center_name if cand.assessment_center else '',
                    'assessment_date': cand.assessment_date.isoformat() if cand.assessment_date else '',
                    'action': action,
                    'series_assigned': series_assigned,
                    'notes': notes,
                })

        if f:
            f.close()
            self.stdout.write(self.style.SUCCESS(f'Exported audit CSV to {export}'))

        self.stdout.write(self.style.SUCCESS(f'Assigned: {assigned}, Cleaned: {cleaned}'))
        if not apply:
            self.stdout.write(self.style.NOTICE('Dry-run only. Use --apply to persist changes.'))
