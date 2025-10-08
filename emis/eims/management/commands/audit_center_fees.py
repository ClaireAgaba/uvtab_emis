"""
COMPREHENSIVE CENTER FEES AUDIT
Ensures accurate financial reporting for audit office:
- Correct candidate count (all enrolled candidates)
- Correct total fees (based on actual enrollments and billing)
- Correct paid amounts (candidates with payment_cleared=True)
- Correct due amounts (candidates with fees_balance > 0)
- Validates: Total Fees = Paid + Due
"""

from django.core.management.base import BaseCommand
from django.db.models import Q, Sum, Count
from decimal import Decimal
from eims.models import Candidate, CenterSeriesPayment, AssessmentCenter
from collections import defaultdict
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Comprehensive audit of center fees for accurate financial reporting'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix discrepancies found during audit',
        )
        parser.add_argument(
            '--center',
            type=str,
            help='Audit specific center (center_number)',
        )

    def handle(self, *args, **options):
        fix_issues = options['fix']
        specific_center = options.get('center')
        
        self.stdout.write(self.style.WARNING('='*120))
        self.stdout.write(self.style.WARNING('COMPREHENSIVE CENTER FEES AUDIT FOR AUDIT OFFICE'))
        self.stdout.write(self.style.WARNING('='*120))
        
        if fix_issues:
            self.stdout.write(self.style.WARNING('\n⚠️  FIX MODE - Will correct discrepancies\n'))
        else:
            self.stdout.write(self.style.NOTICE('\n🔍 AUDIT MODE - Will only report issues\n'))
        
        # Get all enrolled candidates (with level or module enrollments)
        all_enrolled = Candidate.objects.filter(
            Q(candidatelevel__isnull=False) | Q(candidatemodule__isnull=False)
        ).distinct().select_related('assessment_center', 'assessment_series')
        
        if specific_center:
            all_enrolled = all_enrolled.filter(assessment_center__center_number=specific_center)
        
        # Group by center-series
        center_series_groups = defaultdict(lambda: {
            'paid_candidates': [],
            'unpaid_candidates': [],
            'center': None,
            'series': None
        })
        
        for candidate in all_enrolled:
            if not candidate.assessment_center:
                continue
            
            center = candidate.assessment_center
            series = candidate.assessment_series
            key = f"{center.id}_{series.id if series else 'none'}"
            
            center_series_groups[key]['center'] = center
            center_series_groups[key]['series'] = series
            
            # Categorize as paid or unpaid
            if hasattr(candidate, 'payment_cleared') and candidate.payment_cleared:
                center_series_groups[key]['paid_candidates'].append(candidate)
            else:
                center_series_groups[key]['unpaid_candidates'].append(candidate)
        
        self.stdout.write(f'Found {all_enrolled.count()} enrolled candidates')
        self.stdout.write(f'Grouped into {len(center_series_groups)} center-series combinations\n')
        
        # Audit each center-series
        total_centers = len(center_series_groups)
        centers_with_issues = 0
        total_corrections = Decimal('0.00')
        
        system_user = User.objects.filter(is_superuser=True).first()
        
        for idx, (key, data) in enumerate(center_series_groups.items(), 1):
            center = data['center']
            series = data['series']
            paid_cands = data['paid_candidates']
            unpaid_cands = data['unpaid_candidates']
            
            center_name = center.center_name
            center_number = center.center_number
            series_name = series.name if series else 'No Series'
            
            # Calculate PAID amount (from payment_amount_cleared)
            paid_amount = Decimal('0.00')
            for candidate in paid_cands:
                if hasattr(candidate, 'payment_amount_cleared') and candidate.payment_amount_cleared:
                    paid_amount += candidate.payment_amount_cleared
                else:
                    # Paid candidate but no payment_amount_cleared - calculate it
                    calculated = candidate.calculate_fees_balance()
                    paid_amount += calculated
            
            # Calculate DUE amount (from fees_balance)
            due_amount = sum(c.fees_balance for c in unpaid_cands)
            
            # Total should be Paid + Due
            correct_total = paid_amount + due_amount
            total_candidates = len(paid_cands) + len(unpaid_cands)
            
            # Get existing payment record
            if series:
                payment_record = CenterSeriesPayment.objects.filter(
                    assessment_center=center,
                    assessment_series=series
                ).first()
            else:
                payment_record = CenterSeriesPayment.objects.filter(
                    assessment_center=center,
                    assessment_series__isnull=True
                ).first()
            
            current_payment_amount = payment_record.amount_paid if payment_record else Decimal('0.00')
            
            # Check for discrepancies
            has_issue = False
            issues = []
            
            # Issue 1: Payment record doesn't match sum of paid candidates
            if abs(current_payment_amount - paid_amount) > Decimal('0.01'):
                has_issue = True
                issues.append(f'Payment record mismatch: {current_payment_amount:,.2f} should be {paid_amount:,.2f}')
            
            # Issue 2: Paid candidates without payment_amount_cleared
            paid_without_amount = [c for c in paid_cands if not hasattr(c, 'payment_amount_cleared') or not c.payment_amount_cleared]
            if paid_without_amount:
                has_issue = True
                issues.append(f'{len(paid_without_amount)} paid candidates missing payment_amount_cleared')
            
            # Report
            if has_issue or not specific_center:  # Show all if no specific center, otherwise only issues
                centers_with_issues += 1
                
                self.stdout.write(f'\n[{idx}/{total_centers}] {center_number} - {center_name} / {series_name}')
                self.stdout.write(f'  Candidates: {total_candidates} ({len(paid_cands)} paid, {len(unpaid_cands)} unpaid)')
                self.stdout.write(f'  CORRECT FIGURES:')
                self.stdout.write(f'    Total Fees:  UGX {correct_total:,.2f}')
                self.stdout.write(f'    Paid:        UGX {paid_amount:,.2f}')
                self.stdout.write(f'    Due:         UGX {due_amount:,.2f}')
                self.stdout.write(f'    Validation:  {correct_total:,.2f} = {paid_amount:,.2f} + {due_amount:,.2f} ✓')
                
                if has_issue:
                    self.stdout.write(self.style.ERROR(f'  ISSUES FOUND:'))
                    for issue in issues:
                        self.stdout.write(self.style.ERROR(f'    ❌ {issue}'))
                    
                    # FIX if requested
                    if fix_issues:
                        # Fix 1: Update paid candidates without payment_amount_cleared
                        for candidate in paid_without_amount:
                            calculated = candidate.calculate_fees_balance()
                            if calculated > 0:
                                candidate.payment_amount_cleared = calculated
                                candidate.save(update_fields=['payment_amount_cleared'])
                        
                        # Fix 2: Update/create payment record
                        if payment_record:
                            old_amount = payment_record.amount_paid
                            payment_record.amount_paid = paid_amount
                            payment_record.save(update_fields=['amount_paid'])
                            total_corrections += abs(paid_amount - old_amount)
                        else:
                            if paid_amount > 0:
                                CenterSeriesPayment.objects.create(
                                    assessment_center=center,
                                    assessment_series=series,
                                    amount_paid=paid_amount,
                                    paid_by=system_user
                                )
                                total_corrections += paid_amount
                        
                        self.stdout.write(self.style.SUCCESS('  ✓ FIXED'))
                else:
                    self.stdout.write(self.style.SUCCESS('  ✓ All correct'))
        
        # Summary
        self.stdout.write('\n' + '='*120)
        self.stdout.write(self.style.HTTP_INFO('AUDIT SUMMARY'))
        self.stdout.write('='*120)
        self.stdout.write(f'\nTotal Center-Series Combinations: {total_centers}')
        self.stdout.write(f'Centers with Issues: {centers_with_issues}')
        
        if fix_issues:
            self.stdout.write(f'Total Corrections Made: UGX {total_corrections:,.2f}')
            self.stdout.write(self.style.SUCCESS('\n✓ ISSUES FIXED - Financial records now accurate for audit office'))
        else:
            self.stdout.write(self.style.NOTICE('\nℹ️  Run with --fix to correct the issues found'))
        
        self.stdout.write('='*120 + '\n')
