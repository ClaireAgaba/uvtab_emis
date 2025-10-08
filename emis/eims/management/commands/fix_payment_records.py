"""
Management command to fix UVTAB Fees payment records
- Recalculates CenterSeriesPayment amounts based on EXISTING candidates only
- Marks historical cleared candidates (fees_balance=0) with payment_cleared flag
- Provides detailed audit report
"""

from django.core.management.base import BaseCommand
from django.db.models import Sum
from decimal import Decimal
from django.utils import timezone
from eims.models import CenterSeriesPayment, Candidate, AssessmentCenter, AssessmentSeries
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Fix UVTAB Fees payment records and mark historical cleared candidates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making actual changes',
        )
        parser.add_argument(
            '--mark-historical',
            action='store_true',
            help='Mark historical cleared candidates (fees_balance=0) as payment_cleared',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        mark_historical = options['mark_historical']
        
        self.stdout.write(self.style.WARNING('='*80))
        self.stdout.write(self.style.WARNING('UVTAB FEES PAYMENT RECORDS FIX'))
        self.stdout.write(self.style.WARNING('='*80))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n🔍 DRY RUN MODE - No changes will be made\n'))
        
        # Step 1: Mark historical cleared candidates
        if mark_historical:
            self.stdout.write(self.style.HTTP_INFO('\n📋 STEP 1: Marking Historical Cleared Candidates'))
            self.stdout.write('-'*80)
            self.mark_historical_cleared_candidates(dry_run)
        
        # Step 2: Recalculate CenterSeriesPayment amounts
        self.stdout.write(self.style.HTTP_INFO('\n💰 STEP 2: Recalculating Payment Records'))
        self.stdout.write('-'*80)
        self.recalculate_payment_records(dry_run)
        
        # Step 3: Audit report
        self.stdout.write(self.style.HTTP_INFO('\n📊 STEP 3: Financial Audit Report'))
        self.stdout.write('-'*80)
        self.generate_audit_report()
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        if dry_run:
            self.stdout.write(self.style.NOTICE('✓ DRY RUN COMPLETE - Run without --dry-run to apply changes'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ PAYMENT RECORDS FIXED SUCCESSFULLY'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

    def mark_historical_cleared_candidates(self, dry_run):
        """
        Mark candidates with fees_balance=0 and enrollments as historically cleared
        These are candidates who were paid before the payment tracking system was implemented
        """
        # Find candidates who:
        # 1. Have fees_balance = 0
        # 2. Have enrollments (were billed at some point)
        # 3. Don't have payment_cleared flag set
        
        from django.db.models import Q
        
        historical_candidates = Candidate.objects.filter(
            fees_balance=0,
            payment_cleared=False
        ).filter(
            Q(candidatelevel__isnull=False) | Q(candidatemodule__isnull=False)
        ).distinct()
        
        count = historical_candidates.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('   ✓ No historical cleared candidates found'))
            return
        
        self.stdout.write(f'\n   Found {count} historical cleared candidates:')
        
        # Get a system user for historical records
        system_user = User.objects.filter(is_superuser=True).first()
        
        for candidate in historical_candidates:
            # Calculate what their original fee would have been
            original_fee = candidate.calculate_fees_balance()
            
            center_name = candidate.assessment_center.center_name if candidate.assessment_center else 'Unknown'
            series_name = candidate.assessment_series.name if candidate.assessment_series else 'No Series'
            
            self.stdout.write(
                f'   - {candidate.reg_number} ({candidate.full_name}) - '
                f'{center_name} / {series_name} - '
                f'Original Fee: UGX {original_fee:,.2f}'
            )
            
            if not dry_run:
                # Mark as historically cleared
                candidate.payment_cleared = True
                candidate.payment_cleared_date = candidate.created_at if hasattr(candidate, 'created_at') else timezone.now()
                candidate.payment_cleared_by = system_user
                candidate.payment_amount_cleared = original_fee
                
                # Create reference for historical payment
                center_id = candidate.assessment_center.id if candidate.assessment_center else 'none'
                series_id = candidate.assessment_series.id if candidate.assessment_series else 'none'
                candidate.payment_center_series_ref = f"{center_id}_{series_id}_historical"
                
                candidate.save(update_fields=[
                    'payment_cleared',
                    'payment_cleared_date',
                    'payment_cleared_by',
                    'payment_amount_cleared',
                    'payment_center_series_ref'
                ])
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'\n   ✓ Marked {count} candidates as historically cleared'))
        else:
            self.stdout.write(self.style.NOTICE(f'\n   ℹ Would mark {count} candidates as historically cleared'))

    def recalculate_payment_records(self, dry_run):
        """
        Recalculate CenterSeriesPayment.amount_paid based on EXISTING candidates only
        This removes the "ghost" amounts from deleted candidates
        """
        payment_records = CenterSeriesPayment.objects.all()
        
        if not payment_records.exists():
            self.stdout.write(self.style.SUCCESS('   ✓ No payment records to recalculate'))
            return
        
        self.stdout.write(f'\n   Processing {payment_records.count()} payment records...\n')
        
        total_corrections = 0
        
        for payment in payment_records:
            center = payment.assessment_center
            series = payment.assessment_series
            old_amount = payment.amount_paid
            
            # Calculate correct amount based on EXISTING candidates only
            # Get all candidates for this center-series who have been marked as paid
            candidates_query = Candidate.objects.filter(
                assessment_center=center,
                payment_cleared=True
            )
            
            # Filter by series
            if series:
                candidates_query = candidates_query.filter(assessment_series=series)
            else:
                candidates_query = candidates_query.filter(assessment_series__isnull=True)
            
            # Sum up the amount_cleared for existing paid candidates
            correct_amount = candidates_query.aggregate(
                total=Sum('payment_amount_cleared')
            )['total'] or Decimal('0.00')
            
            difference = old_amount - correct_amount
            
            center_name = center.center_name
            series_name = series.name if series else 'No Series'
            
            if difference != 0:
                total_corrections += 1
                self.stdout.write(
                    f'   ⚠ {center_name} / {series_name}\n'
                    f'      Old Amount: UGX {old_amount:,.2f}\n'
                    f'      Correct Amount: UGX {correct_amount:,.2f}\n'
                    f'      Difference: UGX {difference:,.2f} (from deleted candidates)\n'
                )
                
                if not dry_run:
                    payment.amount_paid = correct_amount
                    payment.save(update_fields=['amount_paid'])
            else:
                self.stdout.write(
                    f'   ✓ {center_name} / {series_name} - UGX {old_amount:,.2f} (already correct)'
                )
        
        if total_corrections > 0:
            if not dry_run:
                self.stdout.write(self.style.SUCCESS(f'\n   ✓ Corrected {total_corrections} payment records'))
            else:
                self.stdout.write(self.style.NOTICE(f'\n   ℹ Would correct {total_corrections} payment records'))
        else:
            self.stdout.write(self.style.SUCCESS('\n   ✓ All payment records are already correct'))

    def generate_audit_report(self):
        """Generate a financial audit report"""
        
        # Count paid candidates
        paid_count = Candidate.objects.filter(payment_cleared=True).count()
        paid_total = Candidate.objects.filter(payment_cleared=True).aggregate(
            total=Sum('payment_amount_cleared')
        )['total'] or Decimal('0.00')
        
        # Count unpaid candidates
        unpaid_count = Candidate.objects.filter(fees_balance__gt=0).count()
        unpaid_total = Candidate.objects.filter(fees_balance__gt=0).aggregate(
            total=Sum('fees_balance')
        )['total'] or Decimal('0.00')
        
        # Total in payment records
        payment_records_total = CenterSeriesPayment.objects.aggregate(
            total=Sum('amount_paid')
        )['total'] or Decimal('0.00')
        
        self.stdout.write('\n   FINANCIAL SUMMARY:')
        self.stdout.write('   ' + '-'*60)
        self.stdout.write(f'   Paid Candidates: {paid_count} candidates')
        self.stdout.write(f'   Total Cleared: UGX {paid_total:,.2f}')
        self.stdout.write('')
        self.stdout.write(f'   Unpaid Candidates: {unpaid_count} candidates')
        self.stdout.write(f'   Total Outstanding: UGX {unpaid_total:,.2f}')
        self.stdout.write('')
        self.stdout.write(f'   Payment Records Total: UGX {payment_records_total:,.2f}')
        self.stdout.write('   ' + '-'*60)
        
        # Verify integrity
        if abs(paid_total - payment_records_total) < Decimal('0.01'):  # Allow for rounding
            self.stdout.write(self.style.SUCCESS('   ✓ PAYMENT INTEGRITY CHECK: PASSED'))
            self.stdout.write('   ✓ Payment records match cleared candidate amounts')
        else:
            self.stdout.write(self.style.ERROR('   ✗ PAYMENT INTEGRITY CHECK: FAILED'))
            self.stdout.write(f'   ✗ Mismatch: UGX {abs(paid_total - payment_records_total):,.2f}')
