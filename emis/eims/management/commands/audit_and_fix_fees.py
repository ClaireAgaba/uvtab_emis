"""
CRITICAL: Audit and fix UVTAB Fees discrepancies
- Find centers where candidate count × fee doesn't match total fees
- Identify candidates with enrollments but fees_balance = 0 (not properly billed)
- Recalculate fees for all candidates
- Generate detailed audit report
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum, Q
from decimal import Decimal
from eims.models import Candidate, AssessmentCenter, AssessmentSeries
from collections import defaultdict

class Command(BaseCommand):
    help = 'Audit and fix UVTAB Fees discrepancies where candidate counts dont match fee totals'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show issues without fixing them',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix fees for candidates with discrepancies',
        )
        parser.add_argument(
            '--center',
            type=str,
            help='Only check specific center (center_number)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fix_fees = options['fix']
        specific_center = options.get('center')
        
        self.stdout.write(self.style.WARNING('='*100))
        self.stdout.write(self.style.WARNING('UVTAB FEES AUDIT - FINDING CANDIDATE COUNT VS FEES DISCREPANCIES'))
        self.stdout.write(self.style.WARNING('='*100))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n🔍 DRY RUN MODE - Showing issues only\n'))
        elif fix_fees:
            self.stdout.write(self.style.WARNING('\n⚠️  FIX MODE - Will recalculate fees for problem candidates\n'))
        
        # Get all candidates with enrollments
        candidates_with_enrollments = Candidate.objects.filter(
            Q(candidatelevel__isnull=False) | Q(candidatemodule__isnull=False)
        ).distinct()
        
        if specific_center:
            candidates_with_enrollments = candidates_with_enrollments.filter(
                assessment_center__center_number=specific_center
            )
        
        # Group by center and series
        center_series_data = defaultdict(lambda: {
            'candidates': [],
            'center': None,
            'series': None
        })
        
        for candidate in candidates_with_enrollments:
            if not candidate.assessment_center:
                continue
            
            center_id = candidate.assessment_center.id
            series_id = candidate.assessment_series.id if candidate.assessment_series else None
            key = f"{center_id}_{series_id}"
            
            center_series_data[key]['candidates'].append(candidate)
            center_series_data[key]['center'] = candidate.assessment_center
            center_series_data[key]['series'] = candidate.assessment_series
        
        # Analyze each center-series combination
        total_centers_checked = 0
        centers_with_issues = 0
        total_candidates_fixed = 0
        total_amount_corrected = Decimal('0.00')
        
        self.stdout.write(self.style.HTTP_INFO('\n📊 ANALYZING CENTERS...\n'))
        self.stdout.write('-'*100)
        
        for key, data in center_series_data.items():
            total_centers_checked += 1
            candidates = data['candidates']
            center = data['center']
            series = data['series']
            
            center_name = center.center_name
            center_number = center.center_number
            series_name = series.name if series else 'No Series'
            
            # Count candidates
            total_candidates = len(candidates)
            
            # Calculate what fees SHOULD be
            expected_total = Decimal('0.00')
            actual_total = Decimal('0.00')
            
            candidates_with_zero_fees = []
            candidates_with_wrong_fees = []
            
            for candidate in candidates:
                # Calculate what the fee SHOULD be
                calculated_fee = candidate.calculate_fees_balance()
                current_fee = candidate.fees_balance
                
                expected_total += calculated_fee
                actual_total += current_fee
                
                # Check for discrepancies
                if calculated_fee > 0 and current_fee == 0:
                    # Candidate should be billed but isn't
                    candidates_with_zero_fees.append({
                        'candidate': candidate,
                        'expected': calculated_fee,
                        'actual': current_fee
                    })
                elif abs(calculated_fee - current_fee) > Decimal('0.01'):
                    # Fee is wrong
                    candidates_with_wrong_fees.append({
                        'candidate': candidate,
                        'expected': calculated_fee,
                        'actual': current_fee
                    })
            
            # Check if there's a discrepancy
            discrepancy = abs(expected_total - actual_total)
            
            if discrepancy > Decimal('0.01'):  # More than 1 cent difference
                centers_with_issues += 1
                
                self.stdout.write(self.style.ERROR(f'\n❌ DISCREPANCY FOUND: {center_name} ({center_number}) - {series_name}'))
                self.stdout.write(f'   Total Candidates: {total_candidates}')
                self.stdout.write(f'   Expected Total Fees: UGX {expected_total:,.2f}')
                self.stdout.write(f'   Actual Total Fees: UGX {actual_total:,.2f}')
                self.stdout.write(self.style.ERROR(f'   DIFFERENCE: UGX {discrepancy:,.2f}'))
                
                # Show candidates with zero fees
                if candidates_with_zero_fees:
                    self.stdout.write(f'\n   🔴 {len(candidates_with_zero_fees)} candidates with ZERO fees (but should be billed):')
                    for item in candidates_with_zero_fees[:10]:  # Show first 10
                        cand = item['candidate']
                        self.stdout.write(
                            f'      - {cand.reg_number} ({cand.full_name}) - '
                            f'Expected: UGX {item["expected"]:,.2f}, Actual: UGX {item["actual"]:,.2f}'
                        )
                    if len(candidates_with_zero_fees) > 10:
                        self.stdout.write(f'      ... and {len(candidates_with_zero_fees) - 10} more')
                
                # Show candidates with wrong fees
                if candidates_with_wrong_fees:
                    self.stdout.write(f'\n   ⚠️  {len(candidates_with_wrong_fees)} candidates with INCORRECT fees:')
                    for item in candidates_with_wrong_fees[:5]:  # Show first 5
                        cand = item['candidate']
                        self.stdout.write(
                            f'      - {cand.reg_number} ({cand.full_name}) - '
                            f'Expected: UGX {item["expected"]:,.2f}, Actual: UGX {item["actual"]:,.2f}'
                        )
                    if len(candidates_with_wrong_fees) > 5:
                        self.stdout.write(f'      ... and {len(candidates_with_wrong_fees) - 5} more')
                
                # FIX if requested
                if fix_fees and not dry_run:
                    self.stdout.write(f'\n   🔧 FIXING {len(candidates_with_zero_fees) + len(candidates_with_wrong_fees)} candidates...')
                    
                    for item in candidates_with_zero_fees + candidates_with_wrong_fees:
                        candidate = item['candidate']
                        old_fee = candidate.fees_balance
                        new_fee = item['expected']
                        
                        candidate.fees_balance = new_fee
                        candidate.save(update_fields=['fees_balance'])
                        
                        total_candidates_fixed += 1
                        total_amount_corrected += abs(new_fee - old_fee)
                    
                    self.stdout.write(self.style.SUCCESS(f'   ✓ Fixed {len(candidates_with_zero_fees) + len(candidates_with_wrong_fees)} candidates'))
            else:
                self.stdout.write(f'✓ {center_name} ({center_number}) - {series_name}: {total_candidates} candidates, UGX {actual_total:,.2f}')
        
        # Summary
        self.stdout.write('\n' + '='*100)
        self.stdout.write(self.style.HTTP_INFO('📈 AUDIT SUMMARY'))
        self.stdout.write('='*100)
        self.stdout.write(f'\nTotal Center-Series Combinations Checked: {total_centers_checked}')
        self.stdout.write(f'Centers with Discrepancies: {centers_with_issues}')
        
        if fix_fees and not dry_run:
            self.stdout.write(f'\nTotal Candidates Fixed: {total_candidates_fixed}')
            self.stdout.write(f'Total Amount Corrected: UGX {total_amount_corrected:,.2f}')
            self.stdout.write(self.style.SUCCESS('\n✓ FEES RECALCULATED SUCCESSFULLY'))
        elif dry_run:
            self.stdout.write(self.style.NOTICE('\nℹ️  Run with --fix to apply corrections'))
        
        self.stdout.write('='*100 + '\n')
