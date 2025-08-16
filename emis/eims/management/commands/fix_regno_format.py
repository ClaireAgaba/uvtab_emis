from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Candidate
import re


class Command(BaseCommand):
    help = 'Fix registration numbers from old complex format to new simple format (CENTER/SERIAL)'

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
        
        # Get all candidates with registration numbers
        candidates = Candidate.objects.filter(reg_number__isnull=False).exclude(reg_number='')
        
        if limit:
            candidates = candidates[:limit]
            self.stdout.write(f'Processing first {limit} candidates only')
        
        updated_count = 0
        already_correct_count = 0
        error_count = 0
        error_details = []
        
        self.stdout.write(f'Found {candidates.count()} candidates to process')
        
        for candidate in candidates:
            old_reg_number = candidate.reg_number
            
            try:
                # Check if already in correct simple format (CENTER/SERIAL - 2 parts)
                if self.is_simple_format(old_reg_number):
                    already_correct_count += 1
                    if dry_run and limit and limit <= 10:  # Only show for small test runs
                        self.stdout.write(f'  SKIP (already correct): {old_reg_number}')
                    continue
                
                # Try to extract center and serial from old format
                new_reg_number = self.convert_to_simple_format(old_reg_number)
                
                if new_reg_number:
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
                    error_msg = f'Could not convert format for candidate {candidate.id}: {old_reg_number}'
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
        self.stdout.write(f'  Already in correct format: {already_correct_count}')
        if dry_run:
            self.stdout.write(f'  Would be updated: {updated_count}')
        else:
            self.stdout.write(f'  Successfully updated: {updated_count}')
        self.stdout.write(f'  Errors: {error_count}')
        
        if error_count > 0:
            self.stdout.write('\n' + self.style.WARNING('ERRORS ENCOUNTERED:'))
            for error in error_details[:10]:  # Show first 10 errors
                self.stdout.write(f'  {error}')
            if len(error_details) > 10:
                self.stdout.write(f'  ... and {len(error_details) - 10} more errors')

    def is_simple_format(self, reg_number):
        """Check if registration number is already in simple format (CENTER/SERIAL)"""
        parts = reg_number.split('/')
        return len(parts) == 2 and not '-' in reg_number

    def convert_to_simple_format(self, old_reg_number):
        """Convert old format to simple format (CENTER/SERIAL)"""
        
        # Pattern 1: CENTER/N/YY/I/OC/REG/SERIAL-CENTER/SERIAL
        # Example: UBB185/U/25/M/BKR/004-UBB185/004
        if '-' in old_reg_number:
            # Split by dash first
            before_dash, after_dash = old_reg_number.split('-', 1)
            
            # The part after dash should be CENTER/SERIAL
            after_parts = after_dash.split('/')
            if len(after_parts) == 2:
                center_code, serial = after_parts
                return f"{center_code}/{serial}"
        
        # Pattern 2: CENTER/N/YY/I/OC/REG/SERIAL (7 parts, no dash)
        # Example: UBB185/U/25/M/BKR/004/123
        parts = old_reg_number.split('/')
        if len(parts) == 7:
            center_code = parts[0]
            serial = parts[6]
            return f"{center_code}/{serial}"
        
        # Pattern 3: N/YY/I/OC/REG/SERIAL-CENTER (6 parts with dash in last)
        # Example: U/25/M/BKR/004/123-UBB185
        if len(parts) == 6 and '-' in parts[-1]:
            serial_part, center_code = parts[-1].split('-', 1)
            return f"{center_code}/{serial_part}"
        
        # Pattern 4: Other variations
        # Try to find center code and serial from the structure
        if len(parts) >= 3:
            # Look for a pattern where we have center code at start or end
            first_part = parts[0]
            last_part = parts[-1]
            
            # If first part looks like center code (3+ chars, contains letters)
            if len(first_part) >= 3 and any(c.isalpha() for c in first_part):
                # Try to find serial (usually numeric at the end)
                for i in range(len(parts) - 1, -1, -1):
                    part = parts[i]
                    if '-' in part:
                        serial_candidate = part.split('-')[0]
                    else:
                        serial_candidate = part
                    
                    if serial_candidate.isdigit():
                        return f"{first_part}/{serial_candidate}"
        
        # Could not determine format
        return None
