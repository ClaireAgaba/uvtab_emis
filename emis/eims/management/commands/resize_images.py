import os
from io import BytesIO
from django.core.management.base import BaseCommand, CommandError
from django.core.files.base import ContentFile
from django.conf import settings
from PIL import Image, UnidentifiedImageError
from eims.models import Candidate # Assuming your app is 'eims' and models are in 'emis.eims.models'

class Command(BaseCommand):
    help = 'Resizes existing candidate passport photos to a maximum of 500KB and 800px dimension.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate resizing without actually saving changes.',
        )
        parser.add_argument(
            '--force-reprocess',
            action='store_true',
            help='Force reprocessing of all images, even if they seem to be under the size limit (useful if logic changed).'
        )
        parser.add_argument(
            '--candidate-id',
            type=int,
            help='Process a single candidate by ID.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force_reprocess = options['force_reprocess']
        candidate_id = options['candidate_id']
        MAX_SIZE_KB = 500
        MAX_BYTES = MAX_SIZE_KB * 1024
        MAX_PIXELS = 800 # Max dimension (width or height)

        if dry_run:
            self.stdout.write(self.style.WARNING('--- DRY RUN MODE --- No changes will be saved.'))

        candidates_qs = Candidate.objects.all()
        if candidate_id:
            candidates_qs = candidates_qs.filter(id=candidate_id)
            if not candidates_qs.exists():
                raise CommandError(f"Candidate with ID {candidate_id} not found.")
        
        candidates_to_process = [c for c in candidates_qs if c.passport_photo and c.passport_photo.name]

        if not candidates_to_process:
            self.stdout.write(self.style.SUCCESS('No candidates with passport photos found to process.'))
            return

        processed_count = 0
        resized_count = 0
        error_count = 0

        for candidate in candidates_to_process:
            try:
                if not candidate.passport_photo or not candidate.passport_photo.storage.exists(candidate.passport_photo.name):
                    self.stdout.write(self.style.NOTICE(f'Skipping Candidate ID {candidate.id} ({candidate.full_name}): Photo file does not exist at {candidate.passport_photo.name}'))
                    continue
                
                # Check size before opening if not force_reprocess
                current_size = candidate.passport_photo.size
                if not force_reprocess and current_size <= MAX_BYTES:
                    self.stdout.write(self.style.SUCCESS(f'Skipping Candidate ID {candidate.id} ({candidate.full_name}): Photo already within size limit ({current_size / 1024:.2f}KB).'))
                    continue

                self.stdout.write(f'Processing Candidate ID {candidate.id} ({candidate.full_name}): {candidate.passport_photo.name} ({current_size / 1024:.2f}KB)')
                processed_count += 1

                # Ensure the file pointer is at the beginning
                candidate.passport_photo.open('rb') # Open in binary read mode
                candidate.passport_photo.file.seek(0)
                
                img = Image.open(candidate.passport_photo.file)
                original_format = img.format if img.format else 'JPEG'
                original_mode = img.mode

                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')

                output_buffer = BytesIO()
                
                # Thumbnail if dimensions are too large
                if img.width > MAX_PIXELS or img.height > MAX_PIXELS:
                    self.stdout.write(f'  Resizing dimensions from {img.width}x{img.height} to fit within {MAX_PIXELS}px.')
                    try:
                        resampling_filter = Image.Resampling.LANCZOS
                    except AttributeError: # Fallback for older Pillow versions
                        resampling_filter = Image.LANCZOS
                    img.thumbnail((MAX_PIXELS, MAX_PIXELS), resampling_filter)
                
                # Save logic: try to keep PNG if original was PNG and it's small enough, else JPEG
                if original_format.upper() == 'PNG' and original_mode != 'P': # Avoid re-saving palette PNGs as full PNGs unless necessary
                    img.save(output_buffer, format='PNG', optimize=True)
                    if output_buffer.tell() > MAX_BYTES:
                        self.stdout.write(f'  PNG version too large ({output_buffer.tell() / 1024:.2f}KB). Converting to JPEG.')
                        output_buffer.seek(0); output_buffer.truncate(0)
                        img.save(output_buffer, format='JPEG', quality=85)
                else:
                    img.save(output_buffer, format='JPEG', quality=85)

                # Iteratively reduce JPEG quality if still too large
                # We need to check the format of the image *in the buffer*
                buffer_check_img = Image.open(BytesIO(output_buffer.getvalue()))
                if output_buffer.tell() > MAX_BYTES and buffer_check_img.format == 'JPEG':
                    quality = 80
                    self.stdout.write(f'  JPEG still too large ({output_buffer.tell() / 1024:.2f}KB). Reducing quality...')
                    while output_buffer.tell() > MAX_BYTES and quality >= 10:
                        output_buffer.seek(0); output_buffer.truncate(0)
                        img.save(output_buffer, format='JPEG', quality=quality)
                        self.stdout.write(f'    Quality {quality}: {output_buffer.tell() / 1024:.2f}KB')
                        quality -= 5
                
                final_size_bytes = output_buffer.tell()
                if final_size_bytes <= MAX_BYTES:
                    if final_size_bytes < current_size or force_reprocess:
                        original_filename = os.path.basename(candidate.passport_photo.name)
                        name_part, _ = os.path.splitext(original_filename)
                        
                        final_img_in_buffer = Image.open(BytesIO(output_buffer.getvalue()))
                        final_format_in_buffer = final_img_in_buffer.format
                        new_extension = '.jpg'
                        if final_format_in_buffer == 'JPEG': new_extension = '.jpg'
                        elif final_format_in_buffer == 'PNG': new_extension = '.png'
                        new_filename = name_part + new_extension

                        if not dry_run:
                            # Save the new file content
                            candidate.passport_photo.save(new_filename, ContentFile(output_buffer.getvalue()), save=False)
                            # Explicitly save the Candidate model instance to trigger any other save-related logic if needed
                            # and to persist the changed file field path.
                            candidate.save(update_fields=['passport_photo']) 
                        self.stdout.write(self.style.SUCCESS(f'  Resized Candidate ID {candidate.id} to {final_size_bytes / 1024:.2f}KB. New file: {new_filename}'))
                        resized_count += 1
                    else:
                        self.stdout.write(self.style.NOTICE(f'  Candidate ID {candidate.id} already optimized or no significant size reduction. Size: {final_size_bytes / 1024:.2f}KB.'))
                else:
                    self.stdout.write(self.style.WARNING(f'  Could not resize Candidate ID {candidate.id} ({candidate.full_name}) to under {MAX_SIZE_KB}KB. Final size: {final_size_bytes / 1024:.2f}KB. Original kept.'))
                    error_count +=1 # Count as an error if we couldn't get it below threshold

            except FileNotFoundError:
                self.stdout.write(self.style.ERROR(f'Error for Candidate ID {candidate.id} ({candidate.full_name}): File not found at {candidate.passport_photo.name}'))
                error_count += 1
            except UnidentifiedImageError:
                self.stdout.write(self.style.ERROR(f'Error for Candidate ID {candidate.id} ({candidate.full_name}): Cannot identify image file. It might be corrupted or not an image: {candidate.passport_photo.name}'))
                error_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'An unexpected error occurred for Candidate ID {candidate.id} ({candidate.full_name}): {e}'))
                error_count += 1
            finally:
                # Ensure the file is closed if it was opened
                if candidate.passport_photo and not candidate.passport_photo.closed:
                    candidate.passport_photo.close()

        self.stdout.write(self.style.SUCCESS(f'--- Processing Complete ---'))
        self.stdout.write(f'Total candidates with photos: {len(candidates_to_process)}')
        self.stdout.write(f'Attempted to process: {processed_count}')
        self.stdout.write(self.style.SUCCESS(f'Successfully resized: {resized_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Errors encountered: {error_count}'))
        if dry_run:
            self.stdout.write(self.style.WARNING('--- DRY RUN MODE --- No changes were saved.'))
