from django.core.management.base import BaseCommand
from eims.models import AssessmentCenter, CenterSeriesPayment, AssessmentSeries
from decimal import Decimal


class Command(BaseCommand):
    help = 'Check payment records for a specific center'

    def add_arguments(self, parser):
        parser.add_argument('center_number', type=str, help='Center number (e.g., UVT634)')

    def handle(self, *args, **options):
        center_number = options['center_number']
        
        try:
            center = AssessmentCenter.objects.get(center_number=center_number)
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Center {center_number} not found'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\n=== PAYMENT RECORDS FOR {center.center_name} ===\n'))
        
        # Get all payment records for this center
        payment_records = CenterSeriesPayment.objects.filter(assessment_center=center)
        
        if not payment_records.exists():
            self.stdout.write(self.style.WARNING('No payment records found for this center'))
        else:
            self.stdout.write(f'Found {payment_records.count()} payment record(s):\n')
            
            total_paid = Decimal('0.00')
            for record in payment_records:
                series_name = record.assessment_series.name if record.assessment_series else 'No Series'
                self.stdout.write(f'\nAssessment Series: {series_name}')
                self.stdout.write(f'  Amount Paid: UGX {record.amount_paid:,.2f}')
                if hasattr(record, 'payment_date'):
                    self.stdout.write(f'  Payment Date: {record.payment_date}')
                total_paid += record.amount_paid
            
            self.stdout.write(f'\nTotal Across All Series: UGX {total_paid:,.2f}')
        
        # Check if there's a November 2025 series
        try:
            nov_2025 = AssessmentSeries.objects.filter(name__icontains='November 2025').first()
            if nov_2025:
                self.stdout.write(f'\n--- November 2025 Series Found ---')
                self.stdout.write(f'Series ID: {nov_2025.id}')
                self.stdout.write(f'Series Name: {nov_2025.name}')
                
                # Check if there's a payment record for this series
                payment = CenterSeriesPayment.objects.filter(
                    assessment_center=center,
                    assessment_series=nov_2025
                ).first()
                
                if payment:
                    self.stdout.write(f'\nPayment Record Exists:')
                    self.stdout.write(f'  Amount Paid: UGX {payment.amount_paid:,.2f}')
                    
                    if payment.amount_paid == Decimal('12910000.00'):
                        self.stdout.write(self.style.WARNING('\n⚠️  FOUND THE ISSUE!'))
                        self.stdout.write(self.style.WARNING(f'Payment record has WRONG amount: UGX 12,910,000.00'))
                        self.stdout.write(self.style.WARNING(f'Should be: UGX 12,140,000.00'))
                        self.stdout.write(self.style.WARNING(f'Difference: UGX 770,000.00'))
                else:
                    self.stdout.write('\nNo payment record for November 2025 Series')
        except Exception as e:
            self.stdout.write(f'\nError checking November 2025 series: {e}')
        
        self.stdout.write(self.style.SUCCESS(f'\n=== CHECK COMPLETE ==='))
