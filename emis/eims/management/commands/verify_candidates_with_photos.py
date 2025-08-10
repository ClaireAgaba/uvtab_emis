from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from eims.models import Candidate
import os


class Command(BaseCommand):
    help = 'Bulk verify all candidates that have photos (skip those without photos)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be verified without actually updating the database',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch (default: 100)',
        )
        parser.add_argument(
            '--verified-by-user',
            type=str,
            help='Username of the user to mark as verifier (default: first superuser)',
        )

    def get_verifier_user(self, username=None):
        """Get the user who will be marked as the verifier"""
        User = get_user_model()
        
        if username:
            try:
                return User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User "{username}" not found. Using first superuser instead.')
                )
        
        # Default to first superuser
        superuser = User.objects.filter(is_superuser=True).first()
        if not superuser:
            # If no superuser, try first staff user
            superuser = User.objects.filter(is_staff=True).first()
        
        if not superuser:
            raise Exception('No superuser or staff user found to mark as verifier')
        
        return superuser

    def has_photo(self, candidate):
        """Check if candidate has a photo"""
        if not candidate.passport_photo:
            return False
        
        # Check if the photo file actually exists
        try:
            return candidate.passport_photo and os.path.exists(candidate.passport_photo.path)
        except (ValueError, AttributeError):
            return False

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        verifier_username = options.get('verified_by_user')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting bulk verification of candidates with photos {"(DRY RUN)" if dry_run else ""}'
            )
        )
        
        # Get verifier user
        try:
            verifier_user = self.get_verifier_user(verifier_username)
            self.stdout.write(f'Verifier: {verifier_user.username} ({verifier_user.get_full_name() or "No full name"})')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting verifier user: {str(e)}'))
            return
        
        # Get all candidates
        all_candidates = Candidate.objects.all()
        total_candidates = all_candidates.count()
        
        if total_candidates == 0:
            self.stdout.write(self.style.WARNING('No candidates found in the database.'))
            return
            
        self.stdout.write(f'Found {total_candidates} candidates to check...')
        
        verified_count = 0
        already_verified_count = 0
        no_photo_count = 0
        error_count = 0
        
        # Process candidates individually to avoid database locks
        for i, candidate in enumerate(all_candidates, 1):
            if i % 1000 == 0:  # Progress update every 1000 candidates
                self.stdout.write(f'Progress: {i}/{total_candidates} candidates checked...')
            
            try:
                # Check if candidate has a photo
                if not self.has_photo(candidate):
                    no_photo_count += 1
                    continue
                
                # Check if already verified
                if candidate.verification_status == 'verified':
                    already_verified_count += 1
                    continue
                
                if not dry_run:
                    # Verify the candidate
                    candidate.verification_status = 'verified'
                    candidate.verification_date = timezone.now()
                    candidate.verified_by = verifier_user
                    candidate.decline_reason = None  # Clear any previous decline reason
                    candidate.save(update_fields=['verification_status', 'verification_date', 'verified_by', 'decline_reason'])
                    verified_count += 1
                    
                    if verified_count <= 10:  # Show first 10 verifications
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✓ Verified: {candidate.full_name} (ID: {candidate.id})'
                            )
                        )
                    elif verified_count == 11:
                        self.stdout.write('  ... (showing first 10, continuing verification)')
                else:
                    verified_count += 1
                    if verified_count <= 10:  # Show first 10 in dry run
                        self.stdout.write(
                            f'  Would verify: {candidate.full_name} (ID: {candidate.id})'
                        )
                    elif verified_count == 11:
                        self.stdout.write('  ... (showing first 10, would continue verification)')
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'  Error processing candidate {candidate.id}: {str(e)}'
                    )
                )
            
            # Add a small delay every 100 records to reduce database pressure
            if not dry_run and i % 100 == 0:
                import time
                time.sleep(0.05)  # 50ms pause every 100 records

        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SUMMARY:'))
        self.stdout.write(f'Total candidates processed: {total_candidates}')
        self.stdout.write(f'Candidates with photos: {verified_count + already_verified_count}')
        self.stdout.write(f'Candidates without photos (skipped): {no_photo_count}')
        self.stdout.write(
            self.style.SUCCESS(f'Candidates verified: {verified_count}') if verified_count > 0 
            else f'Candidates verified: {verified_count}'
        )
        self.stdout.write(f'Already verified: {already_verified_count}')
        
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
                    f'\nSuccessfully verified {verified_count} candidates with photos!'
                )
            )
            
        # Statistics
        if total_candidates > 0:
            photo_percentage = ((verified_count + already_verified_count) / total_candidates) * 100
            self.stdout.write(f'\nPhoto completion rate: {photo_percentage:.1f}% ({verified_count + already_verified_count}/{total_candidates})')
