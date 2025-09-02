from django.core.management.base import BaseCommand
from eims.models import Village


class Command(BaseCommand):
    help = 'Update all village names to proper sentence case with articles in lowercase'

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

        # Get all villages
        villages = Village.objects.all().order_by('district__name', 'name')
        
        if not villages.exists():
            self.stdout.write(self.style.WARNING('No villages found.'))
            return

        self.stdout.write(f'Found {villages.count()} villages to process...')
        self.stdout.write('')

        updated_count = 0
        
        for village in villages:
            original_name = village.name
            formatted_name = self.format_village_name(original_name)
            
            if original_name != formatted_name:
                self.stdout.write(f'VILLAGE ({village.district.name}):')
                self.stdout.write(f'  Before: "{original_name}"')
                self.stdout.write(f'  After:  "{formatted_name}"')
                
                if not dry_run:
                    village.name = formatted_name
                    village.save()
                    self.stdout.write(self.style.SUCCESS('  ✓ Updated'))
                else:
                    self.stdout.write(self.style.WARNING('  → Would be updated'))
                
                updated_count += 1
                self.stdout.write('')
            else:
                # Name is already properly formatted
                if not dry_run:
                    self.stdout.write(f'VILLAGE ({village.district.name}): "{original_name}" - Already properly formatted')

        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN COMPLETE: {updated_count} villages would be updated'))
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            self.stdout.write(self.style.SUCCESS(f'COMPLETED: {updated_count} villages updated successfully'))

    def format_village_name(self, name):
        """Format village name to proper sentence case with articles in lowercase"""
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
