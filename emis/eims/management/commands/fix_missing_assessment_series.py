from django.core.management.base import BaseCommand
from eims.models import Result, AssessmentSeries, Candidate
from django.db.models import Q
from datetime import datetime

class Command(BaseCommand):
    help = 'Identify and fix results that are missing assessment_series'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making actual changes'
        )
        parser.add_argument(
            '--auto-assign',
            action='store_true',
            help='Automatically assign assessment series based on assessment_date'
        )
        parser.add_argument(
            '--candidate-id',
            type=int,
            help='Fix only specific candidate ID'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        auto_assign = options['auto_assign']
        candidate_id = options.get('candidate_id')
        
        # Find results without assessment_series
        query = Q(assessment_series__isnull=True)
        if candidate_id:
            query &= Q(candidate_id=candidate_id)
        
        missing_series_results = Result.objects.filter(query).order_by('candidate', 'assessment_date')
        
        if not missing_series_results.exists():
            self.stdout.write(
                self.style.SUCCESS('No results with missing assessment_series found.')
            )
            return
        
        self.stdout.write(f'Found {missing_series_results.count()} results with missing assessment_series')
        self.stdout.write('')
        
        # Group by candidate for better display
        candidates_with_missing = {}
        for result in missing_series_results:
            if result.candidate not in candidates_with_missing:
                candidates_with_missing[result.candidate] = []
            candidates_with_missing[result.candidate].append(result)
        
        fixed_count = 0
        
        for candidate, results in candidates_with_missing.items():
            self.stdout.write(f'Candidate: {candidate.full_name} (ID: {candidate.id})')
            
            # Check if candidate has an assigned assessment series
            candidate_series = candidate.assessment_series
            if candidate_series:
                self.stdout.write(f'  Candidate assigned series: {candidate_series.name}')
            else:
                self.stdout.write('  Candidate has no assigned assessment series')
            
            for result in results:
                self.stdout.write(
                    f'  Result: {result.assessment_type} {result.mark} '
                    f'(Date: {result.assessment_date}) - Missing assessment_series'
                )
                
                # Determine which assessment series to assign
                suggested_series = None
                assignment_reason = ""
                
                if candidate_series:
                    # Use candidate's assigned series
                    suggested_series = candidate_series
                    assignment_reason = "from candidate's assigned series"
                elif auto_assign and result.assessment_date:
                    # Try to find assessment series that matches the assessment date
                    matching_series = AssessmentSeries.objects.filter(
                        start_date__lte=result.assessment_date,
                        end_date__gte=result.assessment_date
                    ).first()
                    
                    if matching_series:
                        suggested_series = matching_series
                        assignment_reason = f"auto-matched by date ({result.assessment_date})"
                    else:
                        # Find the closest assessment series by date
                        all_series = AssessmentSeries.objects.all().order_by('start_date')
                        closest_series = None
                        min_diff = None
                        
                        for series in all_series:
                            if series.start_date:
                                diff = abs((result.assessment_date - series.start_date).days)
                                if min_diff is None or diff < min_diff:
                                    min_diff = diff
                                    closest_series = series
                        
                        if closest_series:
                            suggested_series = closest_series
                            assignment_reason = f"closest by date (diff: {min_diff} days)"
                
                if suggested_series:
                    self.stdout.write(
                        f'    → Suggested: {suggested_series.name} ({assignment_reason})'
                    )
                    
                    if not dry_run:
                        result.assessment_series = suggested_series
                        result.save()
                        fixed_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'    ✓ Assigned {suggested_series.name}')
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'    [DRY RUN] Would assign {suggested_series.name}')
                        )
                else:
                    self.stdout.write(
                        self.style.ERROR('    ✗ No suitable assessment series found')
                    )
            
            self.stdout.write('')  # Empty line between candidates
        
        # Summary
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would fix {len([r for results in candidates_with_missing.values() for r in results if self._can_fix_result(r, candidates_with_missing)])} results')
            )
            self.stdout.write('Run without --dry-run to apply changes')
            self.stdout.write('Use --auto-assign to enable automatic date-based assignment')
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully fixed {fixed_count} results')
            )
        
        # Show available assessment series for reference
        self.stdout.write('')
        self.stdout.write('Available Assessment Series:')
        for series in AssessmentSeries.objects.all().order_by('-start_date'):
            current_marker = ' (Current)' if series.is_current else ''
            self.stdout.write(f'  - {series.name}: {series.start_date} to {series.end_date}{current_marker}')
    
    def _can_fix_result(self, result, candidates_with_missing):
        """Helper to determine if a result can be fixed"""
        candidate = result.candidate
        return (candidate.assessment_series is not None or 
                (result.assessment_date and AssessmentSeries.objects.exists()))
