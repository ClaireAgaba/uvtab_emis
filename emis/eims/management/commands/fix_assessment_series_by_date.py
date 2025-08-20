#!/usr/bin/env python3

from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Result, Candidate, AssessmentSeries, CandidateLevel, CandidateModule, CandidatePaper
from collections import defaultdict
import logging
from datetime import datetime
import calendar

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fix enrollment and results assessment series based on candidate assessment date'

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
        parser.add_argument(
            '--candidate-id',
            type=int,
            help='Fix specific candidate by ID (optional)',
        )

    def find_correct_assessment_series(self, assessment_date):
        """Find the correct assessment series based on assessment date"""
        if not assessment_date:
            return None
            
        # Extract month and year from assessment date
        month = assessment_date.month
        year = assessment_date.year
        
        # Create the series name pattern (e.g., "May 2025", "August 2025")
        month_name = calendar.month_name[month]
        series_name_pattern = f"{month_name} {year}"
        
        # Try to find exact match first
        try:
            series = AssessmentSeries.objects.get(name__icontains=series_name_pattern)
            return series
        except AssessmentSeries.DoesNotExist:
            pass
        except AssessmentSeries.MultipleObjectsReturned:
            # If multiple matches, get the first one
            series = AssessmentSeries.objects.filter(name__icontains=series_name_pattern).first()
            return series
            
        # Try alternative patterns
        alternative_patterns = [
            f"{month_name} {year} Series",
            f"{month_name}{year}",
            f"{month_name.lower()} {year}",
            f"{month_name[:3]} {year}",  # Short month name
        ]
        
        for pattern in alternative_patterns:
            try:
                series = AssessmentSeries.objects.filter(name__icontains=pattern).first()
                if series:
                    return series
            except:
                continue
                
        # If no exact match, try to find series within the same month/year period
        try:
            # Look for series that fall within the assessment month
            series_in_period = AssessmentSeries.objects.filter(
                start_date__year=year,
                start_date__month=month
            ).first()
            if series_in_period:
                return series_in_period
                
            # Look for series that the assessment date falls within
            series_containing_date = AssessmentSeries.objects.filter(
                start_date__lte=assessment_date,
                end_date__gte=assessment_date
            ).first()
            if series_containing_date:
                return series_containing_date
                
        except:
            pass
            
        return None

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        candidate_id = options.get('candidate_id')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        # Get candidates to process
        if candidate_id:
            candidates = Candidate.objects.filter(id=candidate_id)
            if not candidates.exists():
                self.stdout.write(
                    self.style.ERROR(f'Candidate with ID {candidate_id} not found')
                )
                return
        else:
            candidates = Candidate.objects.all()
        
        total_candidates = candidates.count()
        self.stdout.write(f'Processing {total_candidates} candidates...')
        
        processed = 0
        fixed_enrollment = 0
        fixed_results = 0
        errors = 0
        
        # Process candidates in batches
        for start in range(0, total_candidates, batch_size):
            end = min(start + batch_size, total_candidates)
            batch_candidates = candidates[start:end]
            
            self.stdout.write(f'Processing batch {start//batch_size + 1}: candidates {start+1}-{end}')
            
            for candidate in batch_candidates:
                try:
                    with transaction.atomic():
                        processed += 1
                        
                        # Get candidate's assessment date
                        assessment_date = candidate.assessment_date
                        if not assessment_date:
                            self.stdout.write(
                                self.style.WARNING(f'Candidate {candidate.id} has no assessment date - skipping')
                            )
                            continue
                        
                        # Find correct assessment series
                        correct_series = self.find_correct_assessment_series(assessment_date)
                        if not correct_series:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Could not find assessment series for date {assessment_date} (candidate {candidate.id}) - skipping'
                                )
                            )
                            continue
                        
                        current_series = candidate.assessment_series
                        enrollment_fixed = False
                        results_fixed = False
                        
                        # Fix candidate enrollment assessment series
                        if current_series != correct_series:
                            self.stdout.write(
                                f'Candidate {candidate.id} ({candidate.first_name} {candidate.last_name}): '
                                f'Assessment Date: {assessment_date.strftime("%B %d, %Y")} '
                                f'Current Series: {current_series.name if current_series else "None"} '
                                f'→ Correct Series: {correct_series.name}'
                            )
                            
                            if not dry_run:
                                candidate.assessment_series = correct_series
                                candidate.save()
                            
                            enrollment_fixed = True
                            fixed_enrollment += 1
                        
                        # Fix results assessment series
                        results = Result.objects.filter(candidate=candidate)
                        for result in results:
                            if result.assessment_series != correct_series:
                                self.stdout.write(
                                    f'  → Fixing result {result.id} assessment series: '
                                    f'{result.assessment_series.name if result.assessment_series else "None"} '
                                    f'→ {correct_series.name}'
                                )
                                
                                if not dry_run:
                                    result.assessment_series = correct_series
                                    result.save()
                                
                                results_fixed = True
                        
                        if results_fixed:
                            fixed_results += 1
                        
                        # Fix enrollment records (CandidateLevel, CandidateModule, CandidatePaper)
                        enrollment_records = []
                        enrollment_records.extend(CandidateLevel.objects.filter(candidate=candidate))
                        enrollment_records.extend(CandidateModule.objects.filter(candidate=candidate))
                        enrollment_records.extend(CandidatePaper.objects.filter(candidate=candidate))
                        
                        for record in enrollment_records:
                            if hasattr(record, 'assessment_series') and record.assessment_series != correct_series:
                                self.stdout.write(
                                    f'  → Fixing enrollment record {type(record).__name__} {record.id} assessment series'
                                )
                                
                                if not dry_run:
                                    record.assessment_series = correct_series
                                    record.save()
                        
                        if enrollment_fixed or results_fixed:
                            self.stdout.write(
                                self.style.SUCCESS(f'✓ Fixed candidate {candidate.id}')
                            )
                        
                except Exception as e:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f'Error processing candidate {candidate.id}: {str(e)}')
                    )
                    logger.error(f'Error processing candidate {candidate.id}: {str(e)}')
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SUMMARY:'))
        self.stdout.write(f'Total candidates processed: {processed}')
        self.stdout.write(f'Enrollment series fixed: {fixed_enrollment}')
        self.stdout.write(f'Results series fixed: {fixed_results}')
        self.stdout.write(f'Errors: {errors}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nThis was a DRY RUN - no changes were made.')
            )
            self.stdout.write(
                self.style.WARNING('Run without --dry-run to apply these changes.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\nAssessment series correction completed!')
            )
