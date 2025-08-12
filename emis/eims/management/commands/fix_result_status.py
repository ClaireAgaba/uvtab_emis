from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Result
from django.utils import timezone


class Command(BaseCommand):
    help = 'Fix all Result records to apply the corrected Status logic (first sitting = Normal, subsequent -1 = Missing Paper)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch (default: 100)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting Result Status correction process...'
            )
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        # Get all results (we need to reprocess all to apply corrected logic)
        all_results = Result.objects.all().order_by('candidate', 'paper', 'module', 'assessment_type', 'date')
        
        total_count = all_results.count()
        self.stdout.write(f'Found {total_count} results to process')
        
        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS('No results found. All done!')
            )
            return
        
        updated_count = 0
        missing_paper_count = 0
        normal_count = 0
        retake_count = 0
        
        # Process in batches to avoid memory issues
        for i in range(0, total_count, batch_size):
            batch = all_results[i:i + batch_size]
            
            if not dry_run:
                with transaction.atomic():
                    for result in batch:
                        old_status = result.status
                        
                        # Apply the corrected logic manually
                        # Check if there are previous results for the same candidate, paper/module, and assessment type
                        previous_results = Result.objects.filter(
                            candidate=result.candidate,
                            assessment_type=result.assessment_type
                        )
                        
                        # Filter by paper or module depending on what this result has
                        if result.paper:
                            previous_results = previous_results.filter(paper=result.paper)
                        elif result.module:
                            previous_results = previous_results.filter(module=result.module)
                        
                        # Exclude the current result
                        previous_results = previous_results.exclude(pk=result.pk)
                        
                        # Apply corrected status logic
                        if previous_results.exists():
                            # This is NOT the first sitting
                            if result.mark == -1:
                                # Candidate didn't sit for this subsequent attempt
                                new_status = 'Missing Paper'
                                missing_paper_count += 1
                            else:
                                # Candidate sat for this subsequent attempt (regardless of pass/fail)
                                new_status = 'Retake'
                                retake_count += 1
                        else:
                            # No previous results found, this is the first sitting
                            # Always "Normal" regardless of mark (even if -1)
                            new_status = 'Normal'
                            normal_count += 1
                        
                        # Update the status if it changed
                        if new_status != old_status:
                            Result.objects.filter(id=result.id).update(status=new_status)
                            self.stdout.write(
                                f'Updated Result {result.id}: {old_status} -> {new_status} (Mark: {result.mark})'
                            )
                        
                        updated_count += 1
                        
                        if updated_count % 50 == 0:
                            self.stdout.write(f'Processed {updated_count}/{total_count} results...')
            else:
                # Dry run - just simulate the logic
                for result in batch:
                    # Check if there are previous results for the same candidate, paper/module, and assessment type
                    previous_results = Result.objects.filter(
                        candidate=result.candidate,
                        assessment_type=result.assessment_type
                    )
                    
                    # Filter by paper or module depending on what this result has
                    if result.paper:
                        previous_results = previous_results.filter(paper=result.paper)
                    elif result.module:
                        previous_results = previous_results.filter(module=result.module)
                    
                    # Exclude the current result
                    previous_results = previous_results.exclude(pk=result.pk)
                    
                    # Apply corrected status logic
                    if previous_results.exists():
                        # This is NOT the first sitting
                        if result.mark == -1:
                            # Candidate didn't sit for this subsequent attempt
                            new_status = 'Missing Paper'
                            missing_paper_count += 1
                        else:
                            # Candidate sat for this subsequent attempt (regardless of pass/fail)
                            new_status = 'Retake'
                            retake_count += 1
                    else:
                        # No previous results found, this is the first sitting
                        # Always "Normal" regardless of mark (even if -1)
                        new_status = 'Normal'
                        normal_count += 1
                    
                    if new_status != result.status:
                        self.stdout.write(
                            f'Would update Result {result.id}: {result.status} -> {new_status} (Mark: {result.mark})'
                        )
                
                updated_count += len(batch)
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(
            self.style.SUCCESS(f'Process completed!')
        )
        
        if dry_run:
            self.stdout.write('DRY RUN SUMMARY:')
        else:
            self.stdout.write('UPDATE SUMMARY:')
        
        self.stdout.write(f'Total results processed: {updated_count}')
        self.stdout.write(f'Normal (first sitting): {normal_count}')
        self.stdout.write(f'Retake (subsequent sitting with marks): {retake_count}')
        self.stdout.write(f'Missing Paper (subsequent sitting, no marks): {missing_paper_count}')
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    '\nAll results have been updated with corrected Status logic!'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    '\nRun without --dry-run to apply these changes.'
                )
            )
