from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Candidate, AssessmentSeries
from datetime import datetime


class Command(BaseCommand):
    help = 'Enroll existing candidates into correct Assessment Series based on their assessment dates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        # Get all candidates that don't have an assessment series assigned
        candidates_without_series = Candidate.objects.filter(assessment_series__isnull=True)
        total_candidates = candidates_without_series.count()
        
        self.stdout.write(f'Found {total_candidates} candidates without assessment series')
        
        # Get all assessment series
        assessment_series = AssessmentSeries.objects.all()
        
        if not assessment_series.exists():
            self.stdout.write(
                self.style.ERROR('No assessment series found. Please create assessment series first.')
            )
            return
        
        updated_count = 0
        not_matched_count = 0
        
        with transaction.atomic():
            for candidate in candidates_without_series:
                # Find matching assessment series based on assessment date
                matching_series = None
                
                for series in assessment_series:
                    # Check if candidate's assessment date falls within series period
                    if series.start_date <= candidate.assessment_date <= series.end_date:
                        matching_series = series
                        break
                
                if matching_series:
                    if not dry_run:
                        candidate.assessment_series = matching_series
                        candidate.save()
                    
                    self.stdout.write(
                        f'{"[DRY RUN] " if dry_run else ""}Enrolled {candidate.full_name} '
                        f'(Assessment Date: {candidate.assessment_date}) '
                        f'into "{matching_series.name}"'
                    )
                    updated_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'No matching assessment series found for {candidate.full_name} '
                            f'(Assessment Date: {candidate.assessment_date})'
                        )
                    )
                    not_matched_count += 1
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(f'SUMMARY:')
        self.stdout.write(f'Total candidates processed: {total_candidates}')
        self.stdout.write(
            self.style.SUCCESS(f'Successfully {"would enroll" if dry_run else "enrolled"}: {updated_count}')
        )
        if not_matched_count > 0:
            self.stdout.write(
                self.style.WARNING(f'Not matched: {not_matched_count}')
            )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nThis was a dry run. Use --dry-run=False to apply changes.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nSuccessfully enrolled {updated_count} candidates into assessment series!')
            )
