from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Candidate


class Command(BaseCommand):
    help = 'Fix registration numbers that have wrong format with dash (e.g., UVT671/U/25/M/HD/182-UVT671/182)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually updating the database',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of candidates to process (for testing)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options.get('limit')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made to the database'))
        
        # Get candidates with dash in their registration number (the problematic ones)
        candidates = Candidate.objects.filter(
            reg_number__isnull=False,
            reg_number__contains='-'
        ).exclude(reg_number='')
        
        if limit:
            candidates = candidates[:limit]
            self.stdout.write(f'Processing first {limit} candidates only')
        
        updated_count = 0
        error_count = 0
        error_details = []
        
        self.stdout.write(f'Found {candidates.count()} candidates with dash in registration number')
        
        for candidate in candidates:
            old_reg_number = candidate.reg_number
            
            try:
                # Convert the wrong format to correct format
                new_reg_number = self.fix_dash_format(old_reg_number)
                
                if new_reg_number and new_reg_number != old_reg_number:
                    if dry_run:
                        self.stdout.write(f'  UPDATE: {old_reg_number} → {new_reg_number}')
                    else:
                        # Update the candidate
                        candidate.reg_number = new_reg_number
                        candidate.save(update_fields=['reg_number'])
                        self.stdout.write(f'  UPDATED: {old_reg_number} → {new_reg_number}')
                    
                    updated_count += 1
                else:
                    # Could not convert
                    error_count += 1
                    error_msg = f'Could not fix format for candidate {candidate.id}: {old_reg_number}'
                    error_details.append(error_msg)
                    self.stdout.write(self.style.ERROR(f'  ERROR: {error_msg}'))
                    
            except Exception as e:
                error_count += 1
                error_msg = f'Exception processing candidate {candidate.id} ({old_reg_number}): {str(e)}'
                error_details.append(error_msg)
                self.stdout.write(self.style.ERROR(f'  ERROR: {error_msg}'))
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write('SUMMARY:')
        self.stdout.write(f'  Total candidates processed: {candidates.count()}')
        if dry_run:
            self.stdout.write(f'  Would be updated: {updated_count}')
        else:
            self.stdout.write(f'  Successfully updated: {updated_count}')
        self.stdout.write(f'  Errors: {error_count}')
        
        if error_count > 0:
            self.stdout.write('\n' + self.style.WARNING('ERRORS ENCOUNTERED:'))
            for error in error_details:
                self.stdout.write(f'  {error}')

    def fix_dash_format(self, old_reg_number):
        """
        Fix registration numbers with dash format
        
        Examples:
        UVT671/U/25/M/HD/182-UVT671/182 → UVT671/U/25/M/HD/182
        UBB185/U/25/M/BKR/004-UBB185/004 → UBB185/U/25/M/BKR/004
        """
        
        if '-' not in old_reg_number:
            return old_reg_number  # No dash, nothing to fix
        
        # Split by dash
        before_dash, after_dash = old_reg_number.split('-', 1)
        
        # The correct format should be the part before the dash
        # Let's validate this makes sense
        before_parts = before_dash.split('/')
        after_parts = after_dash.split('/')
        
        # Expected pattern: CENTER/U/YY/G/OC/SERIAL-CENTER/SERIAL
        # We want: CENTER/U/YY/G/OC/SERIAL
        
        if len(before_parts) >= 5:  # Should have at least CENTER/U/YY/G/OC/SERIAL (6 parts) or similar
            # Validate that after_dash contains center and serial that match
            if len(after_parts) == 2:
                center_after, serial_after = after_parts
                center_before = before_parts[0]
                
                # Check if centers match
                if center_after == center_before:
                    # This looks like the wrong format we want to fix
                    return before_dash
        
        # If we can't determine the pattern, try some other approaches
        
        # Pattern: something-CENTER/SERIAL where CENTER/SERIAL is redundant
        if len(after_parts) == 2:
            # Just return the part before dash
            return before_dash
        
        # If we can't determine how to fix it, return the original
        return old_reg_number
