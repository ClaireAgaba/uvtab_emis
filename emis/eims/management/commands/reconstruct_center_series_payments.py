from django.core.management.base import BaseCommand
from django.db.models import Q, Sum, Count
from decimal import Decimal
from pathlib import Path
import csv

from eims.models import Candidate, AssessmentCenter, AssessmentSeries, CenterSeriesPayment

class Command(BaseCommand):
    help = (
        "Audit and reconstruct CenterSeriesPayment.amount_paid for center-series combinations that show 0,0 while candidates were billed and cleared.\n"
        "Strategy (safe):\n"
        " 1) For each (center, series or None) with billed/enrolled candidates, compute: \n"
        "    - candidate_count, outstanding_sum (Sum fees_balance),\n"
        "    - paid_sum_candidates = Sum of candidate.payment_amount_cleared for payment_cleared=True.\n"
        " 2) If outstanding_sum == 0 and paid_sum_candidates > 0 but CenterSeriesPayment.amount_paid is 0/NULL, set it to paid_sum_candidates.\n"
        " 3) If paid_sum_candidates == 0, optionally fall back to summing recalculated fees for candidates where fees cleared (behind --use-fee-calc).\n"
        "Dry-run by default. Use --apply to persist. CSV audit supported."
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Persist fixes to CenterSeriesPayment')
        parser.add_argument('--center', type=int, help='Filter by assessment center id')
        parser.add_argument('--series', type=int, help='Filter by assessment series id; use 0 to target "No series" entries')
        parser.add_argument('--export', type=str, help='Path to write CSV audit file')
        parser.add_argument('--limit', type=int, help='Limit number of center-series groups (for testing)')
        parser.add_argument('--use-fee-calc', action='store_true', help='If no candidate payment amounts exist, fall back to recomputing expected fees per candidate')

    def handle(self, *args, **opts):
        apply = opts.get('apply')
        center_id = opts.get('center')
        series_id = opts.get('series')
        export = opts.get('export')
        limit = opts.get('limit')
        use_fee_calc = opts.get('use_fee_calc')

        # Base: candidates considered billed/enrolled as per fees screens
        billed_qs = Candidate.objects.filter(
            Q(candidatelevel__isnull=False) |
            Q(registration_category__iexact='modular', modular_module_count__in=[1, 2]) |
            Q(registration_category__iexact='modular', candidatemodule__isnull=False) |
            Q(fees_balance__gt=0) |
            Q(payment_cleared=True),
            assessment_center__isnull=False,
        ).select_related('assessment_center', 'assessment_series')

        if center_id:
            billed_qs = billed_qs.filter(assessment_center_id=center_id)
        if series_id is not None:
            if series_id == 0:
                billed_qs = billed_qs.filter(assessment_series__isnull=True)
            else:
                billed_qs = billed_qs.filter(assessment_series_id=series_id)

        # Build center-series groups
        groups = (
            billed_qs.values('assessment_center_id', 'assessment_series_id')
            .annotate(
                candidate_count=Count('id', distinct=True),
                outstanding_sum=Sum('fees_balance'),
                paid_sum_candidates=Sum('payment_amount_cleared', filter=Q(payment_cleared=True)),
            )
            .order_by('assessment_center_id', 'assessment_series_id')
        )

        if limit:
            groups = list(groups[:limit])
        else:
            groups = list(groups)

        # Prepare CSV
        writer = None
        f = None
        if export:
            out = Path(export)
            out.parent.mkdir(parents=True, exist_ok=True)
            f = out.open('w', newline='', encoding='utf-8')
            writer = csv.DictWriter(f, fieldnames=[
                'center_id','center_number','center_name','series_id','series_name','candidate_count',
                'outstanding_sum','paid_sum_candidates','payment_record_before','action','amount_set'
            ])
            writer.writeheader()

        fixed = 0
        examined = 0

        # Caches for center and series
        centers = {c.id: c for c in AssessmentCenter.objects.filter(id__in={g['assessment_center_id'] for g in groups})}
        series_map = {s.id: s for s in AssessmentSeries.objects.filter(id__in={g['assessment_series_id'] for g in groups if g['assessment_series_id']})}

        for g in groups:
            examined += 1
            center = centers.get(g['assessment_center_id'])
            series = series_map.get(g['assessment_series_id']) if g['assessment_series_id'] else None
            outstanding = g['outstanding_sum'] or Decimal('0.00')
            paid_from_candidates = g['paid_sum_candidates'] or Decimal('0.00')

            # Load or create payment record (do not create on dry-run unless needed for reporting)
            pr = CenterSeriesPayment.objects.filter(
                assessment_center_id=center.id,
                assessment_series_id=(series.id if series else None)
            ).first()
            current_paid = pr.amount_paid if pr else Decimal('0.00')

            action = 'SKIP'
            amount_set = Decimal('0.00')

            # Anomaly heuristic: all cleared (outstanding==0) AND we have evidence of payments at candidate level, but payment record shows 0
            if outstanding == 0 and paid_from_candidates > 0 and (current_paid or Decimal('0.00')) == 0:
                action = 'SET_FROM_CANDIDATES'
                amount_set = paid_from_candidates
            elif outstanding == 0 and (current_paid or Decimal('0.00')) == 0 and paid_from_candidates == 0 and use_fee_calc:
                # Optional fallback: reconstruct by summing expected fees for all billed candidates
                # Only consider candidates within this group
                cands = billed_qs.filter(assessment_center_id=center.id)
                if series:
                    cands = cands.filter(assessment_series_id=series.id)
                else:
                    cands = cands.filter(assessment_series__isnull=True)
                total_calc = Decimal('0.00')
                for c in cands.iterator(chunk_size=1000):
                    try:
                        if hasattr(c, 'calculate_fees_balance'):
                            amt = c.calculate_fees_balance()
                        else:
                            amt = c.fees_balance or Decimal('0.00')
                    except Exception:
                        amt = c.fees_balance or Decimal('0.00')
                    # For cleared candidates fees_balance=0; use calculated if positive
                    if amt and amt > 0:
                        total_calc += amt
                if total_calc > 0:
                    action = 'SET_FROM_CALC'
                    amount_set = total_calc

            # Apply if requested
            if action.startswith('SET_') and apply:
                if not pr:
                    pr = CenterSeriesPayment(
                        assessment_center=center,
                        assessment_series=series,
                        amount_paid=amount_set,
                    )
                else:
                    pr.amount_paid = amount_set
                pr.save()
                fixed += 1

            # CSV row
            if writer:
                writer.writerow({
                    'center_id': center.id,
                    'center_number': center.center_number,
                    'center_name': center.center_name,
                    'series_id': series.id if series else '',
                    'series_name': series.name if series else 'No series',
                    'candidate_count': g['candidate_count'],
                    'outstanding_sum': f"{outstanding:.2f}",
                    'paid_sum_candidates': f"{paid_from_candidates:.2f}",
                    'payment_record_before': f"{(current_paid or Decimal('0.00')):.2f}",
                    'action': action,
                    'amount_set': f"{(amount_set or Decimal('0.00')):.2f}",
                })

        if f:
            f.close()
            self.stdout.write(self.style.SUCCESS(f"Exported audit to {export}"))

        self.stdout.write(self.style.SUCCESS(f"Examined {examined} center-series groups. Fixes applied: {fixed} (apply={apply})."))
        if not apply:
            self.stdout.write(self.style.NOTICE('Dry-run only. Use --apply to persist changes.'))
