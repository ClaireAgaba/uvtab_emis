"""
Django shell script to update existing records to title case formatting.
Run this with: python manage.py shell < update_title_case_shell.py
"""

from eims.models import Occupation, Module, Paper, Sector, format_title_case
from django.db import transaction

def update_records_to_title_case():
    """Update all records to title case formatting"""
    
    print("🔍 CHECKING EXISTING RECORDS FOR TITLE CASE UPDATES")
    print("=" * 60)
    
    total_updated = 0
    models_to_update = [
        ('Occupations', Occupation),
        ('Modules', Module), 
        ('Papers', Paper),
        ('Sectors', Sector),
    ]
    
    # First, show what would change (dry run)
    print("\n📋 DRY RUN - Showing what would be updated:")
    for model_name, model_class in models_to_update:
        print(f"\n{model_name}:")
        records = model_class.objects.all()
        changes_needed = 0
        
        for record in records:
            old_name = record.name
            new_name = format_title_case(old_name)
            
            if old_name != new_name:
                print(f"  ✏️  {record.code}: \"{old_name}\" → \"{new_name}\"")
                changes_needed += 1
            else:
                print(f"  ✅ {record.code}: \"{old_name}\" (already correct)")
        
        print(f"📊 {model_name}: {changes_needed} records need updating")
        total_updated += changes_needed
    
    print(f"\n🎯 TOTAL: {total_updated} records need title case formatting")
    
    if total_updated > 0:
        print("\n" + "=" * 60)
        confirm = input("🚀 Apply these changes? (yes/no): ")
        
        if confirm.lower() == 'yes':
            print("\n🚀 APPLYING CHANGES...")
            
            with transaction.atomic():
                actual_updated = 0
                for model_name, model_class in models_to_update:
                    print(f"\nUpdating {model_name}...")
                    
                    for record in model_class.objects.all():
                        old_name = record.name
                        new_name = format_title_case(old_name)
                        
                        if old_name != new_name:
                            # Update directly to avoid triggering save() method
                            model_class.objects.filter(pk=record.pk).update(name=new_name)
                            print(f"  ✅ Updated {record.code}")
                            actual_updated += 1
                
                print(f"\n✅ SUCCESS: {actual_updated} records updated to title case!")
        else:
            print("❌ Changes cancelled")
    else:
        print("\n✅ All records are already in correct title case format!")

# Run the update function
update_records_to_title_case()
