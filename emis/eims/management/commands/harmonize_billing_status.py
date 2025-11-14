"""
Management command to harmonize billing status for enrolled candidates.

This command addresses the issue where candidates were enrolled and billed
but the billing status wasn't being properly stored in the database.

The command:
1. Identifies all enrolled candidates (have CandidateLevel or CandidateModule records)
2. Ensures they have proper fees_balance set
3. Updates billing-related fields (modular_module_count, modular_billing_amount)
4. Provides comprehensive reporting

Usage:
    python manage.py harmonize_billing_status --dry-run  # Preview changes
    python manage.py harmonize_billing_status             # Apply fixes
    python manage.py harmonize_billing_status --center UBT154  # Fix specific center
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from decimal import Decimal
from eims.models import Candidate, CandidateLevel, CandidateModule


class Command(BaseCommand):
    help = 'Harmonize billing status for enrolled candidates'

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
            '--series',
            type=str,
            help='Fix only candidates from specific assessment series (series name)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        center_filter = options.get('center')
        series_filter = options.get('series')

        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('BILLING STATUS HARMONIZATION'))
        self.stdout.write(self.style.WARNING('=' * 80))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n🔍 DRY RUN MODE - No changes will be saved\n'))
        else:
            self.stdout.write(self.style.NOTICE('\n✅ LIVE MODE - Changes will be applied\n'))

        # Find all enrolled candidates (have level or module enrollments)
        enrolled_candidates = Candidate.objects.filter(
            Q(candidatelevel__isnull=False) | Q(candidatemodule__isnull=False)
        ).distinct().select_related(
            'occupation', 
            'assessment_center',
            'assessment_series'
        ).prefetch_related(
            'candidatelevel_set__level',
            'candidatemodule_set__module__level'
        )

        # Apply filters
        if center_filter:
            enrolled_candidates = enrolled_candidates.filter(
                assessment_center__center_number__iexact=center_filter
            )
            self.stdout.write(f"📍 Filtering by center: {center_filter}\n")

        if series_filter:
            enrolled_candidates = enrolled_candidates.filter(
                assessment_series__name__icontains=series_filter
            )
            self.stdout.write(f"📅 Filtering by series: {series_filter}\n")

        total_candidates = enrolled_candidates.count()
        self.stdout.write(f"📊 Found {total_candidates} enrolled candidates\n")

        if total_candidates == 0:
            self.stdout.write(self.style.SUCCESS('\n✅ No enrolled candidates found to process'))
            return

        # Statistics
        stats = {
            'modular': {'total': 0, 'fixed': 0, 'fees_recovered': Decimal('0.00')},
            'formal': {'total': 0, 'fixed': 0, 'fees_recovered': Decimal('0.00')},
            'informal': {'total': 0, 'fixed': 0, 'fees_recovered': Decimal('0.00')},
        }

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('PROCESSING CANDIDATES')
        self.stdout.write('=' * 80 + '\n')

        for candidate in enrolled_candidates:
            reg_cat = (candidate.registration_category or '').lower()
            
            # Categorize
            if reg_cat == 'modular':
                category = 'modular'
            elif reg_cat == 'formal':
                category = 'formal'
            else:
                category = 'informal'
            
            stats[category]['total'] += 1

            # Get current state
            current_balance = candidate.fees_balance or Decimal('0.00')
            
            # Calculate correct fee
            try:
                correct_fee = candidate.calculate_fees_balance()
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"❌ Error calculating fee for {candidate.reg_number}: {str(e)}"
                ))
                continue

            # Check if fix is needed
            needs_fix = current_balance != correct_fee

            if needs_fix:
                stats[category]['fixed'] += 1
                fee_difference = correct_fee - current_balance
                stats[category]['fees_recovered'] += fee_difference

                self.stdout.write(f"\n🔧 {candidate.reg_number} - {candidate.full_name}")
                self.stdout.write(f"   Center: {candidate.assessment_center.center_number if candidate.assessment_center else 'N/A'}")
                self.stdout.write(f"   Series: {candidate.assessment_series.name if candidate.assessment_series else 'N/A'}")
                self.stdout.write(f"   Category: {candidate.registration_category}")
                self.stdout.write(f"   Current Balance: UGX {current_balance:,.2f}")
                self.stdout.write(f"   Correct Balance: UGX {correct_fee:,.2f}")
                self.stdout.write(f"   Difference: UGX {fee_difference:,.2f}")

                # Show enrollment details
                if category == 'modular':
                    module_count = candidate.candidatemodule_set.count()
                    self.stdout.write(f"   Enrolled Modules: {module_count}")
                    modules = candidate.candidatemodule_set.select_related('module').all()
                    for cm in modules:
                        self.stdout.write(f"      - {cm.module.name}")
                
                elif category == 'formal':
                    level_count = candidate.candidatelevel_set.count()
                    self.stdout.write(f"   Enrolled Levels: {level_count}")
                    levels = candidate.candidatelevel_set.select_related('level').all()
                    for cl in levels:
                        self.stdout.write(f"      - {cl.level.name}")
                
                else:  # informal
                    module_count = candidate.candidatemodule_set.count()
                    self.stdout.write(f"   Enrolled Modules: {module_count}")
                    modules = candidate.candidatemodule_set.select_related('module').all()
                    for cm in modules:
                        self.stdout.write(f"      - {cm.module.name}")

                # Apply fix
                if not dry_run:
                    try:
                        # For modular candidates, also update module count
                        if category == 'modular':
                            module_count = candidate.candidatemodule_set.count()
                            candidate.modular_module_count = module_count
                            candidate.modular_billing_amount = correct_fee
                            candidate.fees_balance = correct_fee
                            candidate.save(update_fields=[
                                'modular_module_count',
                                'modular_billing_amount',
                                'fees_balance'
                            ])
                        else:
                            candidate.fees_balance = correct_fee
                            candidate.save(update_fields=['fees_balance'])
                        
                        self.stdout.write(self.style.SUCCESS(f"   ✅ Updated successfully"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"   ❌ Error updating: {str(e)}"))

        # Summary Report
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('SUMMARY REPORT')
        self.stdout.write('=' * 80 + '\n')

        for category, data in stats.items():
            if data['total'] > 0:
                self.stdout.write(f"\n📊 {category.upper()} CANDIDATES")
                self.stdout.write(f"   Total: {data['total']}")
                self.stdout.write(f"   Fixed: {data['fixed']}")
                self.stdout.write(f"   Fees Recovered: UGX {data['fees_recovered']:,.2f}")

        total_fixed = sum(s['fixed'] for s in stats.values())
        total_recovered = sum(s['fees_recovered'] for s in stats.values())

        self.stdout.write(f"\n{'=' * 80}")
        self.stdout.write(f"🔧 Total Candidates Fixed: {total_fixed}")
        self.stdout.write(f"💰 Total Fees Recovered: UGX {total_recovered:,.2f}")

        # Final message
        self.stdout.write('\n' + '=' * 80)
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN COMPLETE - No changes were saved'))
            self.stdout.write(self.style.NOTICE('Run without --dry-run to apply fixes'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ HARMONIZATION COMPLETE - All changes have been saved'))
        self.stdout.write('=' * 80 + '\n')
