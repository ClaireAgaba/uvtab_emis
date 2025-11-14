"""
Management command to fix multi-level billing issues.

This command fixes billing for centers with candidates enrolled in multiple levels
(Level 1, Level 2, Level 3, etc.) ensuring each candidate is billed correctly
based on their enrolled level's fee structure.

Usage:
    python manage.py fix_multilevel_billing UVT847 --dry-run  # Preview
    python manage.py fix_multilevel_billing UVT847             # Apply fixes
    python manage.py fix_multilevel_billing UVT847 --series "November 2025"
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from decimal import Decimal
from collections import defaultdict
from eims.models import Candidate, CandidateLevel, CandidateModule, AssessmentCenter


class Command(BaseCommand):
    help = 'Fix multi-level billing issues for assessment centers'

    def add_arguments(self, parser):
        parser.add_argument(
            'center_number',
            type=str,
            help='Center number to fix (e.g., UVT847)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them',
        )
        parser.add_argument(
            '--series',
            type=str,
            help='Filter by assessment series name',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each candidate',
        )

    def handle(self, *args, **options):
        center_number = options['center_number']
        dry_run = options['dry_run']
        series_filter = options.get('series')
        verbose = options['verbose']

        self.stdout.write(self.style.WARNING('=' * 100))
        self.stdout.write(self.style.WARNING(f'MULTI-LEVEL BILLING FIX FOR CENTER: {center_number}'))
        self.stdout.write(self.style.WARNING('=' * 100))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n🔍 DRY RUN MODE - No changes will be saved\n'))
        else:
            self.stdout.write(self.style.NOTICE('\n✅ LIVE MODE - Changes will be applied\n'))

        # Get center
        try:
            center = AssessmentCenter.objects.get(center_number__iexact=center_number)
            self.stdout.write(f"📍 Center: {center.center_name}")
            self.stdout.write(f"   Number: {center.center_number}\n")
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
        ).order_by('registration_category', 'reg_number')

        if series_filter:
            enrolled_candidates = enrolled_candidates.filter(
                assessment_series__name__icontains=series_filter
            )
            self.stdout.write(f"📅 Series Filter: {series_filter}\n")

        total_candidates = enrolled_candidates.count()
        self.stdout.write(f"📊 Total Enrolled Candidates: {total_candidates}\n")

        if total_candidates == 0:
            self.stdout.write(self.style.WARNING('⚠️  No enrolled candidates found'))
            return

        # Statistics
        stats = {
            'modular': {'total': 0, 'fixed': 0, 'fees_recovered': Decimal('0.00')},
            'formal': {'total': 0, 'fixed': 0, 'fees_recovered': Decimal('0.00'), 'by_level': defaultdict(lambda: {'count': 0, 'fixed': 0, 'recovered': Decimal('0.00')})},
            'informal': {'total': 0, 'fixed': 0, 'fees_recovered': Decimal('0.00')},
        }

        self.stdout.write('\n' + '=' * 100)
        self.stdout.write('PROCESSING CANDIDATES')
        self.stdout.write('=' * 100 + '\n')

        for candidate in enrolled_candidates:
            reg_cat = (candidate.registration_category or '').lower()
            
            # Get current and correct fees
            current_balance = candidate.fees_balance or Decimal('0.00')
            
            try:
                correct_fee = candidate.calculate_fees_balance()
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"❌ Error calculating fee for {candidate.reg_number}: {str(e)}"
                ))
                continue

            needs_fix = current_balance != correct_fee

            # Categorize and track
            if reg_cat == 'modular':
                category = 'modular'
                stats['modular']['total'] += 1
            elif reg_cat == 'formal':
                category = 'formal'
                stats['formal']['total'] += 1
                
                # Track by level
                enrolled_levels = candidate.candidatelevel_set.select_related('level').all()
                for cl in enrolled_levels:
                    level_name = cl.level.name if cl.level else 'Unknown'
                    stats['formal']['by_level'][level_name]['count'] += 1
                    if needs_fix:
                        stats['formal']['by_level'][level_name]['fixed'] += 1
                        stats['formal']['by_level'][level_name]['recovered'] += (correct_fee - current_balance)
            else:
                category = 'informal'
                stats['informal']['total'] += 1

            if needs_fix:
                stats[category]['fixed'] += 1
                fee_difference = correct_fee - current_balance
                stats[category]['fees_recovered'] += fee_difference

                if verbose or abs(fee_difference) > Decimal('1000'):
                    self.stdout.write(f"\n{'🔧' if not dry_run else '👁️ '} {candidate.reg_number} - {candidate.full_name}")
                    self.stdout.write(f"   Category: {candidate.registration_category}")
                    
                    # Show level details for formal candidates
                    if category == 'formal':
                        enrolled_levels = candidate.candidatelevel_set.select_related('level').all()
                        for cl in enrolled_levels:
                            level_name = cl.level.name if cl.level else 'Unknown'
                            level_fee = cl.level.formal_fee if cl.level else Decimal('0.00')
                            self.stdout.write(f"   Level: {level_name} (Fee: UGX {level_fee:,.2f})")
                    
                    # Show module details for modular/informal
                    elif category == 'modular':
                        module_count = candidate.candidatemodule_set.count()
                        self.stdout.write(f"   Modules: {module_count}")
                        modules = candidate.candidatemodule_set.select_related('module__level').all()
                        for cm in modules:
                            self.stdout.write(f"      - {cm.module.name}")
                    
                    elif category == 'informal':
                        module_count = candidate.candidatemodule_set.count()
                        self.stdout.write(f"   Modules: {module_count}")

                    self.stdout.write(f"   Current Balance: UGX {current_balance:,.2f}")
                    self.stdout.write(f"   Correct Balance: UGX {correct_fee:,.2f}")
                    self.stdout.write(self.style.ERROR(f"   Difference: UGX {fee_difference:,.2f}"))

                # Apply fix
                if not dry_run:
                    try:
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
                        
                        if verbose or abs(fee_difference) > Decimal('1000'):
                            self.stdout.write(self.style.SUCCESS(f"   ✅ Updated successfully"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"   ❌ Error updating: {str(e)}"))

        # Summary Report
        self.stdout.write('\n' + '=' * 100)
        self.stdout.write('SUMMARY REPORT')
        self.stdout.write('=' * 100 + '\n')

        # Modular summary
        if stats['modular']['total'] > 0:
            self.stdout.write(f"\n📊 MODULAR CANDIDATES")
            self.stdout.write(f"   Total: {stats['modular']['total']}")
            self.stdout.write(f"   Fixed: {stats['modular']['fixed']}")
            self.stdout.write(f"   Fees Recovered: UGX {stats['modular']['fees_recovered']:,.2f}")

        # Formal summary with level breakdown
        if stats['formal']['total'] > 0:
            self.stdout.write(f"\n📊 FORMAL CANDIDATES")
            self.stdout.write(f"   Total: {stats['formal']['total']}")
            self.stdout.write(f"   Fixed: {stats['formal']['fixed']}")
            self.stdout.write(f"   Fees Recovered: UGX {stats['formal']['fees_recovered']:,.2f}")
            
            if stats['formal']['by_level']:
                self.stdout.write(f"\n   BY LEVEL:")
                
                # Sort levels numerically
                import re
                def level_sort_key(level_name):
                    match = re.search(r'(\d+)', level_name)
                    return int(match.group(1)) if match else 999
                
                sorted_levels = sorted(stats['formal']['by_level'].keys(), key=level_sort_key)
                
                for level_name in sorted_levels:
                    level_stats = stats['formal']['by_level'][level_name]
                    self.stdout.write(f"   - {level_name}:")
                    self.stdout.write(f"      Candidates: {level_stats['count']}")
                    self.stdout.write(f"      Fixed: {level_stats['fixed']}")
                    self.stdout.write(f"      Recovered: UGX {level_stats['recovered']:,.2f}")

        # Informal summary
        if stats['informal']['total'] > 0:
            self.stdout.write(f"\n📊 INFORMAL/WORKER'S PAS CANDIDATES")
            self.stdout.write(f"   Total: {stats['informal']['total']}")
            self.stdout.write(f"   Fixed: {stats['informal']['fixed']}")
            self.stdout.write(f"   Fees Recovered: UGX {stats['informal']['fees_recovered']:,.2f}")

        # Grand total
        total_fixed = sum(s['fixed'] for s in [stats['modular'], stats['formal'], stats['informal']])
        total_recovered = sum(s['fees_recovered'] for s in [stats['modular'], stats['formal'], stats['informal']])

        self.stdout.write(f"\n{'=' * 100}")
        self.stdout.write(f"🔧 Total Candidates Fixed: {total_fixed}")
        self.stdout.write(f"💰 Total Fees Recovered: UGX {total_recovered:,.2f}")

        # Final message
        self.stdout.write('\n' + '=' * 100)
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN COMPLETE - No changes were saved'))
            self.stdout.write(self.style.NOTICE('Run without --dry-run to apply fixes'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ FIX COMPLETE - All changes have been saved'))
            self.stdout.write(self.style.NOTICE('\nNext steps:'))
            self.stdout.write(self.style.NOTICE(f'1. Run: python manage.py diagnose_multilevel_billing {center_number}'))
            self.stdout.write(self.style.NOTICE('2. Verify invoice in UVTAB Fees → Center Fees'))
        self.stdout.write('=' * 100 + '\n')
