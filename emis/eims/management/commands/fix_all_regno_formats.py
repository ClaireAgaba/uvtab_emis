from django.core.management.base import BaseCommand
from django.db import transaction
from django.db import models
from eims.models import Candidate
import re


class Command(BaseCommand):
    help = 'Fix all incorrect registration number formats to standard: CenterNo/nationality/entry_year/intake/occupation/regCategory/serialno'

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
        parser.add_argument(
            '--format-type',
            choices=['space_dash_space', 'dash_only', 'all'],
            default='all',
            help='Which format type to fix',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options.get('limit')
        format_type = options['format_type']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made to the database'))
        
        # Get candidates based on format type
        if format_type == 'space_dash_space':
            candidates = Candidate.objects.filter(
                reg_number__isnull=False,
                reg_number__contains=' - '
            ).exclude(reg_number='')
        elif format_type == 'dash_only':
            candidates = Candidate.objects.filter(
                reg_number__isnull=False,
                reg_number__contains='-'
            ).exclude(
                reg_number='',
                reg_number__contains=' - '  # Exclude space-dash-space as they're handled separately
            )
        else:  # all
            candidates = Candidate.objects.filter(
                reg_number__isnull=False
            ).exclude(reg_number='').filter(
                models.Q(reg_number__contains='-') | models.Q(reg_number__contains=' ')
            )
        
        if limit:
            candidates = candidates[:limit]
            self.stdout.write(f'Processing first {limit} candidates only')
        
        updated_count = 0
        already_correct_count = 0
        error_count = 0
        error_details = []
        
        self.stdout.write(f'Found {candidates.count()} candidates with incorrect format')
        
        for candidate in candidates:
            old_reg_number = candidate.reg_number
            
            try:
                # Check if already in correct format (7 parts, no spaces or dashes)
                if self.is_correct_format(old_reg_number):
                    already_correct_count += 1
                    continue
                
                # Try to fix the format
                new_reg_number = self.fix_registration_format(old_reg_number)
                
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

    def is_correct_format(self, reg_number):
        """Check if registration number is in correct format: CenterNo/nationality/entry_year/intake/occupation/regCategory/serialno"""
        if ' ' in reg_number or '-' in reg_number:
            return False
        
        parts = reg_number.split('/')
        return len(parts) == 7

    def fix_registration_format(self, old_reg_number):
        """
        Fix various incorrect registration number formats
        
        Target format: CenterNo/nationality/entry_year/intake/occupation/regCategory/serialno
        """
        
        # Pattern 1: Space-dash-space format
        # UVT710 - KGA/U/25/M/AD/M/001 → UVT710/U/25/M/AD/M/001
        if ' - ' in old_reg_number:
            # Split by ' - ' and combine
            parts = old_reg_number.split(' - ')
            if len(parts) == 2:
                center_part = parts[0].strip()
                rest_part = parts[1].strip()
                
                # Combine: CENTER + / + rest
                new_reg_number = f"{center_part}/{rest_part}"
                
                # Validate the result has 7 parts
                if len(new_reg_number.split('/')) == 7:
                    return new_reg_number
        
        # Pattern 2: Dash with duplicate center/serial
        # UVT671/U/25/M/HD/182-UVT671/182 → UVT671/U/25/M/HD/182
        if '-' in old_reg_number and ' - ' not in old_reg_number:
            before_dash, after_dash = old_reg_number.split('-', 1)
            
            # Check if after_dash is redundant (CENTER/SERIAL format)
            after_parts = after_dash.split('/')
            if len(after_parts) == 2:
                # This looks like redundant CENTER/SERIAL, use before_dash
                before_parts = before_dash.split('/')
                if len(before_parts) >= 6:  # Should have at least 6 parts for a valid registration
                    return before_dash
        
        # Pattern 3: Other space formats
        if ' ' in old_reg_number and '-' not in old_reg_number:
            # Try to remove spaces and see if it makes sense
            no_spaces = old_reg_number.replace(' ', '')
            if len(no_spaces.split('/')) == 7:
                return no_spaces
        
        # Pattern 4: 6 parts format - might be missing regCategory
        parts = old_reg_number.split('/')
        if len(parts) == 6 and ' ' not in old_reg_number and '-' not in old_reg_number:
            # This might be missing the regCategory, but we can't guess it
            # Return as-is for now, might need manual review
            return old_reg_number
        
        # If we can't determine how to fix it, return None
        return None
