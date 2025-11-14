"""
Management command to diagnose multi-level billing issues.

This command provides detailed breakdown of candidates by level and calculates
expected fees for centers with multiple levels (Level 1, 2, 3, etc.)

Usage:
    python manage.py diagnose_multilevel_billing UVT847
    python manage.py diagnose_multilevel_billing UVT847 --series "November 2025"
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from decimal import Decimal
from collections import defaultdict
from eims.models import Candidate, CandidateLevel, CandidateModule, AssessmentCenter, Level


class Command(BaseCommand):
    help = 'Diagnose multi-level billing issues for assessment centers'

    def add_arguments(self, parser):
        parser.add_argument(
            'center_number',
            type=str,
            help='Center number to diagnose (e.g., UVT847)',
        )
        parser.add_argument(
            '--series',
            type=str,
            help='Filter by assessment series name',
        )

    def handle(self, *args, **options):
        center_number = options['center_number']
        series_filter = options.get('series')

        self.stdout.write(self.style.WARNING('=' * 100))
        self.stdout.write(self.style.WARNING(f'MULTI-LEVEL BILLING DIAGNOSTIC FOR CENTER: {center_number}'))
        self.stdout.write(self.style.WARNING('=' * 100 + '\n'))

        # Get center
        try:
            center = AssessmentCenter.objects.get(center_number__iexact=center_number)
            self.stdout.write(f"📍 Center: {center.center_name}")
            self.stdout.write(f"   Number: {center.center_number}")
            self.stdout.write(f"   District: {center.district.name if center.district else 'N/A'}\n")
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Center {center_number} not found"))
            return

        # Get all enrolled candidates
        enrolled_candidates = Candidate.objects.filter(
            assessment_center=center
        ).filter(
            Q(candidatelevel__isnull=False) | Q(candidatemodule__isnull=False)
        ).distinct().select_related(
            'occupation',
            'assessment_series'
        ).prefetch_related(
            'candidatelevel_set__level',
            'candidatemodule_set__module__level'
        ).order_by('registration_category', 'reg_number')

        if series_filter:
            enrolled_candidates = enrolled_candidates.filter(
                assessment_series__name__icontains=series_filter
            )
            self.stdout.write(f"📅 Series Filter: {series_filter}\n")

        total_candidates = enrolled_candidates.count()
        self.stdout.write(f"📊 Total Enrolled Candidates: {total_candidates}\n")

        if total_candidates == 0:
            self.stdout.write(self.style.WARNING('⚠️  No enrolled candidates found'))
            return

        # Categorize candidates
        modular_candidates = []
        formal_by_level = defaultdict(list)
        informal_candidates = []

        for candidate in enrolled_candidates:
            reg_cat = (candidate.registration_category or '').lower()
            
            if reg_cat == 'modular':
                modular_candidates.append(candidate)
            elif reg_cat == 'formal':
                # Get enrolled levels for this candidate
                enrolled_levels = candidate.candidatelevel_set.select_related('level').all()
                for cl in enrolled_levels:
                    level_name = cl.level.name if cl.level else 'Unknown'
                    formal_by_level[level_name].append({
                        'candidate': candidate,
                        'level': cl.level,
                        'candidate_level': cl
                    })
            else:
                informal_candidates.append(candidate)

        # ============================================================================
        # MODULAR CANDIDATES ANALYSIS
        # ============================================================================
        if modular_candidates:
            self.stdout.write('\n' + '=' * 100)
            self.stdout.write('MODULAR CANDIDATES')
            self.stdout.write('=' * 100 + '\n')

            total_current = Decimal('0.00')
            total_correct = Decimal('0.00')

            for candidate in modular_candidates:
                module_count = candidate.candidatemodule_set.count()
                current_balance = candidate.fees_balance or Decimal('0.00')
                
                try:
                    correct_fee = candidate.calculate_fees_balance()
                except:
                    correct_fee = Decimal('0.00')

                total_current += current_balance
                total_correct += correct_fee

                status = '✅' if current_balance == correct_fee else '⚠️ '
                self.stdout.write(f"{status} {candidate.reg_number} - {candidate.full_name}")
                self.stdout.write(f"   Modules: {module_count}")
                self.stdout.write(f"   Current: UGX {current_balance:,.2f}")
                self.stdout.write(f"   Correct: UGX {correct_fee:,.2f}")
                
                if current_balance != correct_fee:
                    self.stdout.write(self.style.ERROR(f"   Discrepancy: UGX {(correct_fee - current_balance):,.2f}"))
                self.stdout.write("")

            self.stdout.write(f"{'-' * 100}")
            self.stdout.write(f"MODULAR SUMMARY:")
            self.stdout.write(f"   Count: {len(modular_candidates)}")
            self.stdout.write(f"   Current Total: UGX {total_current:,.2f}")
            self.stdout.write(f"   Correct Total: UGX {total_correct:,.2f}")
            if total_current != total_correct:
                self.stdout.write(self.style.ERROR(f"   DISCREPANCY: UGX {(total_correct - total_current):,.2f}"))

        # ============================================================================
        # FORMAL CANDIDATES BY LEVEL ANALYSIS
        # ============================================================================
        if formal_by_level:
            self.stdout.write('\n' + '=' * 100)
            self.stdout.write('FORMAL CANDIDATES BY LEVEL')
            self.stdout.write('=' * 100 + '\n')

            formal_total_current = Decimal('0.00')
            formal_total_correct = Decimal('0.00')

            # Sort levels numerically
            import re
            def level_sort_key(level_name):
                match = re.search(r'(\d+)', level_name)
                return int(match.group(1)) if match else 999

            sorted_levels = sorted(formal_by_level.keys(), key=level_sort_key)

            for level_name in sorted_levels:
                candidates_data = formal_by_level[level_name]
                
                self.stdout.write(f"\n{'─' * 100}")
                self.stdout.write(f"📚 {level_name.upper()} ({len(candidates_data)} candidates)")
                self.stdout.write(f"{'─' * 100}\n")

                # Get level fee
                if candidates_data and candidates_data[0]['level']:
                    level_obj = candidates_data[0]['level']
                    level_fee = level_obj.formal_fee or Decimal('0.00')
                    self.stdout.write(f"Level Fee: UGX {level_fee:,.2f}\n")
                else:
                    level_fee = Decimal('0.00')

                level_current = Decimal('0.00')
                level_correct = Decimal('0.00')
                level_discrepancy_count = 0

                for data in candidates_data:
                    candidate = data['candidate']
                    current_balance = candidate.fees_balance or Decimal('0.00')
                    
                    try:
                        correct_fee = candidate.calculate_fees_balance()
                    except:
                        correct_fee = level_fee

                    level_current += current_balance
                    level_correct += correct_fee

                    if current_balance != correct_fee:
                        level_discrepancy_count += 1

                    status = '✅' if current_balance == correct_fee else '⚠️ '
                    self.stdout.write(f"{status} {candidate.reg_number} - {candidate.full_name}")
                    self.stdout.write(f"   Current: UGX {current_balance:,.2f}")
                    self.stdout.write(f"   Correct: UGX {correct_fee:,.2f}")
                    
                    if current_balance != correct_fee:
                        self.stdout.write(self.style.ERROR(f"   Discrepancy: UGX {(correct_fee - current_balance):,.2f}"))
                    self.stdout.write("")

                formal_total_current += level_current
                formal_total_correct += level_correct

                # Level summary
                self.stdout.write(f"{'-' * 100}")
                self.stdout.write(f"{level_name.upper()} SUMMARY:")
                self.stdout.write(f"   Candidates: {len(candidates_data)}")
                self.stdout.write(f"   Expected (@ UGX {level_fee:,.2f} each): UGX {(level_fee * len(candidates_data)):,.2f}")
                self.stdout.write(f"   Current Total: UGX {level_current:,.2f}")
                self.stdout.write(f"   Correct Total: UGX {level_correct:,.2f}")
                if level_current != level_correct:
                    self.stdout.write(self.style.ERROR(f"   DISCREPANCY: UGX {(level_correct - level_current):,.2f}"))
                    self.stdout.write(self.style.ERROR(f"   Candidates with issues: {level_discrepancy_count}"))

            # Formal overall summary
            self.stdout.write(f"\n{'=' * 100}")
            self.stdout.write(f"FORMAL OVERALL SUMMARY:")
            self.stdout.write(f"   Total Candidates: {sum(len(v) for v in formal_by_level.values())}")
            self.stdout.write(f"   Current Total: UGX {formal_total_current:,.2f}")
            self.stdout.write(f"   Correct Total: UGX {formal_total_correct:,.2f}")
            if formal_total_current != formal_total_correct:
                self.stdout.write(self.style.ERROR(f"   DISCREPANCY: UGX {(formal_total_correct - formal_total_current):,.2f}"))

        # ============================================================================
        # INFORMAL CANDIDATES ANALYSIS
        # ============================================================================
        if informal_candidates:
            self.stdout.write('\n' + '=' * 100)
            self.stdout.write('INFORMAL/WORKER\'S PAS CANDIDATES')
            self.stdout.write('=' * 100 + '\n')

            informal_current = Decimal('0.00')
            informal_correct = Decimal('0.00')

            for candidate in informal_candidates:
                module_count = candidate.candidatemodule_set.count()
                current_balance = candidate.fees_balance or Decimal('0.00')
                
                try:
                    correct_fee = candidate.calculate_fees_balance()
                except:
                    correct_fee = Decimal('0.00')

                informal_current += current_balance
                informal_correct += correct_fee

                status = '✅' if current_balance == correct_fee else '⚠️ '
                self.stdout.write(f"{status} {candidate.reg_number} - {candidate.full_name}")
                self.stdout.write(f"   Modules: {module_count}")
                self.stdout.write(f"   Current: UGX {current_balance:,.2f}")
                self.stdout.write(f"   Correct: UGX {correct_fee:,.2f}")
                
                if current_balance != correct_fee:
                    self.stdout.write(self.style.ERROR(f"   Discrepancy: UGX {(correct_fee - current_balance):,.2f}"))
                self.stdout.write("")

            self.stdout.write(f"{'-' * 100}")
            self.stdout.write(f"INFORMAL SUMMARY:")
            self.stdout.write(f"   Count: {len(informal_candidates)}")
            self.stdout.write(f"   Current Total: UGX {informal_current:,.2f}")
            self.stdout.write(f"   Correct Total: UGX {informal_correct:,.2f}")
            if informal_current != informal_correct:
                self.stdout.write(self.style.ERROR(f"   DISCREPANCY: UGX {(informal_correct - informal_current):,.2f}"))

        # ============================================================================
        # GRAND TOTAL
        # ============================================================================
        self.stdout.write('\n' + '=' * 100)
        self.stdout.write('GRAND TOTAL SUMMARY')
        self.stdout.write('=' * 100 + '\n')

        grand_current = Decimal('0.00')
        grand_correct = Decimal('0.00')

        for candidate in enrolled_candidates:
            grand_current += (candidate.fees_balance or Decimal('0.00'))
            try:
                grand_correct += candidate.calculate_fees_balance()
            except:
                pass

        self.stdout.write(f"📊 Total Enrolled Candidates: {total_candidates}")
        self.stdout.write(f"   Modular: {len(modular_candidates)}")
        self.stdout.write(f"   Formal: {sum(len(v) for v in formal_by_level.values())}")
        self.stdout.write(f"   Informal: {len(informal_candidates)}")
        
        self.stdout.write(f"\n💰 Current Total Balance: UGX {grand_current:,.2f}")
        self.stdout.write(f"💰 Correct Total Balance: UGX {grand_correct:,.2f}")

        if grand_current != grand_correct:
            discrepancy = grand_correct - grand_current
            self.stdout.write(self.style.ERROR(f"\n⚠️  TOTAL DISCREPANCY: UGX {discrepancy:,.2f}"))
            
            if discrepancy > 0:
                self.stdout.write(self.style.ERROR(f"   Missing fees: UGX {discrepancy:,.2f}"))
            else:
                self.stdout.write(self.style.ERROR(f"   Overcharged: UGX {abs(discrepancy):,.2f}"))

            self.stdout.write(self.style.NOTICE(f"\n💡 To fix these issues, run:"))
            self.stdout.write(self.style.NOTICE(f"   python manage.py fix_modular_billing --center {center_number}"))
            self.stdout.write(self.style.NOTICE(f"   python manage.py harmonize_billing_status --center {center_number}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✅ No billing discrepancies found"))

        self.stdout.write('\n' + '=' * 100 + '\n')
