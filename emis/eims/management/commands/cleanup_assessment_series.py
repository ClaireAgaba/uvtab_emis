#!/usr/bin/env python3

from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Candidate, AssessmentSeries
import re
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Clean up duplicate assessment series and move candidates to proper series'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(f"{'DRY RUN: ' if dry_run else ''}Cleaning up assessment series...")
        
        # Get all assessment series
        all_series = AssessmentSeries.objects.all().order_by('name')
        
        # Separate proper series (with "Series" in name) from duplicates
        proper_series = {}  # key: normalized name, value: series object
        duplicate_series = []
        
        for series in all_series:
            if 'Series' in series.name:
                # Extract the base name (e.g., "June 2025" from "June 2025 Series")
                base_name = series.name.replace(' Series', '')
                proper_series[base_name.lower()] = series
            else:
                duplicate_series.append(series)
        
        self.stdout.write(f"Found {len(proper_series)} proper series and {len(duplicate_series)} duplicate series")
        
        if dry_run:
            self.stdout.write("\nProper series found:")
            for base_name, series in proper_series.items():
                candidate_count = Candidate.objects.filter(assessment_series=series).count()
                self.stdout.write(f"  {series.name} ({candidate_count} candidates)")
            
            self.stdout.write("\nDuplicate series to be processed:")
            for series in duplicate_series:
                candidate_count = Candidate.objects.filter(assessment_series=series).count()
                self.stdout.write(f"  {series.name} ({candidate_count} candidates)")
        
        # Create mapping from duplicates to proper series
        series_mappings = []
        
        for duplicate in duplicate_series:
            target_series = None
            duplicate_name = duplicate.name.lower()
            
            # Handle special cases first
            if 'may 2020' in duplicate_name:
                # Fix the year error: May 2020 → May 2025
                target_key = 'may 2025'
                if target_key in proper_series:
                    target_series = proper_series[target_key]
                    self.stdout.write(f"  Mapping {duplicate.name} → {target_series.name} (fixing year error)")
            else:
                # Try direct mapping
                if duplicate_name in proper_series:
                    target_series = proper_series[duplicate_name]
                else:
                    # Try fuzzy matching for month/year patterns
                    for proper_key, proper_series_obj in proper_series.items():
                        if self._series_match(duplicate_name, proper_key):
                            target_series = proper_series_obj
                            break
            
            if target_series:
                candidate_count = Candidate.objects.filter(assessment_series=duplicate).count()
                series_mappings.append({
                    'from_series': duplicate,
                    'to_series': target_series,
                    'candidate_count': candidate_count
                })
                
                if not dry_run:
                    self.stdout.write(f"  Will move {candidate_count} candidates: {duplicate.name} → {target_series.name}")
            else:
                candidate_count = Candidate.objects.filter(assessment_series=duplicate).count()
                self.stdout.write(
                    self.style.WARNING(f"  No target found for {duplicate.name} ({candidate_count} candidates)")
                )
        
        if dry_run:
            self.stdout.write(f"\nWould process {len(series_mappings)} series mappings")
            total_candidates = sum(mapping['candidate_count'] for mapping in series_mappings)
            self.stdout.write(f"Would move {total_candidates} candidates total")
            return
        
        # Execute the mappings
        total_moved = 0
        total_series_deleted = 0
        
        for mapping in series_mappings:
            from_series = mapping['from_series']
            to_series = mapping['to_series']
            candidate_count = mapping['candidate_count']
            
            if candidate_count > 0:
                try:
                    with transaction.atomic():
                        # Move all candidates from duplicate to proper series
                        updated = Candidate.objects.filter(
                            assessment_series=from_series
                        ).update(assessment_series=to_series)
                        
                        total_moved += updated
                        self.stdout.write(
                            f"✅ Moved {updated} candidates: {from_series.name} → {to_series.name}"
                        )
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Error moving candidates from {from_series.name}: {e}")
                    )
                    continue
            
            # Delete the duplicate series (only if no candidates left)
            remaining_candidates = Candidate.objects.filter(assessment_series=from_series).count()
            if remaining_candidates == 0:
                try:
                    from_series.delete()
                    total_series_deleted += 1
                    self.stdout.write(f"🗑️  Deleted duplicate series: {from_series.name}")
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Error deleting series {from_series.name}: {e}")
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(f"⚠️  Cannot delete {from_series.name}: {remaining_candidates} candidates still assigned")
                )
        
        # Summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write("CLEANUP SUMMARY")
        self.stdout.write("="*50)
        self.stdout.write(f"Candidates moved: {total_moved}")
        self.stdout.write(f"Duplicate series deleted: {total_series_deleted}")
        
        if total_moved > 0 or total_series_deleted > 0:
            self.stdout.write(self.style.SUCCESS("✅ Assessment series cleanup completed!"))
        else:
            self.stdout.write(self.style.SUCCESS("✅ No cleanup needed - all series are already proper!"))
        
        # Final verification
        remaining_duplicates = AssessmentSeries.objects.exclude(name__icontains='Series').count()
        if remaining_duplicates > 0:
            self.stdout.write(
                self.style.WARNING(f"⚠️  {remaining_duplicates} non-'Series' assessment series still exist")
            )
        else:
            self.stdout.write(self.style.SUCCESS("✅ All assessment series now have 'Series' in their names!"))
    
    def _series_match(self, duplicate_name, proper_key):
        """
        Check if duplicate series name matches proper series key
        Handles variations in formatting and common patterns
        """
        # Normalize both names
        duplicate_clean = re.sub(r'[^a-z0-9\s]', '', duplicate_name.lower())
        proper_clean = re.sub(r'[^a-z0-9\s]', '', proper_key.lower())
        
        # Direct match
        if duplicate_clean == proper_clean:
            return True
        
        # Extract month and year patterns
        duplicate_parts = duplicate_clean.split()
        proper_parts = proper_clean.split()
        
        # If both have 2 parts (month year), compare them
        if len(duplicate_parts) == 2 and len(proper_parts) == 2:
            return duplicate_parts[0] == proper_parts[0] and duplicate_parts[1] == proper_parts[1]
        
        return False
