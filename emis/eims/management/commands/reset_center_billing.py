"""
Emergency command to reset and recalculate billing for a center.

This command:
1. Resets all fees_balance to 0
2. Recalculates from scratch using calculate_fees_balance()
3. Ensures no double-counting

Usage:
    python manage.py reset_center_billing UVT847 --dry-run
    python manage.py reset_center_billing UVT847
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from decimal import Decimal
from eims.models import Candidate, AssessmentCenter


class Command(BaseCommand):
    help = 'Reset and recalculate billing for a center from scratch'

    def add_arguments(self, parser):
        parser.add_argument(
            'center_number',
            type=str,
            help='Center number to reset (e.g., UVT847)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them',
        )

    def handle(self, *args, **options):
        center_number = options['center_number']
        dry_run = options['dry_run']

        self.stdout.write(self.style.WARNING('=' * 100))
        self.stdout.write(self.style.WARNING(f'RESET AND RECALCULATE BILLING FOR CENTER: {center_number}'))
        self.stdout.write(self.style.WARNING('=' * 100))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n🔍 DRY RUN MODE - No changes will be saved\n'))
        else:
            self.stdout.write(self.style.ERROR('\n⚠️  LIVE MODE - This will reset all billing amounts!\n'))

        # Get center
        try:
            center = AssessmentCenter.objects.get(center_number__iexact=center_number)
            self.stdout.write(f"📍 Center: {center.center_name}\n")
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Center {center_number} not found"))
            return

        # Get all enrolled candidates
        enrolled_candidates = Candidate.objects.filter(
            assessment_center=center
        ).filter(
            Q(candidatelevel__isnull=False) | Q(candidatemodule__isnull=False)
        ).distinct().select_related(
            'occupation',
            'assessment_series'
        ).prefetch_related(
            'candidatelevel_set__level',
            'candidatemodule_set__module__level'
        ).order_by('reg_number')

        total_candidates = enrolled_candidates.count()
        self.stdout.write(f"📊 Found {total_candidates} enrolled candidates\n")

        if total_candidates == 0:
            self.stdout.write(self.style.WARNING('⚠️  No enrolled candidates found'))
            return

        self.stdout.write('=' * 100)
        self.stdout.write('RESETTING AND RECALCULATING')
        self.stdout.write('=' * 100 + '\n')

        total_before = Decimal('0.00')
        total_after = Decimal('0.00')
        fixed_count = 0

        for candidate in enrolled_candidates:
            old_balance = candidate.fees_balance or Decimal('0.00')
            total_before += old_balance

            # Calculate correct fee from scratch
            try:
                correct_fee = candidate.calculate_fees_balance()
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"❌ Error calculating fee for {candidate.reg_number}: {str(e)}"
                ))
                continue

            total_after += correct_fee

            if old_balance != correct_fee:
                fixed_count += 1
                
                self.stdout.write(f"🔧 {candidate.reg_number} - {candidate.full_name}")
                self.stdout.write(f"   Category: {candidate.registration_category}")
                self.stdout.write(f"   OLD Balance: UGX {old_balance:,.2f}")
                self.stdout.write(f"   NEW Balance: UGX {correct_fee:,.2f}")
                self.stdout.write(f"   Change: UGX {(correct_fee - old_balance):,.2f}")
                
                # Show enrollment details
                reg_cat = (candidate.registration_category or '').lower()
                if reg_cat == 'modular':
                    module_count = candidate.candidatemodule_set.count()
                    self.stdout.write(f"   Modules: {module_count}")
                elif reg_cat == 'formal':
                    levels = candidate.candidatelevel_set.select_related('level').all()
                    for cl in levels:
                        level_name = cl.level.name if cl.level else 'Unknown'
                        level_fee = cl.level.formal_fee if cl.level else Decimal('0.00')
                        self.stdout.write(f"   Level: {level_name} (Fee: UGX {level_fee:,.2f})")
                
                self.stdout.write("")

                # Apply fix
                if not dry_run:
                    try:
                        if reg_cat == 'modular':
                            module_count = candidate.candidatemodule_set.count()
                            candidate.modular_module_count = module_count
                            candidate.modular_billing_amount = correct_fee
                        
                        candidate.fees_balance = correct_fee
                        candidate.save(update_fields=['modular_module_count', 'modular_billing_amount', 'fees_balance'] if reg_cat == 'modular' else ['fees_balance'])
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"   ❌ Error updating: {str(e)}"))

        # Summary
        self.stdout.write('\n' + '=' * 100)
        self.stdout.write('SUMMARY')
        self.stdout.write('=' * 100 + '\n')

        self.stdout.write(f"📊 Total Candidates: {total_candidates}")
        self.stdout.write(f"🔧 Candidates Changed: {fixed_count}")
        self.stdout.write(f"\n💰 OLD Total: UGX {total_before:,.2f}")
        self.stdout.write(f"💰 NEW Total: UGX {total_after:,.2f}")
        self.stdout.write(f"💰 Difference: UGX {(total_after - total_before):,.2f}")

        if dry_run:
            self.stdout.write('\n' + self.style.WARNING('🔍 DRY RUN COMPLETE - No changes were saved'))
            self.stdout.write(self.style.NOTICE('Run without --dry-run to apply changes'))
        else:
            self.stdout.write('\n' + self.style.SUCCESS('✅ RESET COMPLETE - All billing recalculated from scratch'))

        self.stdout.write('=' * 100 + '\n')
