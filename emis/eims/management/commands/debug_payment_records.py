"""
Debug command to check what's actually in the payment records vs what the view should show
"""

from django.core.management.base import BaseCommand
from django.db.models import Sum, Count
from decimal import Decimal
from eims.models import Candidate, CenterSeriesPayment, AssessmentCenter

class Command(BaseCommand):
    help = 'Debug payment records to see why PAID column shows UGX 0'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('='*100))
        self.stdout.write(self.style.WARNING('DEBUG: PAYMENT RECORDS VS CANDIDATES'))
        self.stdout.write(self.style.WARNING('='*100))
        
        # Check total paid candidates
        paid_candidates = Candidate.objects.filter(payment_cleared=True)
        paid_count = paid_candidates.count()
        paid_total = paid_candidates.aggregate(
            total=Sum('payment_amount_cleared')
        )['total'] or Decimal('0.00')
        
        self.stdout.write(f'\n📊 CANDIDATES DATA:')
        self.stdout.write(f'   Paid Candidates: {paid_count}')
        self.stdout.write(f'   Total payment_amount_cleared: UGX {paid_total:,.2f}')
        
        # Check CenterSeriesPayment records
        payment_records = CenterSeriesPayment.objects.all()
        payment_count = payment_records.count()
        payment_total = payment_records.aggregate(
            total=Sum('amount_paid')
        )['total'] or Decimal('0.00')
        
        self.stdout.write(f'\n💰 CENTERSERIESPAYMENT RECORDS:')
        self.stdout.write(f'   Payment Records: {payment_count}')
        self.stdout.write(f'   Total amount_paid: UGX {payment_total:,.2f}')
        
        # Check specific centers
        self.stdout.write(f'\n🔍 CHECKING SPECIFIC CENTERS:')
        
        test_centers = ['UV1985', 'UV1449', 'UVT003']
        
        for center_num in test_centers:
            center = AssessmentCenter.objects.filter(center_number=center_num).first()
            if not center:
                self.stdout.write(f'\n   {center_num}: NOT FOUND')
                continue
            
            self.stdout.write(f'\n   {center_num} - {center.center_name}:')
            
            # Count paid candidates
            paid_cands = Candidate.objects.filter(
                assessment_center=center,
                payment_cleared=True
            )
            paid_cands_count = paid_cands.count()
            paid_cands_total = paid_cands.aggregate(
                total=Sum('payment_amount_cleared')
            )['total'] or Decimal('0.00')
            
            # Count unpaid candidates
            unpaid_cands = Candidate.objects.filter(
                assessment_center=center,
                fees_balance__gt=0
            )
            unpaid_cands_count = unpaid_cands.count()
            unpaid_cands_total = unpaid_cands.aggregate(
                total=Sum('fees_balance')
            )['total'] or Decimal('0.00')
            
            self.stdout.write(f'      Paid: {paid_cands_count} candidates = UGX {paid_cands_total:,.2f}')
            self.stdout.write(f'      Unpaid: {unpaid_cands_count} candidates = UGX {unpaid_cands_total:,.2f}')
            
            # Check CenterSeriesPayment records for this center
            payment_recs = CenterSeriesPayment.objects.filter(assessment_center=center)
            payment_recs_count = payment_recs.count()
            payment_recs_total = payment_recs.aggregate(
                total=Sum('amount_paid')
            )['total'] or Decimal('0.00')
            
            self.stdout.write(f'      CenterSeriesPayment records: {payment_recs_count}')
            self.stdout.write(f'      CenterSeriesPayment total: UGX {payment_recs_total:,.2f}')
            
            # Show each payment record
            for pr in payment_recs:
                series_name = pr.assessment_series.name if pr.assessment_series else 'No Series'
                self.stdout.write(f'         - {series_name}: UGX {pr.amount_paid:,.2f}')
            
            # Check mismatch
            if abs(paid_cands_total - payment_recs_total) > Decimal('0.01'):
                self.stdout.write(self.style.ERROR(
                    f'      ❌ MISMATCH: UGX {abs(paid_cands_total - payment_recs_total):,.2f}'
                ))
            else:
                self.stdout.write(self.style.SUCCESS('      ✓ Amounts match'))
        
        self.stdout.write('\n' + '='*100 + '\n')
