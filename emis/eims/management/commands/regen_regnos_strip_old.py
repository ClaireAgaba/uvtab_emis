from django.core.management.base import BaseCommand
from django.db import transaction
from eims.models import Candidate

class Command(BaseCommand):
    help = (
        "Regenerate registration numbers for candidates whose occupation code ends with '-old', "
        "so that '-old' is stripped from the regno according to the new rule. Dry-run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument('--center-number', type=str, help='Optional center filter (e.g., UVT454)')
        parser.add_argument('--occupation-code-like', type=str, default='-old', help="Substring to match in occupation code, default='-old'")
        parser.add_argument('--limit', type=int, help='Process at most N candidates for testing')
        parser.add_argument('--apply', action='store_true', help='Persist changes')

    def handle(self, *args, **opts):
        center_number = opts.get('center_number')
        code_like = opts.get('occupation_code_like') or '-old'
        limit = opts.get('limit')
        apply = opts.get('apply', False)

        qs = Candidate.objects.select_related('assessment_center', 'occupation')
        if center_number:
            qs = qs.filter(assessment_center__center_number=center_number)
        # Occupation code suffix '-old' (case-insensitive)
        qs = qs.filter(occupation__code__iendswith=code_like)
        total = qs.count()
        if limit:
            qs = qs.order_by('id')[:limit]
        ids = list(qs.values_list('id', flat=True))

        self.stdout.write(self.style.WARNING('================== DRY RUN ==================' if not apply else '================== EXECUTION =================='))
        self.stdout.write(f"Candidates matched: {total} | processing now: {len(ids)}")

        changed = 0
        with transaction.atomic():
            for cand in Candidate.objects.filter(id__in=ids).iterator(chunk_size=500):
                old = cand.reg_number
                # Force rebuild using current rules
                cand.build_reg_number()
                new = cand.reg_number
                if new != old:
                    self.stdout.write(f"{cand.id}: {old} -> {new}")
                    changed += 1
                    if apply:
                        cand.save(update_fields=['reg_number'])
            if not apply:
                self.stdout.write(self.style.WARNING('Dry-run complete. Re-run with --apply to persist.'))
        self.stdout.write(self.style.SUCCESS(f"Changed: {changed}"))
