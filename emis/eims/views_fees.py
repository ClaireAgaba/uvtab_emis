from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.db import models
from django.db.models import Q, Count, F, Value, DecimalField, ExpressionWrapper, Subquery, OuterRef
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from django.utils import timezone
import io
import json
from urllib.parse import urlencode

# ReportLab imports for PDF generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from .models import Candidate, AssessmentCenter, Occupation, Level, AssessmentSeries, CenterSeriesPayment, CenterRepresentative, CandidateModule, CandidateLevel
from .views import require_staff_permissions
from django.conf import settings
import os
import re
from zoneinfo import ZoneInfo

@login_required
def uvtab_fees_home(request):
    """
    UVTAB Fees dashboard with Candidate Fees and Center Fees tabs
    """
    # Permissions: Allow Accounts, Admin, IT, Data staff; also allow Center Representatives (scoped)
    allowed_departments = ['Accounts', 'Admin', 'IT', 'Data']
    is_center_rep = request.user.groups.filter(name='CenterRep').exists()
    has_perm, _, _ = require_staff_permissions(request, required_departments=allowed_departments)
    if not has_perm and not is_center_rep and not request.user.is_superuser:
        return HttpResponse('Forbidden', status=403)
    # Calculate comprehensive financial metrics like the center fees list
    # Restrict scope for Center Representatives (center and optional branch)
    user_center = None
    user_branch_id = None
    # Detect center by CenterRepresentative record rather than relying on group membership
    try:
        cr_obj = CenterRepresentative.objects.get(user=request.user)
        user_center = cr_obj.center
        # If this CR account is scoped to a specific branch, capture it
        user_branch_id = getattr(cr_obj, 'assessment_center_branch_id', None)
    except CenterRepresentative.DoesNotExist:
        user_center = None
    
    # Base queryset: ALL billed/enrolled candidates (both paid and unpaid)
    qs = Candidate.objects.filter(
        Q(candidatelevel__isnull=False) |
        Q(registration_category__iexact='modular', modular_module_count__in=[1, 2]) |
        Q(registration_category__iexact='modular', candidatemodule__isnull=False) |
        Q(fees_balance__gt=0) |
        Q(payment_cleared=True)
    )
    if user_center:
        qs = qs.filter(assessment_center=user_center)
    if user_branch_id:
        qs = qs.filter(assessment_center_branch_id=user_branch_id)
    # Only fetch fields we show; pull related foreign keys in one go
    qs = qs.select_related('assessment_center', 'occupation', 'assessment_series').distinct()

    # Filters for redesigned list
    search = (request.GET.get('search') or '').strip()
    center_id = request.GET.get('center') or ''
    series_id = request.GET.get('series') or ''
    category = request.GET.get('category') or ''
    occupation_id = request.GET.get('occupation') or ''
    payment_status = request.GET.get('payment_status') or ''  # paid|not_paid

    if search:
        qs = qs.filter(
            Q(full_name__icontains=search) |
            Q(reg_number__icontains=search) |
            Q(assessment_center__center_name__icontains=search)
        )
    if center_id:
        qs = qs.filter(assessment_center_id=center_id)
    if series_id:
        qs = qs.filter(assessment_series_id=series_id)
    if category:
        qs = qs.filter(registration_category__iexact=category)
    if occupation_id:
        qs = qs.filter(occupation_id=occupation_id)

    # Lightweight annotations for counts and totals (explicit Decimal output)
    qs = qs.annotate(
        module_count=Count('candidatemodule', distinct=True),
        amount_paid=Coalesce(
            F('payment_amount_cleared'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        ),
        fees_out=Coalesce(
            F('fees_balance'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        ),
        # First enrolled level name for the candidate (if any)
        level_name=Subquery(
            CandidateLevel.objects.filter(candidate_id=OuterRef('pk'))
            .order_by('id')
            .values('level__name')[:1]
        ),
    ).annotate(
        total_amount=ExpressionWrapper(
            F('amount_paid') + F('fees_out'),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    )

    # Optional filter by payment status
    if payment_status == 'paid':
        qs = qs.filter(total_amount__gt=0, fees_balance=0)
    elif payment_status == 'not_paid':
        qs = qs.filter(Q(total_amount__gt=0) & ~Q(fees_balance=0) | Q(total_amount=0))

    # Pagination directly on queryset — allow variable page_size
    page_number = request.GET.get('page')
    try:
        page_size = int(request.GET.get('page_size') or 25)
    except ValueError:
        page_size = 25
    if page_size not in [10, 25, 50, 100]:
        page_size = 25
    paginator = Paginator(qs.order_by('-total_amount', '-fees_balance', 'reg_number'), page_size)
    try:
        page_qs = paginator.page(page_number)
    except PageNotAnInteger:
        page_qs = paginator.page(1)
    except EmptyPage:
        page_qs = paginator.page(paginator.num_pages)

    # Build lightweight items for current page
    page_items = []
    for candidate in page_qs.object_list:
        status_label = 'Paid' if (candidate.total_amount or Decimal('0')) > 0 and (candidate.fees_balance or Decimal('0')) == 0 else 'Not Paid'
        # Determine display values
        page_items.append({
            'candidate': candidate,
            'name': candidate.full_name,
            'reg_number': candidate.reg_number,
            'assessment_center': candidate.assessment_center,
            'registration_category': (candidate.registration_category or '').lower(),
            'occupation': candidate.occupation,
            'module_count': getattr(candidate, 'module_count', 0),
            'level_name': getattr(candidate, 'level_name', None),
            'assessment_series': candidate.assessment_series,
            'total_amount': getattr(candidate, 'total_amount', Decimal('0.00')),
            'amount_paid': getattr(candidate, 'amount_paid', Decimal('0.00')),
            'fees_balance': candidate.fees_balance or Decimal('0.00'),
            'payment_status': status_label,
        })
    
    # Calculate current outstanding fees (amount due)
    current_outstanding = qs.aggregate(
        total=models.Sum('fees_balance')
    )['total'] or Decimal('0.00')

    # Authoritative paid total from CenterSeriesPayment for this scope
    # IMPORTANT: Only include payment records for series that actually have candidates
    if user_center:
        paid_qs = CenterSeriesPayment.objects.filter(assessment_center=user_center)
    else:
        paid_qs = CenterSeriesPayment.objects.all()

    # Determine which series are present in the enrolled candidates set
    present_series_ids = list(
        qs.exclude(assessment_series__isnull=True)
        .values_list('assessment_series_id', flat=True).distinct()
    )
    has_none_series = qs.filter(assessment_series__isnull=True).exists()

    if present_series_ids:
        paid_qs = paid_qs.filter(
            models.Q(assessment_series_id__in=present_series_ids) |
            models.Q(assessment_series__isnull=True) if has_none_series else models.Q(assessment_series_id__in=present_series_ids)
        )
    elif has_none_series:
        paid_qs = paid_qs.filter(assessment_series__isnull=True)
    else:
        paid_qs = paid_qs.none()

    # Paid total derived from candidates to avoid double-counting duplicate payment records
    paid_candidates_qs = Candidate.objects.filter(payment_cleared=True)
    if user_center:
        paid_candidates_qs = paid_candidates_qs.filter(assessment_center=user_center)
    if user_branch_id:
        paid_candidates_qs = paid_candidates_qs.filter(assessment_center_branch_id=user_branch_id)
    amount_paid = paid_candidates_qs.aggregate(total=models.Sum('payment_amount_cleared'))['total'] or Decimal('0.00')

    # Summary metrics for dashboard (align with Center Fees + invoices)
    total_fees = (amount_paid or Decimal('0.00')) + (current_outstanding or Decimal('0.00'))
    amount_due = current_outstanding     # Current outstanding amount
    
    # Get centers with highest total fees (top 10) – for CenterRep, only their center
    centers = AssessmentCenter.objects.all()
    if user_center:
        centers = centers.filter(id=user_center.id)
    center_fees_data = []
    
    for center in centers:
        total_fees_center = center.get_total_fees_balance()
        if total_fees_center > 0:
            center_fees_data.append({
                'center': center,
                'total_fees': total_fees_center,
                'enrolled_count': center.get_enrolled_candidates_count()
            })
    
    # Sort centers by total fees (descending) and take top 10
    center_fees_data.sort(key=lambda x: x['total_fees'], reverse=True)
    top_centers = center_fees_data[:10]
    
    # Get fees breakdown by registration category
    fees_by_category = {}
    for category in ['Formal', 'Modular', 'Informal']:
        category_qs = Candidate.objects.filter(
            registration_category=category,
            fees_balance__gt=0
        )
        if user_center:
            category_qs = category_qs.filter(assessment_center=user_center)
        if user_branch_id:
            category_qs = category_qs.filter(assessment_center_branch_id=user_branch_id)
        category_fees = category_qs.aggregate(total=models.Sum('fees_balance'))['total'] or Decimal('0.00')

        category_count_qs = Candidate.objects.filter(
            registration_category=category,
            fees_balance__gt=0
        )
        if user_center:
            category_count_qs = category_count_qs.filter(assessment_center=user_center)
        if user_branch_id:
            category_count_qs = category_count_qs.filter(assessment_center_branch_id=user_branch_id)
        category_count = category_count_qs.count()
        
        fees_by_category[category] = {
            'total_fees': category_fees,
            'count': category_count
        }
    
    # Get fees breakdown by assessment series
    fees_by_series = {}
    assessment_series = AssessmentSeries.objects.all().order_by('-is_current', '-start_date')[:5]  # Top 5 series
    
    for series in assessment_series:
        series_qs = Candidate.objects.filter(
            assessment_series=series,
            fees_balance__gt=0
        )
        if user_center:
            series_qs = series_qs.filter(assessment_center=user_center)
        if user_branch_id:
            series_qs = series_qs.filter(assessment_center_branch_id=user_branch_id)
        series_fees = series_qs.aggregate(total=models.Sum('fees_balance'))['total'] or Decimal('0.00')
        
        series_count_qs = Candidate.objects.filter(
            assessment_series=series,
            fees_balance__gt=0
        )
        if user_center:
            series_count_qs = series_count_qs.filter(assessment_center=user_center)
        if user_branch_id:
            series_count_qs = series_count_qs.filter(assessment_center_branch_id=user_branch_id)
        series_count = series_count_qs.count()
        
        fees_by_series[series.name] = {
            'total_fees': series_fees,
            'count': series_count,
            'is_current': series.is_current
        }
    
    # Options for filters (lightweight)
    centers = AssessmentCenter.objects.all().order_by('center_name')
    occupations = Occupation.objects.all().order_by('name')
    series_opts = AssessmentSeries.objects.all().order_by('-is_current', '-start_date')

    # Build query string without 'page' for pagination links
    qs_params = request.GET.copy()
    qs_params.pop('page', None)
    query_no_page = urlencode([(k, v) for k, v in qs_params.items() if v])

    context = {
        'total_candidates': qs.count(),
        'candidates_with_fees': (Candidate.objects.filter(fees_balance__gt=0, assessment_center=user_center, **({'assessment_center_branch_id': user_branch_id} if user_branch_id else {})).count() if user_center else Candidate.objects.filter(fees_balance__gt=0).count()),
        'total_fees': total_fees,
        'amount_paid': amount_paid,
        'amount_due': amount_due,
        'page_qs': page_qs,           # paginator metadata
        'page_items': page_items,     # optimized rows for current page
        'top_centers': top_centers,
        'fees_by_category': fees_by_category,
        'fees_by_series': fees_by_series,
        # filters echo
        'search': search,
        'center_id': str(center_id),
        'series_id': str(series_id),
        'category': category,
        'occupation_id': str(occupation_id),
        'payment_status_filter': payment_status,
        'page_size': page_size,
        # filter options
        'centers': centers,
        'occupations': occupations,
        'series_opts': series_opts,
        'query_no_page': query_no_page,
        'is_center_rep': is_center_rep,
    }
    
    return render(request, 'fees/uvtab_fees_home.html', context)

@login_required
def candidate_fees_list(request):
    """
    Detailed view of all candidates with fees balances
    """
    # Permissions: same as dashboard
    allowed_departments = ['Accounts', 'Admin', 'IT', 'Data']
    is_center_rep = request.user.groups.filter(name='CenterRep').exists()
    has_perm, _, _ = require_staff_permissions(request, required_departments=allowed_departments)
    if not has_perm and not is_center_rep and not request.user.is_superuser:
        return HttpResponse('Forbidden', status=403)
    # Get all candidates with fees balance > 0
    candidates = Candidate.objects.filter(fees_balance__gt=0).select_related(
        'assessment_center', 'occupation', 'assessment_series'
    ).order_by('-fees_balance')
    # Restrict to CenterRepresentative's center if present
    try:
        cr = CenterRepresentative.objects.get(user=request.user)
        candidates = candidates.filter(assessment_center=cr.center)
        if getattr(cr, 'assessment_center_branch_id', None):
            candidates = candidates.filter(assessment_center_branch_id=cr.assessment_center_branch_id)
    except CenterRepresentative.DoesNotExist:
        pass
    
    # Add search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        candidates = candidates.filter(
            models.Q(full_name__icontains=search_query) |
            models.Q(reg_number__icontains=search_query) |
            models.Q(assessment_center__center_name__icontains=search_query) |
            models.Q(occupation__name__icontains=search_query) |
            models.Q(assessment_series__name__icontains=search_query)
        )
    
    # Add filtering by registration category
    category_filter = request.GET.get('category', '')
    if category_filter:
        candidates = candidates.filter(registration_category=category_filter)
    
    # Add filtering by assessment center
    center_filter = request.GET.get('center', '')
    if center_filter:
        candidates = candidates.filter(assessment_center_id=center_filter)
    
    # Add filtering by assessment series
    series_filter = request.GET.get('series', '')
    if series_filter:
        candidates = candidates.filter(assessment_series_id=series_filter)
    
    # Pagination
    paginator = Paginator(candidates, 25)  # Show 25 candidates per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    centers = AssessmentCenter.objects.all().order_by('center_name')
    # Limit centers dropdown for CenterReps to only their center
    try:
        cr = CenterRepresentative.objects.get(user=request.user)
        centers = centers.filter(id=cr.center_id)
    except CenterRepresentative.DoesNotExist:
        pass
    categories = ['Formal', 'Modular', 'Informal']
    assessment_series = AssessmentSeries.objects.all().order_by('-is_current', '-start_date')
    
    # Calculate total fees for filtered results
    total_fees = candidates.aggregate(total=models.Sum('fees_balance'))['total'] or Decimal('0.00')
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'category_filter': category_filter,
        'center_filter': center_filter,
        'series_filter': series_filter,
        'centers': centers,
        'categories': categories,
        'assessment_series': assessment_series,
        'total_candidates': candidates.count() if not page_obj else paginator.count,
        'total_fees': total_fees,
    }
    
    return render(request, 'fees/candidate_fees_list.html', context)

@login_required
def center_fees_list(request):
    """
    Detailed view of centers with their fees balances per assessment series
    Each center appears as a separate row for each assessment series it has billed candidates in
    Shows ALL billed candidates (both paid and unpaid) for complete financial records
    """
    # Permissions: same as dashboard
    allowed_departments = ['Accounts', 'Admin', 'IT', 'Data']
    is_center_rep = request.user.groups.filter(name='CenterRep').exists()
    has_perm, _, _ = require_staff_permissions(request, required_departments=allowed_departments)
    if not has_perm and not is_center_rep and not request.user.is_superuser:
        return HttpResponse('Forbidden', status=403)
    # Get ALL candidates who have been enrolled (have level enrollment) - this includes both paid and unpaid
    from django.db.models import Q
    
    # Get ALL candidates who have been billed or enrolled (level or modular)
    # CRITICAL: Include payment_cleared=True to count historically cleared/paid candidates
    candidates_with_billing = Candidate.objects.filter(
        (
            Q(candidatelevel__isnull=False) |
            Q(registration_category__iexact='modular', modular_module_count__in=[1, 2]) |
            Q(registration_category__iexact='modular', candidatemodule__isnull=False) |
            Q(fees_balance__gt=0) |
            Q(payment_cleared=True)  # Include historically cleared/paid candidates
        ),
        assessment_center__isnull=False
    )
    try:
        cr = CenterRepresentative.objects.get(user=request.user)
        candidates_with_billing = candidates_with_billing.filter(assessment_center=cr.center)
        if getattr(cr, 'assessment_center_branch_id', None):
            candidates_with_billing = candidates_with_billing.filter(assessment_center_branch_id=cr.assessment_center_branch_id)
    except CenterRepresentative.DoesNotExist:
        pass
    candidates_with_billing = candidates_with_billing.distinct().select_related('assessment_center', 'assessment_series', 'assessment_center__district', 'assessment_center__village')
    
    # Group by center and assessment series
    center_series_data = {}
    for candidate in candidates_with_billing:
        center = candidate.assessment_center
        series = candidate.assessment_series
        
        # Create a unique key for center-series combination
        series_key = series.id if series else 'none'
        key = f"{center.id}_{series_key}"
        
        if key not in center_series_data:
            center_series_data[key] = {
                'center': center,
                'assessment_series': series,
                'candidates': [],
                'total_fees': Decimal('0.00'),
                'candidate_count': 0,
                'enrolled_count': 0,
            }
        
        center_series_data[key]['candidates'].append(candidate)
        # Add current unpaid fees only (fees_balance)
        center_series_data[key]['total_fees'] += candidate.fees_balance
        center_series_data[key]['candidate_count'] += 1
        center_series_data[key]['enrolled_count'] += 1  # All these candidates are enrolled
    
    # Convert to list and calculate payment tracking
    center_fees_data = []
    for key, data in center_series_data.items():
        center = data['center']
        series = data['assessment_series']
        current_outstanding = data['total_fees']  # Current fees balance
        
        # Get payment records for this center-series combination
        try:
            if series:
                payment_record = CenterSeriesPayment.objects.filter(
                    assessment_center=center,
                    assessment_series=series
                ).first()
            else:
                payment_record = CenterSeriesPayment.objects.filter(
                    assessment_center=center,
                    assessment_series__isnull=True
                ).first()
            
            amount_paid = payment_record.amount_paid if payment_record else Decimal('0.00')
        except Exception as e:
            # If CenterSeriesPayment table doesn't exist yet or other error, default to 0
            import logging
            logging.error(f"Error getting payment record for {center.center_name}: {e}")
            amount_paid = Decimal('0.00')
        
        # Calculate the original total amount that was ever billed
        # This includes both current outstanding fees AND amounts that have been paid
        original_total_billed = current_outstanding + amount_paid
        
        # For centers that show 0/0/0, we need to calculate what they were originally billed
        # If we have payment records but no current fees, the original bill was the payment amount
        if original_total_billed == 0 and amount_paid == 0:
            # This center has candidates but no fees - they may have been cleared without proper tracking
            # Calculate what they should have been billed based on their enrolled candidates
            calculated_total = Decimal('0.00')
            for candidate in data['candidates']:
                # Get the candidate's calculated fees (what they should be billed)
                if hasattr(candidate, 'calculate_fees_balance'):
                    try:
                        calculated_fees = candidate.calculate_fees_balance()
                        calculated_total += calculated_fees
                    except:
                        # If calculation fails, use a default or skip
                        pass
            
            # If we calculated a total but current balance is 0, assume it was paid
            if calculated_total > 0 and current_outstanding == 0:
                original_total_billed = calculated_total
                amount_paid = calculated_total  # Assume it was paid
        
        amount_due = current_outstanding  # Current outstanding amount
        
        # Re-compute candidate count using the SAME billing query used by modal/PDF
        # to avoid any edge-case discrepancies from in-memory grouping
        try:
            billing_qs = Candidate.objects.filter(
                assessment_center=center
            ).filter(
                Q(candidatelevel__isnull=False) |
                Q(registration_category__iexact='modular', modular_module_count__in=[1, 2]) |
                Q(registration_category__iexact='modular', candidatemodule__isnull=False) |
                Q(fees_balance__gt=0) |
                Q(payment_cleared=True)
            )
            if series:
                billing_qs = billing_qs.filter(assessment_series=series)
            else:
                billing_qs = billing_qs.filter(assessment_series__isnull=True)
            candidate_count_exact = billing_qs.distinct().count()
        except Exception:
            # Fallback to grouped count if anything goes wrong
            candidate_count_exact = data['candidate_count']

        center_fees_data.append({
            'key': key,
            'center': center,
            'assessment_series': series,
            'candidate_count': candidate_count_exact,
            'enrolled_count': data['enrolled_count'],
            'total_fees': original_total_billed,  # Original amount ever billed
            'amount_paid': amount_paid,   # Amount already paid
            'amount_due': amount_due,     # Current outstanding amount
        })
    
    show_with_fees_only = request.GET.get('with_fees_only', '') == 'true'
    # Note: with_fees_only intentionally not applied to show full billing picture
    
    # Sort by total fees (descending)
    center_fees_data.sort(key=lambda x: x['total_fees'], reverse=True)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(center_fees_data, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate totals
    unique_centers = len({data['center'].id for data in center_fees_data})
    total_system_fees = sum((data['total_fees'] or Decimal('0.00')) for data in center_fees_data)
    
    # Get filter options
    assessment_series = AssessmentSeries.objects.all().order_by('-is_current', '-start_date')
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'series_filter': series_filter,
        'show_with_fees_only': show_with_fees_only,
        'assessment_series': assessment_series,
        'total_centers': unique_centers,
        'total_system_fees': total_system_fees,
        'total_entries': len(center_fees_data),  # Total center-series combinations
        'is_center_rep': request.user.groups.filter(name='CenterRep').exists(),
    }
    
    return render(request, 'fees/center_fees_list.html', context)

@login_required
def center_candidates_report(request, center_id, series_id=None):
    """
    AJAX view to generate invoice data for a specific center and assessment series
    Shows ALL billed candidates (both paid and unpaid) for complete financial records
    """
    # Permissions: same as dashboard
    allowed_departments = ['Accounts', 'Admin', 'IT', 'Data']
    is_center_rep = request.user.groups.filter(name='CenterRep').exists()
    has_perm, _, _ = require_staff_permissions(request, required_departments=allowed_departments)
    if not has_perm and not is_center_rep and not request.user.is_superuser:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    # Access control: CenterRep can only view their own center
    if request.user.groups.filter(name='CenterRep').exists():
        try:
            cr = CenterRepresentative.objects.get(user=request.user)
            if int(center_id) != int(cr.center.id):
                return JsonResponse({'error': 'Forbidden'}, status=403)
        except CenterRepresentative.DoesNotExist:
            return JsonResponse({'error': 'Forbidden'}, status=403)
    try:
        center = AssessmentCenter.objects.get(id=center_id)
    except AssessmentCenter.DoesNotExist:
        return JsonResponse({'error': 'Center not found'}, status=404)
    
    # Get assessment series if provided
    assessment_series = None
    if series_id and series_id != 'none':
        try:
            assessment_series = AssessmentSeries.objects.get(id=series_id)
        except AssessmentSeries.DoesNotExist:
            return JsonResponse({'error': 'Assessment series not found'}, status=404)
    
    try:
        # Get ALL candidates for this center-series combination (both paid and unpaid)
        # Include: level enrollments, modular billed/enrolled, any positive fees_balance, OR paid candidates
        try:
            # Include payment_cleared to capture all paid candidates
            candidates_query = Candidate.objects.filter(
                assessment_center=center
            ).filter(
                Q(candidatelevel__isnull=False) |
                Q(registration_category__iexact='modular', modular_module_count__in=[1, 2]) |
                Q(registration_category__iexact='modular', candidatemodule__isnull=False) |
                Q(fees_balance__gt=0) |
                Q(payment_cleared=True)
            ).distinct().select_related('occupation', 'assessment_series')
        except:
            # Fallback if payment_cleared column doesn't exist
            candidates_query = Candidate.objects.filter(
                assessment_center=center
            ).filter(
                Q(candidatelevel__isnull=False) |
                Q(registration_category__iexact='modular', modular_module_count__in=[1, 2]) |
                Q(registration_category__iexact='modular', candidatemodule__isnull=False) |
                Q(fees_balance__gt=0)
            ).distinct().select_related('occupation', 'assessment_series')
        # If the requesting user is a Branch CenterRep, restrict to their branch
        try:
            cr = CenterRepresentative.objects.get(user=request.user)
            if getattr(cr, 'assessment_center_branch_id', None):
                candidates_query = candidates_query.filter(assessment_center_branch_id=cr.assessment_center_branch_id)
        except CenterRepresentative.DoesNotExist:
            pass
        
        if assessment_series:
            candidates_query = candidates_query.filter(assessment_series=assessment_series)
        elif series_id == 'none':
            candidates_query = candidates_query.filter(assessment_series__isnull=True)
        
        candidates = candidates_query.order_by('reg_number')
        
        # Calculate totals using authoritative data
        total_candidates = candidates.count()
        current_outstanding = sum((c.fees_balance or Decimal('0.00')) for c in candidates)
        # Paid comes from CenterSeriesPayment for this center+series
        try:
            if assessment_series:
                pr = CenterSeriesPayment.objects.filter(
                    assessment_center=center,
                    assessment_series=assessment_series
                ).first()
            else:
                pr = CenterSeriesPayment.objects.filter(
                    assessment_center=center,
                    assessment_series__isnull=True
                ).first()
            amount_paid = pr.amount_paid if pr else Decimal('0.00')
        except Exception:
            amount_paid = Decimal('0.00')
        
        total_bill = (amount_paid or Decimal('0.00')) + (current_outstanding or Decimal('0.00'))
        amount_due = current_outstanding
        
        # Prepare candidate data for invoice
        candidates_data = []
        for candidate in candidates:
            # Determine original billed amount per candidate
            try:
                if hasattr(candidate, 'calculate_fees_balance'):
                    original_fee_local = candidate.calculate_fees_balance()
                    if (original_fee_local or Decimal('0.00')) <= 0 and (candidate.fees_balance or Decimal('0.00')) > 0:
                        original_fee_local = candidate.fees_balance
                else:
                    original_fee_local = candidate.fees_balance
            except Exception:
                original_fee_local = candidate.fees_balance

            # Determine payment status
            payment_status = 'paid' if candidate.fees_balance == 0 and float(original_fee_local) > 0 else 'unpaid'
            
            candidates_data.append({
                'reg_number': candidate.reg_number,
                'full_name': candidate.full_name,
                'occupation': candidate.occupation.name if candidate.occupation else 'N/A',
                'registration_category': candidate.registration_category or 'N/A',
                'fees_balance': float(candidate.fees_balance),  # Current balance
                'original_fee': float(original_fee_local),  # Original billed
                'payment_status': payment_status,
            })
        
        # Generate invoice number
        if assessment_series:
            series_code = ''.join(c for c in assessment_series.name if c.isalnum())[:10]
        else:
            series_code = 'NONE'
        invoice_number = f"{center.center_number}-{series_code}-{total_candidates:03d}"
        
        # Use East Africa Time for generated date/time in response
        ea_now = timezone.localtime(timezone.now(), ZoneInfo('Africa/Kampala'))
        response_data = {
            'center': {
                'id': center.id,
                'center_name': center.center_name,
                'center_number': center.center_number,
                'district': center.district.name if center.district else 'N/A',
                'village': center.village.name if center.village else 'N/A',
            },
            'assessment_series': {
                'id': assessment_series.id if assessment_series else None,
                'name': assessment_series.name if assessment_series else 'No series assigned',
                'is_current': assessment_series.is_current if assessment_series else False,
            },
            'summary': {
                'total_candidates': total_candidates,
                'total_bill': float(total_bill),  # Total amount ever billed
                'amount_paid': float(amount_paid),  # Amount already paid
                'amount_due': float(amount_due),    # Current outstanding amount
            },
            'candidates': candidates_data,
            'invoice_number': invoice_number,
            'generated_date': ea_now.strftime('%B %d, %Y'),
            'generated_time': ea_now.strftime('%I:%M %p'),
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        # Return detailed error for debugging
        import traceback
        error_details = {
            'error': f'Invoice generation failed: {str(e)}',
            'traceback': traceback.format_exc(),
            'center_id': center_id,
            'series_id': series_id
        }
        return JsonResponse(error_details, status=500)

@login_required
def generate_pdf_invoice(request, center_id, series_id=None):
    """
    Generate PDF invoice for download with proper filename format:
    assessmentcenter_assessmentseries_invoice.pdf (e.g., uvt001_may2025_invoice.pdf)
    """
    # Permissions: same as dashboard
    allowed_departments = ['Accounts', 'Admin', 'IT', 'Data']
    is_center_rep = request.user.groups.filter(name='CenterRep').exists()
    has_perm, _, _ = require_staff_permissions(request, required_departments=allowed_departments)
    if not has_perm and not is_center_rep and not request.user.is_superuser:
        return HttpResponse('Forbidden', status=403)
    try:
        center = AssessmentCenter.objects.get(id=center_id)
    except AssessmentCenter.DoesNotExist:
        return HttpResponse('Center not found', status=404)
    
    # Get assessment series if provided
    assessment_series = None
    if series_id and series_id != 'none':
        try:
            assessment_series = AssessmentSeries.objects.get(id=series_id)
        except AssessmentSeries.DoesNotExist:
            return HttpResponse('Assessment series not found', status=404)
    
    # Get invoice type (summary or detailed)
    invoice_type = request.GET.get('type', 'summary')
    
    # Get ALL candidates for this center-series combination (both paid and unpaid)
    # Use the same logic as the audit command - include enrolled AND paid candidates
    try:
        # Include payment_cleared to capture all paid candidates
        candidates_query = Candidate.objects.filter(
            assessment_center=center
        ).filter(
            Q(candidatelevel__isnull=False) |
            Q(registration_category__iexact='modular', modular_module_count__in=[1, 2]) |
            Q(registration_category__iexact='modular', candidatemodule__isnull=False) |
            Q(fees_balance__gt=0) |
            Q(payment_cleared=True)
        ).distinct().select_related('occupation', 'assessment_series')
    except:
        # Fallback if payment_cleared column doesn't exist
        candidates_query = Candidate.objects.filter(
            assessment_center=center
        ).filter(
            Q(candidatelevel__isnull=False) |
            Q(registration_category__iexact='modular', modular_module_count__in=[1, 2]) |
            Q(registration_category__iexact='modular', candidatemodule__isnull=False) |
            Q(fees_balance__gt=0)
        ).distinct().select_related('occupation', 'assessment_series')
    
    if assessment_series:
        candidates_query = candidates_query.filter(assessment_series=assessment_series)
    elif series_id == 'none':
        candidates_query = candidates_query.filter(assessment_series__isnull=True)
    
    candidates = candidates_query.order_by('reg_number')
    
    # Authoritative totals for PDF:
    # - total_candidates: count of candidates in billing set
    # - current_outstanding: sum of current fees_balance
    # - amount_paid: CenterSeriesPayment.amount_paid for this center+series
    # - total_bill = amount_paid + current_outstanding
    total_candidates = candidates.count()
    current_outstanding = sum((c.fees_balance or Decimal('0.00')) for c in candidates)
    try:
        if assessment_series:
            pr = CenterSeriesPayment.objects.filter(
                assessment_center=center,
                assessment_series=assessment_series
            ).first()
        else:
            pr = CenterSeriesPayment.objects.filter(
                assessment_center=center,
                assessment_series__isnull=True
            ).first()
        amount_paid = pr.amount_paid if pr else Decimal('0.00')
    except Exception:
        amount_paid = Decimal('0.00')
    total_bill = (amount_paid or Decimal('0.00')) + (current_outstanding or Decimal('0.00'))
    amount_due = current_outstanding
    
    # Registration category breakdown (counts and current outstanding per category)
    modular_candidates = []
    formal_candidates = []
    workers_candidates = []
    for c in candidates:
        cat = (c.registration_category or '').strip().lower()
        if cat == 'modular':
            modular_candidates.append(c)
        elif cat == 'formal':
            formal_candidates.append(c)
        else:
            # Treat remaining categories as Worker's PAS/Informal for summary purposes
            workers_candidates.append(c)
    
    modular_count = len(modular_candidates)
    formal_count = len(formal_candidates)
    workers_count = len(workers_candidates)
    modular_due = sum((c.fees_balance or Decimal('0.00')) for c in modular_candidates)
    formal_due = sum((c.fees_balance or Decimal('0.00')) for c in formal_candidates)
    workers_due = sum((c.fees_balance or Decimal('0.00')) for c in workers_candidates)
    
    # Prepare candidate data for invoice
    candidates_data = []
    for candidate in candidates:
        # Determine payment status
        payment_status = 'paid' if candidate.fees_balance == 0 and total_bill > 0 else 'unpaid'
        
        candidates_data.append({
            'reg_number': candidate.reg_number,
            'full_name': candidate.full_name,
            'occupation': candidate.occupation.name if candidate.occupation else 'N/A',
            'registration_category': candidate.registration_category or 'N/A',
            'fees_balance': float(candidate.fees_balance),  # Current balance
            'original_fee': float(candidate.fees_balance),  # Simplified for now
            'payment_status': payment_status,
        })
    
    # Generate filename components
    center_code = center.center_number.lower().replace(' ', '')
    if assessment_series:
        # Create a simple code from the series name (remove spaces and special characters)
        series_code = ''.join(c for c in assessment_series.name if c.isalnum()).lower()[:15]
    else:
        series_code = 'noseries'
    
    # Create filename: assessmentcenter_assessmentseries_invoice.pdf
    filename = f"{center_code}_{series_code}_invoice.pdf"
    
    # Generate invoice number for display
    if assessment_series:
        series_code = ''.join(c for c in assessment_series.name if c.isalnum())[:10]
    else:
        series_code = 'NONE'
    invoice_number = f"{center.center_number}-{series_code.upper()}-{total_candidates:03d}"
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    buffer = io.BytesIO()
    # Use landscape for detailed invoices to prevent column clipping (e.g., long Reg. Numbers)
    page_size = landscape(A4) if (request.GET.get('type', 'summary') == 'detailed') else A4
    doc = SimpleDocTemplate(buffer, pagesize=page_size, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    elements = []
    
    # UVTAB Header with Logo (consistent with Albums)
    contact_style = ParagraphStyle('ContactInfo', parent=styles['Normal'], fontSize=9, leading=11)
    board_title_style = ParagraphStyle('BoardTitle', parent=styles['h1'], fontSize=14, alignment=TA_CENTER, spaceBefore=6, spaceAfter=6, textColor=colors.HexColor('#000000'))
    
    # Resolve logo path across common locations
    logo_path = None
    possible_paths = [
        # Legacy filename with space
        os.path.join(settings.BASE_DIR, 'eims', 'static', 'images', 'uvtab logo.png'),
        os.path.join(settings.BASE_DIR, 'static', 'images', 'uvtab logo.png'),
        os.path.join(settings.BASE_DIR, 'emis', 'static', 'images', 'uvtab logo.png'),
        os.path.join(settings.STATIC_ROOT or '', 'images', 'uvtab logo.png'),
        # New filename with underscore
        os.path.join(settings.BASE_DIR, 'eims', 'static', 'images', 'uvtab_logo.png'),
        os.path.join(settings.BASE_DIR, 'emis', 'eims', 'static', 'images', 'uvtab_logo.png'),
        os.path.join(settings.BASE_DIR, 'emis', 'static', 'images', 'uvtab_logo.png'),
        os.path.join(settings.BASE_DIR, 'static', 'images', 'uvtab_logo.png'),
        os.path.join(settings.STATIC_ROOT or '', 'images', 'uvtab_logo.png'),
    ]
    for path in possible_paths:
        if path and os.path.exists(path):
            logo_path = path
            break
    logo_image = Image(logo_path, width=1*inch, height=1*inch) if logo_path else Paragraph(" ", styles['Normal'])

    # Header table: contact | logo | phone
    header_table_data = [
        [Paragraph("P.O.Box 1499<br/>Email: info@uvtab.go.ug", contact_style), 
         logo_image, 
         Paragraph("Tel: 256 414 289786", contact_style)]
    ]
    header_table = Table(header_table_data, colWidths=[2.5*inch, 2*inch, 2.5*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
        ('ALIGN', (2,0), (2,0), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 6))

    # Board Title below the contact+logo row
    elements.append(Paragraph("UGANDA VOCATIONAL AND TECHNICAL ASSESSMENT BOARD (UVTAB)", board_title_style))
    address_style = ParagraphStyle('Address', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, spaceAfter=12)
    elements.append(Paragraph("P.O.Box 1499, Plot 7, Valley Drive, Ntinda-Kyambogo Road<br/>Kampala, Uganda | +256 414 289786 | info@uvtab.go.ug", address_style))
    elements.append(Spacer(1, 6))
    
    # Invoice Title
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading2'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.HexColor('#dc2626')
    )
    title = Paragraph(f'<b>CENTER INVOICE: {invoice_number}</b>', title_style)
    elements.append(title)
    elements.append(Spacer(1, 15))
    
    # Center and Series Information
    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=10
    )
    
    # Safely handle missing village/district to avoid runtime errors
    village_name = center.village.name if getattr(center, 'village', None) else 'N/A'
    district_name = center.district.name if getattr(center, 'district', None) else 'N/A'
    center_info = Paragraph(
        f'<b>Center Details:</b><br/>'
        f'Center No.: {center.center_number}<br/>'
        f'Center Name: {center.center_name}<br/>'
        f'Location: {village_name}, {district_name}, Uganda',
        info_style
    )
    elements.append(center_info)
    
    series_name = assessment_series.name if assessment_series else 'No series assigned'
    series_info = Paragraph(f'<b>Assessment Series:</b> {series_name}', info_style)
    elements.append(series_info)
    # UVTAB Bank Account Information (requested addition)
    bank_style = ParagraphStyle(
        'BankInfo',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=8
    )
    bank_info = Paragraph(
        '<b>Payment Details:</b> UVTAB Account <b>9030026294419</b> at <b>Stanbic Bank, Metro Branch</b>.',
        bank_style
    )
    elements.append(bank_info)
    elements.append(Spacer(1, 12))
    
    # Summary Table
    summary_data = [
        ['Description', 'Amount (UGX)'],
        ['Number of Candidates', f'{total_candidates:,}'],
    ]
    # Insert category breakdown in requested order: Modular, Formal, Worker's PAS
    if modular_count:
        summary_data.append([f'Modular — {modular_count} candidate(s)', f'{float(modular_due):,.2f}'])
    if formal_count:
        summary_data.append([f'Formal — {formal_count} candidate(s)', f'{float(formal_due):,.2f}'])
    if workers_count:
        summary_data.append([f"Worker's PAS — {workers_count} candidate(s)", f'{float(workers_due):,.2f}'])
    # Totals
    summary_data.extend([
        ['Total Bill', f'{float(total_bill):,.2f}'],
        ['Amount Paid', f'{float(amount_paid):,.2f}'],
        ['Amount Due', f'{float(amount_due):,.2f}']
    ])
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fef3c7')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black)
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    # Subheader style for section titles within detailed invoices
    subheader_style = ParagraphStyle(
        'SubHeader',
        parent=styles['Heading4'],
        fontSize=11,
        leading=13,
        textColor=colors.HexColor('#1f2937'),
        spaceBefore=6,
        spaceAfter=6
    )
    
    # Detailed Candidates Tables split by category (only for detailed invoices)
    if invoice_type == 'detailed' and candidates:
        elements.append(Paragraph('<b>Candidate Details</b>', styles['Heading3']))
        elements.append(Spacer(1, 10))

        def short(txt, n):
            if not txt:
                return 'N/A'
            return txt if len(txt) <= n else txt[:n] + '...'

        def get_level_name(c):
            name = 'N/A'
            try:
                cl = c.candidatelevel_set.first()
                if cl and getattr(cl, 'level', None):
                    name = cl.level.name
            except Exception:
                name = 'N/A'
            return name

        def level_order(c):
            import re as _re
            lvl = get_level_name(c)
            m = _re.search(r'(\d+)', lvl or '')
            return int(m.group(1)) if m else 999

        def is_workers_pas(c):
            try:
                cat = c.occupation.category.name if c.occupation and c.occupation.category else ''
            except Exception:
                cat = ''
            return re.search(r"worker('?s)?\s*pas", cat, flags=re.I) is not None

        modular = []
        formal = []
        workers = []
        for c in candidates:
            regcat = (getattr(c, 'registration_category', '') or '').lower()
            if regcat == 'modular':
                modular.append(c)
            elif is_workers_pas(c):
                workers.append(c)
            else:
                formal.append(c)

        # Modular Candidates Details
        if modular:
            elements.append(Paragraph('Modular Candidates Details', subheader_style))
            elements.append(Spacer(1, 6))
            mod_data = [['Reg. Number', 'Name', 'Occupation', 'No. of Modules', 'Billed (UGX)', 'Paid (UGX)', 'Due (UGX)', 'Specify Modules Candidate Trained In']]
            for c in modular:
                try:
                    mods_qs = CandidateModule.objects.filter(candidate=c).select_related('module')
                    num_mods = mods_qs.count()
                except Exception:
                    num_mods = getattr(c, 'modular_module_count', 0) or 0
                # Original billed per candidate
                try:
                    billed = c.calculate_fees_balance() if hasattr(c, 'calculate_fees_balance') else Decimal('0.00')
                    if (billed or Decimal('0.00')) <= 0 and (c.fees_balance or Decimal('0.00')) > 0:
                        billed = c.fees_balance
                except Exception:
                    billed = c.fees_balance or Decimal('0.00')
                # Paid/due per candidate
                paid = getattr(c, 'payment_amount_cleared', None) or (billed if getattr(c, 'payment_cleared', False) else Decimal('0.00'))
                due = c.fees_balance or Decimal('0.00')
                try:
                    mods_str = ', '.join(m.module.name for m in mods_qs) if num_mods else ''
                except Exception:
                    mods_str = ''
                mod_data.append([
                    c.reg_number,
                    short(c.full_name, 25),
                    short(c.occupation.name if c.occupation else 'N/A', 20),
                    str(num_mods),
                    f'{float(billed):,.2f}',
                    f'{float(paid):,.2f}',
                    f'{float(due):,.2f}',
                    short(mods_str, 60)
                ])
            # Landscape width budget ~9.69in (A4 landscape minus default left/right margins). Keep <= 9.6in
            # Widen Reg. Number and reduce right-most column slightly
            mod_table = Table(mod_data, colWidths=[1.6*inch, 1.8*inch, 1.4*inch, 0.7*inch, 1.0*inch, 1.0*inch, 1.0*inch, 1.7*inch])
            mod_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),  # Reg. Number left-align for readability
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),  # Name left-align
                ('LEFTPADDING', (0,0), (-1,-1), 3),
                ('RIGHTPADDING', (0,0), (-1,-1), 3),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('REPEATROWS', (0,0), (-1,0)),
            ]))
            elements.append(mod_table)
            elements.append(Spacer(1, 14))

        # Formal Candidates Details (sorted by level order)
        if formal:
            elements.append(Paragraph('Formal Candidates Details', subheader_style))
            elements.append(Spacer(1, 6))
            formal_sorted = sorted(formal, key=level_order)
            for_data = [['Reg. Number', 'Name', 'Occupation', 'Level', 'Billed (UGX)', 'Paid (UGX)', 'Due (UGX)']]
            for c in formal_sorted:
                try:
                    billed_f = c.calculate_fees_balance() if hasattr(c, 'calculate_fees_balance') else Decimal('0.00')
                    if (billed_f or Decimal('0.00')) <= 0 and (c.fees_balance or Decimal('0.00')) > 0:
                        billed_f = c.fees_balance
                except Exception:
                    billed_f = c.fees_balance or Decimal('0.00')
                paid_f = getattr(c, 'payment_amount_cleared', None) or (billed_f if getattr(c, 'payment_cleared', False) else Decimal('0.00'))
                due_f = c.fees_balance or Decimal('0.00')
                for_data.append([
                    c.reg_number,
                    short(c.full_name, 25),
                    short(c.occupation.name if c.occupation else 'N/A', 20),
                    get_level_name(c),
                    f'{float(billed_f):,.2f}',
                    f'{float(paid_f):,.2f}',
                    f'{float(due_f):,.2f}'
                ])
            for_table = Table(for_data, colWidths=[1.6*inch, 1.8*inch, 1.5*inch, 0.9*inch, 1.0*inch, 1.0*inch, 1.0*inch])
            for_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('LEFTPADDING', (0,0), (-1,-1), 3),
                ('RIGHTPADDING', (0,0), (-1,-1), 3),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('REPEATROWS', (0,0), (-1,0)),
            ]))
            elements.append(for_table)
            elements.append(Spacer(1, 14))

        # Worker's PAS Candidates Details
        if workers:
            elements.append(Paragraph("Worker's PAS Candidates Details", subheader_style))
            elements.append(Spacer(1, 6))
            pas_data = [['Reg. Number', 'Name', 'Occupation', 'Level', 'Billed (UGX)', 'Paid (UGX)', 'Due (UGX)', 'Modules Candidate Is Enrolled In']]
            for c in workers:
                try:
                    mods = CandidateModule.objects.filter(candidate=c).select_related('module')
                    mods_str = ', '.join(short(m.module.name, 18) for m in mods) if mods else ''
                except Exception:
                    mods_str = ''
                try:
                    billed_w = c.calculate_fees_balance() if hasattr(c, 'calculate_fees_balance') else Decimal('0.00')
                    if (billed_w or Decimal('0.00')) <= 0 and (c.fees_balance or Decimal('0.00')) > 0:
                        billed_w = c.fees_balance
                except Exception:
                    billed_w = c.fees_balance or Decimal('0.00')
                paid_w = getattr(c, 'payment_amount_cleared', None) or (billed_w if getattr(c, 'payment_cleared', False) else Decimal('0.00'))
                due_w = c.fees_balance or Decimal('0.00')
                pas_data.append([
                    c.reg_number,
                    short(c.full_name, 25),
                    short(c.occupation.name if c.occupation else 'N/A', 20),
                    get_level_name(c),
                    f'{float(billed_w):,.2f}',
                    f'{float(paid_w):,.2f}',
                    f'{float(due_w):,.2f}',
                    mods_str
                ])
            pas_table = Table(pas_data, colWidths=[1.6*inch, 1.8*inch, 1.5*inch, 0.9*inch, 1.0*inch, 1.0*inch, 1.0*inch, 1.7*inch])
            pas_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('LEFTPADDING', (0,0), (-1,-1), 3),
                ('RIGHTPADDING', (0,0), (-1,-1), 3),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('REPEATROWS', (0,0), (-1,0)),
            ]))
            elements.append(pas_table)
            elements.append(Spacer(1, 20))
    
    # Footer
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#6b7280')
    )
    
    # Use East Africa Time (Africa/Kampala) for the footer timestamp
    current_time = timezone.localtime(timezone.now(), ZoneInfo('Africa/Kampala'))
    footer_text = f'Generated on {current_time.strftime("%B %d, %Y")} at {current_time.strftime("%I:%M %p")}<br/>' \
                  f'UVTAB EIMS - Education Information Management System'
    footer = Paragraph(footer_text, footer_style)
    elements.append(footer)
    
    # Build PDF
    doc.build(elements)
    
    # Return PDF
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

@login_required
@require_POST
def mark_centers_as_paid(request):
    """
    Mark specific center-series combinations as paid
    This only affects the selected center-series combination, not all series for that center
    """
    # Permissions: Restrict to Accounts and Admin only (can process payments)
    processor_departments = ['Accounts', 'Admin']
    has_perm, _, _ = require_staff_permissions(request, required_departments=processor_departments)
    if not has_perm and not request.user.is_superuser:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    try:
        data = json.loads(request.body)
        center_series_ids = data.get('center_series_ids', [])
        
        if not center_series_ids:
            return JsonResponse({'error': 'No centers selected'}, status=400)
        
        updated_centers = []
        total_amount_processed = Decimal('0.00')
        
        for center_series_id in center_series_ids:
            # Parse center_id and series_id from the combined ID
            parts = center_series_id.split('_')
            center_id = parts[0]
            series_id = parts[1] if len(parts) > 1 and parts[1] != 'none' else None
            
            try:
                center = AssessmentCenter.objects.get(id=center_id)
            except AssessmentCenter.DoesNotExist:
                continue
            
            # Get assessment series if provided
            assessment_series = None
            if series_id and series_id != 'none':
                try:
                    assessment_series = AssessmentSeries.objects.get(id=series_id)
                except AssessmentSeries.DoesNotExist:
                    continue
            
            # Get ONLY candidates for this SPECIFIC center-series combination with fees > 0
            candidates_query = Candidate.objects.filter(
                assessment_center=center,
                fees_balance__gt=0
            )
            
            # CRITICAL: Filter by the specific assessment series
            if assessment_series:
                candidates_query = candidates_query.filter(assessment_series=assessment_series)
            elif series_id == 'none':
                candidates_query = candidates_query.filter(assessment_series__isnull=True)
            
            candidates = candidates_query.all()
            
            # Calculate total amount for this SPECIFIC center-series combination
            total_fees = sum(candidate.fees_balance for candidate in candidates)
            
            if total_fees > 0:
                # Clear fees ONLY for candidates in this specific center-series combination
                # AND set payment tracking flags for audit trail
                payment_ref = f"{center_id}_{series_id if series_id else 'none'}"
                for candidate in candidates:
                    # Store the amount being cleared for this candidate (for audit trail)
                    amount_being_cleared = candidate.fees_balance
                    
                    # Clear the fees balance
                    candidate.fees_balance = Decimal('0.00')
                    
                    # Set payment tracking flags - CRITICAL for preventing anomalies
                    candidate.payment_cleared = True
                    candidate.payment_cleared_date = timezone.now()
                    candidate.payment_cleared_by = request.user
                    candidate.payment_amount_cleared = amount_being_cleared
                    candidate.payment_center_series_ref = payment_ref
                    
                    candidate.save()
                
                # Create or update CenterSeriesPayment record to track this payment
                payment_record, created = CenterSeriesPayment.objects.get_or_create(
                    assessment_center=center,
                    assessment_series=assessment_series,
                    defaults={
                        'amount_paid': total_fees,
                        'paid_by': request.user
                    }
                )
                
                if not created:
                    # If record exists, add to the existing amount
                    payment_record.amount_paid += total_fees
                    payment_record.paid_by = request.user
                    payment_record.save()
                
                total_amount_processed += total_fees
                updated_centers.append({
                    'center_id': center_id,
                    'center_name': center.center_name,
                    'series_id': series_id,
                    'series_name': assessment_series.name if assessment_series else 'No series assigned',
                    'amount_processed': float(total_fees)
                })
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully processed payments for {len(updated_centers)} center-series combinations',
            'total_amount': float(total_amount_processed),
            'updated_centers': updated_centers
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
