from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from eims.models import Candidate
from PIL import Image, ExifTags
import io
import os


class Command(BaseCommand):
    help = 'Fix orientation of existing candidate photos that were imported with rotation issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without actually changing files',
        )
        parser.add_argument(
            '--candidate-id',
            type=int,
            help='Fix orientation for a specific candidate ID only',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information about each candidate processed',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        candidate_id = options.get('candidate_id')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No files will be modified'))
        
        # Get candidates with photos
        candidates = Candidate.objects.exclude(passport_photo='')
        
        if candidate_id:
            candidates = candidates.filter(id=candidate_id)
            
        total_candidates = candidates.count()
        self.stdout.write(f'Found {total_candidates} candidates with photos to check')
        
        fixed_count = 0
        error_count = 0
        error_details = []
        
        for candidate in candidates:
            try:
                if self.fix_candidate_photo(candidate, dry_run):
                    fixed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Fixed photo for candidate {candidate.id}: {candidate.full_name}')
                    )
            except Exception as e:
                error_count += 1
                error_msg = f'❌ Error fixing photo for candidate {candidate.id} ({candidate.full_name}): {str(e)}'
                error_details.append(error_msg)
                self.stdout.write(self.style.ERROR(error_msg))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted! Fixed: {fixed_count}, Errors: {error_count}, Total checked: {total_candidates}'
            )
        )
        
        # Show error details if any
        if error_details:
            self.stdout.write(self.style.WARNING('\n📋 Error Details:'))
            for error_detail in error_details:
                self.stdout.write(f'   {error_detail}')
            
            self.stdout.write(self.style.WARNING('\n💡 Common causes of errors:'))
            self.stdout.write('   • Photo file missing from disk')
            self.stdout.write('   • Corrupted image files')
            self.stdout.write('   • Permission issues accessing files')
            self.stdout.write('   • Invalid image format or metadata')

    def fix_candidate_photo(self, candidate, dry_run=False):
        """Fix orientation for a single candidate's photo"""
        if not candidate.passport_photo:
            return False
            
        try:
            # Open the existing photo
            photo_path = candidate.passport_photo.path
            if not os.path.exists(photo_path):
                self.stdout.write(f'Photo file not found: {photo_path}')
                return False
                
            with Image.open(photo_path) as img:
                # Check if image has EXIF orientation data
                orientation_applied = False
                
                try:
                    for orientation in ExifTags.TAGS.keys():
                        if ExifTags.TAGS[orientation] == 'Orientation':
                            break
                    
                    exif = img._getexif()
                    if exif is not None:
                        orientation_value = exif.get(orientation)
                        
                        if orientation_value and orientation_value != 1:  # 1 means normal orientation
                            if dry_run:
                                self.stdout.write(f'Would fix orientation {orientation_value} for candidate {candidate.id}')
                                return True
                            
                            # Apply rotation based on EXIF orientation
                            # Handle all 8 EXIF orientation values
                            if orientation_value == 2:
                                img = img.transpose(Image.FLIP_LEFT_RIGHT)
                                orientation_applied = True
                            elif orientation_value == 3:
                                img = img.rotate(180, expand=True)
                                orientation_applied = True
                            elif orientation_value == 4:
                                img = img.transpose(Image.FLIP_TOP_BOTTOM)
                                orientation_applied = True
                            elif orientation_value == 5:
                                img = img.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                                orientation_applied = True
                            elif orientation_value == 6:
                                img = img.rotate(270, expand=True)
                                orientation_applied = True
                            elif orientation_value == 7:
                                img = img.rotate(270, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                                orientation_applied = True
                            elif orientation_value == 8:
                                img = img.rotate(90, expand=True)
                                orientation_applied = True
                            
                            if orientation_applied:
                                # Convert to RGB if needed
                                if img.mode != 'RGB':
                                    img = img.convert('RGB')
                                
                                # Save the corrected image
                                buffer = io.BytesIO()
                                img.save(buffer, format='JPEG', quality=85)
                                buffer.seek(0)
                                
                                # Get the original filename
                                original_name = os.path.basename(candidate.passport_photo.name)
                                
                                # Save the corrected image back to the same field
                                candidate.passport_photo.save(
                                    original_name,
                                    ContentFile(buffer.getvalue()),
                                    save=True
                                )
                                
                                # Also fix the passport_photo_with_regno if it exists
                                if candidate.passport_photo_with_regno:
                                    try:
                                        self.regenerate_photo_with_regno(candidate)
                                    except Exception as e:
                                        self.stdout.write(f'Warning: Could not regenerate photo with regno: {str(e)}')
                                
                                return True
                                
                except (AttributeError, KeyError, TypeError):
                    # No EXIF data, check if we can detect rotation by image dimensions or other means
                    pass
                    
        except Exception as e:
            raise Exception(f'Error processing photo: {str(e)}')
            
        return False

    def regenerate_photo_with_regno(self, candidate):
        """Regenerate the photo with registration number overlay using the corrected base photo"""
        # This is a simplified version - you might want to call the actual stamping function
        # For now, we'll just copy the corrected base photo
        if candidate.passport_photo and candidate.passport_photo_with_regno:
            with open(candidate.passport_photo.path, 'rb') as f:
                candidate.passport_photo_with_regno.save(
                    os.path.basename(candidate.passport_photo_with_regno.name),
                    ContentFile(f.read()),
                    save=True
                )
