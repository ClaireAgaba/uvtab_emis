from django.core.management.base import BaseCommand
from django.db.models import Count
from eims.models import CandidateModule


class Command(BaseCommand):
    help = 'Clean up duplicate CandidateModule records before migration'

    def handle(self, *args, **options):
        self.stdout.write('Starting cleanup of duplicate CandidateModule records...')
        
        # Find duplicates
        duplicates = (CandidateModule.objects
                     .values('candidate_id', 'module_id')
                     .annotate(count=Count('id'))
                     .filter(count__gt=1))
        
        total_duplicates = duplicates.count()
        self.stdout.write(f'Found {total_duplicates} sets of duplicate records')
        
        removed_count = 0
        
        for duplicate in duplicates:
            candidate_id = duplicate['candidate_id']
            module_id = duplicate['module_id']
            
            # Get all records for this candidate-module combination
            records = CandidateModule.objects.filter(
                candidate_id=candidate_id,
                module_id=module_id
            ).order_by('id')
            
            # Keep the first record, delete the rest
            records_to_delete = records[1:]
            
            for record in records_to_delete:
                self.stdout.write(f'Removing duplicate: Candidate {candidate_id}, Module {module_id}, ID {record.id}')
                record.delete()
                removed_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully removed {removed_count} duplicate records')
        )
        
        # Verify no duplicates remain
        remaining_duplicates = (CandidateModule.objects
                               .values('candidate_id', 'module_id')
                               .annotate(count=Count('id'))
                               .filter(count__gt=1).count())
        
        if remaining_duplicates == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ All duplicates cleaned up successfully. Migration should now work.')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ {remaining_duplicates} duplicate sets still remain')
            )
