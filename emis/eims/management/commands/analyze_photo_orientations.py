from django.core.management.base import BaseCommand
from eims.models import Candidate
from PIL import Image, ExifTags
import os
from collections import defaultdict


class Command(BaseCommand):
    help = 'Analyze EXIF orientation values in candidate photos to understand what needs fixing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sample-size',
            type=int,
            default=1000,
            help='Number of candidates to sample (default: 1000, use 0 for all)',
        )

    def handle(self, *args, **options):
        sample_size = options['sample_size']
        
        candidates = Candidate.objects.exclude(passport_photo='')
        total_candidates = candidates.count()
        
        if sample_size > 0 and sample_size < total_candidates:
            candidates = candidates[:sample_size]
            self.stdout.write(f'🔍 Analyzing orientation values for {sample_size} candidates (sample)...\n')
        else:
            self.stdout.write(f'🔍 Analyzing orientation values for all {total_candidates} candidates...\n')
        
        orientation_counts = defaultdict(int)
        no_exif_count = 0
        error_count = 0
        
        # EXIF orientation value meanings
        orientation_meanings = {
            1: "Normal (no rotation needed)",
            2: "Flipped horizontally", 
            3: "Rotated 180°",
            4: "Flipped vertically",
            5: "Rotated 90° CCW + flipped horizontally",
            6: "Rotated 90° CW (270° CCW)",
            7: "Rotated 90° CW + flipped horizontally", 
            8: "Rotated 90° CCW (270° CW)"
        }
        
        for candidate in candidates:
            try:
                photo_path = candidate.passport_photo.path
                if not os.path.exists(photo_path):
                    continue
                    
                with Image.open(photo_path) as img:
                    try:
                        # Get EXIF orientation
                        for orientation in ExifTags.TAGS.keys():
                            if ExifTags.TAGS[orientation] == 'Orientation':
                                break
                        
                        exif = img._getexif()
                        if exif is not None:
                            orientation_value = exif.get(orientation, 1)
                            orientation_counts[orientation_value] += 1
                        else:
                            no_exif_count += 1
                            
                    except (AttributeError, KeyError, TypeError):
                        no_exif_count += 1
                        
            except Exception as e:
                error_count += 1
        
        # Display results
        self.stdout.write(self.style.SUCCESS('📊 EXIF Orientation Analysis Results:\n'))
        
        # Show orientation value distribution
        for orientation_value in sorted(orientation_counts.keys()):
            count = orientation_counts[orientation_value]
            meaning = orientation_meanings.get(orientation_value, "Unknown orientation")
            
            if orientation_value in [3, 6, 8]:  # Currently handled
                status = "✅ HANDLED"
            elif orientation_value == 1:  # Normal
                status = "✅ NORMAL"
            else:  # Not handled
                status = "❌ NOT HANDLED"
            
            self.stdout.write(f'   Orientation {orientation_value}: {count:,} photos - {meaning} - {status}')
        
        # Show summary
        self.stdout.write(f'\n📋 Summary:')
        self.stdout.write(f'   • Photos with EXIF data: {sum(orientation_counts.values()):,}')
        self.stdout.write(f'   • Photos without EXIF data: {no_exif_count:,}')
        self.stdout.write(f'   • Errors: {error_count:,}')
        
        # Show what needs attention
        needs_fixing = []
        for orientation_value, count in orientation_counts.items():
            if orientation_value not in [1, 3, 6, 8]:  # Not normal and not currently handled
                needs_fixing.append((orientation_value, count))
        
        if needs_fixing:
            self.stdout.write(self.style.WARNING('\n⚠️  Orientation values that need attention:'))
            for orientation_value, count in needs_fixing:
                meaning = orientation_meanings.get(orientation_value, "Unknown")
                self.stdout.write(f'   • Orientation {orientation_value}: {count:,} photos - {meaning}')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ All orientation values are being handled correctly!'))
        
        if no_exif_count > 0:
            self.stdout.write(self.style.WARNING(f'\n📝 Note: {no_exif_count:,} photos have no EXIF orientation data'))
            self.stdout.write('   These may need manual inspection if they appear rotated.')
