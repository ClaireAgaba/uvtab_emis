from django.core.management.base import BaseCommand
from eims.models import AssessmentCenter, Candidate, CandidateLevel, CandidateModule
from django.db.models import Count, Q


class Command(BaseCommand):
    help = 'Investigate billing discrepancy for a specific assessment center'

    def add_arguments(self, parser):
        parser.add_argument('center_number', type=str, help='Center number to investigate (e.g., UVT634)')

    def handle(self, *args, **options):
        center_number = options['center_number']
        
        try:
            center = AssessmentCenter.objects.get(center_number=center_number)
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Center {center_number} not found'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\n=== BILLING INVESTIGATION FOR {center.center_name} ({center_number}) ===\n'))
        
        # Get all candidates for this center
        candidates = Candidate.objects.filter(assessment_center=center)
        total_candidates = candidates.count()
        
        self.stdout.write(f'Total Candidates: {total_candidates}')
        self.stdout.write(f'Center Total Fees Balance: UGX {center.get_total_fees_balance():,.2f}\n')
        
        # Break down by registration category
        modular_candidates = candidates.filter(registration_category='Modular')
        formal_candidates = candidates.filter(registration_category='Formal')
        informal_candidates = candidates.filter(registration_category='Informal')
        
        self.stdout.write(f'\n--- REGISTRATION CATEGORY BREAKDOWN ---')
        self.stdout.write(f'Modular: {modular_candidates.count()} candidates')
        self.stdout.write(f'Formal: {formal_candidates.count()} candidates')
        self.stdout.write(f'Informal: {informal_candidates.count()} candidates')
        
        # Analyze Modular candidates
        self.stdout.write(f'\n--- MODULAR CANDIDATES ANALYSIS ---')
        modular_total_fees = 0
        modular_enrolled = 0
        modular_1_module = 0
        modular_2_modules = 0
        
        for candidate in modular_candidates:
            module_count = CandidateModule.objects.filter(candidate=candidate).count()
            if module_count > 0:
                modular_enrolled += 1
                if module_count == 1:
                    modular_1_module += 1
                elif module_count == 2:
                    modular_2_modules += 1
                
                modular_total_fees += candidate.fees_balance
        
        self.stdout.write(f'Enrolled Modular: {modular_enrolled}')
        self.stdout.write(f'  - 1 Module: {modular_1_module} candidates')
        self.stdout.write(f'  - 2 Modules: {modular_2_modules} candidates')
        self.stdout.write(f'Total Modular Fees: UGX {modular_total_fees:,.2f}')
        
        # Analyze Formal candidates
        self.stdout.write(f'\n--- FORMAL CANDIDATES ANALYSIS ---')
        formal_total_fees = 0
        formal_enrolled = 0
        formal_by_level = {}
        
        for candidate in formal_candidates:
            level_count = CandidateLevel.objects.filter(candidate=candidate).count()
            if level_count > 0:
                formal_enrolled += 1
                formal_total_fees += candidate.fees_balance
                
                # Get level details
                levels = CandidateLevel.objects.filter(candidate=candidate).select_related('level')
                for cl in levels:
                    level_name = cl.level.name
                    if level_name not in formal_by_level:
                        formal_by_level[level_name] = {
                            'count': 0,
                            'fee': cl.level.formal_fee or 0
                        }
                    formal_by_level[level_name]['count'] += 1
        
        self.stdout.write(f'Enrolled Formal: {formal_enrolled}')
        for level_name, data in formal_by_level.items():
            self.stdout.write(f'  - {level_name}: {data["count"]} candidates @ UGX {data["fee"]:,.2f} each')
        self.stdout.write(f'Total Formal Fees: UGX {formal_total_fees:,.2f}')
        
        # Analyze Informal candidates
        if informal_candidates.count() > 0:
            self.stdout.write(f'\n--- INFORMAL/WORKER\'S PAS CANDIDATES ANALYSIS ---')
            informal_total_fees = 0
            informal_enrolled = 0
            
            for candidate in informal_candidates:
                module_count = CandidateModule.objects.filter(candidate=candidate).count()
                if module_count > 0:
                    informal_enrolled += 1
                    informal_total_fees += candidate.fees_balance
            
            self.stdout.write(f'Enrolled Informal: {informal_enrolled}')
            self.stdout.write(f'Total Informal Fees: UGX {informal_total_fees:,.2f}')
        
        # Calculate expected vs actual
        self.stdout.write(f'\n--- BILLING SUMMARY ---')
        expected_total = modular_total_fees + formal_total_fees
        if informal_candidates.count() > 0:
            expected_total += informal_total_fees
        
        actual_total = center.get_total_fees_balance()
        discrepancy = actual_total - expected_total
        
        self.stdout.write(f'Expected Total: UGX {expected_total:,.2f}')
        self.stdout.write(f'Actual Total: UGX {actual_total:,.2f}')
        self.stdout.write(f'Discrepancy: UGX {discrepancy:,.2f}')
        
        if abs(discrepancy) > 1:
            self.stdout.write(self.style.WARNING(f'\n⚠️  DISCREPANCY DETECTED: UGX {discrepancy:,.2f}'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Billing is accurate'))
        
        # Find candidates with non-zero fees
        self.stdout.write(f'\n--- CANDIDATES WITH FEES (NON-ZERO ONLY) ---')
        candidates_with_fees = candidates.filter(fees_balance__gt=0).order_by('-fees_balance')
        
        if candidates_with_fees.count() == 0:
            self.stdout.write(self.style.WARNING('No candidates have fees balance > 0'))
        else:
            self.stdout.write(f'{"Reg No":<20} {"Category":<10} {"Enrollment":<20} {"Expected Fee":<15} {"Actual Fee":<15} {"Diff":<12}')
            self.stdout.write('-' * 102)
            
            total_expected = 0
            total_actual = 0
            
            for candidate in candidates_with_fees:
                # Calculate expected fee
                if candidate.registration_category == 'Modular':
                    module_count = CandidateModule.objects.filter(candidate=candidate).count()
                    level_enrollment = CandidateLevel.objects.filter(candidate=candidate).first()
                    if level_enrollment and level_enrollment.level:
                        if module_count == 1:
                            expected_fee = level_enrollment.level.modular_fee_single or 0
                        elif module_count >= 2:
                            expected_fee = level_enrollment.level.modular_fee_double or 0
                        else:
                            expected_fee = 0
                    else:
                        expected_fee = 0
                    enrollment_info = f'{module_count} module(s)'
                    
                elif candidate.registration_category == 'Formal':
                    level_enrollments = CandidateLevel.objects.filter(candidate=candidate).select_related('level')
                    expected_fee = sum(le.level.formal_fee or 0 for le in level_enrollments)
                    level_count = level_enrollments.count()
                    enrollment_info = f'{level_count} level(s)'
                    
                else:  # Informal
                    module_count = CandidateModule.objects.filter(candidate=candidate).count()
                    level_enrollment = CandidateLevel.objects.filter(candidate=candidate).first()
                    if level_enrollment and level_enrollment.level:
                        workers_pas_fee = level_enrollment.level.workers_pas_module_fee or 0
                        expected_fee = workers_pas_fee * module_count
                    else:
                        expected_fee = 0
                    enrollment_info = f'{module_count} module(s)'
                
                actual_fee = candidate.fees_balance
                difference = actual_fee - expected_fee
                
                total_expected += expected_fee
                total_actual += actual_fee
                
                # Mark mismatches
                status = '⚠️' if abs(difference) > 0.01 else '✓'
                
                self.stdout.write(
                    f'{candidate.reg_number:<20} '
                    f'{candidate.registration_category:<10} '
                    f'{enrollment_info:<20} '
                    f'UGX {expected_fee:>12,.2f} '
                    f'UGX {actual_fee:>12,.2f} '
                    f'{status} {difference:>10,.2f}'
                )
            
            self.stdout.write('-' * 102)
            self.stdout.write(
                f'{"TOTALS":<20} {"":10} {"":20} '
                f'UGX {total_expected:>12,.2f} '
                f'UGX {total_actual:>12,.2f} '
                f'  {total_actual - total_expected:>10,.2f}'
            )
        
        # Show candidates with zero fees but enrolled
        self.stdout.write(f'\n--- ENROLLED CANDIDATES WITH ZERO FEES ---')
        enrolled_with_zero = []
        for candidate in candidates.filter(fees_balance=0):
            if candidate.registration_category == 'Modular':
                module_count = CandidateModule.objects.filter(candidate=candidate).count()
                if module_count > 0:
                    enrolled_with_zero.append((candidate, f'{module_count} module(s)'))
            elif candidate.registration_category == 'Formal':
                level_count = CandidateLevel.objects.filter(candidate=candidate).count()
                if level_count > 0:
                    enrolled_with_zero.append((candidate, f'{level_count} level(s)'))
            else:
                module_count = CandidateModule.objects.filter(candidate=candidate).count()
                if module_count > 0:
                    enrolled_with_zero.append((candidate, f'{module_count} module(s)'))
        
        if enrolled_with_zero:
            self.stdout.write(f'Found {len(enrolled_with_zero)} enrolled candidates with zero fees:')
            for candidate, enrollment_info in enrolled_with_zero[:10]:  # Show first 10
                self.stdout.write(f'  {candidate.reg_number} ({candidate.registration_category}) - {enrollment_info}')
            if len(enrolled_with_zero) > 10:
                self.stdout.write(f'  ... and {len(enrolled_with_zero) - 10} more')
        else:
            self.stdout.write('No enrolled candidates with zero fees found.')
        
        self.stdout.write(self.style.SUCCESS(f'\n=== INVESTIGATION COMPLETE ==='))
