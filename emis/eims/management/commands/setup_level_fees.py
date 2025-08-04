from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Level, Occupation


class Command(BaseCommand):
    help = 'Set up fees for existing levels in the system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--occupation',
            type=str,
            help='Occupation code to set fees for (optional, if not provided will process all)',
        )
        parser.add_argument(
            '--formal-fee',
            type=float,
            help='Default formal fee (varies by level)',
        )
        parser.add_argument(
            '--workers-pas-fee',
            type=float,
            help='Default Worker\'s PAS fee (flat rate)',
        )
        parser.add_argument(
            '--modular-single',
            type=float,
            help='Default fee for Modular registration with 1 module',
        )
        parser.add_argument(
            '--modular-double',
            type=float,
            help='Default fee for Modular registration with 2 modules',
        )
        parser.add_argument(
            '--interactive',
            action='store_true',
            help='Interactive mode to set fees for each level individually',
        )

    def handle(self, *args, **options):
        occupation_code = options.get('occupation')
        formal_fee = options.get('formal_fee')
        workers_pas_fee = options.get('workers_pas_fee')
        modular_single = options.get('modular_single')
        modular_double = options.get('modular_double')
        interactive = options.get('interactive')

        # Filter levels based on occupation if provided
        if occupation_code:
            try:
                occupation = Occupation.objects.get(code=occupation_code)
                levels = Level.objects.filter(occupation=occupation)
                self.stdout.write(f"Processing levels for occupation: {occupation.name}")
            except Occupation.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Occupation with code '{occupation_code}' not found")
                )
                return
        else:
            levels = Level.objects.all()
            self.stdout.write("Processing all levels in the system")

        if not levels.exists():
            self.stdout.write(self.style.WARNING("No levels found to process"))
            return

        self.stdout.write(f"Found {levels.count()} levels to process")

        if interactive:
            self._interactive_setup(levels)
        else:
            self._batch_setup(levels, formal_fee, workers_pas_fee, modular_single, modular_double)

    def _interactive_setup(self, levels):
        """Interactive mode to set fees for each level individually"""
        self.stdout.write(self.style.SUCCESS("\n=== Interactive Fees Setup ==="))
        
        for level in levels:
            self.stdout.write(f"\n--- Setting fees for: {level.name} ({level.occupation.code}) ---")
            self.stdout.write(f"Current fees:")
            self.stdout.write(f"  Formal Fee: UGX {level.formal_fee}")
            self.stdout.write(f"  Worker's PAS Fee: UGX {level.workers_pas_fee}")
            self.stdout.write(f"  Modular Single: UGX {level.modular_fee_single}")
            self.stdout.write(f"  Modular Double: UGX {level.modular_fee_double}")
            
            # Ask if user wants to update this level
            update = input("\nUpdate this level's fees? (y/n/skip): ").lower()
            if update == 'n':
                continue
            elif update == 'skip':
                break
            
            # Get new fees
            try:
                formal_fee = float(input("Enter Formal Fee (varies by level): ") or level.formal_fee)
                workers_pas_fee = float(input("Enter Worker's PAS Fee (flat rate): ") or level.workers_pas_fee)
                modular_single = float(input("Enter Modular Fee (1 Module): ") or level.modular_fee_single)
                modular_double = float(input("Enter Modular Fee (2 Modules): ") or level.modular_fee_double)
                
                # Update the level
                level.formal_fee = formal_fee
                level.workers_pas_fee = workers_pas_fee
                level.modular_fee_single = modular_single
                level.modular_fee_double = modular_double
                level.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Updated fees for {level.name}")
                )
            except ValueError:
                self.stdout.write(
                    self.style.ERROR("Invalid fee amount. Skipping this level.")
                )
                continue

    def _batch_setup(self, levels, formal_fee, workers_pas_fee, modular_single, modular_double):
        """Batch mode to set the same fees for all levels"""
        if not all([formal_fee, workers_pas_fee, modular_single, modular_double]):
            self.stdout.write(
                self.style.ERROR(
                    "For batch mode, you must provide --formal-fee, --workers-pas-fee, --modular-single, and --modular-double"
                )
            )
            return

        self.stdout.write(f"\n=== Batch Fees Setup ===")
        self.stdout.write(f"Formal Fee: UGX {formal_fee}")
        self.stdout.write(f"Worker's PAS Fee: UGX {workers_pas_fee}")
        self.stdout.write(f"Modular Single: UGX {modular_single}")
        self.stdout.write(f"Modular Double: UGX {modular_double}")
        
        confirm = input(f"\nApply these fees to {levels.count()} levels? (y/n): ")
        if confirm.lower() != 'y':
            self.stdout.write("Operation cancelled")
            return

        with transaction.atomic():
            updated_count = 0
            for level in levels:
                level.formal_fee = formal_fee
                level.workers_pas_fee = workers_pas_fee
                level.modular_fee_single = modular_single
                level.modular_fee_double = modular_double
                level.save()
                updated_count += 1

            self.stdout.write(
                self.style.SUCCESS(f"✓ Successfully updated fees for {updated_count} levels")
            )

        # Update all candidate fees balances
        self.stdout.write("\nUpdating candidate fees balances...")
        from eims.models import Candidate
        
        candidates_updated = 0
        for candidate in Candidate.objects.filter(candidatelevel__isnull=False).distinct():
            candidate.update_fees_balance()
            candidates_updated += 1
        
        self.stdout.write(
            self.style.SUCCESS(f"✓ Updated fees balance for {candidates_updated} candidates")
        )
