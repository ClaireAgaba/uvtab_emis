"""
Management command to diagnose and fix modular candidate billing issues.

This command:
1. Identifies modular candidates with incorrect fees_balance (showing 0.00)
2. Recalculates fees based on enrolled modules and level fees
3. Updates modular_billing_amount and fees_balance fields
4. Provides detailed reporting of changes

Usage:
    python manage.py fix_modular_billing --dry-run  # Preview changes
    python manage.py fix_modular_billing             # Apply fixes
    python manage.py fix_modular_billing --center UBT154  # Fix specific center
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from decimal import Decimal
from eims.models import Candidate, CandidateModule, Level


class Command(BaseCommand):
    help = 'Diagnose and fix modular candidate billing issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them',
        )
        parser.add_argument(
            '--center',
            type=str,
            help='Fix only candidates from specific center (center number)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each candidate',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        center_filter = options.get('center')
        verbose = options['verbose']

        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('MODULAR BILLING DIAGNOSTIC AND FIX'))
        self.stdout.write(self.style.WARNING('=' * 80))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n🔍 DRY RUN MODE - No changes will be saved\n'))
        else:
            self.stdout.write(self.style.NOTICE('\n✅ LIVE MODE - Changes will be applied\n'))

        # Find all modular candidates with enrollments
        modular_candidates = Candidate.objects.filter(
            Q(registration_category__iexact='modular')
        ).annotate(
            module_count=Count('candidatemodule', distinct=True)
        ).filter(
            module_count__gt=0  # Only candidates with enrolled modules
        ).select_related('occupation', 'assessment_center').prefetch_related('candidatemodule_set__module__level')

        # Apply center filter if specified
        if center_filter:
            modular_candidates = modular_candidates.filter(
                assessment_center__center_number__iexact=center_filter
            )
            self.stdout.write(f"📍 Filtering by center: {center_filter}\n")

        total_candidates = modular_candidates.count()
        self.stdout.write(f"📊 Found {total_candidates} modular candidates with enrollments\n")

        if total_candidates == 0:
            self.stdout.write(self.style.SUCCESS('\n✅ No modular candidates found to process'))
            return

        # Statistics
        candidates_with_zero_balance = 0
        candidates_with_zero_billing_amount = 0
        candidates_fixed = 0
        total_fees_recovered = Decimal('0.00')
        
        # Group by center for reporting
        center_stats = {}

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('PROCESSING CANDIDATES')
        self.stdout.write('=' * 80 + '\n')

        for candidate in modular_candidates:
            center_number = candidate.assessment_center.center_number if candidate.assessment_center else 'NO_CENTER'
            
            if center_number not in center_stats:
                center_stats[center_number] = {
                    'total': 0,
                    'fixed': 0,
                    'fees_recovered': Decimal('0.00')
                }
            
            center_stats[center_number]['total'] += 1

            # Get current values
            current_balance = candidate.fees_balance or Decimal('0.00')
            current_billing_amount = candidate.modular_billing_amount or Decimal('0.00')
            module_count = candidate.candidatemodule_set.count()
            stored_module_count = candidate.modular_module_count or 0

            # Track issues
            has_zero_balance = current_balance == Decimal('0.00')
            has_zero_billing = current_billing_amount == Decimal('0.00')
            
            if has_zero_balance:
                candidates_with_zero_balance += 1
            if has_zero_billing:
                candidates_with_zero_billing_amount += 1

            # Calculate correct fee
            correct_fee = self.calculate_modular_fee(candidate, module_count)

            # Determine if fix is needed
            needs_fix = (
                has_zero_balance or 
                has_zero_billing or 
                current_balance != correct_fee or
                current_billing_amount != correct_fee or
                stored_module_count != module_count
            )

            if needs_fix:
                candidates_fixed += 1
                fee_difference = correct_fee - current_balance
                total_fees_recovered += fee_difference
                center_stats[center_number]['fixed'] += 1
                center_stats[center_number]['fees_recovered'] += fee_difference

                if verbose or has_zero_balance:
                    self.stdout.write(f"\n{'🔧' if not dry_run else '👁️ '} {candidate.reg_number} - {candidate.full_name}")
                    self.stdout.write(f"   Center: {center_number}")
                    self.stdout.write(f"   Occupation: {candidate.occupation.name if candidate.occupation else 'N/A'}")
                    self.stdout.write(f"   Enrolled Modules: {module_count}")
                    self.stdout.write(f"   Stored Module Count: {stored_module_count} → {module_count}")
                    self.stdout.write(f"   Current Balance: UGX {current_balance:,.2f}")
                    self.stdout.write(f"   Current Billing Amount: UGX {current_billing_amount:,.2f}")
                    self.stdout.write(f"   Correct Fee: UGX {correct_fee:,.2f}")
                    self.stdout.write(f"   Difference: UGX {fee_difference:,.2f}")
                    
                    # Show module details
                    modules = candidate.candidatemodule_set.select_related('module__level').all()
                    if modules:
                        self.stdout.write(f"   Modules:")
                        for cm in modules:
                            self.stdout.write(f"      - {cm.module.name} (Level: {cm.module.level.name})")

                # Apply fix if not dry run
                if not dry_run:
                    try:
                        candidate.modular_module_count = module_count
                        candidate.modular_billing_amount = correct_fee
                        candidate.fees_balance = correct_fee
                        candidate.save(update_fields=['modular_module_count', 'modular_billing_amount', 'fees_balance'])
                        
                        if verbose or has_zero_balance:
                            self.stdout.write(self.style.SUCCESS(f"   ✅ Updated successfully"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"   ❌ Error updating: {str(e)}"))

        # Summary Report
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('SUMMARY REPORT')
        self.stdout.write('=' * 80 + '\n')

        self.stdout.write(f"📊 Total Modular Candidates Processed: {total_candidates}")
        self.stdout.write(f"⚠️  Candidates with Zero Balance: {candidates_with_zero_balance}")
        self.stdout.write(f"⚠️  Candidates with Zero Billing Amount: {candidates_with_zero_billing_amount}")
        self.stdout.write(f"🔧 Candidates Fixed: {candidates_fixed}")
        self.stdout.write(f"💰 Total Fees Recovered: UGX {total_fees_recovered:,.2f}")

        # Center-wise breakdown
        if center_stats:
            self.stdout.write('\n' + '-' * 80)
            self.stdout.write('CENTER-WISE BREAKDOWN')
            self.stdout.write('-' * 80 + '\n')
            
            for center_number, stats in sorted(center_stats.items()):
                if stats['fixed'] > 0:
                    self.stdout.write(f"\n📍 {center_number}")
                    self.stdout.write(f"   Total Candidates: {stats['total']}")
                    self.stdout.write(f"   Fixed: {stats['fixed']}")
                    self.stdout.write(f"   Fees Recovered: UGX {stats['fees_recovered']:,.2f}")

        # Final message
        self.stdout.write('\n' + '=' * 80)
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN COMPLETE - No changes were saved'))
            self.stdout.write(self.style.NOTICE('Run without --dry-run to apply fixes'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ FIX COMPLETE - All changes have been saved'))
        self.stdout.write('=' * 80 + '\n')

    def calculate_modular_fee(self, candidate, module_count):
        """
        Calculate the correct modular fee for a candidate based on enrolled modules.
        """
        from decimal import Decimal

        if module_count == 0:
            return Decimal('0.00')

        # Cap at 2 modules for billing purposes
        billing_count = min(module_count, 2)

        # Get the level from the first enrolled module
        first_module = candidate.candidatemodule_set.select_related('module__level').first()
        
        if not first_module or not first_module.module:
            # Fallback to hardcoded fees if no module found
            if billing_count == 1:
                return Decimal('70000.00')
            elif billing_count == 2:
                return Decimal('90000.00')
            return Decimal('0.00')

        level = first_module.module.level

        # Use level's fee structure
        try:
            fee = level.get_fee_for_registration('Modular', billing_count)
            return Decimal(str(fee))
        except Exception:
            # Fallback to hardcoded fees
            if billing_count == 1:
                return Decimal('70000.00')
            elif billing_count == 2:
                return Decimal('90000.00')
            return Decimal('0.00')
