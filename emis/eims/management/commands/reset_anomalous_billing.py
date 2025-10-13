from django.core.management.base import BaseCommand
from django.db.models import Q, Count
from decimal import Decimal
from eims.models import Candidate
from pathlib import Path
import csv

class Command(BaseCommand):
    help = (
        "Reset billing/payment flags for anomalous candidates: no enrollments but have payment cleared/amount/fees.\n"
        "Dry-run by default. Use --apply to persist. Supports filters and CSV export."
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Persist corrections')
        parser.add_argument('--center', type=int, help='Filter by assessment center id')
        parser.add_argument('--series', type=int, help='Filter by assessment series id')
        parser.add_argument('--category', type=str, help='Filter by registration category (Formal|Modular|Informal)')
        parser.add_argument('--limit', type=int, help='Limit for testing')
        parser.add_argument('--export', type=str, help='Export CSV to this path')

    def handle(self, *args, **opts):
        apply = opts.get('apply')
        center_id = opts.get('center')
        series_id = opts.get('series')
        category = opts.get('category')
        limit = opts.get('limit')
        export = opts.get('export')

        qs = (
            Candidate.objects
            .select_related('assessment_center', 'assessment_series', 'occupation')
            .annotate(level_count=Count('candidatelevel'), module_count=Count('candidatemodule', distinct=True))
        )
        if center_id:
            qs = qs.filter(assessment_center_id=center_id)
        if series_id:
            qs = qs.filter(assessment_series_id=series_id)
        if category:
            qs = qs.filter(registration_category__iexact=category)

        # Anomaly definition: no level/modules AND (payment flags present OR fees_balance>0)
        anomalies = qs.filter(
            Q(level_count=0, module_count=0)
            & (
                Q(payment_cleared=True)
                | Q(payment_amount_cleared__isnull=False)
                | Q(payment_center_series_ref__isnull=False)
                | Q(payment_center_series_ref__gt='')
                | Q(fees_balance__gt=0)
            )
        )
        if limit:
            anomalies = anomalies.order_by('id')[:limit]

        total = anomalies.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No anomalous candidates found.'))
            return

        self.stdout.write(self.style.WARNING(f'Found {total} anomalous candidate(s). apply={apply}'))

        writer = None
        f = None
        if export:
            out_path = Path(export)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            f = out_path.open('w', newline='', encoding='utf-8')
            writer = csv.DictWriter(f, fieldnames=[
                'id','reg_number','name','center','series','category','fees_balance',
                'payment_cleared','payment_amount_cleared','action'
            ])
            writer.writeheader()

        fixed = 0
        for cand in anomalies.iterator(chunk_size=1000):
            action = 'RESET'
            if apply:
                cand.fees_balance = Decimal('0.00')
                cand.payment_cleared = False
                cand.payment_cleared_date = None
                cand.payment_cleared_by = None
                cand.payment_amount_cleared = None
                cand.payment_center_series_ref = None
                cand.save(update_fields=[
                    'fees_balance','payment_cleared','payment_cleared_date','payment_cleared_by','payment_amount_cleared','payment_center_series_ref'
                ])
                fixed += 1
            if writer:
                writer.writerow({
                    'id': cand.id,
                    'reg_number': cand.reg_number or '',
                    'name': cand.full_name,
                    'center': cand.assessment_center.center_name if cand.assessment_center else '',
                    'series': cand.assessment_series.name if cand.assessment_series else '',
                    'category': cand.registration_category,
                    'fees_balance': f"{(cand.fees_balance or Decimal('0.00')):.2f}",
                    'payment_cleared': 'YES' if cand.payment_cleared else 'NO',
                    'payment_amount_cleared': f"{(cand.payment_amount_cleared or Decimal('0.00')):.2f}" if cand.payment_amount_cleared else '',
                    'action': action,
                })

        if f:
            f.close()
            self.stdout.write(self.style.SUCCESS(f'Exported CSV to {export}'))

        if apply:
            self.stdout.write(self.style.SUCCESS(f'Reset {fixed} candidate(s).'))
        else:
            self.stdout.write(self.style.NOTICE('Dry-run only. Use --apply to persist corrections.'))
