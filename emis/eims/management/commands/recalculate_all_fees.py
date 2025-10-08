"""
Recalculate fees for ALL candidates with enrollments
This fixes the issue where modular_module_count was not set but candidates have modules
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from decimal import Decimal
from eims.models import Candidate

class Command(BaseCommand):
    help = 'Recalculate fees_balance for all candidates with enrollments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.WARNING('='*80))
        self.stdout.write(self.style.WARNING('RECALCULATING FEES FOR ALL ENROLLED CANDIDATES'))
        self.stdout.write(self.style.WARNING('='*80))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n🔍 DRY RUN MODE\n'))
        
        # Get all candidates with enrollments
        candidates = Candidate.objects.filter(
            Q(candidatelevel__isnull=False) | Q(candidatemodule__isnull=False)
        ).distinct()
        
        total_candidates = candidates.count()
        self.stdout.write(f'\nFound {total_candidates} candidates with enrollments\n')
        
        candidates_changed = 0
        total_fees_added = Decimal('0.00')
        total_fees_reduced = Decimal('0.00')
        
        modular_fixed = []
        formal_fixed = []
        workers_pas_fixed = []
        
        for candidate in candidates:
            old_fee = candidate.fees_balance
            calculated_fee = candidate.calculate_fees_balance()
            
            # Skip if already cleared (payment_cleared = True)
            if hasattr(candidate, 'payment_cleared') and candidate.payment_cleared:
                continue
            
            if abs(old_fee - calculated_fee) > Decimal('0.01'):  # More than 1 cent difference
                candidates_changed += 1
                difference = calculated_fee - old_fee
                
                if difference > 0:
                    total_fees_added += difference
                else:
                    total_fees_reduced += abs(difference)
                
                # Track by registration category
                if candidate.registration_category == 'Modular':
                    modular_fixed.append({
                        'reg': candidate.reg_number,
                        'name': candidate.full_name,
                        'old': old_fee,
                        'new': calculated_fee,
                        'diff': difference
                    })
                elif candidate.registration_category == 'Formal':
                    formal_fixed.append({
                        'reg': candidate.reg_number,
                        'name': candidate.full_name,
                        'old': old_fee,
                        'new': calculated_fee,
                        'diff': difference
                    })
                else:
                    workers_pas_fixed.append({
                        'reg': candidate.reg_number,
                        'name': candidate.full_name,
                        'old': old_fee,
                        'new': calculated_fee,
                        'diff': difference
                    })
                
                if not dry_run:
                    candidate.fees_balance = calculated_fee
                    candidate.save(update_fields=['fees_balance'])
        
        # Report results
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.HTTP_INFO('SUMMARY'))
        self.stdout.write('='*80)
        
        self.stdout.write(f'\nTotal Candidates Checked: {total_candidates}')
        self.stdout.write(f'Candidates with Fee Changes: {candidates_changed}')
        self.stdout.write(f'\nTotal Fees Added: UGX {total_fees_added:,.2f}')
        self.stdout.write(f'Total Fees Reduced: UGX {total_fees_reduced:,.2f}')
        self.stdout.write(f'Net Change: UGX {(total_fees_added - total_fees_reduced):,.2f}')
        
        # Show details by category
        if modular_fixed:
            self.stdout.write(f'\n' + '-'*80)
            self.stdout.write(self.style.HTTP_INFO(f'MODULAR CANDIDATES ({len(modular_fixed)} changed)'))
            self.stdout.write('-'*80)
            for item in modular_fixed[:20]:  # Show first 20
                self.stdout.write(
                    f"  {item['reg']} ({item['name'][:30]}): "
                    f"UGX {item['old']:,.2f} → UGX {item['new']:,.2f} "
                    f"({'+' if item['diff'] > 0 else ''}{item['diff']:,.2f})"
                )
            if len(modular_fixed) > 20:
                self.stdout.write(f"  ... and {len(modular_fixed) - 20} more")
        
        if formal_fixed:
            self.stdout.write(f'\n' + '-'*80)
            self.stdout.write(self.style.HTTP_INFO(f'FORMAL CANDIDATES ({len(formal_fixed)} changed)'))
            self.stdout.write('-'*80)
            for item in formal_fixed[:10]:
                self.stdout.write(
                    f"  {item['reg']} ({item['name'][:30]}): "
                    f"UGX {item['old']:,.2f} → UGX {item['new']:,.2f} "
                    f"({'+' if item['diff'] > 0 else ''}{item['diff']:,.2f})"
                )
            if len(formal_fixed) > 10:
                self.stdout.write(f"  ... and {len(formal_fixed) - 10} more")
        
        if workers_pas_fixed:
            self.stdout.write(f'\n' + '-'*80)
            self.stdout.write(self.style.HTTP_INFO(f"WORKER'S PAS CANDIDATES ({len(workers_pas_fixed)} changed)"))
            self.stdout.write('-'*80)
            for item in workers_pas_fixed[:10]:
                self.stdout.write(
                    f"  {item['reg']} ({item['name'][:30]}): "
                    f"UGX {item['old']:,.2f} → UGX {item['new']:,.2f} "
                    f"({'+' if item['diff'] > 0 else ''}{item['diff']:,.2f})"
                )
            if len(workers_pas_fixed) > 10:
                self.stdout.write(f"  ... and {len(workers_pas_fixed) - 10} more")
        
        self.stdout.write('\n' + '='*80)
        if dry_run:
            self.stdout.write(self.style.NOTICE('✓ DRY RUN COMPLETE - Run without --dry-run to apply changes'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ FEES RECALCULATED SUCCESSFULLY'))
        self.stdout.write('='*80 + '\n')
