from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Result, AssessmentSeries
from django.utils import timezone


class Command(BaseCommand):
    help = 'Update all Result records to use the candidate\'s current assessment series'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of records to process in each batch (default: 1000)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        
        self.stdout.write(
            self.style.SUCCESS(
                f"{'DRY RUN: ' if dry_run else ''}Updating Result records to use candidate's assessment series"
            )
        )
        
        # Get all results that don't have an assessment series set
        results_without_series = Result.objects.filter(assessment_series__isnull=True)
        total_count = results_without_series.count()
        
        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS("No Result records need updating - all already have assessment series set.")
            )
            return
        
        self.stdout.write(f"Found {total_count} Result records without assessment series")
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        # Process results in batches
        for offset in range(0, total_count, batch_size):
            batch_results = results_without_series[offset:offset + batch_size]
            
            self.stdout.write(f"Processing batch {offset//batch_size + 1}: records {offset + 1} to {min(offset + batch_size, total_count)}")
            
            if not dry_run:
                with transaction.atomic():
                    for result in batch_results:
                        try:
                            # Check if candidate has an assessment series
                            if result.candidate and result.candidate.assessment_series:
                                result.assessment_series = result.candidate.assessment_series
                                result.save(update_fields=['assessment_series'])
                                updated_count += 1
                                
                                if updated_count % 100 == 0:
                                    self.stdout.write(f"  Updated {updated_count} records...")
                            else:
                                skipped_count += 1
                                if skipped_count <= 10:  # Show first 10 skipped records
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f"  Skipped Result ID {result.id}: Candidate {result.candidate} has no assessment series"
                                        )
                                    )
                        except Exception as e:
                            error_count += 1
                            self.stdout.write(
                                self.style.ERROR(
                                    f"  Error updating Result ID {result.id}: {str(e)}"
                                )
                            )
            else:
                # Dry run - just count what would be updated
                for result in batch_results:
                    if result.candidate and result.candidate.assessment_series:
                        updated_count += 1
                        if updated_count <= 10:  # Show first 10 examples
                            self.stdout.write(
                                f"  Would update Result ID {result.id}: {result.candidate} -> {result.candidate.assessment_series.name}"
                            )
                    else:
                        skipped_count += 1
                        if skipped_count <= 10:  # Show first 10 examples
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  Would skip Result ID {result.id}: Candidate {result.candidate} has no assessment series"
                                )
                            )
        
        # Summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write(f"{'DRY RUN ' if dry_run else ''}SUMMARY:")
        self.stdout.write(f"Total Result records processed: {total_count}")
        self.stdout.write(f"Records {'that would be ' if dry_run else ''}updated: {updated_count}")
        self.stdout.write(f"Records skipped (no candidate series): {skipped_count}")
        if error_count > 0:
            self.stdout.write(f"Records with errors: {error_count}")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\nThis was a dry run. No changes were made. Run without --dry-run to apply changes."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully updated {updated_count} Result records with assessment series!"
                )
            )
            
        # Show statistics about candidates without assessment series
        if skipped_count > 0:
            candidates_without_series = Result.objects.filter(
                assessment_series__isnull=True,
                candidate__assessment_series__isnull=True
            ).values_list('candidate__id', flat=True).distinct().count()
            
            self.stdout.write(
                self.style.WARNING(
                    f"\nNote: {candidates_without_series} candidates don't have assessment series assigned. "
                    "Consider running the sync_assessment_series command first."
                )
            )
