from django.core.management.base import BaseCommand
from django.db.models import Sum
from eims.models import Candidate, AssessmentCenter, CandidateLevel

class Command(BaseCommand):
    help = 'Diagnose billing issues for UVT1126 center'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== UVT1126 CENTER BILLING DIAGNOSIS ===\n'))
        
        try:
            center = AssessmentCenter.objects.get(center_number='UVT1126')
            self.stdout.write(f"Center: {center.center_name}")
            self.stdout.write(f"Center Number: {center.center_number}\n")
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR("Center UVT1126 not found!"))
            return
        
        # Get all enrolled candidates
        candidates = Candidate.objects.filter(
            assessment_center=center,
            status='enrolled'
        ).order_by('registration_category', 'reg_number')
        
        self.stdout.write(f"Total Enrolled Candidates: {candidates.count()}\n")
        
        # Track totals
        modular_count = 0
        modular_total = 0
        formal_level2_count = 0
        formal_level2_total = 0
        formal_level3_count = 0
        formal_level3_total = 0
        other_total = 0
        
        self.stdout.write("=" * 120)
        self.stdout.write(f"{'Reg Number':<25} {'Name':<25} {'Category':<12} {'Levels':<20} {'Balance':<15} {'Status'}")
        self.stdout.write("=" * 120)
        
        for candidate in candidates:
            # Get level enrollments
            level_enrollments = CandidateLevel.objects.filter(candidate=candidate)
            level_names = ', '.join([le.level.name for le in level_enrollments]) if level_enrollments.exists() else 'None'
            
            # Categorize
            if candidate.registration_category == 'Modular':
                modular_count += 1
                modular_total += candidate.fees_balance
                category_label = "MODULAR"
            elif candidate.registration_category == 'Formal':
                # Check which level
                if 'Level 2' in level_names or 'LEVEL 2' in level_names:
                    formal_level2_count += 1
                    formal_level2_total += candidate.fees_balance
                    category_label = "FORMAL-L2"
                elif 'Level 3' in level_names or 'LEVEL 3' in level_names:
                    formal_level3_count += 1
                    formal_level3_total += candidate.fees_balance
                    category_label = "FORMAL-L3"
                else:
                    category_label = "FORMAL-?"
                    other_total += candidate.fees_balance
            else:
                category_label = candidate.registration_category
                other_total += candidate.fees_balance
            
            # Check if cleared
            cleared_status = "✓ CLEARED" if candidate.fees_balance == 0 else "UNPAID"
            
            self.stdout.write(
                f"{candidate.reg_number:<25} "
                f"{candidate.full_name[:24]:<25} "
                f"{category_label:<12} "
                f"{level_names[:19]:<20} "
                f"UGX {candidate.fees_balance:>10,.2f}   "
                f"{cleared_status}"
            )
        
        self.stdout.write("=" * 120)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== BILLING SUMMARY ===\n'))
        
        self.stdout.write(f"Modular Candidates: {modular_count}")
        self.stdout.write(f"  Expected: {modular_count} × 70,000 = UGX {modular_count * 70000:,.2f}")
        self.stdout.write(f"  Actual Total: UGX {modular_total:,.2f}")
        if modular_total != modular_count * 70000:
            self.stdout.write(self.style.ERROR(f"  ❌ DISCREPANCY: UGX {modular_total - (modular_count * 70000):,.2f}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"  ✓ Correct"))
        
        self.stdout.write(f"\nFormal Level 2 Candidates: {formal_level2_count}")
        self.stdout.write(f"  Expected: {formal_level2_count} × 100,000 = UGX {formal_level2_count * 100000:,.2f}")
        self.stdout.write(f"  Actual Total: UGX {formal_level2_total:,.2f}")
        if formal_level2_total != formal_level2_count * 100000:
            self.stdout.write(self.style.ERROR(f"  ❌ DISCREPANCY: UGX {formal_level2_total - (formal_level2_count * 100000):,.2f}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"  ✓ Correct"))
        
        self.stdout.write(f"\nFormal Level 3 Candidates: {formal_level3_count}")
        self.stdout.write(f"  Expected: {formal_level3_count} × 150,000 = UGX {formal_level3_count * 150000:,.2f}")
        self.stdout.write(f"  Actual Total: UGX {formal_level3_total:,.2f}")
        if formal_level3_total != formal_level3_count * 150000:
            self.stdout.write(self.style.ERROR(f"  ❌ DISCREPANCY: UGX {formal_level3_total - (formal_level3_count * 150000):,.2f}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"  ✓ Correct"))
        
        if other_total > 0:
            self.stdout.write(f"\nOther/Unclassified: UGX {other_total:,.2f}")
        
        # Grand totals
        expected_total = (modular_count * 70000) + (formal_level2_count * 100000) + (formal_level3_count * 150000)
        actual_total = modular_total + formal_level2_total + formal_level3_total + other_total
        
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(f"EXPECTED TOTAL: UGX {expected_total:,.2f}")
        self.stdout.write(f"ACTUAL TOTAL:   UGX {actual_total:,.2f}")
        
        if actual_total != expected_total:
            discrepancy = actual_total - expected_total
            self.stdout.write(self.style.ERROR(f"DISCREPANCY:    UGX {discrepancy:,.2f}"))
            
            if discrepancy > 0:
                self.stdout.write(self.style.ERROR(f"\n❌ System is OVERCHARGING by UGX {discrepancy:,.2f}"))
            else:
                self.stdout.write(self.style.WARNING(f"\n⚠️  System is UNDERCHARGING by UGX {abs(discrepancy):,.2f}"))
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ BILLING IS CORRECT!"))
        
        self.stdout.write("=" * 60)
        
        # Check for multi-level enrollments
        self.stdout.write(self.style.SUCCESS('\n=== CHECKING FOR MULTI-LEVEL ENROLLMENTS ===\n'))
        
        multi_level_candidates = []
        for candidate in candidates:
            level_count = CandidateLevel.objects.filter(candidate=candidate).count()
            if level_count > 1:
                levels = CandidateLevel.objects.filter(candidate=candidate)
                level_names = ', '.join([le.level.name for le in levels])
                multi_level_candidates.append({
                    'candidate': candidate,
                    'level_count': level_count,
                    'levels': level_names
                })
        
        if multi_level_candidates:
            self.stdout.write(self.style.ERROR(f"Found {len(multi_level_candidates)} candidates with multiple level enrollments:"))
            for item in multi_level_candidates:
                c = item['candidate']
                self.stdout.write(
                    f"  {c.reg_number} | {c.full_name} | "
                    f"{item['level_count']} levels: {item['levels']} | "
                    f"Balance: UGX {c.fees_balance:,.2f}"
                )
        else:
            self.stdout.write(self.style.SUCCESS("✓ No multi-level enrollments found"))
        
        self.stdout.write('\n')
