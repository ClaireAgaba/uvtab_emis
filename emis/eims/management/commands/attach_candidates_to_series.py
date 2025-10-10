from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Candidate, AssessmentCenter, AssessmentSeries


class Command(BaseCommand):
    help = 'Attach candidates from UVT746 Brandom Vocational Skills Center to October 2025 Series'

    def add_arguments(self, parser):
        parser.add_argument(
            '--center-number',
            type=str,
            default='UVT746',
            help='Center number (default: UVT746)'
        )
        parser.add_argument(
            '--series-name',
            type=str,
            default='October 2025 Series',
            help='Assessment series name (default: October 2025 Series)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them'
        )

    def handle(self, *args, **options):
        center_number = options['center_number']
        series_name = options['series_name']
        dry_run = options['dry_run']

        self.stdout.write(self.style.WARNING(f'\n{"="*80}'))
        self.stdout.write(self.style.WARNING('ATTACH CANDIDATES TO ASSESSMENT SERIES'))
        self.stdout.write(self.style.WARNING(f'{"="*80}\n'))

        # Find the assessment center
        try:
            center = AssessmentCenter.objects.get(center_number=center_number)
            self.stdout.write(self.style.SUCCESS(f'✓ Found center: {center.center_name} ({center.center_number})'))
        except AssessmentCenter.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'✗ Center {center_number} not found!'))
            return

        # Find the assessment series
        try:
            series = AssessmentSeries.objects.get(name=series_name)
            self.stdout.write(self.style.SUCCESS(f'✓ Found series: {series.name}'))
            self.stdout.write(self.style.SUCCESS(f'  Start: {series.start_date}, End: {series.end_date}'))
        except AssessmentSeries.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'✗ Assessment series "{series_name}" not found!'))
            self.stdout.write(self.style.WARNING('\nAvailable series:'))
            for s in AssessmentSeries.objects.all().order_by('-start_date'):
                self.stdout.write(f'  - {s.name}')
            return

        # Find candidates without assessment series at this center
        candidates_without_series = Candidate.objects.filter(
            assessment_center=center,
            assessment_series__isnull=True
        ).select_related('occupation')

        total_count = candidates_without_series.count()
        
        self.stdout.write(self.style.WARNING(f'\n{"="*80}'))
        self.stdout.write(self.style.WARNING(f'Found {total_count} candidates without assessment series'))
        self.stdout.write(self.style.WARNING(f'{"="*80}\n'))

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('No candidates need to be updated. All candidates have assessment series attached.'))
            return

        # Display candidate details
        self.stdout.write(self.style.WARNING('Candidates to be updated:\n'))
        for idx, candidate in enumerate(candidates_without_series[:10], 1):
            self.stdout.write(
                f'{idx}. {candidate.reg_number} - {candidate.full_name} '
                f'({candidate.registration_category}) - {candidate.occupation.name if candidate.occupation else "No occupation"}'
            )
        
        if total_count > 10:
            self.stdout.write(f'... and {total_count - 10} more candidates')

        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n[DRY RUN] Would update {total_count} candidates'))
            self.stdout.write(self.style.WARNING('Run without --dry-run to apply changes'))
            return

        # Confirm before updating
        self.stdout.write(self.style.WARNING(f'\nAbout to update {total_count} candidates'))
        confirm = input('Type "yes" to proceed: ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('Operation cancelled'))
            return

        # Update candidates with the assessment series
        with transaction.atomic():
            updated_count = 0
            for candidate in candidates_without_series:
                candidate.assessment_series = series
                candidate.save(update_fields=['assessment_series', 'updated_at'])
                updated_count += 1
                
                if updated_count % 10 == 0:
                    self.stdout.write(f'Updated {updated_count}/{total_count} candidates...', ending='\r')

        self.stdout.write(self.style.SUCCESS(f'\n\n✓ Successfully updated {updated_count} candidates!'))
        self.stdout.write(self.style.SUCCESS(f'All candidates from {center.center_name} are now attached to {series.name}'))
        
        # Verify the update
        remaining = Candidate.objects.filter(
            assessment_center=center,
            assessment_series__isnull=True
        ).count()
        
        if remaining > 0:
            self.stdout.write(self.style.WARNING(f'\nWarning: {remaining} candidates still have no assessment series'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ All candidates at this center now have an assessment series attached'))
