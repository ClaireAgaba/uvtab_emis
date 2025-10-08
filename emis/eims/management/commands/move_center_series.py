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
        parser.add_argument('--branch-code', help='Optional: limit to a specific branch_code under the center')
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
        parser.add_argument('--results-any', action='store_true', help='Also move Result.assessment_series for selected candidates regardless of current series (useful when results have NULL or mismatched series).')
        parser.add_argument('--results-null', action='store_true', help='Include results with NULL assessment_series (when --results-any is not set).')
        parser.add_argument('--ignore-from-series', action='store_true', help='Select candidates by center (and optional branch) regardless of their current assessment_series.')
        parser.add_argument('--report', action='store_true', help='In dry-run, print a breakdown by current series for candidates and results.')
        parser.add_argument('--log', default='', help='Optional path to write a CSV log of moved records')

    def handle(self, *args, **options):
        center_code = options['center'].strip()
        branch_code = (options.get('branch_code') or '').strip() or None
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

        # Candidates selection by center/branch; optionally constrained by from_series
        cand_filters = {
            'assessment_center__center_number': center_code,
        }
        if not options['ignore_from_series']:
            cand_filters['assessment_series'] = from_series
        if branch_code:
            cand_filters['assessment_center_branch__branch_code'] = branch_code
        candidates_qs = Candidate.objects.filter(**cand_filters).only('id', 'assessment_series', 'assessment_center_id')

        candidate_ids = list(candidates_qs.values_list('id', flat=True))
        total_candidates = len(candidate_ids)

        # Results attached to those candidates
        if options['results_any']:
            results_qs = Result.objects.filter(candidate_id__in=candidate_ids).only('id', 'candidate_id', 'assessment_series_id')
        else:
            res_filters = {'candidate_id__in': candidate_ids}
            if options['results_null']:
                from django.db.models import Q
                res_q = Q(assessment_series=from_series) | Q(assessment_series__isnull=True)
                results_qs = Result.objects.filter(res_q, **res_filters).only('id', 'candidate_id', 'assessment_series_id')
            else:
                results_qs = Result.objects.filter(assessment_series=from_series, **res_filters).only('id', 'candidate_id', 'assessment_series_id')
        total_results = results_qs.count()

        self.stdout.write(self.style.NOTICE("=== DRY-RUN SUMMARY ===" if not apply_changes else "=== APPLY SUMMARY ==="))
        self.stdout.write(f"Center: {center_code}")
        if branch_code:
            self.stdout.write(f"Branch: {branch_code}")
        self.stdout.write(f"From series: {from_series.name} [id={from_series.id}] ({from_series.start_date:%Y-%m})")
        self.stdout.write(f"To series:   {to_series.name} [id={to_series.id}] ({to_series.start_date:%Y-%m})")
        if options['ignore_from_series']:
            self.stdout.write("Candidate selection is NOT constrained by from-series (ignore-from-series=ON)")
        if options['results_any']:
            self.stdout.write("Results selection: ALL results for selected candidates (results-any=ON)")
        elif options['results_null']:
            self.stdout.write("Results selection: results in from-series OR NULL series (results-null=ON)")
        self.stdout.write(f"Candidates to move: {total_candidates}")
        self.stdout.write(f"Results to move:    {total_results}")

        # Optional breakdown report
        if options['report']:
            from collections import Counter
            cand_series = Counter(
                Candidate.objects.filter(
                    assessment_center__center_number=center_code,
                    **({ 'assessment_center_branch__branch_code': branch_code } if branch_code else {})
                ).values_list('assessment_series_id', flat=True)
            )
            self.stdout.write("Candidate count by current series id:")
            def _sort_key_cand(item):
                sid, cnt = item
                from_id = getattr(from_series, 'id', None)
                # Primary: put from_series id first, then others; treat None as max
                primary = 0 if (sid == from_id) else 1
                secondary = (sid if sid is not None else float('inf'))
                return (primary, secondary)
            for sid, cnt in sorted(cand_series.items(), key=_sort_key_cand):
                self.stdout.write(f"  series_id={sid}: {cnt}")
            res_series = Counter(
                Result.objects.filter(candidate_id__in=candidate_ids).values_list('assessment_series_id', flat=True)
            )
            self.stdout.write("Result count by current series id (for selected candidates):")
            def _sort_key_res(item):
                sid, cnt = item
                from_id = getattr(from_series, 'id', None)
                primary = 0 if (sid == from_id) else 1
                # Use string for stable ordering; None goes last
                secondary = (str(sid) if sid is not None else 'zzzzzz')
                return (primary, secondary)
            for sid, cnt in sorted(res_series.items(), key=_sort_key_res):
                self.stdout.write(f"  series_id={sid}: {cnt}")

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
