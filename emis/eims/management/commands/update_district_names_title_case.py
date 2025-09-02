from django.core.management.base import BaseCommand
from eims.models import District


class Command(BaseCommand):
    help = 'Update all district names to proper sentence case with articles in lowercase'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what changes would be made without actually updating the database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made to the database'))
            self.stdout.write('')

        # Get all districts
        districts = District.objects.all().order_by('name')
        
        if not districts.exists():
            self.stdout.write(self.style.WARNING('No districts found.'))
            return

        self.stdout.write(f'Found {districts.count()} districts to process...')
        self.stdout.write('')

        updated_count = 0
        
        for district in districts:
            original_name = district.name
            formatted_name = self.format_district_name(original_name)
            
            if original_name != formatted_name:
                self.stdout.write(f'DISTRICT:')
                self.stdout.write(f'  Before: "{original_name}"')
                self.stdout.write(f'  After:  "{formatted_name}"')
                
                if not dry_run:
                    district.name = formatted_name
                    district.save()
                    self.stdout.write(self.style.SUCCESS('  ✓ Updated'))
                else:
                    self.stdout.write(self.style.WARNING('  → Would be updated'))
                
                updated_count += 1
                self.stdout.write('')
            else:
                # Name is already properly formatted
                if not dry_run:
                    self.stdout.write(f'DISTRICT: "{original_name}" - Already properly formatted')

        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN COMPLETE: {updated_count} districts would be updated'))
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            self.stdout.write(self.style.SUCCESS(f'COMPLETED: {updated_count} districts updated successfully'))

    def format_district_name(self, name):
        """Format district name to proper sentence case with articles in lowercase"""
        if not name:
            return name
            
        # Convert to proper sentence case with articles in lowercase
        words = name.strip().split()
        formatted_words = []
        
        # Articles and prepositions to keep lowercase (except at start)
        lowercase_words = {'in', 'and', 'for', 'of', 'the', 'at', 'on', 'by', 'with', 'to'}
        
        for i, word in enumerate(words):
            if i == 0:  # First word is always capitalized
                formatted_words.append(word.capitalize())
            elif word.lower() in lowercase_words:
                formatted_words.append(word.lower())
            else:
                formatted_words.append(word.capitalize())
        
        return ' '.join(formatted_words)
