from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Candidate


class Command(BaseCommand):
    help = 'Update all existing candidate registration numbers from old format (N/YY/I/OC/REG/SERIAL-CENTER) to new format (CENTER/N/YY/I/OC/REG/SERIAL)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually updating the database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made to the database'))
        
        # Get all candidates with registration numbers
        candidates = Candidate.objects.filter(reg_number__isnull=False).exclude(reg_number='')
        
        updated_count = 0
        error_count = 0
        already_new_format_count = 0
        
        self.stdout.write(f'Found {candidates.count()} candidates with registration numbers')
        
        for candidate in candidates:
            old_reg_number = candidate.reg_number
            
            try:
                # Check if already in new format (CENTER_NO/N/YY/I/OC/REG/SERIAL - 7 parts)
                parts = old_reg_number.split('/')
                if len(parts) == 7:
                    # Already in new format
                    already_new_format_count += 1
                    if dry_run:
                        self.stdout.write(f'  SKIP (already new format): {old_reg_number}')
                    continue
                
                # Check if in old format (N/YY/I/OC/REG/SERIAL-CENTER - 6 parts with dash in last)
                if len(parts) == 6 and '-' in parts[-1]:
                    # Old format: N/YY/I/OC/REG/SERIAL-CENTER
                    # Split the last part to get serial and center
                    last_part = parts[-1]
                    serial_part, center_part = last_part.split('-', 1)
                    
                    # Build new format: CENTER/N/YY/I/OC/REG/SERIAL
                    new_reg_number = f"{center_part}/{parts[0]}/{parts[1]}/{parts[2]}/{parts[3]}/{parts[4]}/{serial_part}"
                    
                    if dry_run:
                        self.stdout.write(f'  UPDATE: {old_reg_number} → {new_reg_number}')
                    else:
                        # Update the candidate
                        candidate.reg_number = new_reg_number
                        candidate.save(update_fields=['reg_number'])
                        self.stdout.write(f'  UPDATED: {old_reg_number} → {new_reg_number}')
                    
                    updated_count += 1
                else:
                    # Unknown format
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'  ERROR: Unknown format for candidate {candidate.id}: {old_reg_number}')
                    )
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  ERROR processing candidate {candidate.id} ({old_reg_number}): {str(e)}')
                )
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write('SUMMARY:')
        self.stdout.write(f'  Total candidates processed: {candidates.count()}')
        self.stdout.write(f'  Already in new format: {already_new_format_count}')
        if dry_run:
            self.stdout.write(f'  Would be updated: {updated_count}')
        else:
            self.stdout.write(f'  Successfully updated: {updated_count}')
        self.stdout.write(f'  Errors: {error_count}')
        
        if dry_run:
            self.stdout.write('\n' + self.style.WARNING('This was a DRY RUN. To actually update the database, run without --dry-run'))
        else:
            self.stdout.write('\n' + self.style.SUCCESS('Registration number update completed!'))
