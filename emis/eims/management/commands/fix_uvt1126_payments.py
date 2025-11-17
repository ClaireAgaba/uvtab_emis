from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from eims.models import Candidate, AssessmentCenter, CenterSeriesPayment, AssessmentSeries

class Command(BaseCommand):
    help = 'Fix payment records for UVT1126 to match corrected billing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making actual changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('\n=== UVT1126 PAYMENT RECORDS FIX ===\n'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        try:
            center = AssessmentCenter.objects.get(center_number='UVT1126')
            self.stdout.write(f"Center: {center.center_name}\n")
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR("Center UVT1126 not found!"))
            return
        
        # Get November 2025 series
        try:
            series = AssessmentSeries.objects.get(name='November 2025 Series')
            self.stdout.write(f"Assessment Series: {series.name}\n")
        except AssessmentSeries.DoesNotExist:
            self.stdout.write(self.style.ERROR("November 2025 Series not found!"))
            return
        
        # Get all candidates for this center in this series
        candidates = Candidate.objects.filter(
            assessment_center=center,
            assessment_series=series
        )
        
        self.stdout.write(f"Total Candidates: {candidates.count()}\n")
        
        # Calculate correct totals
        total_billed = sum(c.fees_balance for c in candidates)
        
        self.stdout.write(f"Current Total Fees Balance: UGX {total_billed:,.2f}\n")
        
        # Check current payment record
        try:
            payment_record = CenterSeriesPayment.objects.get(
                assessment_center=center,
                assessment_series=series
            )
            self.stdout.write(f"\nExisting Payment Record Found:")
            self.stdout.write(f"  Amount Paid: UGX {payment_record.amount_paid:,.2f}")
            self.stdout.write(f"  Last Updated: {payment_record.updated_at}")
            
            # Calculate what the correct payment should be
            # Total billed = 1,230,000
            # Amount paid from invoice = 1,130,000
            # Amount due = 1,230,000 - 1,130,000 = 100,000
            
            # But we need to verify the actual payment from the invoice
            self.stdout.write(f"\n=== ANALYSIS ===")
            self.stdout.write(f"Correct Total Bill: UGX 1,230,000")
            self.stdout.write(f"Payment from Invoice: UGX 1,130,000")
            self.stdout.write(f"Correct Amount Due: UGX 100,000")
            
            # The issue is that amount_paid might be wrong
            # Let's recalculate based on cleared candidates
            cleared_candidates = candidates.filter(fees_balance=0)
            unpaid_candidates = candidates.exclude(fees_balance=0)
            
            self.stdout.write(f"\nCandidate Breakdown:")
            self.stdout.write(f"  Cleared (balance=0): {cleared_candidates.count()}")
            self.stdout.write(f"  Unpaid (balance>0): {unpaid_candidates.count()}")
            
            # Calculate what was actually paid
            # If a candidate has 0 balance, they were billed and paid
            # We need to recalculate their original bill
            actual_amount_paid = Decimal('0.00')
            
            for candidate in cleared_candidates:
                # Recalculate what they should have been billed
                if candidate.registration_category == 'Modular':
                    actual_amount_paid += Decimal('70000')
                elif candidate.registration_category == 'Formal':
                    from eims.models import CandidateLevel
                    level_enrollments = CandidateLevel.objects.filter(candidate=candidate)
                    if level_enrollments.exists():
                        level_names = [le.level.name for le in level_enrollments]
                        if any('Level 2' in name or 'LEVEL 2' in name for name in level_names):
                            actual_amount_paid += Decimal('100000')
                        elif any('Level 3' in name or 'LEVEL 3' in name for name in level_names):
                            actual_amount_paid += Decimal('150000')
            
            self.stdout.write(f"\nRecalculated Actual Payment: UGX {actual_amount_paid:,.2f}")
            self.stdout.write(f"Current Outstanding: UGX {total_billed:,.2f}")
            self.stdout.write(f"Correct Total Bill: UGX {actual_amount_paid + total_billed:,.2f}")
            
            if actual_amount_paid != payment_record.amount_paid:
                self.stdout.write(self.style.WARNING(
                    f"\n⚠️  Payment record mismatch!"
                ))
                self.stdout.write(f"  Recorded: UGX {payment_record.amount_paid:,.2f}")
                self.stdout.write(f"  Actual: UGX {actual_amount_paid:,.2f}")
                self.stdout.write(f"  Difference: UGX {actual_amount_paid - payment_record.amount_paid:,.2f}")
                
                if not dry_run:
                    confirm = input('\nUpdate payment record to correct amount? (yes/no): ')
                    if confirm.lower() == 'yes':
                        with transaction.atomic():
                            payment_record.amount_paid = actual_amount_paid
                            payment_record.save()
                            self.stdout.write(self.style.SUCCESS(
                                f"\n✓ Updated payment record to UGX {actual_amount_paid:,.2f}"
                            ))
                    else:
                        self.stdout.write(self.style.ERROR('Aborted.'))
                else:
                    self.stdout.write(self.style.WARNING('\nDRY RUN - Would update payment record'))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"\n✓ Payment record is correct!"
                ))
                
        except CenterSeriesPayment.DoesNotExist:
            self.stdout.write(self.style.WARNING("\nNo payment record found for this center-series combination"))
            
            # Calculate actual payment from cleared candidates
            cleared_candidates = candidates.filter(fees_balance=0)
            actual_amount_paid = Decimal('0.00')
            
            for candidate in cleared_candidates:
                if candidate.registration_category == 'Modular':
                    actual_amount_paid += Decimal('70000')
                elif candidate.registration_category == 'Formal':
                    from eims.models import CandidateLevel
                    level_enrollments = CandidateLevel.objects.filter(candidate=candidate)
                    if level_enrollments.exists():
                        level_names = [le.level.name for le in level_enrollments]
                        if any('Level 2' in name or 'LEVEL 2' in name for name in level_names):
                            actual_amount_paid += Decimal('100000')
                        elif any('Level 3' in name or 'LEVEL 3' in name for name in level_names):
                            actual_amount_paid += Decimal('150000')
            
            if actual_amount_paid > 0:
                self.stdout.write(f"Calculated payment from cleared candidates: UGX {actual_amount_paid:,.2f}")
                
                if not dry_run:
                    confirm = input('\nCreate payment record? (yes/no): ')
                    if confirm.lower() == 'yes':
                        with transaction.atomic():
                            payment_record = CenterSeriesPayment.objects.create(
                                assessment_center=center,
                                assessment_series=series,
                                amount_paid=actual_amount_paid
                            )
                            self.stdout.write(self.style.SUCCESS(
                                f"\n✓ Created payment record with UGX {actual_amount_paid:,.2f}"
                            ))
                    else:
                        self.stdout.write(self.style.ERROR('Aborted.'))
                else:
                    self.stdout.write(self.style.WARNING('\nDRY RUN - Would create payment record'))
        
        self.stdout.write('\n')
