from django.core.management.base import BaseCommand
from eims.models import AssessmentCenter, Candidate, CandidateLevel, CandidateModule
from django.db import transaction


class Command(BaseCommand):
    help = 'Recalculate fees for all candidates in a specific assessment center'

    def add_arguments(self, parser):
        parser.add_argument('center_number', type=str, help='Center number to recalculate (e.g., UVT634)')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually changing it',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Actually apply the fee recalculation',
        )

    def handle(self, *args, **options):
        center_number = options['center_number']
        dry_run = options['dry_run']
        fix = options['fix']
        
        if not dry_run and not fix:
            self.stdout.write(self.style.ERROR('Please specify either --dry-run or --fix'))
            return
        
        try:
            center = AssessmentCenter.objects.get(center_number=center_number)
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Center {center_number} not found'))
            return
        
        mode = 'DRY RUN' if dry_run else 'FIXING'
        self.stdout.write(self.style.SUCCESS(f'\n=== {mode}: RECALCULATING FEES FOR {center.center_name} ({center_number}) ===\n'))
        
        # Get all candidates for this center
        candidates = Candidate.objects.filter(assessment_center=center)
        total_candidates = candidates.count()
        
        self.stdout.write(f'Total Candidates: {total_candidates}')
        self.stdout.write(f'Current Center Total: UGX {center.get_total_fees_balance():,.2f}\n')
        
        changes_made = 0
        total_old_fees = 0
        total_new_fees = 0
        
        self.stdout.write(f'\n{"Reg No":<20} {"Category":<10} {"Old Fees":<15} {"New Fees":<15} {"Change":<15} {"Status"}')
        self.stdout.write('-' * 95)
        
        for candidate in candidates.order_by('registration_category', 'reg_number'):
            old_fees = candidate.fees_balance
            
            # Recalculate fees based on enrollment
            new_fees = self.calculate_candidate_fees(candidate)
            
            total_old_fees += old_fees
            total_new_fees += new_fees
            
            change = new_fees - old_fees
            
            if abs(change) > 0.01:  # If there's a difference
                changes_made += 1
                status = '⚠️  MISMATCH'
                
                self.stdout.write(
                    f'{candidate.reg_number:<20} '
                    f'{candidate.registration_category:<10} '
                    f'UGX {old_fees:>12,.2f} '
                    f'UGX {new_fees:>12,.2f} '
                    f'UGX {change:>12,.2f} '
                    f'{status}'
                )
                
                # Update if not dry run
                if fix:
                    candidate.fees_balance = new_fees
                    candidate.save(update_fields=['fees_balance'])
            else:
                # Only show if verbose
                pass
        
        self.stdout.write('-' * 95)
        self.stdout.write(f'{"TOTALS":<20} {"":10} UGX {total_old_fees:>12,.2f} UGX {total_new_fees:>12,.2f} UGX {total_new_fees - total_old_fees:>12,.2f}')
        
        self.stdout.write(f'\n--- SUMMARY ---')
        self.stdout.write(f'Candidates with fee mismatches: {changes_made}')
        self.stdout.write(f'Old Total: UGX {total_old_fees:,.2f}')
        self.stdout.write(f'New Total: UGX {total_new_fees:,.2f}')
        self.stdout.write(f'Difference: UGX {total_new_fees - total_old_fees:,.2f}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN - No changes were made'))
            self.stdout.write(self.style.WARNING('Run with --fix to apply these changes'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✓ Updated {changes_made} candidates'))
            self.stdout.write(self.style.SUCCESS(f'New Center Total: UGX {center.get_total_fees_balance():,.2f}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n=== RECALCULATION COMPLETE ==='))

    def calculate_candidate_fees(self, candidate):
        """
        Recalculate fees for a candidate based on their enrollment
        """
        total_fees = 0
        
        if candidate.registration_category == 'Modular':
            # Modular: Based on number of modules enrolled
            module_count = CandidateModule.objects.filter(candidate=candidate).count()
            
            if module_count > 0:
                # Get the level to get fees
                level_enrollment = CandidateLevel.objects.filter(candidate=candidate).first()
                if level_enrollment and level_enrollment.level:
                    level = level_enrollment.level
                    if module_count == 1:
                        total_fees = level.modular_fee_single or 0
                    elif module_count >= 2:
                        total_fees = level.modular_fee_double or 0
        
        elif candidate.registration_category == 'Formal':
            # Formal: Based on level base_fee
            level_enrollments = CandidateLevel.objects.filter(candidate=candidate).select_related('level')
            for level_enrollment in level_enrollments:
                if level_enrollment.level:
                    total_fees += level_enrollment.level.base_fee or 0
        
        elif candidate.registration_category == 'Informal':
            # Informal/Worker's PAS: Based on number of modules × workers_pas_module_fee
            module_count = CandidateModule.objects.filter(candidate=candidate).count()
            
            if module_count > 0:
                # Get the level to get workers_pas_module_fee
                level_enrollment = CandidateLevel.objects.filter(candidate=candidate).first()
                if level_enrollment and level_enrollment.level:
                    level = level_enrollment.level
                    workers_pas_fee = level.workers_pas_module_fee or 0
                    total_fees = workers_pas_fee * module_count
        
        return total_fees
