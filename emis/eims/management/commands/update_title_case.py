from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Occupation, Module, Paper, Sector, format_title_case


class Command(BaseCommand):
    help = 'Update existing records to use title case formatting for names'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--model',
            type=str,
            choices=['occupation', 'module', 'paper', 'sector', 'all'],
            default='all',
            help='Specify which model to update (default: all)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        model_choice = options['model']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        total_updated = 0
        
        # Define models to update
        models_to_update = []
        if model_choice == 'all':
            models_to_update = [
                ('Occupation', Occupation),
                ('Module', Module),
                ('Paper', Paper),
                ('Sector', Sector),
            ]
        else:
            model_map = {
                'occupation': ('Occupation', Occupation),
                'module': ('Module', Module),
                'paper': ('Paper', Paper),
                'sector': ('Sector', Sector),
            }
            models_to_update = [model_map[model_choice]]
        
        # Update each model
        for model_name, model_class in models_to_update:
            self.stdout.write(f'\nProcessing {model_name} records...')
            updated_count = self.update_model_records(model_class, model_name, dry_run)
            total_updated += updated_count
        
        # Summary
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nDRY RUN COMPLETE: {total_updated} records would be updated'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSUCCESS: {total_updated} records updated to title case'
                )
            )

    def update_model_records(self, model_class, model_name, dry_run):
        """Update records for a specific model"""
        updated_count = 0
        
        # Get all records
        records = model_class.objects.all()
        total_records = records.count()
        
        self.stdout.write(f'Found {total_records} {model_name} records')
        
        if not dry_run:
            # Use transaction for safety
            with transaction.atomic():
                for record in records:
                    old_name = record.name
                    new_name = format_title_case(old_name)
                    
                    if old_name != new_name:
                        # Show the change - handle models with/without code field
                        identifier = getattr(record, 'code', f'ID:{record.pk}')
                        self.stdout.write(
                            f'  {model_name} {identifier}: "{old_name}" → "{new_name}"'
                        )
                        
                        # Update the record directly in database to avoid triggering save() method
                        model_class.objects.filter(pk=record.pk).update(name=new_name)
                        updated_count += 1
                    else:
                        # Name is already in correct format
                        identifier = getattr(record, 'code', f'ID:{record.pk}')
                        self.stdout.write(
                            f'  {model_name} {identifier}: "{old_name}" (no change needed)',
                            ending=''
                        )
                        self.stdout.write('', ending='\r')  # Overwrite line
        else:
            # Dry run - just show what would change
            for record in records:
                old_name = record.name
                new_name = format_title_case(old_name)
                
                if old_name != new_name:
                    identifier = getattr(record, 'code', f'ID:{record.pk}')
                    self.stdout.write(
                        f'  {model_name} {identifier}: "{old_name}" → "{new_name}"'
                    )
                    updated_count += 1
        
        if not dry_run:
            self.stdout.write(f'Updated {updated_count} {model_name} records')
        else:
            self.stdout.write(f'Would update {updated_count} {model_name} records')
        
        return updated_count
