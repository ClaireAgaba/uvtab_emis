"""
Management command to check and optionally clear payment records for a center.

This helps fix the invoice doubling issue where CenterSeriesPayment records
exist but shouldn't, causing total_bill to be doubled.

Usage:
    python manage.py clear_payment_record UVT847 --series "November 2025" --dry-run
    python manage.py clear_payment_record UVT847 --series "November 2025"
"""

from django.core.management.base import BaseCommand
from decimal import Decimal
from eims.models import CenterSeriesPayment, AssessmentCenter, AssessmentSeries, Candidate


class Command(BaseCommand):
    help = 'Check and optionally clear payment records for a center'

    def add_arguments(self, parser):
        parser.add_argument(
            'center_number',
            type=str,
            help='Center number (e.g., UVT847)',
        )
        parser.add_argument(
            '--series',
            type=str,
            help='Assessment series name',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview without making changes',
        )

    def handle(self, *args, **options):
        center_number = options['center_number']
        series_name = options.get('series')
        dry_run = options['dry_run']

        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING(f'PAYMENT RECORD CHECK FOR CENTER: {center_number}'))
        self.stdout.write(self.style.WARNING('=' * 80 + '\n'))

        # Get center
        try:
            center = AssessmentCenter.objects.get(center_number__iexact=center_number)
            self.stdout.write(f"📍 Center: {center.center_name}\n")
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Center {center_number} not found"))
            return

        # Get series if specified
        assessment_series = None
        if series_name:
            try:
                assessment_series = AssessmentSeries.objects.get(name__icontains=series_name)
                self.stdout.write(f"📅 Series: {assessment_series.name}\n")
            except AssessmentSeries.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Series '{series_name}' not found"))
                return

        # Check for payment record
        if assessment_series:
            payment = CenterSeriesPayment.objects.filter(
                assessment_center=center,
                assessment_series=assessment_series
            ).first()
        else:
            payment = CenterSeriesPayment.objects.filter(
                assessment_center=center
            ).first()

        if not payment:
            self.stdout.write(self.style.SUCCESS('✅ No payment record found'))
            self.stdout.write('This is good - invoice will show correct total_bill\n')
            return

        # Payment record exists
        self.stdout.write(self.style.WARNING('⚠️  Payment record found:'))
        self.stdout.write(f"   Amount Paid: UGX {payment.amount_paid:,.2f}")
        if payment.payment_date:
            self.stdout.write(f"   Payment Date: {payment.payment_date}")
        self.stdout.write("")

        # Calculate what invoice will show
        if assessment_series:
            candidates = Candidate.objects.filter(
                assessment_center=center,
                assessment_series=assessment_series
            )
        else:
            candidates = Candidate.objects.filter(
                assessment_center=center
            )

        current_outstanding = sum((c.fees_balance or Decimal('0.00')) for c in candidates)
        
        self.stdout.write(f"💰 Current Outstanding (fees_balance): UGX {current_outstanding:,.2f}")
        self.stdout.write(f"💰 Invoice Will Show Total Bill: UGX {(payment.amount_paid + current_outstanding):,.2f}")
        self.stdout.write("")

        # Ask if this is correct
        self.stdout.write(self.style.WARNING('QUESTION: Did this center actually pay UGX {:,.2f}?'.format(payment.amount_paid)))
        self.stdout.write("")
        self.stdout.write("If YES:")
        self.stdout.write("  - Invoice showing {:,.2f} is CORRECT".format(payment.amount_paid + current_outstanding))
        self.stdout.write("  - This is the original bill amount")
        self.stdout.write("  - No action needed\n")
        
        self.stdout.write("If NO:")
        self.stdout.write("  - Payment record should be deleted")
        self.stdout.write("  - Invoice will then show {:,.2f} (correct amount)".format(current_outstanding))
        self.stdout.write("  - Run without --dry-run to delete\n")

        if dry_run:
            self.stdout.write(self.style.NOTICE('🔍 DRY RUN - No changes made'))
        else:
            self.stdout.write(self.style.ERROR('⚠️  DELETING payment record...'))
            payment.delete()
            self.stdout.write(self.style.SUCCESS('✅ Payment record deleted'))
            self.stdout.write(f"\nInvoice will now show:")
            self.stdout.write(f"  Total Bill: UGX {current_outstanding:,.2f}")
            self.stdout.write(f"  Amount Paid: UGX 0.00")
            self.stdout.write(f"  Amount Due: UGX {current_outstanding:,.2f}")

        self.stdout.write('\n' + '=' * 80 + '\n')
