#!/usr/bin/env python3

from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Result, Candidate, AssessmentSeries
from collections import defaultdict
import logging
import calendar

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Synchronize candidates assessment series enrollment with their result dates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of candidates to process in each batch (default: 50)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        
        self.stdout.write(f"{'DRY RUN: ' if dry_run else ''}Synchronizing assessment series with result dates...")
        
        # Get all candidates who have results
        candidates_with_results = Candidate.objects.filter(
            result__isnull=False
        ).distinct().prefetch_related('result_set').select_related('assessment_series')
        
        total_candidates = candidates_with_results.count()
        self.stdout.write(f"Found {total_candidates} candidates with results to check")
        
        if total_candidates == 0:
            self.stdout.write(self.style.SUCCESS("No candidates with results found!"))
            return
        
        # Track statistics
        candidates_to_update = []
        series_needed = set()
        
        # Analyze each candidate
        for candidate in candidates_with_results:
            # Get all result dates for this candidate
            results = candidate.result_set.all().order_by('assessment_date')
            
            if not results:
                continue
                
            # Group results by month/year
            result_periods = defaultdict(list)
            for result in results:
                if result.assessment_date:
                    month_name = calendar.month_name[result.assessment_date.month]
                    year = result.assessment_date.year
                    period_key = f"{month_name} {year}"
                    result_periods[period_key].append(result)
            
            # Get candidate's current assessment series enrollment
            current_enrollments = set()
            if candidate.assessment_series:
                current_enrollments.add(candidate.assessment_series.series_name)
            
            # Check if candidate needs to be enrolled in series matching their result dates
            needed_series = set(result_periods.keys())
            missing_series = needed_series - current_enrollments
            
            if missing_series:
                candidates_to_update.append({
                    'candidate': candidate,
                    'current_series': current_enrollments,
                    'needed_series': needed_series,
                    'missing_series': missing_series,
                    'result_periods': dict(result_periods)
                })
                series_needed.update(missing_series)
        
        self.stdout.write(f"Found {len(candidates_to_update)} candidates needing series updates")
        self.stdout.write(f"Assessment series needed: {sorted(series_needed)}")
        
        if dry_run:
            self.stdout.write("DRY RUN - showing first 10 candidates that would be updated:")
            for i, update_info in enumerate(candidates_to_update[:10]):
                candidate = update_info['candidate']
                self.stdout.write(
                    f"  {i+1}. {candidate.reg_number} ({candidate.full_name})"
                )
                self.stdout.write(f"     Current series: {update_info['current_series']}")
                self.stdout.write(f"     Needed series: {update_info['needed_series']}")
                self.stdout.write(f"     Missing series: {update_info['missing_series']}")
                
                # Show result periods
                for period, results in update_info['result_periods'].items():
                    self.stdout.write(f"     Results in {period}: {len(results)} results")
                self.stdout.write("")
            
            if len(candidates_to_update) > 10:
                self.stdout.write(f"  ... and {len(candidates_to_update) - 10} more candidates")
            return
        
        # First, ensure all needed assessment series exist
        self.stdout.write("Checking/creating assessment series...")
        created_series = 0
        for series_name in series_needed:
            series, created = AssessmentSeries.objects.get_or_create(
                series_name=series_name,
                defaults={
                    'series_name': series_name,
                    'is_active': True
                }
            )
            if created:
                created_series += 1
                self.stdout.write(f"  Created assessment series: {series_name}")
        
        if created_series > 0:
            self.stdout.write(f"Created {created_series} new assessment series")
        
        # Process candidates in batches
        updated_count = 0
        enrollments_created = 0
        batch_start = 0
        
        while batch_start < len(candidates_to_update):
            batch_end = min(batch_start + batch_size, len(candidates_to_update))
            batch_candidates = candidates_to_update[batch_start:batch_end]
            
            self.stdout.write(f"Processing batch {batch_start + 1}-{batch_end} of {len(candidates_to_update)}...")
            
            try:
                with transaction.atomic():
                    for update_info in batch_candidates:
                        candidate = update_info['candidate']
                        
                        # Update candidate's assessment series (only if they have missing series)
                        if update_info['missing_series']:
                            # For now, we'll assign the most recent series from their results
                            # In the future, you might want to handle multiple series differently
                            most_recent_series = sorted(update_info['needed_series'])[-1]  # Get latest series
                            
                            try:
                                assessment_series = AssessmentSeries.objects.get(series_name=most_recent_series)
                                
                                # Update candidate's assessment series if different
                                if candidate.assessment_series != assessment_series:
                                    old_series = candidate.assessment_series.series_name if candidate.assessment_series else "None"
                                    candidate.assessment_series = assessment_series
                                    candidate.save(update_fields=['assessment_series'])
                                    
                                    enrollments_created += 1
                                    self.stdout.write(
                                        f"  Updated {candidate.reg_number}: {old_series} → {most_recent_series}"
                                    )
                                    
                            except AssessmentSeries.DoesNotExist:
                                self.stdout.write(
                                    self.style.ERROR(f"Assessment series not found: {most_recent_series}")
                                )
                                continue
                        
                        updated_count += 1
                        
                        if updated_count % 25 == 0:
                            self.stdout.write(f"  Processed {updated_count} candidates...")
                            
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing batch {batch_start + 1}-{batch_end}: {e}")
                )
                continue
            
            batch_start = batch_end
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed {updated_count} candidates and created {enrollments_created} new enrollments"
            )
        )
        
        # Summary report
        self.stdout.write("\n" + "="*50)
        self.stdout.write("SUMMARY REPORT")
        self.stdout.write("="*50)
        self.stdout.write(f"Total candidates checked: {total_candidates}")
        self.stdout.write(f"Candidates needing updates: {len(candidates_to_update)}")
        self.stdout.write(f"Candidates processed: {updated_count}")
        self.stdout.write(f"New series enrollments created: {enrollments_created}")
        self.stdout.write(f"Assessment series created: {created_series}")
        
        if enrollments_created > 0:
            self.stdout.write(self.style.SUCCESS("✅ Assessment series synchronization completed!"))
        else:
            self.stdout.write(self.style.SUCCESS("✅ All candidates were already properly enrolled!"))
