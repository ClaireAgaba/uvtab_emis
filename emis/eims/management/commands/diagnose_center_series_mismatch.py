from django.core.management.base import BaseCommand
from django.db.models import Q
from decimal import Decimal
from eims.models import Candidate, AssessmentCenter, AssessmentSeries

class Command(BaseCommand):
    help = 'Diagnose mismatch between center-series total candidates and billing query candidates, with optional fixes.'

    def add_arguments(self, parser):
        parser.add_argument('--center-number', type=str, required=True, help='Center number, e.g. UVT746')
        parser.add_argument('--series-name', type=str, required=True, help='Assessment series name, e.g. October 2025 Series')
        parser.add_argument('--mark-paid', action='store_true', help='Mark missing paid candidates as payment_cleared with calculated amount')
        parser.add_argument('--attach-series', action='store_true', help='Attach missing-series candidates to the target series')
        parser.add_argument('--dry-run', action='store_true', help='Preview fixes without applying')

    def handle(self, *args, **opts):
        center_number = opts['center_number']
        series_name = opts['series_name']
        mark_paid = opts['mark_paid']
        attach_series = opts['attach_series']
        dry = opts['dry_run']

        self.stdout.write('\n' + '='*90)
        self.stdout.write('CENTER-SERIES MISMATCH DIAGNOSTICS')
        self.stdout.write('='*90 + '\n')

        # Resolve center and series
        center = AssessmentCenter.objects.filter(center_number=center_number).first()
        if not center:
            self.stdout.write(self.style.ERROR(f'Center {center_number} not found'))
            return
        series = AssessmentSeries.objects.filter(name=series_name).first()
        if not series:
            self.stdout.write(self.style.ERROR(f'Assessment series "{series_name}" not found'))
            return

        self.stdout.write(self.style.SUCCESS(f'Center: {center.center_name} ({center.center_number})'))
        self.stdout.write(self.style.SUCCESS(f'Series: {series.name}'))

        # Set A: all candidates at center+series (ground truth expectation)
        all_set = Candidate.objects.filter(assessment_center=center, assessment_series=series)
        all_ids = set(all_set.values_list('id', flat=True))

        # Set B: candidates included by billing query (what Center Fees counts)
        billing_qs = Candidate.objects.filter(assessment_center=center).filter(
            Q(candidatelevel__isnull=False) |
            Q(registration_category__iexact='modular', modular_module_count__in=[1, 2]) |
            Q(registration_category__iexact='modular', candidatemodule__isnull=False) |
            Q(fees_balance__gt=0) |
            Q(payment_cleared=True)
        ).filter(assessment_series=series).distinct()
        billing_ids = set(billing_qs.values_list('id', flat=True))

        self.stdout.write(f'Expected (center+series): {len(all_ids)}')
        self.stdout.write(f'Counted by billing query: {len(billing_ids)}')

        missing_ids = all_ids - billing_ids
        extra_ids = billing_ids - all_ids  # should be empty

        if not missing_ids and not extra_ids:
            self.stdout.write(self.style.SUCCESS('\n✓ No mismatch: sets are identical'))
            return

        if missing_ids:
            self.stdout.write(self.style.ERROR(f'\nMissing from billing ({len(missing_ids)}):'))
            missing = Candidate.objects.filter(id__in=missing_ids).select_related('occupation')
            for c in missing:
                has_level = c.candidatelevel_set.exists()
                has_modules = c.candidatemodule_set.exists()
                cat = (c.registration_category or '').lower()
                self.stdout.write(
                    f' - {c.reg_number} | {c.full_name} | cat={cat} | fees_balance={c.fees_balance} | '
                    f'payment_cleared={getattr(c, "payment_cleared", False)} | level={has_level} | modules={has_modules}'
                )

            # Optional fixes
            if mark_paid or attach_series:
                if dry:
                    self.stdout.write(self.style.WARNING('\n[DRY RUN] Would apply fixes below'))
                applied = 0
                for c in missing:
                    changed = False
                    # Attach series if somehow missing (should not be in this set, but safe-guard)
                    if attach_series and c.assessment_series_id != series.id:
                        c.assessment_series = series
                        changed = True
                    # Mark paid if zero balance and not flagged
                    if mark_paid and getattr(c, 'payment_cleared', False) is False and (c.fees_balance or Decimal('0.00')) == 0:
                        try:
                            amount = c.calculate_fees_balance() if hasattr(c, 'calculate_fees_balance') else Decimal('0.00')
                            if not amount or amount == 0:
                                # conservative default
                                amount = Decimal('70000.00')
                            c.payment_cleared = True
                            c.payment_amount_cleared = amount
                            changed = True
                        except Exception:
                            pass
                    if changed and not dry:
                        c.save()
                        applied += 1
                if mark_paid or attach_series:
                    self.stdout.write(self.style.SUCCESS(f'Applied changes to {applied} candidates' + (' (dry-run)' if dry else '')))

        if extra_ids:
            self.stdout.write(self.style.WARNING(f'\nExtra in billing but not in center+series set ({len(extra_ids)}):'))
            for c in Candidate.objects.filter(id__in=extra_ids):
                self.stdout.write(f' - {c.reg_number} | series={c.assessment_series_id} center={c.assessment_center_id}')

        self.stdout.write('\nDone.')
