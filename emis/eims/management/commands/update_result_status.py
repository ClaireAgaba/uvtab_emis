from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Result
from django.utils import timezone


class Command(BaseCommand):
    help = 'Update all existing Result records to populate Status column based on new logic'

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
                f'Starting Result Status update process...'
            )
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        # Get all results that need status updates (empty or null status)
        results_to_update = Result.objects.filter(
            status__in=['', None]
        ).order_by('id')
        
        total_count = results_to_update.count()
        self.stdout.write(f'Found {total_count} results to update')
        
        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS('No results need updating. All done!')
            )
            return
        
        updated_count = 0
        missing_paper_count = 0
        normal_count = 0
        retake_count = 0
        
        # Process in batches to avoid memory issues
        for i in range(0, total_count, batch_size):
            batch = results_to_update[i:i + batch_size]
            
            if not dry_run:
                with transaction.atomic():
                    for result in batch:
                        old_status = result.status
                        old_grade = result.grade
                        
                        # Apply the same logic as in the save method
                        if result.mark == -1:
                            result.grade = 'Ms'
                            result.comment = 'Missing'
                            result.status = 'Missing Paper'
                            missing_paper_count += 1
                        else:
                            # Determine status using the same logic
                            result._determine_status()
                            if result.status == 'Normal':
                                normal_count += 1
                            elif result.status == 'Retake':
                                retake_count += 1
                        
                        # Save without triggering the full save method logic again
                        Result.objects.filter(id=result.id).update(
                            status=result.status,
                            grade=result.grade,
                            comment=result.comment
                        )
                        
                        updated_count += 1
                        
                        if updated_count % 50 == 0:
                            self.stdout.write(f'Updated {updated_count}/{total_count} results...')
            else:
                # Dry run - just simulate the logic
                for result in batch:
                    if result.mark == -1:
                        missing_paper_count += 1
                        self.stdout.write(
                            f'Would update Result {result.id}: Mark={result.mark} -> Status="Missing Paper", Grade="Ms"'
                        )
                    else:
                        # Simulate status determination
                        previous_results = Result.objects.filter(
                            candidate=result.candidate,
                            assessment_type=result.assessment_type
                        )
                        
                        if result.paper:
                            previous_results = previous_results.filter(paper=result.paper)
                        elif result.module:
                            previous_results = previous_results.filter(module=result.module)
                        
                        previous_results = previous_results.exclude(pk=result.pk)
                        
                        if previous_results.exists():
                            grade_type = result.assessment_type
                            passmark = 65 if grade_type == 'practical' else 50
                            failed_previous = previous_results.filter(mark__lt=passmark, mark__gte=0).exists()
                            
                            if failed_previous:
                                status = 'Retake'
                                retake_count += 1
                            else:
                                status = 'Retake'
                                retake_count += 1
                        else:
                            status = 'Normal'
                            normal_count += 1
                        
                        self.stdout.write(
                            f'Would update Result {result.id}: Mark={result.mark} -> Status="{status}"'
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
        self.stdout.write(f'Missing Paper (-1 marks): {missing_paper_count}')
        self.stdout.write(f'Normal (first sitting): {normal_count}')
        self.stdout.write(f'Retake (repeat sitting): {retake_count}')
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    '\nAll existing results have been updated with Status values!'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    '\nRun without --dry-run to apply these changes.'
                )
            )
