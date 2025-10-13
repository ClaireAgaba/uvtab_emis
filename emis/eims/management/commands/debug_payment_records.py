"""
Debug command to check what's actually in the payment records vs what the view should show
"""

from django.core.management.base import BaseCommand
from django.db.models import Sum, Count, Q
from decimal import Decimal
from eims.models import Candidate, CenterSeriesPayment, AssessmentCenter, AssessmentSeries

class Command(BaseCommand):
    help = 'Debug payment records to see why PAID column shows UGX 0 (supports filtering by center and series)'

    def add_arguments(self, parser):
        parser.add_argument('--center-number', type=str, help='Filter by assessment center number (e.g., UVT001)')
        parser.add_argument('--series-name', type=str, help='Filter by assessment series name (exact match); use "No series" to target null series')

    def handle(self, *args, **options):
        center_number = options.get('center_number')
        series_name = options.get('series_name')
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
        
        # If specific center filter provided, scope down
        centers_with_data = set()
        if center_number:
            try:
                center = AssessmentCenter.objects.get(center_number__iexact=center_number)
                centers_with_data.add(center)
            except AssessmentCenter.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Center {center_number} not found"))
                return
        
        if not centers_with_data:
            # Add centers with paid candidates
            for candidate in paid_candidates:
                if candidate.assessment_center:
                    centers_with_data.add(candidate.assessment_center)
            # Add centers with payment records
            for payment_rec in payment_records:
                centers_with_data.add(payment_rec.assessment_center)
        
        self.stdout.write(f'\n🔍 CHECKING ALL CENTERS WITH PAYMENT DATA ({len(centers_with_data)} centers):')
        
        for center in sorted(centers_with_data, key=lambda c: c.center_number):
            
            self.stdout.write(f'\n   {center.center_number} - {center.center_name}:')
            
            # Series scoping
            series_obj = None
            series_filter_q = Q()
            if series_name:
                if series_name.lower() == 'no series':
                    series_filter_q = Q(assessment_series__isnull=True)
                else:
                    try:
                        series_obj = AssessmentSeries.objects.get(name=series_name)
                        series_filter_q = Q(assessment_series=series_obj)
                    except AssessmentSeries.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f"Series '{series_name}' not found"))
                        return

            # Count paid candidates
            paid_cands = Candidate.objects.filter(
                Q(assessment_center=center) & Q(payment_cleared=True) & series_filter_q
            )
            paid_cands_count = paid_cands.count()
            paid_cands_total = paid_cands.aggregate(
                total=Sum('payment_amount_cleared')
            )['total'] or Decimal('0.00')
            
            # Count unpaid candidates
            unpaid_cands = Candidate.objects.filter(
                Q(assessment_center=center) & Q(fees_balance__gt=0) & series_filter_q
            )
            unpaid_cands_count = unpaid_cands.count()
            unpaid_cands_total = unpaid_cands.aggregate(
                total=Sum('fees_balance')
            )['total'] or Decimal('0.00')
            
            self.stdout.write(f'      Paid: {paid_cands_count} candidates = UGX {paid_cands_total:,.2f}')
            self.stdout.write(f'      Unpaid: {unpaid_cands_count} candidates = UGX {unpaid_cands_total:,.2f}')
            
            # Check CenterSeriesPayment records for this center
            payment_recs = CenterSeriesPayment.objects.filter(assessment_center=center)
            if series_obj is not None:
                payment_recs = payment_recs.filter(assessment_series=series_obj)
            elif series_name and series_name.lower() == 'no series':
                payment_recs = payment_recs.filter(assessment_series__isnull=True)
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
