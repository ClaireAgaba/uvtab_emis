#!/usr/bin/env python
"""
Simple script to update existing records to title case formatting.
Run this from the project root directory.
"""

import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/home/claire/Desktop/projects/emis/emis')

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'emis.settings')
django.setup()

from eims.models import Occupation, Module, Paper, Sector, format_title_case


def update_records(dry_run=True):
    """Update all records to title case formatting"""
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("=" * 50)
    else:
        print("🚀 UPDATING RECORDS - Changes will be saved")
        print("=" * 50)
    
    total_updated = 0
    models_to_update = [
        ('Occupations', Occupation),
        ('Modules', Module),
        ('Papers', Paper),
        ('Sectors', Sector),
    ]
    
    for model_name, model_class in models_to_update:
        print(f"\n📋 Processing {model_name}...")
        records = model_class.objects.all()
        updated_count = 0
        
        for record in records:
            old_name = record.name
            new_name = format_title_case(old_name)
            
            if old_name != new_name:
                print(f"  ✏️  {record.code}: \"{old_name}\" → \"{new_name}\"")
                
                if not dry_run:
                    # Update directly in database to avoid triggering save() method
                    model_class.objects.filter(pk=record.pk).update(name=new_name)
                
                updated_count += 1
            else:
                print(f"  ✅ {record.code}: \"{old_name}\" (already correct)")
        
        print(f"📊 {model_name}: {updated_count} records {'would be ' if dry_run else ''}updated")
        total_updated += updated_count
    
    print("\n" + "=" * 50)
    if dry_run:
        print(f"🎯 SUMMARY: {total_updated} records would be updated to title case")
        print("\n💡 To actually apply changes, run: python update_existing_to_title_case.py --apply")
    else:
        print(f"✅ SUCCESS: {total_updated} records updated to title case")


if __name__ == "__main__":
    # Check command line arguments
    apply_changes = '--apply' in sys.argv
    
    if apply_changes:
        confirm = input("⚠️  This will update existing records. Are you sure? (yes/no): ")
        if confirm.lower() == 'yes':
            update_records(dry_run=False)
        else:
            print("❌ Operation cancelled")
    else:
        print("💡 Running in dry-run mode. Use --apply to make actual changes.")
        update_records(dry_run=True)
