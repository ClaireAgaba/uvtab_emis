from django.core.management.base import BaseCommand
from django.db.models import Q
from decimal import Decimal
import csv
from pathlib import Path

from eims.models import Candidate, AssessmentCenter, AssessmentSeries

class Command(BaseCommand):
    help = (
        "Backfill Candidate.modular_billing_amount for modular candidates using modular_module_count and fee tables.\n"
        "Scans candidates where registration_category='Modular', modular_module_count in (1,2), and modular_billing_amount is NULL.\n"
        "Computes the expected fee and (on --apply) writes it to modular_billing_amount. Exports CSV for audit."
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Persist computed modular_billing_amount to database')
        parser.add_argument('--center', type=int, help='Filter by assessment center id')
        parser.add_argument('--series', type=int, help='Filter by assessment series id; 0 means NULL series')
        parser.add_argument('--export', type=str, help='CSV export path', default='tmp/modular_backfill_audit.csv')
        parser.add_argument('--limit', type=int, help='Limit number of candidates (for testing)')
        # Hardcoded fee fallback for Modular pricing when fee tables are incomplete
        parser.add_argument('--default-modular-1', type=int, default=70000, help='Default fee for 1 module if lookup returns 0')
        parser.add_argument('--default-modular-2', type=int, default=90000, help='Default fee for 2 modules if lookup returns 0')

    def handle(self, *args, **opts):
        apply = opts.get('apply')
        center_id = opts.get('center')
        series_id = opts.get('series')
        export = opts.get('export')
        limit = opts.get('limit')
        default_mod1 = Decimal(str(opts.get('default_modular_1') or 70000))
        default_mod2 = Decimal(str(opts.get('default_modular_2') or 90000))

        qs = Candidate.objects.filter(
            registration_category__iexact='Modular'
        ).filter(
            Q(modular_billing_amount__isnull=True) | Q(modular_billing_amount=0)
        ).filter(
            Q(modular_module_count__in=[1,2]) | Q(candidatemodule__isnull=False)
        ).distinct().select_related('assessment_center','assessment_series','occupation')

        if center_id:
            qs = qs.filter(assessment_center_id=center_id)
        if series_id is not None:
            if series_id == 0:
                qs = qs.filter(assessment_series__isnull=True)
            else:
                qs = qs.filter(assessment_series_id=series_id)

        total = qs.count()
        if limit:
            qs = qs[:limit]

        out_path = Path(export)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        f = out_path.open('w', newline='', encoding='utf-8')
        writer = csv.DictWriter(f, fieldnames=[
            'candidate_id','reg_number','center_id','center_number','series_id','series_name',
            'module_count','computed_fee','applied'
        ])
        writer.writeheader()

        updated = 0
        skipped = 0

        # Helper to compute modular fee using similar logic to calculate_fees_balance
        def compute_modular_fee(cand: Candidate) -> Decimal:
            from eims.models import OccupationLevel
            try:
                # module count: prefer explicit field, else count enrolled modules (cap at 2)
                count = cand.modular_module_count or 0
                if count == 0:
                    mcount = cand.candidatemodule_set.count()
                    if mcount > 0:
                        count = min(mcount, 2)
                if count not in (1,2):
                    return Decimal('0.00')

                # choose level: from enrolled module if any, else first/level1 from occupation
                level = None
                first_cm = cand.candidatemodule_set.first()
                if first_cm and getattr(first_cm, 'module', None):
                    level = first_cm.module.level
                if level is None and cand.occupation_id:
                    occ_levels = OccupationLevel.objects.filter(occupation=cand.occupation).select_related('level')
                    # Prefer a level whose name contains '1'
                    level1 = next((ol.level for ol in occ_levels if '1' in str(ol.level.name)), None)
                    level = level1 or (occ_levels.first().level if occ_levels.exists() else None)
                if level is None:
                    return Decimal('0.00')

                fee = Decimal(level.get_fee_for_registration('Modular', count))
                # If fee tables are incomplete, use hardcoded defaults
                if (fee or Decimal('0.00')) == 0:
                    if count == 1:
                        fee = default_mod1
                    elif count == 2:
                        fee = default_mod2
                return fee
            except Exception:
                return Decimal('0.00')

        for cand in qs.iterator(chunk_size=1000):
            fee = compute_modular_fee(cand)
            applied = ''
            if fee and fee > 0:
                if apply:
                    cand.modular_billing_amount = fee
                    cand.save(update_fields=['modular_billing_amount'])
                    updated += 1
                    applied = 'YES'
                else:
                    applied = 'NO'
            else:
                skipped += 1
                applied = 'SKIP'

            writer.writerow({
                'candidate_id': cand.id,
                'reg_number': cand.reg_number,
                'center_id': getattr(cand.assessment_center, 'id', ''),
                'center_number': getattr(cand.assessment_center, 'center_number', ''),
                'series_id': getattr(cand.assessment_series, 'id', ''),
                'series_name': getattr(cand.assessment_series, 'name', '') or 'No series',
                'module_count': cand.modular_module_count or cand.candidatemodule_set.count(),
                'computed_fee': f"{fee:.2f}",
                'applied': applied,
            })

        f.close()
        self.stdout.write(self.style.SUCCESS(f"Scanned {total} modular candidates needing backfill. Updated: {updated}, Skipped: {skipped}. Export: {export}"))
        if not apply:
            self.stdout.write(self.style.NOTICE('Dry-run only. Use --apply to persist changes.'))
