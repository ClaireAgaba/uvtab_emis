"""
Management command to diagnose billing issues for a specific center.

This provides detailed diagnostic information about:
- All enrolled candidates at the center
- Their registration categories
- Module/level enrollments
- Current fees_balance vs calculated fees
- Billing amounts and discrepancies

Usage:
    python manage.py diagnose_center_billing UBT154
    python manage.py diagnose_center_billing UBT154 --series "August 2025"
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from decimal import Decimal
from eims.models import Candidate, CandidateLevel, CandidateModule, AssessmentCenter, AssessmentSeries


class Command(BaseCommand):
    help = 'Diagnose billing issues for a specific assessment center'

    def add_arguments(self, parser):
        parser.add_argument(
            'center_number',
            type=str,
            help='Center number to diagnose (e.g., UBT154)',
        )
        parser.add_argument(
            '--series',
            type=str,
            help='Filter by assessment series name',
        )

    def handle(self, *args, **options):
        center_number = options['center_number']
        series_filter = options.get('series')

        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING(f'BILLING DIAGNOSTIC FOR CENTER: {center_number}'))
        self.stdout.write(self.style.WARNING('=' * 80 + '\n'))

        # Get center
        try:
            center = AssessmentCenter.objects.get(center_number__iexact=center_number)
            self.stdout.write(f"📍 Center: {center.center_name}")
            self.stdout.write(f"   Number: {center.center_number}")
            self.stdout.write(f"   District: {center.district.name if center.district else 'N/A'}")
            self.stdout.write(f"   Village: {center.village.name if center.village else 'N/A'}\n")
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Center {center_number} not found"))
            return

        # Get all enrolled candidates at this center
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
        ).order_by('registration_category', 'reg_number')

        # Apply series filter if specified
        if series_filter:
            enrolled_candidates = enrolled_candidates.filter(
                assessment_series__name__icontains=series_filter
            )
            self.stdout.write(f"📅 Filtering by series: {series_filter}\n")

        total_candidates = enrolled_candidates.count()
        self.stdout.write(f"📊 Total Enrolled Candidates: {total_candidates}\n")

        if total_candidates == 0:
            self.stdout.write(self.style.WARNING('⚠️  No enrolled candidates found at this center'))
            return

        # Group by registration category
        category_groups = {
            'Modular': [],
            'Formal': [],
            'Informal': [],
        }

        for candidate in enrolled_candidates:
            reg_cat = candidate.registration_category or 'Unknown'
            if reg_cat.lower() == 'modular':
                category_groups['Modular'].append(candidate)
            elif reg_cat.lower() == 'formal':
                category_groups['Formal'].append(candidate)
            else:
                category_groups['Informal'].append(candidate)

        # Process each category
        for category, candidates in category_groups.items():
            if not candidates:
                continue

            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(f'{category.upper()} CANDIDATES ({len(candidates)})')
            self.stdout.write('=' * 80 + '\n')

            category_total_current = Decimal('0.00')
            category_total_correct = Decimal('0.00')
            category_discrepancy = Decimal('0.00')

            for candidate in candidates:
                current_balance = candidate.fees_balance or Decimal('0.00')
                
                # Calculate correct fee
                try:
                    correct_fee = candidate.calculate_fees_balance()
                except Exception as e:
                    correct_fee = Decimal('0.00')
                    self.stdout.write(self.style.ERROR(
                        f"❌ Error calculating fee for {candidate.reg_number}: {str(e)}"
                    ))

                discrepancy = correct_fee - current_balance
                category_total_current += current_balance
                category_total_correct += correct_fee
                category_discrepancy += discrepancy

                # Show candidate details
                status_icon = '✅' if discrepancy == 0 else '⚠️ '
                self.stdout.write(f"\n{status_icon} {candidate.reg_number} - {candidate.full_name}")
                self.stdout.write(f"   Occupation: {candidate.occupation.name if candidate.occupation else 'N/A'}")
                self.stdout.write(f"   Series: {candidate.assessment_series.name if candidate.assessment_series else 'N/A'}")
                
                # Category-specific details
                if category == 'Modular':
                    module_count = candidate.candidatemodule_set.count()
                    stored_count = candidate.modular_module_count or 0
                    billing_amount = candidate.modular_billing_amount or Decimal('0.00')
                    
                    self.stdout.write(f"   Enrolled Modules: {module_count}")
                    self.stdout.write(f"   Stored Module Count: {stored_count}")
                    self.stdout.write(f"   Billing Amount: UGX {billing_amount:,.2f}")
                    
                    # List modules
                    modules = candidate.candidatemodule_set.select_related('module__level').all()
                    if modules:
                        self.stdout.write(f"   Modules:")
                        for cm in modules:
                            level_name = cm.module.level.name if cm.module.level else 'N/A'
                            self.stdout.write(f"      - {cm.module.name} (Level: {level_name})")
                            
                            # Show level fees
                            if cm.module.level:
                                level = cm.module.level
                                self.stdout.write(f"        Level Fees: Single={level.modular_fee_single}, Double={level.modular_fee_double}")
                
                elif category == 'Formal':
                    level_count = candidate.candidatelevel_set.count()
                    self.stdout.write(f"   Enrolled Levels: {level_count}")
                    
                    # List levels
                    levels = candidate.candidatelevel_set.select_related('level').all()
                    if levels:
                        self.stdout.write(f"   Levels:")
                        for cl in levels:
                            self.stdout.write(f"      - {cl.level.name}")
                            self.stdout.write(f"        Formal Fee: UGX {cl.level.formal_fee:,.2f}")
                
                else:  # Informal
                    module_count = candidate.candidatemodule_set.count()
                    self.stdout.write(f"   Enrolled Modules: {module_count}")
                    
                    # List modules
                    modules = candidate.candidatemodule_set.select_related('module__level').all()
                    if modules:
                        self.stdout.write(f"   Modules:")
                        for cm in modules:
                            level_name = cm.module.level.name if cm.module.level else 'N/A'
                            self.stdout.write(f"      - {cm.module.name} (Level: {level_name})")
                            
                            # Show level fees
                            if cm.module.level:
                                level = cm.module.level
                                self.stdout.write(f"        Worker's PAS Module Fee: UGX {level.workers_pas_module_fee:,.2f}")

                # Show billing comparison
                self.stdout.write(f"   Current Balance: UGX {current_balance:,.2f}")
                self.stdout.write(f"   Calculated Fee: UGX {correct_fee:,.2f}")
                if discrepancy != 0:
                    self.stdout.write(self.style.ERROR(f"   ⚠️  DISCREPANCY: UGX {discrepancy:,.2f}"))

            # Category summary
            self.stdout.write(f"\n{'-' * 80}")
            self.stdout.write(f"{category.upper()} SUMMARY:")
            self.stdout.write(f"   Candidates: {len(candidates)}")
            self.stdout.write(f"   Current Total: UGX {category_total_current:,.2f}")
            self.stdout.write(f"   Correct Total: UGX {category_total_correct:,.2f}")
            if category_discrepancy != 0:
                self.stdout.write(self.style.ERROR(f"   DISCREPANCY: UGX {category_discrepancy:,.2f}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"   ✅ No discrepancies"))

        # Overall summary
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('OVERALL CENTER SUMMARY')
        self.stdout.write('=' * 80 + '\n')

        overall_current = sum(
            (c.fees_balance or Decimal('0.00')) 
            for c in enrolled_candidates
        )
        
        overall_correct = Decimal('0.00')
        for c in enrolled_candidates:
            try:
                overall_correct += c.calculate_fees_balance()
            except:
                pass

        overall_discrepancy = overall_correct - overall_current

        self.stdout.write(f"📊 Total Enrolled Candidates: {total_candidates}")
        self.stdout.write(f"   Modular: {len(category_groups['Modular'])}")
        self.stdout.write(f"   Formal: {len(category_groups['Formal'])}")
        self.stdout.write(f"   Informal: {len(category_groups['Informal'])}")
        self.stdout.write(f"\n💰 Current Total Balance: UGX {overall_current:,.2f}")
        self.stdout.write(f"💰 Correct Total Balance: UGX {overall_correct:,.2f}")
        
        if overall_discrepancy != 0:
            self.stdout.write(self.style.ERROR(f"\n⚠️  TOTAL DISCREPANCY: UGX {overall_discrepancy:,.2f}"))
            self.stdout.write(self.style.NOTICE(f"\n💡 To fix these issues, run:"))
            self.stdout.write(self.style.NOTICE(f"   python manage.py fix_modular_billing --center {center_number}"))
            self.stdout.write(self.style.NOTICE(f"   python manage.py harmonize_billing_status --center {center_number}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✅ No billing discrepancies found"))

        self.stdout.write('\n' + '=' * 80 + '\n')
