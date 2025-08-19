from django.core.management.base import BaseCommand
from eims.models import Candidate, AssessmentSeries, Result
from django.db.models import Q
import calendar

class Command(BaseCommand):
    help = 'Fix candidate assessment series based on their actual result assessment dates (MM/YY)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making actual changes'
        )
        parser.add_argument(
            '--candidate-id',
            type=int,
            help='Fix only specific candidate ID'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        candidate_id = options.get('candidate_id')
        
        # Find candidates that need assessment series correction
        query = Q()
        if candidate_id:
            query &= Q(id=candidate_id)
        
        candidates = Candidate.objects.filter(query)
        
        # Create month-to-series mapping for 2025
        assessment_series_2025 = AssessmentSeries.objects.filter(
            start_date__year=2025
        ).order_by('start_date')
        
        month_to_series = {}
        for series in assessment_series_2025:
            month = series.start_date.month
            month_to_series[month] = series
        
        self.stdout.write('=== AVAILABLE 2025 ASSESSMENT SERIES ===')
        for month, series in month_to_series.items():
            month_name = calendar.month_name[month]
            current_marker = ' (Current)' if series.is_current else ''
            self.stdout.write(f'  {month_name} 2025 (Month {month}) → {series.name}{current_marker}')
        self.stdout.write('')
        
        # Process candidates
        fixed_count = 0
        candidates_processed = 0
        
        for candidate in candidates:
            # Get candidate's results to determine correct assessment series
            results = Result.objects.filter(candidate=candidate).order_by('assessment_date')
            
            if not results.exists():
                continue  # Skip candidates with no results
            
            # Find the most common assessment month/year from results
            result_months = {}
            for result in results:
                if result.assessment_date and result.assessment_date.year == 2025:
                    month = result.assessment_date.month
                    if month in result_months:
                        result_months[month] += 1
                    else:
                        result_months[month] = 1
            
            if not result_months:
                continue  # Skip candidates with no 2025 results
            
            # Get the most frequent month (in case of multiple assessment dates)
            most_common_month = max(result_months, key=result_months.get)
            month_name = calendar.month_name[most_common_month]
            
            # Find the corresponding assessment series
            if most_common_month not in month_to_series:
                self.stdout.write(
                    self.style.ERROR(
                        f'ERROR: No assessment series found for {month_name} 2025 (Month {most_common_month})'
                    )
                )
                continue
            
            correct_series = month_to_series[most_common_month]
            current_series = candidate.assessment_series
            
            # Check if candidate needs update
            if current_series != correct_series:
                candidates_processed += 1
                
                self.stdout.write(f'Candidate: {candidate.full_name} (ID: {candidate.id})')
                self.stdout.write(f'  Registration: {candidate.registration_category}')
                
                # Show result assessment dates
                result_dates = [r.assessment_date.strftime('%Y-%m-%d') for r in results if r.assessment_date]
                self.stdout.write(f'  Result dates: {", ".join(result_dates)}')
                self.stdout.write(f'  Most common month: {month_name} 2025 (Month {most_common_month})')
                
                current_name = current_series.name if current_series else 'None'
                self.stdout.write(f'  Current series: {current_name}')
                self.stdout.write(f'  Correct series: {correct_series.name}')
                
                if not dry_run:
                    candidate.assessment_series = correct_series
                    candidate.save()
                    fixed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Updated to {correct_series.name}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'  [DRY RUN] Would update to {correct_series.name}')
                    )
                
                self.stdout.write('')
        
        # Summary
        self.stdout.write('=== SUMMARY ===')
        if candidates_processed == 0:
            self.stdout.write(
                self.style.SUCCESS('No candidates need assessment series correction based on their result dates.')
            )
        elif dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would fix {candidates_processed} candidates based on their result assessment dates')
            )
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully fixed {fixed_count} candidates based on their result assessment dates')
            )
        
        self.stdout.write('')
        self.stdout.write('=== LOGIC EXPLANATION ===')
        self.stdout.write('This script:')
        self.stdout.write('1. Looks at each candidate\'s actual result assessment dates')
        self.stdout.write('2. Finds the most common month/year from their results')
        self.stdout.write('3. Assigns the matching assessment series for that month')
        self.stdout.write('4. Ensures enrollment assessment series matches result assessment series')
