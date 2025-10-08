from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from eims.models import AssessmentSeries, Candidate, Result

import csv
from pathlib import Path


class Command(BaseCommand):
    help = (
        "Move candidates and their results from one assessment series to another, "
        "restricted to a single assessment center (by center_number)."
    )

    def add_arguments(self, parser):
        parser.add_argument('--center', required=True, help='Assessment center code (center_number), e.g., UVT794')
        # Preferred: identify series explicitly
        parser.add_argument('--from-series-id', type=int, help='Source AssessmentSeries ID (preferred)')
        parser.add_argument('--to-series-id', type=int, help='Destination AssessmentSeries ID (preferred)')
        parser.add_argument('--from-series-name', help='Source AssessmentSeries name (exact match)')
        parser.add_argument('--to-series-name', help='Destination AssessmentSeries name (exact match)')
        # Legacy fallback: year/month
        parser.add_argument('--from-year', type=int, help='DEPRECATED: Source series year')
        parser.add_argument('--from-month', type=int, help='DEPRECATED: Source series month (1-12)')
        parser.add_argument('--to-year', type=int, help='DEPRECATED: Destination series year')
        parser.add_argument('--to-month', type=int, help='DEPRECATED: Destination series month (1-12)')
        parser.add_argument('--apply', action='store_true', help='Actually perform the move. Without this, runs as a dry-run.')
        parser.add_argument('--log', default='', help='Optional path to write a CSV log of moved records')

    def handle(self, *args, **options):
        center_code = options['center'].strip()
        from_series_id = options.get('from_series_id')
        to_series_id = options.get('to_series_id')
        from_series_name = options.get('from_series_name')
        to_series_name = options.get('to_series_name')
        from_year = options.get('from_year')
        from_month = options.get('from_month')
        to_year = options.get('to_year')
        to_month = options.get('to_month')
        apply_changes = options['apply']
        log_path = options['log'].strip()

        # Locate series objects with robust resolution order
        def resolve_series(series_id, series_name, year, month, label):
            if series_id:
                obj = AssessmentSeries.objects.filter(pk=series_id).first()
                if not obj:
                    raise CommandError(f"{label} series not found by id={series_id}")
                return obj
            if series_name:
                obj = AssessmentSeries.objects.filter(name=series_name).first()
                if not obj:
                    raise CommandError(f"{label} series not found by name='{series_name}'")
                return obj
            if year and month:
                obj = AssessmentSeries.objects.filter(start_date__year=year, start_date__month=month).first()
                if not obj:
                    raise CommandError(f"{label} series not found for {year}-{month}")
                return obj
            raise CommandError(f"{label} series not specified. Provide --{label.lower()}-series-id or --{label.lower()}-series-name (or legacy --{ 'from' if label=='From' else 'to' }-year/--{ 'from' if label=='From' else 'to' }-month)")

        from_series = resolve_series(from_series_id, from_series_name, from_year, from_month, 'From')
        to_series = resolve_series(to_series_id, to_series_name, to_year, to_month, 'To')

        # Candidates strictly in the specified center (any branch under it) and in the from_series
        candidates_qs = Candidate.objects.filter(
            assessment_center__center_number=center_code,
            assessment_series=from_series,
        ).only('id', 'assessment_series', 'assessment_center_id')

        candidate_ids = list(candidates_qs.values_list('id', flat=True))
        total_candidates = len(candidate_ids)

        # Results attached to those candidates and in the from_series
        results_qs = Result.objects.filter(candidate_id__in=candidate_ids, assessment_series=from_series).only('id', 'candidate_id', 'assessment_series_id')
        total_results = results_qs.count()

        self.stdout.write(self.style.NOTICE("=== DRY-RUN SUMMARY ===" if not apply_changes else "=== APPLY SUMMARY ==="))
        self.stdout.write(f"Center: {center_code}")
        self.stdout.write(f"From series: {from_series.name} [id={from_series.id}] ({from_series.start_date:%Y-%m})")
        self.stdout.write(f"To series:   {to_series.name} [id={to_series.id}] ({to_series.start_date:%Y-%m})")
        self.stdout.write(f"Candidates to move: {total_candidates}")
        self.stdout.write(f"Results to move:    {total_results}")

        writer = None
        log_file = None
        if log_path:
            log_file = Path(log_path)
            # Ensure parent directory exists
            if log_file.parent and not log_file.parent.exists():
                log_file.parent.mkdir(parents=True, exist_ok=True)
            fp = log_file.open('w', newline='')
            writer = csv.writer(fp)
            writer.writerow(['timestamp', 'action', 'model', 'id', 'candidate_id', 'from_series', 'to_series'])

        if not apply_changes:
            self.stdout.write(self.style.WARNING("Dry-run complete. Re-run with --apply to make changes."))
            if writer:
                fp.close()
            return

        with transaction.atomic():
            # Update candidates
            updated_cands = candidates_qs.update(assessment_series=to_series)
            # Update results
            updated_results = results_qs.update(assessment_series=to_series)

            ts = timezone.now().isoformat()
            if writer:
                for cid in candidate_ids:
                    writer.writerow([ts, 'update', 'Candidate', cid, cid, from_series.id, to_series.id])
                for rid in results_qs.values_list('id', flat=True):
                    writer.writerow([ts, 'update', 'Result', rid, '', from_series.id, to_series.id])

        if writer:
            fp.close()

        self.stdout.write(self.style.SUCCESS(f"Moved {updated_cands} candidates and {updated_results} results from {from_series.name} -> {to_series.name} for center {center_code}."))
