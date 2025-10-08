"""
Synchronize CenterSeriesPayment.amount_paid with sum of candidates' payment_amount_cleared
This fixes the issue where payment records exist but have wrong amounts
"""

from django.core.management.base import BaseCommand
from django.db.models import Sum
from decimal import Decimal
from eims.models import Candidate, CenterSeriesPayment
from collections import defaultdict
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Sync CenterSeriesPayment amounts with candidates payment_amount_cleared'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.WARNING('='*100))
        self.stdout.write(self.style.WARNING('SYNC CENTERSERIESPAYMENT RECORDS WITH CANDIDATES'))
        self.stdout.write(self.style.WARNING('='*100))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n🔍 DRY RUN MODE\n'))
        
        # Get all paid candidates grouped by center-series
        paid_candidates = Candidate.objects.filter(
            payment_cleared=True,
            assessment_center__isnull=False
        ).select_related('assessment_center', 'assessment_series')
        
        self.stdout.write(f'Found {paid_candidates.count()} paid candidates\n')
        
        # Group by center-series
        center_series_totals = defaultdict(lambda: {'candidates': [], 'total': Decimal('0.00')})
        
        for candidate in paid_candidates:
            center = candidate.assessment_center
            series = candidate.assessment_series
            key = f"{center.id}_{series.id if series else 'none'}"
            
            amount = candidate.payment_amount_cleared or Decimal('0.00')
            center_series_totals[key]['candidates'].append(candidate)
            center_series_totals[key]['total'] += amount
            center_series_totals[key]['center'] = center
            center_series_totals[key]['series'] = series
        
        self.stdout.write(f'Grouped into {len(center_series_totals)} center-series combinations\n')
        
        # Check each center-series combination
        records_updated = 0
        records_created = 0
        total_difference = Decimal('0.00')
        
        system_user = User.objects.filter(is_superuser=True).first()
        
        for key, data in center_series_totals.items():
            center = data['center']
            series = data['series']
            correct_total = data['total']
            candidate_count = len(data['candidates'])
            
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
            
            center_name = center.center_name
            series_name = series.name if series else 'No Series'
            
            if payment_record:
                old_amount = payment_record.amount_paid
                difference = correct_total - old_amount
                
                if abs(difference) > Decimal('0.01'):  # More than 1 cent difference
                    self.stdout.write(
                        f'\n⚠️  {center_name} - {series_name}:'
                    )
                    self.stdout.write(
                        f'   {candidate_count} paid candidates'
                    )
                    self.stdout.write(
                        f'   Old amount: UGX {old_amount:,.2f}'
                    )
                    self.stdout.write(
                        f'   Correct amount: UGX {correct_total:,.2f}'
                    )
                    self.stdout.write(
                        f'   Difference: UGX {difference:,.2f}'
                    )
                    
                    if not dry_run:
                        payment_record.amount_paid = correct_total
                        payment_record.save(update_fields=['amount_paid'])
                        self.stdout.write(self.style.SUCCESS('   ✓ Updated'))
                    
                    records_updated += 1
                    total_difference += abs(difference)
            else:
                # No payment record exists - create one
                self.stdout.write(
                    f'\n🆕 {center_name} - {series_name}:'
                )
                self.stdout.write(
                    f'   {candidate_count} paid candidates'
                )
                self.stdout.write(
                    f'   Creating payment record: UGX {correct_total:,.2f}'
                )
                
                if not dry_run:
                    CenterSeriesPayment.objects.create(
                        assessment_center=center,
                        assessment_series=series,
                        amount_paid=correct_total,
                        paid_by=system_user
                    )
                    self.stdout.write(self.style.SUCCESS('   ✓ Created'))
                
                records_created += 1
                total_difference += correct_total
        
        # Summary
        self.stdout.write('\n' + '='*100)
        self.stdout.write(self.style.HTTP_INFO('SUMMARY'))
        self.stdout.write('='*100)
        self.stdout.write(f'\nRecords Updated: {records_updated}')
        self.stdout.write(f'Records Created: {records_created}')
        self.stdout.write(f'Total Corrections: UGX {total_difference:,.2f}')
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n✓ DRY RUN COMPLETE - Run without --dry-run to apply changes'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ PAYMENT RECORDS SYNCHRONIZED SUCCESSFULLY'))
        
        self.stdout.write('='*100 + '\n')
