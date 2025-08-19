from django.core.management.base import BaseCommand
from eims.models import Result, Candidate
from django.db.models import Q

class Command(BaseCommand):
    help = 'Fix incorrect "Retake" status for results that should be "Updated" or "Normal"'

    def add_arguments(self, parser):
        parser.add_argument(
            '--candidate-id',
            type=int,
            help='Fix status for specific candidate ID only'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making actual changes'
        )
        parser.add_argument(
            '--fix-all',
            action='store_true',
            help='Fix all candidates with incorrect retake status'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        candidate_id = options.get('candidate_id')
        fix_all = options['fix_all']
        
        if not candidate_id and not fix_all:
            self.stdout.write(
                self.style.ERROR('Please specify either --candidate-id <ID> or --fix-all')
            )
            return
        
        # Build query
        query = Q(status='Retake')
        if candidate_id:
            query &= Q(candidate_id=candidate_id)
        
        # Find results marked as "Retake"
        retake_results = Result.objects.filter(query).order_by('candidate', 'assessment_date', 'assessment_type')
        
        if not retake_results.exists():
            self.stdout.write(
                self.style.SUCCESS('No results with "Retake" status found.')
            )
            return
        
        self.stdout.write(f'Found {retake_results.count()} results with "Retake" status')
        
        fixed_count = 0
        
        for result in retake_results:
            # Check if there are multiple results for same candidate/assessment_type
            same_type_results = Result.objects.filter(
                candidate=result.candidate,
                assessment_type=result.assessment_type,
                result_type=result.result_type,
                level=result.level
            ).order_by('assessment_date')
            
            if same_type_results.count() <= 1:
                # Only one result, should be "Normal" not "Retake"
                new_status = 'Normal'
                reason = 'Only one result exists'
            else:
                # Multiple results - check if assessment dates are different
                assessment_dates = set(r.assessment_date for r in same_type_results if r.assessment_date)
                
                if len(assessment_dates) <= 1:
                    # Same assessment date - should be "Updated"
                    new_status = 'Updated'
                    reason = 'Same assessment date - mark correction'
                else:
                    # Different assessment dates - keep as "Retake" but check if it's the latest
                    latest_result = same_type_results.last()
                    if result == latest_result:
                        new_status = 'Retake'  # Keep as retake for latest
                        reason = 'Latest result with different assessment date'
                    else:
                        new_status = 'Normal'  # Earlier results should be normal
                        reason = 'Earlier result, not latest retake'
            
            # Display what would be changed
            self.stdout.write(
                f'Candidate: {result.candidate.full_name} ({result.candidate.id})'
            )
            self.stdout.write(
                f'  {result.assessment_type.title()} Mark: {result.mark} '
                f'({result.assessment_date}) - Status: "{result.status}" → "{new_status}"'
            )
            self.stdout.write(f'  Reason: {reason}')
            
            # Apply change if not dry run
            if not dry_run and result.status != new_status:
                result.status = new_status
                result.save()
                fixed_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Updated status to "{new_status}"')
                )
            elif dry_run:
                self.stdout.write(
                    self.style.WARNING(f'  [DRY RUN] Would update to "{new_status}"')
                )
            
            self.stdout.write('')  # Empty line for readability
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would fix {retake_results.count()} results')
            )
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully fixed {fixed_count} results')
            )
