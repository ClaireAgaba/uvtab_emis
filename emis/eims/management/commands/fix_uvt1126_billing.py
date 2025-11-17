from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Candidate, AssessmentCenter, CandidateLevel, CandidateModule

class Command(BaseCommand):
    help = 'Fix billing for UVT1126 center to correct total of 1,230,000'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making actual changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Apply fixes without confirmation',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(self.style.SUCCESS('\n=== UVT1126 BILLING FIX ===\n'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        try:
            center = AssessmentCenter.objects.get(center_number='UVT1126')
            self.stdout.write(f"Center: {center.center_name}\n")
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR("Center UVT1126 not found!"))
            return
        
        # Get all candidates
        candidates = Candidate.objects.filter(
            assessment_center=center
        ).order_by('registration_category', 'reg_number')
        
        self.stdout.write(f"Found {candidates.count()} candidates\n")
        
        # Expected fees based on your specification
        expected_fees = {
            'modular': 70000,
            'level2': 100000,
            'level3': 150000
        }
        
        changes = []
        total_old = 0
        total_new = 0
        
        self.stdout.write("=" * 120)
        self.stdout.write(f"{'Reg Number':<25} {'Name':<25} {'Category':<12} {'Old Balance':<15} {'New Balance':<15} {'Change'}")
        self.stdout.write("=" * 120)
        
        for candidate in candidates:
            old_balance = candidate.fees_balance
            total_old += old_balance
            
            # Determine correct fee based on category and level
            if candidate.registration_category == 'Modular':
                # Modular: 70,000 per candidate
                correct_fee = expected_fees['modular']
                category_label = "MODULAR"
                
            elif candidate.registration_category == 'Formal':
                # Check which level they're enrolled in
                level_enrollments = CandidateLevel.objects.filter(candidate=candidate)
                
                if level_enrollments.exists():
                    level_names = [le.level.name for le in level_enrollments]
                    
                    # Check for Level 2
                    if any('Level 2' in name or 'LEVEL 2' in name for name in level_names):
                        correct_fee = expected_fees['level2']
                        category_label = "FORMAL-L2"
                    # Check for Level 3
                    elif any('Level 3' in name or 'LEVEL 3' in name for name in level_names):
                        correct_fee = expected_fees['level3']
                        category_label = "FORMAL-L3"
                    else:
                        # Unknown level, skip
                        self.stdout.write(self.style.WARNING(
                            f"⚠️  {candidate.reg_number} | {candidate.full_name[:24]} | "
                            f"Unknown level: {', '.join(level_names)}"
                        ))
                        continue
                else:
                    # No level enrollment, skip
                    self.stdout.write(self.style.WARNING(
                        f"⚠️  {candidate.reg_number} | {candidate.full_name[:24]} | "
                        f"No level enrollment found"
                    ))
                    continue
            else:
                # Other category, skip
                continue
            
            total_new += correct_fee
            change = correct_fee - old_balance
            
            if change != 0:
                changes.append({
                    'candidate': candidate,
                    'old_balance': old_balance,
                    'new_balance': correct_fee,
                    'change': change,
                    'category': category_label
                })
                
                change_indicator = "+" if change > 0 else ""
                self.stdout.write(
                    f"{candidate.reg_number:<25} "
                    f"{candidate.full_name[:24]:<25} "
                    f"{category_label:<12} "
                    f"UGX {old_balance:>10,.2f}   "
                    f"UGX {correct_fee:>10,.2f}   "
                    f"{change_indicator}UGX {change:>10,.2f}"
                )
            else:
                self.stdout.write(
                    f"{candidate.reg_number:<25} "
                    f"{candidate.full_name[:24]:<25} "
                    f"{category_label:<12} "
                    f"UGX {old_balance:>10,.2f}   "
                    f"UGX {correct_fee:>10,.2f}   "
                    f"✓ Correct"
                )
        
        self.stdout.write("=" * 120)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== SUMMARY ===\n'))
        self.stdout.write(f"Current Total:  UGX {total_old:>12,.2f}")
        self.stdout.write(f"Expected Total: UGX {total_new:>12,.2f}")
        self.stdout.write(f"Adjustment:     UGX {total_new - total_old:>12,.2f}")
        self.stdout.write(f"\nCandidates to update: {len(changes)}")
        
        if not changes:
            self.stdout.write(self.style.SUCCESS("\n✓ All billing is already correct!"))
            return
        
        # Show what will be changed
        if changes:
            self.stdout.write(self.style.WARNING('\n=== CHANGES TO BE MADE ===\n'))
            for change in changes:
                c = change['candidate']
                self.stdout.write(
                    f"{c.reg_number} | {c.full_name[:30]:30} | "
                    f"{change['old_balance']:>10,.2f} → {change['new_balance']:>10,.2f} "
                    f"({'+' if change['change'] > 0 else ''}{change['change']:,.2f})"
                )
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes made'))
            return
        
        # Confirmation
        if not force:
            self.stdout.write(self.style.WARNING('\n⚠️  This will update fees_balance for the candidates listed above.'))
            self.stdout.write(self.style.WARNING('⚠️  Payment records will be preserved.'))
            confirm = input('\nType "yes" to proceed: ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Aborted.'))
                return
        
        # Apply changes
        self.stdout.write(self.style.SUCCESS('\n=== APPLYING CHANGES ===\n'))
        
        with transaction.atomic():
            updated_count = 0
            for change in changes:
                candidate = change['candidate']
                old_balance = candidate.fees_balance
                new_balance = change['new_balance']
                
                candidate.fees_balance = new_balance
                candidate.save(update_fields=['fees_balance'])
                
                updated_count += 1
                self.stdout.write(
                    f"✓ Updated {candidate.reg_number}: "
                    f"UGX {old_balance:,.2f} → UGX {new_balance:,.2f}"
                )
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully updated {updated_count} candidates'))
            self.stdout.write(self.style.SUCCESS(f'✓ New center total: UGX {total_new:,.2f}'))
        
        self.stdout.write('\n')
