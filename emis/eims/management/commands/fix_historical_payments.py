"""
BETTER APPROACH: Fix historical payments using ACTUAL candidate count × standard fee
Instead of trying to calculate individual fees (which might be wrong for old data),
we calculate: Number of paid candidates × UGX 70,000 (standard module fee)
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from decimal import Decimal
from eims.models import Candidate, CenterSeriesPayment, AssessmentCenter, AssessmentSeries
from django.contrib.auth import get_user_model
from django.utils import timezone
from collections import defaultdict

User = get_user_model()

class Command(BaseCommand):
    help = 'Fix historical payments using candidate count × standard fee'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--fee-per-candidate',
            type=int,
            default=70000,
            help='Standard fee per candidate (default: 70000)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fee_per_candidate = Decimal(str(options['fee_per_candidate']))
        
        self.stdout.write(self.style.WARNING('='*100))
        self.stdout.write(self.style.WARNING('FIX HISTORICAL PAYMENTS USING CANDIDATE COUNT × STANDARD FEE'))
        self.stdout.write(self.style.WARNING('='*100))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE(f'\n🔍 DRY RUN MODE - Fee per candidate: UGX {fee_per_candidate:,.2f}\n'))
        else:
            self.stdout.write(self.style.WARNING(f'\n⚠️  LIVE MODE - Fee per candidate: UGX {fee_per_candidate:,.2f}\n'))
        
        # Find historical cleared candidates (fees_balance = 0 with enrollments)
        historical_candidates = Candidate.objects.filter(
            fees_balance=0,
            payment_cleared=False
        ).filter(
            Q(candidatelevel__isnull=False) | Q(candidatemodule__isnull=False)
        ).distinct().select_related('assessment_center', 'assessment_series')
        
        # Group by center-series
        center_series_groups = defaultdict(list)
        for candidate in historical_candidates:
            if not candidate.assessment_center:
                continue
            
            center = candidate.assessment_center
            series = candidate.assessment_series
            key = f"{center.id}_{series.id if series else 'none'}"
            center_series_groups[key].append({
                'candidate': candidate,
                'center': center,
                'series': series
            })
        
        self.stdout.write(f'\nFound {historical_candidates.count()} historical cleared candidates')
        self.stdout.write(f'Grouped into {len(center_series_groups)} center-series combinations\n')
        
        # Process each center-series group
        system_user = User.objects.filter(is_superuser=True).first()
        
        for key, candidates_data in center_series_groups.items():
            center = candidates_data[0]['center']
            series = candidates_data[0]['series']
            count = len(candidates_data)
            
            # Calculate total for this center-series
            total_amount = count * fee_per_candidate
            
            center_name = center.center_name
            series_name = series.name if series else 'No Series'
            
            self.stdout.write(
                f'\n{center_name} ({center.center_number}) - {series_name}:'
            )
            self.stdout.write(
                f'  {count} candidates × UGX {fee_per_candidate:,.2f} = UGX {total_amount:,.2f}'
            )
            
            if not dry_run:
                # Mark each candidate as paid
                for item in candidates_data:
                    candidate = item['candidate']
                    candidate.payment_cleared = True
                    candidate.payment_cleared_date = candidate.created_at if hasattr(candidate, 'created_at') else timezone.now()
                    candidate.payment_cleared_by = system_user
                    candidate.payment_amount_cleared = fee_per_candidate
                    candidate.payment_center_series_ref = f"{center.id}_{series.id if series else 'none'}_historical"
                    candidate.save(update_fields=[
                        'payment_cleared',
                        'payment_cleared_date',
                        'payment_cleared_by',
                        'payment_amount_cleared',
                        'payment_center_series_ref'
                    ])
                
                # Create or update CenterSeriesPayment record
                payment_record, created = CenterSeriesPayment.objects.get_or_create(
                    assessment_center=center,
                    assessment_series=series,
                    defaults={
                        'amount_paid': total_amount,
                        'paid_by': system_user
                    }
                )
                
                if not created:
                    payment_record.amount_paid += total_amount
                    payment_record.save(update_fields=['amount_paid'])
                    self.stdout.write(f'  ✓ Updated payment record: Added UGX {total_amount:,.2f}')
                else:
                    self.stdout.write(f'  ✓ Created payment record: UGX {total_amount:,.2f}')
        
        # Summary
        total_candidates = sum(len(group) for group in center_series_groups.values())
        total_amount = total_candidates * fee_per_candidate
        
        self.stdout.write('\n' + '='*100)
        self.stdout.write(self.style.HTTP_INFO('SUMMARY'))
        self.stdout.write('='*100)
        self.stdout.write(f'\nTotal Historical Candidates: {total_candidates}')
        self.stdout.write(f'Fee Per Candidate: UGX {fee_per_candidate:,.2f}')
        self.stdout.write(f'Total Historical Payment Amount: UGX {total_amount:,.2f}')
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n✓ DRY RUN COMPLETE - Run without --dry-run to apply changes'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ HISTORICAL PAYMENTS FIXED SUCCESSFULLY'))
        
        self.stdout.write('='*100 + '\n')
