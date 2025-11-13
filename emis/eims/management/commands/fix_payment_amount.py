from django.core.management.base import BaseCommand
from eims.models import AssessmentCenter, CenterSeriesPayment, AssessmentSeries
from decimal import Decimal


class Command(BaseCommand):
    help = 'Fix incorrect payment amount for a center-series combination'

    def add_arguments(self, parser):
        parser.add_argument('center_number', type=str, help='Center number (e.g., UVT634)')
        parser.add_argument('series_id', type=int, help='Assessment Series ID')
        parser.add_argument('correct_amount', type=float, help='Correct payment amount')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually changing it',
        )

    def handle(self, *args, **options):
        center_number = options['center_number']
        series_id = options['series_id']
        correct_amount = Decimal(str(options['correct_amount']))
        dry_run = options['dry_run']
        
        try:
            center = AssessmentCenter.objects.get(center_number=center_number)
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Center {center_number} not found'))
            return
        
        try:
            series = AssessmentSeries.objects.get(id=series_id)
        except AssessmentSeries.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Assessment Series {series_id} not found'))
            return
        
        mode = 'DRY RUN' if dry_run else 'FIXING'
        self.stdout.write(self.style.SUCCESS(f'\n=== {mode}: PAYMENT AMOUNT CORRECTION ===\n'))
        
        self.stdout.write(f'Center: {center.center_name} ({center_number})')
        self.stdout.write(f'Assessment Series: {series.name}')
        
        # Get the payment record
        try:
            payment_record = CenterSeriesPayment.objects.get(
                assessment_center=center,
                assessment_series=series
            )
        except CenterSeriesPayment.DoesNotExist:
            self.stdout.write(self.style.ERROR('No payment record found for this center-series combination'))
            return
        
        old_amount = payment_record.amount_paid
        difference = correct_amount - old_amount
        
        self.stdout.write(f'\nCurrent Amount: UGX {old_amount:,.2f}')
        self.stdout.write(f'Correct Amount: UGX {correct_amount:,.2f}')
        self.stdout.write(f'Difference: UGX {difference:+,.2f}')
        
        if abs(difference) < Decimal('0.01'):
            self.stdout.write(self.style.SUCCESS('\n✓ Amount is already correct!'))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN - No changes will be made'))
            self.stdout.write(f'Would update payment amount from UGX {old_amount:,.2f} to UGX {correct_amount:,.2f}')
        else:
            # Update the payment record
            payment_record.amount_paid = correct_amount
            payment_record.save(update_fields=['amount_paid'])
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Payment amount updated successfully!'))
            self.stdout.write(f'Old Amount: UGX {old_amount:,.2f}')
            self.stdout.write(f'New Amount: UGX {correct_amount:,.2f}')
            self.stdout.write(f'Corrected by: UGX {difference:+,.2f}')
        
        self.stdout.write(self.style.SUCCESS(f'\n=== CORRECTION COMPLETE ==='))
