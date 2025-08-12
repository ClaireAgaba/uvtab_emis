#!/usr/bin/env python3

from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Result
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fix results with mark = -1 that have blank grade and comment fields'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch (default: 100)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        
        self.stdout.write(f"{'DRY RUN: ' if dry_run else ''}Fixing results with mark = -1 and blank grade/comment...")
        
        # Find all results with mark = -1 but blank grade and comment
        problematic_results = Result.objects.filter(
            mark=-1,
            grade__in=['', None],
            comment__in=['', None]
        ).order_by('id')
        
        total_count = problematic_results.count()
        self.stdout.write(f"Found {total_count} results to fix")
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("No results need fixing!"))
            return
        
        if dry_run:
            self.stdout.write("DRY RUN - showing first 10 records that would be updated:")
            for result in problematic_results[:10]:
                self.stdout.write(
                    f"  ID: {result.id}, Candidate: {result.candidate.reg_number}, "
                    f"Mark: {result.mark}, Grade: '{result.grade}', Comment: '{result.comment}', "
                    f"User: {result.user}, Status: '{result.status}'"
                )
            if total_count > 10:
                self.stdout.write(f"  ... and {total_count - 10} more records")
            return
        
        # Process in batches to avoid memory issues
        updated_count = 0
        batch_start = 0
        
        while batch_start < total_count:
            batch_end = min(batch_start + batch_size, total_count)
            batch_results = problematic_results[batch_start:batch_end]
            
            self.stdout.write(f"Processing batch {batch_start + 1}-{batch_end} of {total_count}...")
            
            try:
                with transaction.atomic():
                    for result in batch_results:
                        # Set grade to "Ms" and comment to "Missing" for mark = -1
                        result.grade = 'Ms'
                        result.comment = 'Missing'
                        result.save(update_fields=['grade', 'comment'])
                        updated_count += 1
                        
                        if updated_count % 50 == 0:
                            self.stdout.write(f"  Updated {updated_count} records...")
                            
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing batch {batch_start + 1}-{batch_end}: {e}")
                )
                continue
            
            batch_start = batch_end
        
        self.stdout.write(
            self.style.SUCCESS(f"Successfully updated {updated_count} results with grade='Ms' and comment='Missing'")
        )
        
        # Verify the fix
        remaining_problematic = Result.objects.filter(
            mark=-1,
            grade__in=['', None],
            comment__in=['', None]
        ).count()
        
        if remaining_problematic == 0:
            self.stdout.write(self.style.SUCCESS("✅ All problematic results have been fixed!"))
        else:
            self.stdout.write(
                self.style.WARNING(f"⚠️  {remaining_problematic} results still need fixing")
            )
