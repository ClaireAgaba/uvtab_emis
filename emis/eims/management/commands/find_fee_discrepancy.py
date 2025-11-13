from django.core.management.base import BaseCommand
from eims.models import AssessmentCenter, Candidate, CandidateLevel, CandidateModule
from decimal import Decimal


class Command(BaseCommand):
    help = 'Find the exact source of fee discrepancy for a center'

    def add_arguments(self, parser):
        parser.add_argument('center_number', type=str, help='Center number (e.g., UVT634)')
        parser.add_argument('--expected-total', type=float, help='Expected total amount')

    def handle(self, *args, **options):
        center_number = options['center_number']
        expected_total = Decimal(str(options.get('expected_total', 0))) if options.get('expected_total') else None
        
        try:
            center = AssessmentCenter.objects.get(center_number=center_number)
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Center {center_number} not found'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\n=== FINDING FEE DISCREPANCY FOR {center.center_name} ===\n'))
        
        candidates = Candidate.objects.filter(assessment_center=center)
        actual_total = center.get_total_fees_balance()
        
        self.stdout.write(f'Actual Total: UGX {actual_total:,.2f}')
        if expected_total:
            discrepancy = actual_total - expected_total
            self.stdout.write(f'Expected Total: UGX {expected_total:,.2f}')
            self.stdout.write(f'Discrepancy: UGX {discrepancy:,.2f}\n')
        
        # Analyze by category
        modular = candidates.filter(registration_category='Modular')
        formal = candidates.filter(registration_category='Formal')
        
        self.stdout.write('--- CATEGORY BREAKDOWN ---')
        
        # Modular Analysis
        modular_with_fees = modular.filter(fees_balance__gt=0)
        modular_total = sum(c.fees_balance for c in modular_with_fees)
        
        self.stdout.write(f'\nMODULAR:')
        self.stdout.write(f'  Total candidates: {modular.count()}')
        self.stdout.write(f'  With fees > 0: {modular_with_fees.count()}')
        self.stdout.write(f'  Total fees: UGX {modular_total:,.2f}')
        
        # Check for anomalies in modular
        modular_anomalies = []
        for candidate in modular_with_fees:
            module_count = CandidateModule.objects.filter(candidate=candidate).count()
            level_enrollment = CandidateLevel.objects.filter(candidate=candidate).first()
            
            if level_enrollment and level_enrollment.level:
                level = level_enrollment.level
                if module_count == 1:
                    expected = level.modular_fee_single
                elif module_count >= 2:
                    expected = level.modular_fee_double
                else:
                    expected = Decimal('0')
                
                if abs(candidate.fees_balance - expected) > Decimal('0.01'):
                    modular_anomalies.append({
                        'regno': candidate.reg_number,
                        'modules': module_count,
                        'expected': expected,
                        'actual': candidate.fees_balance,
                        'diff': candidate.fees_balance - expected
                    })
        
        if modular_anomalies:
            self.stdout.write(f'\n  ⚠️  Found {len(modular_anomalies)} modular candidates with fee mismatches:')
            for anomaly in modular_anomalies:
                self.stdout.write(
                    f'    {anomaly["regno"]}: {anomaly["modules"]} module(s) - '
                    f'Expected UGX {anomaly["expected"]:,.2f}, Got UGX {anomaly["actual"]:,.2f} '
                    f'(Diff: {anomaly["diff"]:+,.2f})'
                )
        
        # Formal Analysis
        formal_with_fees = formal.filter(fees_balance__gt=0)
        formal_total = sum(c.fees_balance for c in formal_with_fees)
        
        self.stdout.write(f'\nFORMAL:')
        self.stdout.write(f'  Total candidates: {formal.count()}')
        self.stdout.write(f'  With fees > 0: {formal_with_fees.count()}')
        self.stdout.write(f'  Total fees: UGX {formal_total:,.2f}')
        
        # Check for anomalies in formal
        formal_anomalies = []
        formal_multi_level = []
        
        for candidate in formal_with_fees:
            level_enrollments = CandidateLevel.objects.filter(candidate=candidate).select_related('level')
            level_count = level_enrollments.count()
            expected = sum(le.level.formal_fee for le in level_enrollments)
            
            if abs(candidate.fees_balance - expected) > Decimal('0.01'):
                formal_anomalies.append({
                    'regno': candidate.reg_number,
                    'levels': level_count,
                    'expected': expected,
                    'actual': candidate.fees_balance,
                    'diff': candidate.fees_balance - expected
                })
            
            if level_count > 1:
                level_names = [le.level.name for le in level_enrollments]
                formal_multi_level.append({
                    'regno': candidate.reg_number,
                    'levels': level_names,
                    'fees': candidate.fees_balance
                })
        
        if formal_anomalies:
            self.stdout.write(f'\n  ⚠️  Found {len(formal_anomalies)} formal candidates with fee mismatches:')
            for anomaly in formal_anomalies:
                self.stdout.write(
                    f'    {anomaly["regno"]}: {anomaly["levels"]} level(s) - '
                    f'Expected UGX {anomaly["expected"]:,.2f}, Got UGX {anomaly["actual"]:,.2f} '
                    f'(Diff: {anomaly["diff"]:+,.2f})'
                )
        
        if formal_multi_level:
            self.stdout.write(f'\n  ⚠️  Found {len(formal_multi_level)} formal candidates enrolled in MULTIPLE levels:')
            for item in formal_multi_level:
                self.stdout.write(
                    f'    {item["regno"]}: {", ".join(item["levels"])} - '
                    f'Total fees: UGX {item["fees"]:,.2f}'
                )
        
        # Summary
        self.stdout.write(f'\n--- SUMMARY ---')
        calculated_total = modular_total + formal_total
        self.stdout.write(f'Modular Total: UGX {modular_total:,.2f}')
        self.stdout.write(f'Formal Total: UGX {formal_total:,.2f}')
        self.stdout.write(f'Calculated Total: UGX {calculated_total:,.2f}')
        self.stdout.write(f'Actual Total: UGX {actual_total:,.2f}')
        
        if abs(calculated_total - actual_total) > Decimal('0.01'):
            self.stdout.write(self.style.WARNING(f'Mismatch: UGX {actual_total - calculated_total:,.2f}'))
        
        # Possible causes
        self.stdout.write(f'\n--- POSSIBLE CAUSES OF DISCREPANCY ---')
        
        total_anomaly_diff = sum(a['diff'] for a in modular_anomalies) + sum(a['diff'] for a in formal_anomalies)
        
        if modular_anomalies or formal_anomalies:
            self.stdout.write(f'1. Fee calculation errors: UGX {total_anomaly_diff:+,.2f}')
        
        if formal_multi_level:
            multi_level_extra = sum(item['fees'] for item in formal_multi_level)
            # Estimate what they should have paid (assuming 1 level each)
            if formal_multi_level:
                sample_level = CandidateLevel.objects.filter(
                    candidate__reg_number=formal_multi_level[0]['regno']
                ).first()
                if sample_level:
                    estimated_single = sample_level.level.formal_fee * len(formal_multi_level)
                    multi_level_excess = multi_level_extra - estimated_single
                    self.stdout.write(f'2. Multi-level enrollments excess: ~UGX {multi_level_excess:+,.2f}')
        
        # Check for candidates with fees but no enrollment
        self.stdout.write(f'\n--- CANDIDATES WITH FEES BUT NO ENROLLMENT ---')
        orphan_fees = Decimal('0')
        orphan_count = 0
        
        for candidate in candidates.filter(fees_balance__gt=0):
            module_count = CandidateModule.objects.filter(candidate=candidate).count()
            level_count = CandidateLevel.objects.filter(candidate=candidate).count()
            
            if module_count == 0 and level_count == 0:
                orphan_count += 1
                orphan_fees += candidate.fees_balance
                self.stdout.write(f'  {candidate.reg_number} ({candidate.registration_category}): UGX {candidate.fees_balance:,.2f}')
        
        if orphan_count > 0:
            self.stdout.write(f'\nTotal orphan fees: UGX {orphan_fees:,.2f} from {orphan_count} candidates')
        else:
            self.stdout.write('No candidates with fees but no enrollment found.')
        
        self.stdout.write(self.style.SUCCESS(f'\n=== ANALYSIS COMPLETE ==='))
