from django.core.management.base import BaseCommand
from eims.models import AssessmentCenter, Candidate, Level, CandidateModule
from decimal import Decimal


class Command(BaseCommand):
    help = 'Check Level fees for candidates at a specific center'

    def add_arguments(self, parser):
        parser.add_argument('center_number', type=str, help='Center number (e.g., UVT634)')

    def handle(self, *args, **options):
        center_number = options['center_number']
        
        try:
            center = AssessmentCenter.objects.get(center_number=center_number)
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Center {center_number} not found'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\n=== LEVEL FEES CHECK FOR {center.center_name} ===\n'))
        
        candidates = Candidate.objects.filter(assessment_center=center)
        
        # Get unique occupations
        occupations = set()
        for candidate in candidates:
            if candidate.occupation:
                occupations.add(candidate.occupation)
        
        self.stdout.write(f'Found {len(occupations)} unique occupation(s)\n')
        
        for occupation in occupations:
            self.stdout.write(f'\n--- OCCUPATION: {occupation.name} ({occupation.code}) ---')
            
            # Get all levels for this occupation
            levels = Level.objects.filter(occupation=occupation).order_by('name')
            
            if not levels.exists():
                self.stdout.write(self.style.WARNING('  No levels found for this occupation!'))
                continue
            
            for level in levels:
                self.stdout.write(f'\n  Level: {level.name}')
                self.stdout.write(f'    Formal Fee: UGX {level.formal_fee:,.2f}')
                self.stdout.write(f'    Modular Single (1 module): UGX {level.modular_fee_single:,.2f}')
                self.stdout.write(f'    Modular Double (2 modules): UGX {level.modular_fee_double:,.2f}')
                self.stdout.write(f'    Worker\'s PAS Module Fee: UGX {level.workers_pas_module_fee:,.2f}')
        
        # Now calculate expected totals
        self.stdout.write(f'\n\n--- EXPECTED BILLING CALCULATION ---')
        
        modular_candidates = candidates.filter(registration_category='Modular')
        formal_candidates = candidates.filter(registration_category='Formal')
        
        # Modular calculation
        modular_total = Decimal('0.00')
        modular_1_module = 0
        modular_2_modules = 0
        
        self.stdout.write(f'\nMODULAR CANDIDATES:')
        for candidate in modular_candidates:
            module_count = CandidateModule.objects.filter(candidate=candidate).count()
            if module_count > 0:
                first_module = CandidateModule.objects.filter(candidate=candidate).first()
                if first_module and first_module.module and first_module.module.level:
                    level = first_module.module.level
                    if module_count == 1:
                        fee = level.modular_fee_single
                        modular_1_module += 1
                    elif module_count >= 2:
                        fee = level.modular_fee_double
                        modular_2_modules += 1
                    else:
                        fee = Decimal('0.00')
                    
                    modular_total += fee
                    
                    # Show first 5 as examples
                    if modular_1_module + modular_2_modules <= 5:
                        self.stdout.write(f'  {candidate.reg_number}: {module_count} module(s) = UGX {fee:,.2f}')
        
        self.stdout.write(f'\n  Total Modular: {modular_1_module} with 1 module + {modular_2_modules} with 2 modules')
        self.stdout.write(f'  Total Modular Fees: UGX {modular_total:,.2f}')
        
        # Formal calculation
        formal_total = Decimal('0.00')
        formal_by_level = {}
        
        self.stdout.write(f'\nFORMAL CANDIDATES:')
        for candidate in formal_candidates:
            from eims.models import CandidateLevel
            level_enrollments = CandidateLevel.objects.filter(candidate=candidate).select_related('level')
            
            for level_enrollment in level_enrollments:
                level = level_enrollment.level
                fee = level.formal_fee
                formal_total += fee
                
                if level.name not in formal_by_level:
                    formal_by_level[level.name] = {'count': 0, 'fee': fee}
                formal_by_level[level.name]['count'] += 1
        
        for level_name, data in formal_by_level.items():
            self.stdout.write(f'  {level_name}: {data["count"]} candidates @ UGX {data["fee"]:,.2f} each')
        
        self.stdout.write(f'\n  Total Formal Fees: UGX {formal_total:,.2f}')
        
        # Grand total
        grand_total = modular_total + formal_total
        self.stdout.write(f'\n--- GRAND TOTAL ---')
        self.stdout.write(f'Expected Total: UGX {grand_total:,.2f}')
        
        # Compare with what system shows
        actual_total = center.get_total_fees_balance()
        self.stdout.write(f'System Shows: UGX {actual_total:,.2f}')
        
        if abs(grand_total - actual_total) > Decimal('0.01'):
            discrepancy = actual_total - grand_total
            self.stdout.write(self.style.WARNING(f'\n⚠️  DISCREPANCY: UGX {discrepancy:,.2f}'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Totals match!'))
        
        self.stdout.write(self.style.SUCCESS(f'\n=== CHECK COMPLETE ==='))
