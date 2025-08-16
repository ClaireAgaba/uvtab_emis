from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Candidate


class Command(BaseCommand):
    help = 'Regenerate registration numbers for all candidates not in correct 7-part format: CENTER_NO/N/YY/I/OC_CODE/REG_TYPE/SERIAL'

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
        all_candidates = Candidate.objects.filter(
            reg_number__isnull=False
        ).exclude(reg_number='')
        
        # Filter to find candidates with incorrect format
        incorrect_format_candidates = []
        
        self.stdout.write(f'Analyzing {all_candidates.count()} candidates...')
        
        for candidate in all_candidates:
            if not self.is_correct_format(candidate.reg_number):
                incorrect_format_candidates.append(candidate)
        
        self.stdout.write(f'Found {len(incorrect_format_candidates)} candidates with incorrect registration number format')
        
        if limit:
            incorrect_format_candidates = incorrect_format_candidates[:limit]
            self.stdout.write(f'Processing first {limit} candidates only')
        
        regenerated_count = 0
        error_count = 0
        error_details = []
        
        for candidate in incorrect_format_candidates:
            old_reg_number = candidate.reg_number
            
            try:
                if dry_run:
                    # Simulate what the new reg number would be
                    new_reg_number = self.simulate_new_reg_number(candidate)
                    self.stdout.write(f'  WOULD REGENERATE: {old_reg_number} → {new_reg_number}')
                else:
                    # Actually regenerate by clearing reg_number and saving
                    candidate.reg_number = None
                    candidate.save()  # This triggers build_reg_number()
                    new_reg_number = candidate.reg_number
                    self.stdout.write(f'  REGENERATED: {old_reg_number} → {new_reg_number}')
                
                regenerated_count += 1
                
            except Exception as e:
                error_count += 1
                error_msg = f'Error regenerating for candidate {candidate.id} ({old_reg_number}): {str(e)}'
                error_details.append(error_msg)
                self.stdout.write(self.style.ERROR(f'  ERROR: {error_msg}'))
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write('SUMMARY:')
        self.stdout.write(f'  Total candidates analyzed: {all_candidates.count()}')
        self.stdout.write(f'  Candidates with incorrect format: {len(incorrect_format_candidates)}')
        if dry_run:
            self.stdout.write(f'  Would be regenerated: {regenerated_count}')
        else:
            self.stdout.write(f'  Successfully regenerated: {regenerated_count}')
        self.stdout.write(f'  Errors: {error_count}')
        
        if error_count > 0:
            self.stdout.write('\n' + self.style.WARNING('ERRORS ENCOUNTERED:'))
            for error in error_details[:10]:  # Show first 10 errors
                self.stdout.write(f'  {error}')
            if len(error_details) > 10:
                self.stdout.write(f'  ... and {len(error_details) - 10} more errors')

    def is_correct_format(self, reg_number):
        """
        Check if registration number is in correct format:
        CENTER_NO/N/YY/I/OC_CODE/REG_TYPE/SERIAL (7 parts, no spaces, no dashes)
        """
        if not reg_number:
            return False
        
        # Must not contain spaces or dashes
        if ' ' in reg_number or '-' in reg_number:
            return False
        
        # Must have exactly 7 parts when split by '/'
        parts = reg_number.split('/')
        if len(parts) != 7:
            return False
        
        # Basic validation of parts
        center_no, nationality, year, intake, occ_code, reg_type, serial = parts
        
        # Center number should not be empty
        if not center_no:
            return False
        
        # Nationality should be single character (U or X)
        if len(nationality) != 1:
            return False
        
        # Year should be 2 digits
        if len(year) != 2 or not year.isdigit():
            return False
        
        # Intake should be single character (M or A)
        if len(intake) != 1:
            return False
        
        # Registration type should be single character
        if len(reg_type) != 1:
            return False
        
        # Serial should be numeric
        if not serial.isdigit():
            return False
        
        return True

    def simulate_new_reg_number(self, candidate):
        """
        Simulate what the new registration number would be without actually saving
        """
        # Use 'U' for Uganda, 'X' for any other country
        UGANDA_VALUES = {"uganda", "ugandan", "ug", "256"}
        nat_val = str(candidate.nationality).strip().lower()
        nat = 'U' if nat_val in UGANDA_VALUES else 'X'
        year = str(candidate.entry_year)[-2:]  # last 2 digits
        intake = candidate.intake.upper()  # "M" or "A"
        occ_code = candidate.occupation.code if candidate.occupation else "XXX"
        reg_type = candidate.registration_category[0].upper() if candidate.registration_category else "X"
        center_code = candidate.assessment_center.center_number if candidate.assessment_center else "NOCNTR"
        
        # For simulation, just use a placeholder serial
        serial_str = "XXX"
        
        return f"{center_code}/{nat}/{year}/{intake}/{occ_code}/{reg_type}/{serial_str}"
