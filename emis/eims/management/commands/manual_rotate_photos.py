from django.core.management.base import BaseCommand
from eims.models import Candidate
from PIL import Image
from django.core.files.base import ContentFile
import io
import os


class Command(BaseCommand):
    help = 'Manually rotate candidate photos by specified degrees (for photos without EXIF orientation data)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--candidate-ids',
            nargs='+',
            type=int,
            help='List of candidate IDs to rotate (space-separated)',
        )
        parser.add_argument(
            '--rotation',
            type=int,
            choices=[90, 180, 270],
            default=180,
            help='Degrees to rotate (90, 180, or 270). Default: 180',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be rotated without making changes',
        )

    def handle(self, *args, **options):
        candidate_ids = options['candidate_ids']
        rotation = options['rotation']
        dry_run = options['dry_run']
        
        if not candidate_ids:
            self.stdout.write(self.style.ERROR('Please provide candidate IDs using --candidate-ids'))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No files will be modified'))
        
        self.stdout.write(f'🔄 Manual rotation: {rotation}° for {len(candidate_ids)} candidates\n')
        
        success_count = 0
        error_count = 0
        
        for candidate_id in candidate_ids:
            try:
                candidate = Candidate.objects.get(id=candidate_id)
                
                if not candidate.passport_photo:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️  Candidate {candidate_id} ({candidate.full_name}) has no photo')
                    )
                    continue
                
                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Would rotate {rotation}° for candidate {candidate_id}: {candidate.full_name}')
                    )
                    success_count += 1
                else:
                    if self.rotate_candidate_photo(candidate, rotation):
                        self.stdout.write(
                            self.style.SUCCESS(f'✅ Rotated {rotation}° for candidate {candidate_id}: {candidate.full_name}')
                        )
                        success_count += 1
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'❌ Failed to rotate photo for candidate {candidate_id}: {candidate.full_name}')
                        )
                        error_count += 1
                        
            except Candidate.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ Candidate {candidate_id} not found')
                )
                error_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error processing candidate {candidate_id}: {str(e)}')
                )
                error_count += 1
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\n📊 Manual rotation completed: {success_count} success, {error_count} errors'
            )
        )

    def rotate_candidate_photo(self, candidate, rotation_degrees):
        """Manually rotate a candidate's photo by specified degrees"""
        try:
            photo_path = candidate.passport_photo.path
            if not os.path.exists(photo_path):
                return False
                
            with Image.open(photo_path) as img:
                # Apply manual rotation
                if rotation_degrees == 90:
                    rotated_img = img.rotate(270, expand=True)  # 270° to get 90° clockwise
                elif rotation_degrees == 180:
                    rotated_img = img.rotate(180, expand=True)
                elif rotation_degrees == 270:
                    rotated_img = img.rotate(90, expand=True)   # 90° to get 270° clockwise
                else:
                    return False
                
                # Convert to RGB if needed
                if rotated_img.mode != 'RGB':
                    rotated_img = rotated_img.convert('RGB')
                
                # Save the rotated image
                buffer = io.BytesIO()
                rotated_img.save(buffer, format='JPEG', quality=85)
                buffer.seek(0)
                
                # Get the original filename
                original_name = os.path.basename(candidate.passport_photo.name)
                
                # Save the rotated image back to the same field
                candidate.passport_photo.save(
                    original_name,
                    ContentFile(buffer.getvalue()),
                    save=True
                )
                
                return True
                
        except Exception as e:
            raise Exception(f'Error rotating photo: {str(e)}')
        
        return False
