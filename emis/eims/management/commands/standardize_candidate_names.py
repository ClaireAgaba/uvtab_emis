from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.utils import OperationalError
from eims.models import Candidate
import time


class Command(BaseCommand):
    help = 'Standardize all existing candidate names to format: SURNAME Other Names (sentence case)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually updating the database',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch (default: 100)',
        )

    def format_name(self, name):
        """Format name to standard format: SURNAME Other Names (sentence case)"""
        if not name:
            return name
            
        # Split the name into parts
        name_parts = name.strip().split()
        if not name_parts:
            return name
            
        # Format: First part (surname) in UPPERCASE, rest in sentence case
        formatted_parts = []
        for i, part in enumerate(name_parts):
            if i == 0:  # First part (surname) - all uppercase
                formatted_parts.append(part.upper())
            else:  # Other parts - sentence case (first letter upper, rest lower)
                formatted_parts.append(part.capitalize())
                
        return ' '.join(formatted_parts)

    def update_candidate_with_retry(self, candidate, formatted_name, max_retries=3):
        """Update a single candidate with retry logic for database locks"""
        for attempt in range(max_retries):
            try:
                candidate.full_name = formatted_name
                candidate.save(update_fields=['full_name'])
                return True
            except OperationalError as e:
                if 'database is locked' in str(e).lower() and attempt < max_retries - 1:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  Database locked, retrying in {2 ** attempt} seconds... (attempt {attempt + 1}/{max_retries})'
                        )
                    )
                    time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                    continue
                else:
                    raise e
        return False

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting candidate name standardization {"(DRY RUN)" if dry_run else ""}'
            )
        )
        
        # Get all candidates
        all_candidates = Candidate.objects.all()
        total_candidates = all_candidates.count()
        
        if total_candidates == 0:
            self.stdout.write(self.style.WARNING('No candidates found in the database.'))
            return
            
        self.stdout.write(f'Found {total_candidates} candidates to process...')
        
        updated_count = 0
        unchanged_count = 0
        error_count = 0
        
        # Process candidates individually to avoid database locks
        for i, candidate in enumerate(all_candidates, 1):
            self.stdout.write(f'Processing candidate {i}/{total_candidates}: {candidate.full_name}')
            
            try:
                original_name = candidate.full_name
                formatted_name = self.format_name(original_name)
                
                if original_name != formatted_name:
                    if not dry_run:
                        # Update individual candidate with retry logic
                        success = self.update_candidate_with_retry(candidate, formatted_name)
                        if success:
                            updated_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  ✓ Updated: "{original_name}" → "{formatted_name}"'
                                )
                            )
                        else:
                            error_count += 1
                            self.stdout.write(
                                self.style.ERROR(
                                    f'  ✗ Failed to update: "{original_name}"'
                                )
                            )
                    else:
                        updated_count += 1
                        self.stdout.write(
                            f'  Would update: "{original_name}" → "{formatted_name}"'
                        )
                else:
                    unchanged_count += 1
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'  Error processing candidate {candidate.id}: {str(e)}'
                    )
                )
            
            # Add a small delay between updates to reduce database pressure
            if not dry_run and i % 10 == 0:
                time.sleep(0.1)  # 100ms pause every 10 records

        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SUMMARY:'))
        self.stdout.write(f'Total candidates processed: {total_candidates}')
        self.stdout.write(
            self.style.SUCCESS(f'Names updated: {updated_count}') if updated_count > 0 
            else f'Names updated: {updated_count}'
        )
        self.stdout.write(f'Names unchanged: {unchanged_count}')
        
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Errors encountered: {error_count}'))
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\nThis was a DRY RUN. No changes were made to the database.'
                )
            )
            self.stdout.write(
                'To apply these changes, run the command without --dry-run flag.'
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully standardized {updated_count} candidate names!'
                )
            )
