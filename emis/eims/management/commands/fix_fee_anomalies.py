from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum, Count
from decimal import Decimal
from eims.models import Candidate, Level, CandidateLevel, CandidateModule, AssessmentCenter, AssessmentSeries
import csv
from pathlib import Path

class Command(BaseCommand):
    help = (
        "Audit and fix candidate fee anomalies by recomputing expected totals from occupation/level fees.\n"
        "Dry-run by default. Use --apply to write corrections. Optionally filter by center/series/category."
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Persist corrections to the database')
        parser.add_argument('--center', type=int, help='Filter by assessment center id')
        parser.add_argument('--series', type=int, help='Filter by assessment series id')
        parser.add_argument('--category', type=str, help="Filter by registration category: Formal|Modular|Worker's PAS|Informal")
        parser.add_argument('--limit', type=int, help='Limit candidates for testing')
        parser.add_argument('--export', type=str, help='Export audit CSV to this file path')

    def handle(self, *args, **opts):
        apply = opts.get('apply')
        center_id = opts.get('center')
        series_id = opts.get('series')
        category = opts.get('category')
        limit = opts.get('limit')
        export = opts.get('export')

        qs = Candidate.objects.select_related('assessment_center', 'assessment_series', 'occupation').all()
        if center_id:
            qs = qs.filter(assessment_center_id=center_id)
        if series_id:
            qs = qs.filter(assessment_series_id=series_id)
        if category:
            qs = qs.filter(registration_category__iexact=category)
        if limit:
            qs = qs.order_by('id')[:limit]

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('No candidates match filters.'))
            return

        self.stdout.write(self.style.WARNING(f'Auditing {total} candidate(s)... apply={apply}'))

        rows = []
        fixed = 0
        anomalies = 0

        for cand in qs.iterator(chunk_size=500):
            reg_cat = (cand.registration_category or '').lower()
            amount_paid = cand.payment_amount_cleared or Decimal('0.00')

            # Determine level for fee lookup (first enrolled level)
            level_obj = (
                Level.objects.filter(occupation=cand.occupation, occupation_levels__isnull=False)
                .first()
            )
            # Prefer explicit CandidateLevel
            cl = CandidateLevel.objects.filter(candidate=cand).order_by('id').select_related('level').first()
            if cl:
                level_obj = cl.level

            # Count modules (for modular/workers PAS when module-based)
            module_count = CandidateModule.objects.filter(candidate=cand).count()

            expected_total = Decimal('0.00')
            if reg_cat == 'formal':
                if not level_obj:
                    # If no level, cannot compute formal fee
                    expected_total = Decimal('0.00')
                else:
                    expected_total = level_obj.formal_fee or Decimal('0.00')
            elif reg_cat == 'modular':
                # Use Level modular fees (1 or 2 modules) – prefer candidate.modular_module_count
                if not level_obj:
                    expected_total = Decimal('0.00')
                else:
                    mmc = cand.modular_module_count or (2 if module_count >= 2 else 1)
                    if mmc and int(mmc) >= 2:
                        expected_total = level_obj.modular_fee_double or Decimal('0.00')
                    else:
                        expected_total = level_obj.modular_fee_single or Decimal('0.00')
            else:
                # Worker's PAS / Informal
                if not level_obj:
                    expected_total = Decimal('0.00')
                else:
                    if (level_obj.workers_pas_module_fee or Decimal('0')) > 0 and module_count > 0:
                        expected_total = (level_obj.workers_pas_module_fee or Decimal('0')) * Decimal(module_count)
                    else:
                        expected_total = level_obj.workers_pas_fee or Decimal('0.00')

            current_total = (cand.payment_amount_cleared or Decimal('0.00')) + (cand.fees_balance or Decimal('0.00'))
            new_balance = (expected_total - amount_paid)
            if new_balance < 0:
                new_balance = Decimal('0.00')

            mismatch = abs(current_total - expected_total) > Decimal('0.01')
            if mismatch:
                anomalies += 1

            rows.append({
                'id': cand.id,
                'reg_number': cand.reg_number or '',
                'name': cand.full_name,
                'center': cand.assessment_center.center_name if cand.assessment_center else '',
                'series': cand.assessment_series.name if cand.assessment_series else '',
                'category': cand.registration_category,
                'level': level_obj.name if level_obj else '',
                'module_count': module_count,
                'expected_total': f"{expected_total:.2f}",
                'amount_paid': f"{amount_paid:.2f}",
                'current_fees_balance': f"{(cand.fees_balance or Decimal('0.00')):.2f}",
                'current_total': f"{current_total:.2f}",
                'new_balance': f"{new_balance:.2f}",
                'mismatch': 'YES' if mismatch else 'NO',
            })

            if apply and mismatch:
                cand.fees_balance = new_balance
                # Persist modular cached amount to keep consistency
                if reg_cat == 'modular':
                    cand.modular_billing_amount = expected_total
                cand.save(update_fields=['fees_balance', 'modular_billing_amount'] if reg_cat == 'modular' else ['fees_balance'])
                fixed += 1

        # Export CSV if requested
        if export:
            out_path = Path(export)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            self.stdout.write(self.style.SUCCESS(f'Exported audit CSV to {out_path}'))

        self.stdout.write(self.style.WARNING(f'Anomalies found: {anomalies}'))
        if apply:
            self.stdout.write(self.style.SUCCESS(f'Corrected: {fixed}'))
        else:
            self.stdout.write(self.style.NOTICE('Dry-run only. Use --apply to persist corrections.'))
