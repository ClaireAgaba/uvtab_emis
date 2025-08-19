from django.core.management.base import BaseCommand
from eims.models import Result, AssessmentSeries, Candidate
from django.db.models import Q
from datetime import datetime
import calendar

class Command(BaseCommand):
    help = 'Fix assessment series for results based on assessment_date month/year matching'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making actual changes'
        )
        parser.add_argument(
            '--fix-2025-only',
            action='store_true',
            help='Only fix results with 2025 dates, flag others as errors'
        )
        parser.add_argument(
            '--candidate-id',
            type=int,
            help='Fix only specific candidate ID'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fix_2025_only = options['fix_2025_only']
        candidate_id = options.get('candidate_id')
        
        # Find all results without assessment_series
        query = Q(assessment_series__isnull=True)
        if candidate_id:
            query &= Q(candidate_id=candidate_id)
        
        missing_series_results = Result.objects.filter(query).order_by('assessment_date', 'candidate')
        
        if not missing_series_results.exists():
            self.stdout.write(
                self.style.SUCCESS('No results with missing assessment_series found.')
            )
            return
        
        self.stdout.write(f'Found {missing_series_results.count()} results with missing assessment_series')
        self.stdout.write('')
        
        # Get all available 2025 assessment series and create month mapping
        assessment_series_2025 = AssessmentSeries.objects.filter(
            start_date__year=2025
        ).order_by('start_date')
        
        if not assessment_series_2025.exists():
            self.stdout.write(
                self.style.ERROR('No 2025 assessment series found in the system!')
            )
            return
        
        # Create month-to-series mapping
        month_to_series = {}
        for series in assessment_series_2025:
            month = series.start_date.month
            month_name = calendar.month_name[month]
            month_to_series[month] = series
            self.stdout.write(f'Available: {series.name} (Month {month} - {month_name})')
        
        self.stdout.write('')
        
        # Categorize results
        results_2025 = []
        results_non_2025 = []
        
        for result in missing_series_results:
            if result.assessment_date and result.assessment_date.year == 2025:
                results_2025.append(result)
            else:
                results_non_2025.append(result)
        
        # Process 2025 results
        fixed_count = 0
        error_count = 0
        
        if results_2025:
            self.stdout.write(f'=== PROCESSING {len(results_2025)} RESULTS WITH 2025 DATES ===')
            self.stdout.write('')
            
            for result in results_2025:
                month = result.assessment_date.month
                month_name = calendar.month_name[month]
                
                if month in month_to_series:
                    suggested_series = month_to_series[month]
                    
                    self.stdout.write(
                        f'Candidate: {result.candidate.full_name} (ID: {result.candidate.id})'
                    )
                    self.stdout.write(
                        f'  Result: {result.assessment_type} {result.mark} '
                        f'(Date: {result.assessment_date} - {month_name} 2025)'
                    )
                    self.stdout.write(
                        f'  → Assigning: {suggested_series.name}'
                    )
                    
                    if not dry_run:
                        result.assessment_series = suggested_series
                        result.save()
                        fixed_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Assigned {suggested_series.name}')
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'  [DRY RUN] Would assign {suggested_series.name}')
                        )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f'ERROR: No assessment series found for month {month} ({month_name}) 2025'
                        )
                    )
                    error_count += 1
                
                self.stdout.write('')
        
        # Process non-2025 results (flag as errors)
        if results_non_2025:
            self.stdout.write(f'=== FLAGGING {len(results_non_2025)} RESULTS WITH NON-2025 DATES AS ERRORS ===')
            self.stdout.write('')
            
            for result in results_non_2025:
                year = result.assessment_date.year if result.assessment_date else 'Unknown'
                month_name = calendar.month_name[result.assessment_date.month] if result.assessment_date else 'Unknown'
                
                self.stdout.write(
                    self.style.ERROR(
                        f'ERROR: {result.candidate.full_name} (ID: {result.candidate.id}) - '
                        f'{result.assessment_type} {result.mark} '
                        f'(Date: {result.assessment_date} - {month_name} {year})'
                    )
                )
                self.stdout.write(
                    self.style.ERROR(
                        f'  ✗ Non-2025 date detected - MANUAL REVIEW REQUIRED'
                    )
                )
                error_count += 1
                self.stdout.write('')
        
        # Summary
        self.stdout.write('=== SUMMARY ===')
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would fix {len(results_2025)} results from 2025')
            )
            if results_non_2025:
                self.stdout.write(
                    self.style.ERROR(f'ERRORS: {len(results_non_2025)} results with non-2025 dates need manual review')
                )
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully fixed {fixed_count} results from 2025')
            )
            if error_count > 0:
                self.stdout.write(
                    self.style.ERROR(f'ERRORS: {error_count} results need manual review')
                )
        
        # Show month mapping for reference
        self.stdout.write('')
        self.stdout.write('=== MONTH TO ASSESSMENT SERIES MAPPING ===')
        for month, series in month_to_series.items():
            month_name = calendar.month_name[month]
            current_marker = ' (Current)' if series.is_current else ''
            self.stdout.write(f'  {month_name} 2025 (Month {month}) → {series.name}{current_marker}')
        
        if results_non_2025:
            self.stdout.write('')
            self.stdout.write('=== MANUAL REVIEW REQUIRED ===')
            self.stdout.write('The following results have non-2025 dates and need manual correction:')
            for result in results_non_2025:
                year = result.assessment_date.year if result.assessment_date else 'Unknown'
                self.stdout.write(
                    f'  - {result.candidate.full_name}: {result.assessment_type} {result.mark} '
                    f'({result.assessment_date} - Year {year})'
                )
