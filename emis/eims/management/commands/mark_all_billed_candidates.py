"""
Mark ALL billed candidates (including those without enrollment records)
This handles the data inconsistency where candidates were billed but don't have enrollment records
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from decimal import Decimal
from eims.models import Candidate, CenterSeriesPayment
from collections import defaultdict
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Mark ALL billed candidates as paid (for historical data with fees_balance=0)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--center',
            type=str,
            help='Process specific center only',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        specific_center = options.get('center')
        
        self.stdout.write(self.style.WARNING('='*100))
        self.stdout.write(self.style.WARNING('MARK ALL BILLED CANDIDATES (INCLUDING THOSE WITHOUT ENROLLMENTS)'))
        self.stdout.write(self.style.WARNING('='*100))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n🔍 DRY RUN MODE\n'))
        
        # Find ALL candidates at centers (regardless of enrollment status)
        # Group by center to process them
        from eims.models import AssessmentCenter
        
        if specific_center:
            centers = AssessmentCenter.objects.filter(center_number=specific_center)
        else:
            centers = AssessmentCenter.objects.all()
        
        system_user = User.objects.filter(is_superuser=True).first()
        
        total_paid_marked = 0
        total_unpaid_found = 0
        total_payment_records_created = 0
        
        for center in centers:
            # Get ALL candidates for this center
            all_candidates = Candidate.objects.filter(
                assessment_center=center
            ).select_related('assessment_series')
            
            if not all_candidates.exists():
                continue
            
            # Group by series
            series_groups = defaultdict(list)
            for candidate in all_candidates:
                series = candidate.assessment_series
                key = series.id if series else 'none'
                series_groups[key].append({
                    'candidate': candidate,
                    'series': series
                })
            
            # Process each series
            for series_key, candidates_data in series_groups.items():
                series = candidates_data[0]['series']
                series_name = series.name if series else 'No Series'
                
                paid_count = 0
                unpaid_count = 0
                paid_total = Decimal('0.00')
                unpaid_total = Decimal('0.00')
                
                for item in candidates_data:
                    candidate = item['candidate']
                    
                    # Check if already marked as paid
                    is_already_paid = (hasattr(candidate, 'payment_cleared') and 
                                     candidate.payment_cleared)
                    
                    if candidate.fees_balance == 0 and not is_already_paid:
                        # This candidate was cleared but not marked as paid
                        # Calculate what they should have been billed
                        calculated_fee = candidate.calculate_fees_balance()
                        
                        # If calculated fee is 0, use a default (UGX 70,000 per candidate)
                        if calculated_fee == 0:
                            calculated_fee = Decimal('70000.00')
                        
                        paid_count += 1
                        paid_total += calculated_fee
                        
                        if not dry_run:
                            candidate.payment_cleared = True
                            candidate.payment_cleared_date = (candidate.created_at 
                                                             if hasattr(candidate, 'created_at') 
                                                             else timezone.now())
                            candidate.payment_cleared_by = system_user
                            candidate.payment_amount_cleared = calculated_fee
                            candidate.payment_center_series_ref = f"{center.id}_{series.id if series else 'none'}_historical"
                            candidate.save()
                    
                    elif candidate.fees_balance > 0:
                        unpaid_count += 1
                        unpaid_total += candidate.fees_balance
                
                if paid_count > 0 or unpaid_count > 0:
                    self.stdout.write(
                        f'\n{center.center_number} - {center.center_name} / {series_name}'
                    )
                    self.stdout.write(
                        f'  Paid candidates: {paid_count} = UGX {paid_total:,.2f}'
                    )
                    self.stdout.write(
                        f'  Unpaid candidates: {unpaid_count} = UGX {unpaid_total:,.2f}'
                    )
                    self.stdout.write(
                        f'  Total: {paid_count + unpaid_count} = UGX {(paid_total + unpaid_total):,.2f}'
                    )
                    
                    if paid_count > 0 and not dry_run:
                        # Create/update payment record
                        payment_record, created = CenterSeriesPayment.objects.get_or_create(
                            assessment_center=center,
                            assessment_series=series,
                            defaults={
                                'amount_paid': paid_total,
                                'paid_by': system_user
                            }
                        )
                        
                        if not created:
                            payment_record.amount_paid = paid_total
                            payment_record.save()
                        
                        if created:
                            total_payment_records_created += 1
                        
                        self.stdout.write(self.style.SUCCESS(f'  ✓ Payment record {"created" if created else "updated"}'))
                    
                    total_paid_marked += paid_count
                    total_unpaid_found += unpaid_count
        
        # Summary
        self.stdout.write('\n' + '='*100)
        self.stdout.write(self.style.HTTP_INFO('SUMMARY'))
        self.stdout.write('='*100)
        self.stdout.write(f'\nPaid Candidates Marked: {total_paid_marked}')
        self.stdout.write(f'Unpaid Candidates Found: {total_unpaid_found}')
        self.stdout.write(f'Payment Records Created/Updated: {total_payment_records_created}')
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n✓ DRY RUN COMPLETE - Run without --dry-run to apply changes'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ ALL BILLED CANDIDATES PROCESSED'))
        
        self.stdout.write('='*100 + '\n')
