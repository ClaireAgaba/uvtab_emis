from django.core.management.base import BaseCommand
from eims.models import Candidate
from PIL import Image
import os


class Command(BaseCommand):
    help = 'Diagnose photo issues to identify candidates with problematic photos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-missing',
            action='store_true',
            help='Check for candidates with photo records but missing files',
        )
        parser.add_argument(
            '--check-corrupted',
            action='store_true',
            help='Check for candidates with corrupted image files',
        )
        parser.add_argument(
            '--check-all',
            action='store_true',
            help='Run all diagnostic checks',
        )

    def handle(self, *args, **options):
        check_missing = options['check_missing'] or options['check_all']
        check_corrupted = options['check_corrupted'] or options['check_all']
        
        if not (check_missing or check_corrupted):
            self.stdout.write(self.style.WARNING('Please specify at least one check option. Use --help for options.'))
            return
        
        candidates = Candidate.objects.exclude(passport_photo='')
        total_candidates = candidates.count()
        
        self.stdout.write(f'🔍 Diagnosing {total_candidates} candidates with photos...\n')
        
        missing_files = []
        corrupted_files = []
        
        for candidate in candidates:
            candidate_info = f"ID: {candidate.id}, Name: {candidate.full_name}"
            
            if check_missing:
                # Check if photo file exists on disk
                if candidate.passport_photo:
                    try:
                        photo_path = candidate.passport_photo.path
                        if not os.path.exists(photo_path):
                            missing_files.append(f"{candidate_info}, Photo: {candidate.passport_photo.name}")
                    except Exception as e:
                        missing_files.append(f"{candidate_info}, Error accessing path: {str(e)}")
            
            if check_corrupted:
                # Check if photo file can be opened
                if candidate.passport_photo:
                    try:
                        photo_path = candidate.passport_photo.path
                        if os.path.exists(photo_path):
                            with Image.open(photo_path) as img:
                                # Try to load the image data
                                img.verify()
                    except Exception as e:
                        corrupted_files.append(f"{candidate_info}, Error: {str(e)}")
        
        # Report results
        if check_missing:
            self.stdout.write(self.style.WARNING(f'📂 Missing Files Check: {len(missing_files)} issues found'))
            if missing_files:
                for missing in missing_files[:10]:  # Show first 10
                    self.stdout.write(f'   ❌ {missing}')
                if len(missing_files) > 10:
                    self.stdout.write(f'   ... and {len(missing_files) - 10} more')
            else:
                self.stdout.write('   ✅ No missing files found')
        
        if check_corrupted:
            self.stdout.write(self.style.WARNING(f'\n🖼️  Corrupted Files Check: {len(corrupted_files)} issues found'))
            if corrupted_files:
                for corrupted in corrupted_files[:10]:  # Show first 10
                    self.stdout.write(f'   ❌ {corrupted}')
                if len(corrupted_files) > 10:
                    self.stdout.write(f'   ... and {len(corrupted_files) - 10} more')
            else:
                self.stdout.write('   ✅ No corrupted files found')
        
        # Summary
        total_issues = len(missing_files) + len(corrupted_files)
        self.stdout.write(
            self.style.SUCCESS(
                f'\n📊 Summary: {total_issues} total issues found out of {total_candidates} candidates checked'
            )
        )
        
        if total_issues > 0:
            self.stdout.write(self.style.WARNING('\n💡 Recommendations:'))
            if missing_files:
                self.stdout.write('   • Missing files: Update candidate records to remove invalid photo references')
            if corrupted_files:
                self.stdout.write('   • Corrupted files: Re-import photos for affected candidates')
