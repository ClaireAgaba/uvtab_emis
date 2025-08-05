from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from django.contrib.auth.decorators import login_required
from reportlab.platypus import Image as RLImage
import calendar
import logging
from django.db.models import Count
from .models import Candidate, Occupation, AssessmentCenter, Result
from .models import SupportStaff
from .forms import SupportStaffForm
from .models import Staff
from .forms import StaffForm
from .forms import CenterRepForm
from .models import AssessmentSeries
from .forms import AssessmentSeriesForm
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from collections import Counter

@login_required
def staff_list(request):
    """List all staff members with their departments"""
    staff_members = Staff.objects.select_related('user').all()
    return render(request, 'users/staff/list_staff.html', {'staff_members': staff_members})

@login_required
def staff_create(request):
    """Create a new staff member with department assignment"""
    if request.method == 'POST':
        print(f"[DEBUG] POST data: {request.POST}")
        form = StaffForm(request.POST)
        print(f"[DEBUG] Form is_valid: {form.is_valid()}")
        
        if not form.is_valid():
            print(f"[DEBUG] Form errors: {form.errors}")
            print(f"[DEBUG] Form non_field_errors: {form.non_field_errors()}")
            
        if form.is_valid():
            try:
                print("[DEBUG] Form is valid, attempting to save...")
                staff = form.save(commit=False)
                print(f"[DEBUG] Staff object created: {staff}")
                staff.created_by = request.user
                staff.updated_by = request.user
                staff.save()
                print(f"[DEBUG] Staff saved successfully: {staff.id}")
                messages.success(request, f'Staff member {staff.name} created successfully!')
                return redirect('staff_list')
            except Exception as e:
                print(f"[DEBUG] Exception during save: {e}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Error creating staff: {e}')
    else:
        form = StaffForm()
    return render(request, 'users/staff/create_staff.html', {'form': form})
@login_required
def staff_detail(request, pk):
    """View staff member details"""
    staff = get_object_or_404(Staff, pk=pk)
    return render(request, 'users/staff/view_staff.html', {'staff': staff})

@login_required
def staff_edit(request, pk):
    """Edit staff member details and department"""
    staff = get_object_or_404(Staff, pk=pk)
    if request.method == 'POST':
        form = StaffForm(request.POST, instance=staff)
        if form.is_valid():
            staff_obj = form.save(commit=False)
            staff_obj.updated_by = request.user
            staff_obj.save()
            messages.success(request, f'Staff member {staff.name} updated successfully!')
            return redirect('staff_detail', pk=staff.pk)
    else:
        form = StaffForm(instance=staff)
    return render(request, 'users/staff/edit_staff.html', {'form': form, 'staff': staff})

def get_user_department_modules(user):
    """Get modules accessible to user based on their staff department"""
    try:
        staff = Staff.objects.get(user=user)  # Changed from SupportStaff to Staff
        department = staff.department
        
        if department == 'Research':
            return {
                'assessment_centers': {'access': 'create_edit', 'name': 'Assessment Centers'},
                'occupations': {'access': 'view_only', 'name': 'Occupations'},
                'statistics': {'access': 'view_only', 'name': 'Statistics'},
            }
        elif department == 'Data':
            return {
                'candidates': {'access': 'full_access', 'name': 'Candidates'},
                'results': {'access': 'full_access', 'name': 'Results'},
                'reports': {'access': 'full_access', 'name': 'Reports'},
            }
    except Staff.DoesNotExist:  # Changed from SupportStaff to Staff
        pass
    
    return {}

@login_required
def generate_result_list(request):
    months = [
        {"value": "1", "name": "January"},
        {"value": "2", "name": "February"},
        {"value": "3", "name": "March"},
        {"value": "4", "name": "April"},
        {"value": "5", "name": "May"},
        {"value": "6", "name": "June"},
        {"value": "7", "name": "July"},
        {"value": "8", "name": "August"},
        {"value": "9", "name": "September"},
        {"value": "10", "name": "October"},
        {"value": "11", "name": "November"},
        {"value": "12", "name": "December"},
    ]
    years = ["2021", "2022", "2023", "2024", "2025"]

    if request.method == 'POST':
        # Get form data
        month = request.POST.get('assessment_month')
        year = request.POST.get('assessment_year')
        regcat = request.POST.get('registration_category')
        occupation_id = request.POST.get('occupation')
        level_id = request.POST.get('level')
        center_id = request.POST.get('assessment_center')
        # Validate required fields
        errors = []
        if not (month and year and regcat and occupation_id):
            errors.append('Please fill in all required fields.')
        from datetime import datetime
        from .models import Candidate, Result, Occupation, Level
        candidates = []
        result_data = []
        papers_list = []
        if not errors:
            # Build assessment period filter
            period_start = datetime(int(year), int(month), 1)
            period_end = datetime(int(year), int(month), 28)  # crude, will catch all results in month
            # Filter candidates for occupation, level, center
            filters = {
                'occupation_id': occupation_id,
                'registration_category__iexact': regcat,
            }
            # For paper-based, fetch all papers for occupation/level
            structure_type = 'modules'
            if regcat.lower() == 'formal' and occupation_id and level_id:
                from .models import OccupationLevel, Paper
                occ_level = OccupationLevel.objects.filter(occupation_id=occupation_id, level_id=level_id).first()
                if occ_level:
                    structure_type = occ_level.structure_type
                if structure_type == 'papers':
                    papers = Paper.objects.filter(occupation_id=occupation_id, level_id=level_id)
                    papers_list = [{'code': p.code, 'name': p.name, 'type': p.get_grade_type_display()} for p in papers]
                    print(f'[DEBUG] Papers for occupation_id={occupation_id}, level_id={level_id}: {papers_list}')
            if center_id:
                filters['assessment_center_id'] = center_id
            if level_id:
                filters['candidatelevel__level_id'] = level_id
                from .models import CandidateLevel
                candidate_levels = CandidateLevel.objects.filter(level_id=level_id)
                print(f'[DEBUG] CandidateLevel entries for level_id={level_id}: ' + str([{"candidate_id": cl.candidate_id, "level_id": cl.level_id} for cl in candidate_levels]))
                # Print all candidates for this level with their registration_category and occupation_id
                from .models import Candidate
                candidate_ids = [cl.candidate_id for cl in candidate_levels]
                debug_candidates = Candidate.objects.filter(id__in=candidate_ids)
                for c in debug_candidates:
                    print(f'[DEBUG] Candidate id={c.id}, reg_number={c.reg_number}, full_name={c.full_name}, occupation_id={c.occupation_id}, registration_category={c.registration_category}')
            qs = Candidate.objects.filter(**filters).distinct()
            print(f'[DEBUG] Candidate queryset count: {qs.count()}')
            print(f'[DEBUG] Candidate IDs in queryset: {list(qs.values_list("id", flat=True))}')
            print(f'[DEBUG] Candidate filter values: occupation_id={occupation_id}, regcat={regcat}, level_id={level_id}, center_id={center_id}')
            # Only keep candidates with at least one result in period
            for cand in qs:
                print(f'[DEBUG] Processing candidate: id={cand.id}, regno={cand.reg_number}, name={cand.full_name}, center={getattr(cand.assessment_center, "center_name", None)}')
                regcat_lower = regcat.lower()
                if regcat_lower == 'modular':
                    results = Result.objects.filter(
                        candidate=cand,
                        assessment_date__year=year,
                        assessment_date__month=month,
                        result_type='modular',
                    )
                    print(f'[DEBUG] Filtering results for candidate {cand.reg_number} (modular): year={year}, month={month}, result_type=modular')
                elif regcat_lower == 'formal':
                    # Determine structure type for occupation/level
                    structure_type = 'modules'
                    if occupation_id and level_id:
                        from .models import OccupationLevel
                        occ_level = OccupationLevel.objects.filter(occupation_id=occupation_id, level_id=level_id).first()
                        if occ_level:
                            structure_type = occ_level.structure_type
                    if structure_type == 'papers':
                        # Paper-based: fetch paper results
                        results = Result.objects.filter(
                            candidate=cand,
                            assessment_date__year=year,
                            assessment_date__month=month,
                            result_type='formal',
                            paper__isnull=False
                        )
                        print(f'[DEBUG] Filtering results for candidate {cand.reg_number} (formal, papers): year={year}, month={month}, result_type=formal, structure_type=papers')
                    else:
                        # Module-based: keep old logic
                        results = Result.objects.filter(
                            candidate=cand,
                            assessment_date__year=year,
                            assessment_date__month=month,
                            result_type='formal',
                        )
                        print(f'[DEBUG] Filtering results for candidate {cand.reg_number} (formal, modules): year={year}, month={month}, result_type=formal, structure_type=modules')
                elif regcat_lower in ['informal', "worker's pas", "workers pas"]:
                    results = Result.objects.filter(
                        candidate=cand,
                        assessment_date__year=year,
                        assessment_date__month=month,
                        result_type='informal',
                    )
                    print(f'[DEBUG] Filtering results for candidate {cand.reg_number} (informal): year={year}, month={month}, result_type=informal')
                else:
                    results = Result.objects.none()
                print(f'[DEBUG] Results found for candidate {cand.reg_number}: {results.count()}')
                if results.exists():
                    candidates.append(cand)
                    # Serialize candidate fields needed by template
                    cand_dict = {
                        'id': cand.id,  # Add id field for module grouping
                        'reg_number': cand.reg_number,
                        'full_name': cand.full_name,
                        'gender': cand.get_gender_display(),
                        'passport_photo_with_regno': cand.passport_photo_with_regno.url if cand.passport_photo_with_regno else None,
                        'passport_photo': cand.passport_photo.url if cand.passport_photo else None,
                        'assessment_center': getattr(cand.assessment_center, 'center_name', None),
                    }
                    # Serialize results fields needed by template
                    results_list = []
                    if regcat_lower == 'formal' and 'structure_type' in locals() and structure_type == 'papers':
                        for r in results:
                            results_list.append({
                                'grade': r.grade,
                                'comment': r.comment,
                                'assessment_type': getattr(r, 'assessment_type', ''),
                                'paper_code': r.paper.code if r.paper else '',
                                'paper_name': r.paper.name if r.paper else '',
                                'paper_type': r.paper.get_grade_type_display() if r.paper else '',
                                'mark': r.mark,
                                'date': r.assessment_date,
                                'status': getattr(r, 'status', ''),
                                'user': getattr(r, 'user', ''),
                            })
                    else:
                        for r in results:
                            results_list.append({
                                'grade': r.grade,
                                'comment': r.comment,
                                'assessment_type': getattr(r, 'assessment_type', ''),
                                'module_code': getattr(r, 'module_code', ''),
                                'module_name': getattr(r, 'module_name', ''),
                                'mark': r.mark,
                                'date': r.assessment_date,
                                'status': getattr(r, 'status', ''),
                                'user': getattr(r, 'user', ''),
                            })
                    is_successful = any(r['comment'] == 'Successful' for r in results_list)
                    result_data.append({
                        'candidate': cand_dict,
                        'results': results_list,
                        'successful': is_successful,
                    })
        # Get occupation and level names for display
        occupation_name = None
        level_name = None
        if occupation_id:
            try:
                occ = Occupation.objects.filter(id=int(occupation_id)).first()
                if occ:
                    occupation_name = occ.name
            except Exception:
                occupation_name = None
        if level_id:
            try:
                print(f"DEBUG: level_id received: {level_id}")
                lvl = Level.objects.filter(id=int(level_id)).first()
                if lvl:
                    level_name = lvl.name
                else:
                    pass
            except Exception as e:
                level_name = None
        else:
            pass
        # Format month as "June, 2025"
        import calendar
        formatted_period = f"{calendar.month_name[int(month)]}, {year}"
        
        # For modular category, group by modules instead of centers (DISABLED - restoring original functionality)
        # Enable module grouping for modular category
        module_result_data = None
        if regcat.lower() == 'modular':
            from collections import defaultdict
            from .models import CandidateModule, Module
            module_result_data = defaultdict(list)
            
            # Get all results for modular category
            modular_results = Result.objects.filter(
                candidate__occupation_id=occupation_id,
                assessment_date__year=year,
                assessment_date__month=month,
                result_type='modular',
            )
            if level_id:
                modular_results = modular_results.filter(candidate__candidatelevel__level=level_id)
            if center_id:
                modular_results = modular_results.filter(candidate__assessment_center=center_id)
            
            # Process all results to group by module
            for result in modular_results:
                candidate = result.candidate
                candidate_id = candidate.id
                
                # Get all modules this candidate is enrolled in
                candidate_modules = CandidateModule.objects.filter(candidate_id=candidate_id).select_related('module')
                
                for cm in candidate_modules:
                    module = cm.module
                    module_key = f"{module.code} - {module.name}"
                    
                    # Check if this result belongs to this module
                    if hasattr(result, 'module') and result.module == module:
                        # Create candidate entry for this module
                        candidate_entry = {
                            'id': candidate.id,
                            'reg_number': candidate.reg_number,
                            'full_name': candidate.full_name,
                            'gender': candidate.get_gender_display(),
                            'assessment_center': getattr(candidate.assessment_center, 'center_name', None),
                        }
                        
                        # Add result data
                        result_entry = {
                            'candidate': candidate_entry,
                            'results': [{
                                'grade': result.grade,
                                'comment': result.comment,
                                'mark': result.mark,
                            }],
                            'successful': result.comment != 'CTR',
                        }
                        
                        module_result_data[module_key].append(result_entry)
            
            # Convert to regular dict
            module_result_data = dict(module_result_data)
                    # Enable module and paper grouping for informal category
        informal_module_data = None
        if regcat.lower() in ['informal', "worker's pas", "workers pas"] and result_data:
            from collections import defaultdict
            from .models import Module, Paper
            informal_module_data = defaultdict(lambda: defaultdict(lambda: {'papers': [], 'candidates': []}))
            
            # Get all modules for this level to ensure we show all modules even if no results
            if level_id and occupation_id:
                all_modules = Module.objects.filter(occupation_id=occupation_id, level_id=level_id)
                for module in all_modules:
                    module_key = f"{module.code} - {module.name}"
                    # Get all papers for this module
                    module_papers = Paper.objects.filter(module=module)
                    # Initialize for all centers that have candidates
                    centers_with_candidates = set(entry['candidate']['assessment_center'] for entry in result_data)
                    for center_name in centers_with_candidates:
                        informal_module_data[center_name][module_key]['papers'] = [{
                            'code': p.code,
                            'name': p.name,
                            'id': p.id
                        } for p in module_papers]
            
            # Process all results to group by center, then by module
            processed_candidates = set()
            for entry in result_data:
                candidate = entry['candidate']
                candidate_id = candidate['id']
                center_name = candidate['assessment_center'] or 'Unknown Center'
                
                # Get all results for this candidate
                candidate_results = Result.objects.filter(
                    candidate_id=candidate_id,
                    assessment_date__year=year,
                    assessment_date__month=month,
                    result_type='informal',
                ).select_related('module', 'paper')
                
                for result in candidate_results:
                    if result.module:
                        module = result.module
                        module_key = f"{module.code} - {module.name}"
                        
                        # Check if we already processed this candidate for this module in this center
                        candidate_module_key = f"{candidate_id}_{module.id}_{center_name}"
                        if candidate_module_key not in processed_candidates:
                            processed_candidates.add(candidate_module_key)
                            
                            # Create candidate entry for this module in this center
                            candidate_entry = {
                                'id': candidate['id'],
                                'reg_number': candidate['reg_number'],
                                'full_name': candidate['full_name'],
                                'gender': candidate['gender'],
                                'passport_photo_with_regno': candidate['passport_photo_with_regno'],
                                'passport_photo': candidate['passport_photo'],
                                'assessment_center': candidate['assessment_center'],
                            }
                            
                            # Get all results for this candidate in this module
                            candidate_module_results = candidate_results.filter(module=module)
                            
                            # Create paper results mapping
                            paper_results = {}
                            for r in candidate_module_results:
                                if r.paper:
                                    paper_results[r.paper.id] = {
                                        'grade': r.grade,
                                        'comment': r.comment,
                                        'mark': r.mark,
                                    }
                            
                            candidate_entry['paper_results'] = paper_results
                            candidate_entry['has_ctr'] = any(r.comment == 'CTR' for r in candidate_module_results)
                            
                            informal_module_data[center_name][module_key]['candidates'].append(candidate_entry)
            
            # Convert to regular dict
            informal_module_data = dict(informal_module_data)
            for center_name in informal_module_data:
                informal_module_data[center_name] = dict(informal_module_data[center_name])



        # Group by center if all centers (for non-modular or when no module grouping)
        centered_result_data = None
        if not center_id:
            from collections import defaultdict
            centered_result_data = defaultdict(list)
            for entry in result_data:
                center_name = entry['candidate'].get('assessment_center', 'No Center')
                centered_result_data[center_name].append(entry)
        # Always include occupations, levels, centers for dropdowns
        from .models import AssessmentCenter
        occupations = Occupation.objects.all()
        levels = Level.objects.all()
        centers = AssessmentCenter.objects.all()
        print(f'[DEBUG] centered_result_data: {centered_result_data}')
        print(f'[DEBUG] informal_module_data: {informal_module_data}')

        context = {
            'months': months,
            'years': years,
            'preview': True,
            'form_data': {
                'month': month,
                'year': year,
                'regcat': regcat,
                'occupation_id': occupation_id,
                'occupation_name': occupation_name,
                'level_id': level_id,
                'level_name': level_name,
                'center_id': center_id,
            },
            'candidates': candidates,
            'result_data': result_data,
            'data': result_data,  # Template expects 'data' variable
            'centered_result_data': dict(centered_result_data) if centered_result_data else None,
            'module_result_data': dict(module_result_data) if module_result_data else None,
            'informal_module_data': informal_module_data,
            'formatted_period': formatted_period,
            'logo_path': '/static/images/uvtab_logo.png',
            'errors': errors,
            'occupations': occupations,
            'levels': levels,
            'centers': centers,
            'papers_list': papers_list,
        }
        return render(request, 'reports/result_list.html', context)
    else:
        # GET: show form only
        from .models import AssessmentCenter, Occupation, Level
        occupations = Occupation.objects.all()
        levels = Level.objects.all()
        centers = AssessmentCenter.objects.all()
        context = {
            'preview': False,
            'form_data': {},
            'candidates': [],
            'result_data': [],
            'centered_result_data': None,
            'formatted_period': '',
            'logo_path': '/static/images/uvtab_logo.png',
            'errors': [],
            'occupations': occupations,
            'levels': levels,
            'centers': centers,
            'months': months,
            'years': years,
        }
        return render(request, 'reports/result_list.html', context)
        return render(request, 'reports/result_list.html', context)


@login_required
def results_home(request):
    logger = logging.getLogger(__name__)
    logger.info(f'Results home accessed by user: {request.user}')
    
    # Get filter parameters
    reg_number = request.GET.get('reg_number', '').strip()
    name = request.GET.get('name', '').strip()
    registration_category = request.GET.get('registration_category', '').strip()
    
    # Fetch enrolled candidates with their marks status
    from django.db.models import Q
    from django.core.paginator import Paginator
    
    enrolled_candidates = Candidate.objects.filter(
        status='Active'
    ).filter(
        Q(candidatelevel__isnull=False) | Q(candidatemodule__isnull=False)
    ).distinct().select_related('occupation', 'assessment_center')
    
    # Apply filters
    if reg_number:
        enrolled_candidates = enrolled_candidates.filter(reg_number__icontains=reg_number)
    if name:
        enrolled_candidates = enrolled_candidates.filter(full_name__icontains=name)
    if registration_category:
        enrolled_candidates = enrolled_candidates.filter(registration_category=registration_category)
    
    enrolled_candidates = enrolled_candidates.order_by('reg_number')
    
    # Pagination: 50 per page
    paginator = Paginator(enrolled_candidates, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Add upload status annotation
    candidates_with_status = []
    for candidate in page_obj.object_list:
        # Check if candidate has any results/marks
        has_marks = Result.objects.filter(candidate=candidate).exists()
        
        candidates_with_status.append({
            'candidate': candidate,
            'upload_status': 'Uploaded' if has_marks else 'Not Uploaded'
        })
    
    # Get registration categories for filter dropdown
    reg_categories = [
        ('Formal', 'Formal'),
        ('Modular', 'Modular'),
        ('Informal', "Worker's PAS")
    ]
    
    return render(request, 'results/home.html', {
        'candidates_with_status': candidates_with_status,
        'page_obj': page_obj,
        'paginator': paginator,
        'reg_categories': reg_categories,
        'filters': {
            'reg_number': reg_number,
            'name': name,
            'registration_category': registration_category,
        }
    })

from django.views.decorators.http import require_POST
from django.http import JsonResponse
from openpyxl import Workbook
from openpyxl import load_workbook
from io import BytesIO
from .models import Candidate, Module, Paper, Level, Occupation, CandidateLevel, CandidateModule, CandidatePaper, Result
import datetime


@login_required
@require_POST
def upload_marks(request):
    """
    Bulk upload candidate marks from Excel for all registration categories.
    Expects POST with Excel file and selection params (occupation, level, registration_category, etc).
    """
    
    errors = []
    updated = 0
    file = request.FILES.get('marks_file') or request.FILES.get('excel_file')
    regcat = request.POST.get('registration_category')
    occupation_id = request.POST.get('occupation')
    level_id = request.POST.get('level')
    center_id = request.POST.get('assessment_center')
    modules_param = request.POST.get('modules')
    assessment_month = request.POST.get('assessment_month')
    assessment_year = request.POST.get('assessment_year')
    print(assessment_month)
    print(assessment_year)
    # Normalize registration category
    regcat_normalized = regcat.strip().lower() if regcat else ''
    if regcat_normalized in ["workers_pas", "worker's pas"]:
        regcat_normalized = "informal"
    try:
        wb = load_workbook(file)
        ws = wb.active
    except Exception as e:
        print('Excel file load error:', e)
        return JsonResponse({'success': False, 'error': 'Invalid Excel file.'})
    import re
    def normalize_header(h):
        return re.sub(r'[^a-z0-9]', '', h.strip().lower())
    headers = [str(cell.value).strip() if cell.value else '' for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    normalized_headers = {normalize_header(h): h for h in headers}
    regno_header = None
    for candidate in ['regnumber', 'registrationno', 'registrationnumber', 'regno']:
        if candidate in normalized_headers:
            regno_header = normalized_headers[candidate]
            break
    if not regno_header:
        return JsonResponse({'success': False, 'error': 'Missing registration number (reg_number) column in Excel. Please use a marksheet generated by the system.'})

    # Get occupation, level, center
    occupation = Occupation.objects.filter(pk=occupation_id).first() if occupation_id else None
    level = Level.objects.filter(pk=level_id).first() if level_id else None
    # Determine structure_type
    structure_type = None
    from .models import OccupationLevel
    occ_level = None
    if occupation and level:
        occ_level = OccupationLevel.objects.filter(occupation=occupation, level=level).first()
        if occ_level:
            structure_type = occ_level.structure_type
    # Determine which modules/papers are in the Excel
    code_to_obj = {}
    # Modular: use selected module and 'PRACTICAL' column
    if regcat_normalized == 'modular':
        selected_module_id = modules_param
        selected_module = Module.objects.filter(pk=selected_module_id).first() if selected_module_id else None
    # Formal module-based: use 'THEORY' and 'PRACTICAL' columns
    # Paper-based/informal: use paper codes as columns
    if regcat_normalized in ['formal', 'informal', 'modular']:
        papers = Paper.objects.filter(occupation=occupation, level=level)
        for p in papers:
            code_to_obj[p.code] = p
        modules = Module.objects.filter(occupation=occupation, level=level)
        for m in modules:
            code_to_obj[m.code] = m
    # For each row, update results
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        row_data = dict(zip(headers, row))
        print(f"[DEBUG] Row {idx} raw data: {row_data}")
        regno = str(row_data.get(regno_header, '')).strip()
        print(f"[DEBUG] Row {idx} regno: '{regno}'")
        if not regno:
            errors.append(f"Row {idx}: Missing reg_number.")
            continue
        candidate = Candidate.objects.filter(reg_number__iexact=regno).first()
        if not candidate:
            errors.append(f"Row {idx}: Candidate with reg_number '{regno}' not found.")
            continue
        # Validate candidate registration category, occupation, level
        cand_regcat = getattr(candidate, 'registration_category', '').strip().lower()
        cand_occupation_id = getattr(candidate, 'occupation_id', None)
        if regcat_normalized != cand_regcat:
            errors.append(f"Row {idx}: Candidate '{regno}' registration category mismatch.")
            continue
        if occupation and candidate.occupation_id != occupation.id:
            errors.append(f"Row {idx}: Candidate '{regno}' occupation mismatch.")
            continue
        # For formal/module-based and informal, check level enrollment
        if regcat_normalized in ['formal', 'informal'] and level:
            if not CandidateLevel.objects.filter(candidate=candidate, level=level).exists():
                errors.append(f"Row {idx}: Candidate '{regno}' not enrolled in selected level.")
                continue
        # Assessment date
        assessment_month = int(assessment_month)
        print(assessment_month)
        assessment_year = int(assessment_year)
        print(assessment_year)
        from datetime import date
        try:
            # code to convert 06/2025 to date time object of 2025-06-01
            assessment_day = date(assessment_year, assessment_month, 1)
            print(assessment_day)
        except Exception as e:
            print(e)
            errors.append(f"Row {idx}: Invalid conversion of assessment month/year {assessment_month}/{assessment_year}")
            continue
        # Modular: expects PRACTICAL column and selected module
        if regcat_normalized == 'modular':
            mark = row_data.get('PRACTICAL') or row_data.get('Practical') or row_data.get('practical')
            if selected_module is None:
                errors.append(f"Row {idx}: No module selected for modular upload.")
                continue
            if mark is None or str(mark).strip() == '':
                errors.append(f"Row {idx}: Missing practical mark for candidate '{regno}'.")
                continue
            try:
                mark_val = float(mark)
            except Exception:
                errors.append(f"Row {idx}: Invalid practical mark for candidate '{regno}'.")
                continue
            Result.objects.update_or_create(
                candidate=candidate,
                module=selected_module,
                assessment_date=assessment_day,
                result_type='modular',
                defaults={
                    'assessment_type': 'practical',
                    'mark': mark_val,
                    'user': request.user,
                    'status': ''
                }
            )
            updated += 1
        # Formal module-based: expects THEORY and PRACTICAL columns
        elif regcat_normalized == 'formal' and structure_type == 'modules':
            theory_mark = row_data.get('THEORY') or row_data.get('Theory') or row_data.get('theory')
            practical_mark = row_data.get('PRACTICAL') or row_data.get('Practical') or row_data.get('practical')
            # Save theory result (if present)
            if theory_mark is not None and str(theory_mark).strip() != '':
                try:
                    theory_mark_val = float(theory_mark)
                except Exception:
                    errors.append(f"Row {idx}: Invalid THEORY mark for candidate '{regno}'.")
                    theory_mark_val = None
                if theory_mark_val is not None:
                    Result.objects.update_or_create(
                        candidate=candidate,
                        level=level,
                        assessment_date=assessment_day,
                        assessment_type='theory',
                        result_type='formal',
                        defaults={
                            'mark': theory_mark_val,
                            'user': request.user,
                            'status': ''
                        }
                    )
                    updated += 1
            # Save practical result (if present)
            if practical_mark is not None and str(practical_mark).strip() != '':
                try:
                    practical_mark_val = float(practical_mark)
                except Exception:
                    errors.append(f"Row {idx}: Invalid PRACTICAL mark for candidate '{regno}'.")
                    practical_mark_val = None
                if practical_mark_val is not None:
                    Result.objects.update_or_create(
                        candidate=candidate,
                        level=level,
                        assessment_date=assessment_date,
                        assessment_type='practical',
                        result_type='formal',
                        defaults={
                            'mark': practical_mark_val,
                            'user': request.user,
                            'status': ''
                        }
                    )
                    updated += 1
        # Formal paper-based and informal: expects paper code columns
        else:
            for code, obj in code_to_obj.items():
                mark = row_data.get(code)
                if mark is None or str(mark).strip() == '':
                    continue
                try:
                    mark_val = float(mark)
                except Exception:
                    errors.append(f"Row {idx}: Invalid mark for {code} (candidate '{regno}').")
                    continue
                if not (0 <= mark_val <= 100):
                    errors.append(f"Row {idx}: Mark for {code} (candidate '{regno}') must be between 0 and 100. Got {mark_val}.")
                    continue
                # Paper-based formal
                if regcat_normalized == 'formal' and structure_type == 'papers':
                    Result.objects.update_or_create(
                        candidate=candidate,
                        level=level,
                        paper=obj,
                        assessment_date=assessment_date,
                        result_type='formal',
                        defaults={
                            'assessment_type': obj.grade_type if hasattr(obj, 'grade_type') else 'practical',
                            'mark': mark_val,
                            'user': request.user,
                            'status': ''
                        }
                    )
                    updated += 1
                # Informal/worker's PAS
                elif regcat_normalized == 'informal':
                    candidate_paper = CandidatePaper.objects.filter(candidate=candidate, paper=obj, level=level).first()
                    module = candidate_paper.module if candidate_paper else None
                    Result.objects.update_or_create(
                        candidate=candidate,
                        level=level,
                        module=module,
                        paper=obj,
                        assessment_type='practical',
                        assessment_date=assessment_date,
                        result_type='informal',
                        defaults={
                            'mark': mark_val,
                            'user': request.user,
                            'status': ''
                        }
                    )
                    updated += 1

    if errors:
        return JsonResponse({'success': False, 'updated_count': updated, 'errors': errors})
    return JsonResponse({'success': True, 'updated_count': updated, 'errors': []})

@login_required
@require_POST
def generate_marksheet(request):
    """
    Accepts POST with params, returns JSON with download URL for marksheet.
    Now supports 'modules' param for Modular marksheet generation.
    """
    # Extract params
    month = request.POST.get('assessment_month')
    year = request.POST.get('assessment_year')
    regcat = request.POST.get('registration_category')
    occupation = request.POST.get('occupation')
    level = request.POST.get('level')
    center = request.POST.get('assessment_center')
    modules = request.POST.getlist('modules')  # Accept multiple module IDs

    # Determine structure_type for occupation/level
    structure_type = None
    if occupation and level:
        from .models import OccupationLevel
        occ_level = OccupationLevel.objects.filter(occupation_id=occupation, level_id=level).first()
        if occ_level:
            structure_type = occ_level.structure_type
    print(f'[DEBUG] structure_type for occupation {occupation}, level {level}:', structure_type)
    from django.urls import reverse
    import urllib.parse
    params = {
        'assessment_month': month,
        'assessment_year': year,
        'registration_category': regcat,
        'occupation': occupation,
        'level': level,
        'assessment_center': center,
    }
    # Add modules to params for Modular
    if regcat and regcat.lower() == 'modular' and modules:
        params['modules'] = ','.join(modules)
    # Remove empty params
    params = {k: v for k, v in params.items() if v}

    # Validate required params for occupation and level
    from .models import Occupation, Level, Module, Candidate
    occ = None
    lvl = None
    if occupation:
        try:
            occ = Occupation.objects.get(pk=occupation)
        except Occupation.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Selected occupation not found.'})
    if level:
        try:
            lvl = Level.objects.get(pk=level)
        except Level.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Selected level not found.'})

    # Check for enrolled candidates
    candidates = Candidate.objects.all()
    print('[DEBUG] Initial candidates:', candidates.count())
    print('[DEBUG] Initial candidate IDs and regcat:', list(candidates.values_list('id', 'registration_category')))
    if regcat and regcat.lower() == 'modular':
        candidates = candidates.filter(occupation__has_modular=True)
        print('[DEBUG] After has_modular filter:', candidates.count())
        print('[DEBUG] After has_modular IDs and regcat:', list(candidates.values_list('id', 'registration_category')))
        # Filter by selected modules if provided
        if modules:
            module_objs = Module.objects.filter(id__in=modules)
            from .models import CandidateModule
            enrolled_ids = set(CandidateModule.objects.filter(module__in=module_objs).values_list('candidate_id', flat=True))
            print('[DEBUG] Modular enrolled_ids:', enrolled_ids)
            candidates = candidates.filter(id__in=enrolled_ids)
            print('[DEBUG] After module enrollment filter:', candidates.count())
            print('[DEBUG] After module enrollment IDs and regcat:', list(candidates.values_list('id', 'registration_category')))
    elif regcat and regcat.lower() == 'formal' and structure_type == 'papers':
        candidates = candidates.filter(occupation__has_modular=False)
        print('[DEBUG] After NOT has_modular filter (paper-based):', candidates.count())
        print('[DEBUG] After NOT has_modular IDs and regcat (paper-based):', list(candidates.values_list('id', 'registration_category')))
    else:
        print('[DEBUG] Skipping occupation__has_modular filter for formal module-based marksheet.')
    # Normalize 'workers_pas' to 'Informal' for DB filtering
    regcat_db = regcat
    if regcat and regcat.lower() in ['workers_pas', "worker's pas"]:
        regcat_db = 'Informal'
    if regcat_db:
        candidates = candidates.filter(registration_category__iexact=regcat_db)
        print(f'[DEBUG] After regcat ({regcat_db}) filter:', candidates.count())
        print(f'[DEBUG] After regcat IDs and regcat:', list(candidates.values_list('id', 'registration_category')))
    print('[DEBUG] Candidate IDs and occupation IDs:', list(candidates.values_list('id', 'occupation_id')))
    # For formal (module-based), filter by CandidateLevel FIRST, do NOT apply occupation filter before this!
    if regcat and regcat.lower() == 'formal' and level and occupation:
        from .models import CandidateLevel
        candidate_levels_qs = CandidateLevel.objects.filter(level=level, candidate__occupation=occupation)
        print(f"[DEBUG] CandidateLevel entries for occupation {occupation}, level {level}: {[{'candidate_id': cl.candidate.id, 'candidate_occupation_id': cl.candidate.occupation_id} for cl in candidate_levels_qs]}")
        enrolled_ids = set(candidate_levels_qs.values_list('candidate_id', flat=True))
        print(f"[DEBUG] Enrolled candidate IDs for occupation {occupation}, level {level}: {enrolled_ids}")
        candidates = candidates.filter(id__in=enrolled_ids)
        print('[DEBUG] After CandidateLevel filter:', candidates.count())
    elif occupation:
        candidates = candidates.filter(occupation_id=occupation)
        print(f'[DEBUG] After occupation ({occupation}) filter:', candidates.count())
    if center:
        candidates = candidates.filter(assessment_center=center)
        print(f'[DEBUG] After center ({center}) filter:', candidates.count())
    if not occ:
        return JsonResponse({'success': False, 'error': 'Please select an occupation.'})
    if lvl is None and regcat and regcat.lower() != 'modular':
        return JsonResponse({'success': False, 'error': 'Please select a level.'})
    if regcat and regcat.lower() == 'modular' and (not modules or not Module.objects.filter(id__in=modules).exists()):
        return JsonResponse({'success': False, 'error': 'Please select at least one module for Modular marksheet generation.'})
    print("DEBUG: Candidate IDs after all filters:", list(candidates.values_list('id', flat=True)))
    print("DEBUG: Level param:", level)
    print("DEBUG: Registration category param:", regcat)
    print("DEBUG: Occupation param:", occupation)
    if not candidates.exists():
        return JsonResponse({'success': False, 'error': 'No enrolled candidates found for the selected parameters.'})

    url = reverse('download_marksheet') + '?' + urllib.parse.urlencode(params)
    return JsonResponse({'success': True, 'download_url': url})


@login_required
@require_POST
def print_marksheet(request):
    """
    Accepts POST with params, validates them, and returns a JSON response with a URL
    to download the printable PDF marksheet. This logic mirrors `generate_marksheet`.
    """
    from .models import Occupation, Level, Module, Candidate, OccupationLevel, CandidateLevel, CandidateModule
    from django.urls import reverse
    import urllib.parse

    # Extract params
    month = request.POST.get('assessment_month')
    year = request.POST.get('assessment_year')
    regcat = request.POST.get('registration_category')
    occupation_id = request.POST.get('occupation')
    level_id = request.POST.get('level')
    center_id = request.POST.get('assessment_center')
    modules = request.POST.getlist('modules')

    # Determine structure_type for validation
    structure_type = None
    if occupation_id and level_id:
        occ_level = OccupationLevel.objects.filter(occupation_id=occupation_id, level_id=level_id).first()
        if occ_level:
            structure_type = occ_level.structure_type

    # --- Validation --- #
    if not all([month, year, regcat, occupation_id]):
        return JsonResponse({'success': False, 'error': 'Missing required fields (Month, Year, Category, Occupation).'})

    if regcat.lower() != 'modular' and not level_id:
        return JsonResponse({'success': False, 'error': 'Level is required for this registration category.'})

    if regcat.lower() == 'modular' and not modules:
        return JsonResponse({'success': False, 'error': 'Please select at least one module for Modular registration.'})

    # Check if any candidates match the criteria
    candidates = Candidate.objects.all()
    regcat_filter = 'Informal' if regcat.lower() in ['workers_pas', "worker's pas"] else regcat
    candidates = candidates.filter(registration_category__iexact=regcat_filter)
    candidates = candidates.filter(occupation_id=occupation_id)

    if level_id:
        candidates = candidates.filter(candidatelevel__level_id=level_id)
    if center_id:
        candidates = candidates.filter(assessment_center_id=center_id)
    if regcat.lower() == 'modular' and modules:
        candidates = candidates.filter(candidatemodule__module_id__in=modules)

    if not candidates.exists():
        return JsonResponse({'success': False, 'error': 'No enrolled candidates found for the selected criteria.'})

    # --- URL Generation --- #
    params = {
        'assessment_month': month,
        'assessment_year': year,
        'registration_category': regcat,
        'occupation': occupation_id,
        'level': level_id,
        'assessment_center': center_id,
    }
    if regcat.lower() == 'modular' and modules:
        params['modules'] = ','.join(modules)

    params = {k: v for k, v in params.items() if v}
    url = reverse('download_printed_marksheet') + '?' + urllib.parse.urlencode(params)
    return JsonResponse({'success': True, 'download_url': url})


@login_required
def download_printed_marksheet(request):
    """
    Generates a printable PDF marksheet with candidates grouped by assessment center.
    The logic mirrors the filtering of `print_marksheet` to ensure consistency.
    """
    # 1. Imports and setup
    from io import BytesIO
    from .models import Candidate, Occupation, Level, Module, Paper, Result, AssessmentCenter, OccupationLevel
    from collections import defaultdict
    import calendar
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors

    logger = logging.getLogger(__name__)

    # 2. Get and log params from request.GET
    month = request.GET.get('assessment_month')
    year = request.GET.get('assessment_year')
    regcat = request.GET.get('registration_category')
    occupation_id = request.GET.get('occupation')
    occupation = Occupation.objects.get(id=occupation_id)   
    level_id = request.GET.get('level')
    center_id = request.GET.get('assessment_center')
    module_ids_raw = request.GET.get('modules', '')
    module_ids = [mid for mid in module_ids_raw.split(',') if mid]

    logger.info(f"--- PDF Marksheet: regcat='{regcat}', occupation='{occupation_id}', level='{level_id}', modules='{module_ids}' ---")

    # 3. Filter candidates (mirroring the logic from print_marksheet)
    candidates = Candidate.objects.select_related('occupation', 'assessment_center').order_by('assessment_center__center_name', 'full_name')
    
    regcat_filter = 'Informal' if regcat and regcat.lower() in ['workers_pas', "worker's pas"] else regcat
    if regcat_filter:
        candidates = candidates.filter(registration_category__iexact=regcat_filter)
    if occupation_id:
        candidates = candidates.filter(occupation_id=occupation_id)
    if level_id:
        candidates = candidates.filter(candidatelevel__level_id=level_id)
    if center_id:
        candidates = candidates.filter(assessment_center_id=center_id)
    if regcat.lower() == 'modular' and module_ids:
        candidates = candidates.filter(candidatemodule__module_id__in=module_ids).distinct()

    logger.info(f"Found {candidates.count()} candidates after filtering.")

    # 4. Prepare PDF document
    response = HttpResponse(content_type='application/pdf')
    filename = f'marksheet_{regcat_filter}_{occupation.name}_{year}_{month}.pdf'
    pdf_title = f"Marksheet: {occupation.name} ({regcat.replace('_', ' ').title()}) - {month}/{year}"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), topMargin=30, bottomMargin=30, title=pdf_title)
    elements = []
    styles = getSampleStyleSheet()

    # Main Title
    title_style = styles['h1']
    title_style.alignment = 1 # Center
    elements.append(Paragraph(f"UGANDA VOCATIONAL AND TECHNICAL ASSESSMENT BOARD", title_style))
    elements.append(Paragraph(f"CANDIDATES MARKSHEETS - {calendar.month_name[int(month)]} {year}", title_style))   
    elements.append(Spacer(1, 24))

    # 5. Handle no candidates
    if not candidates.exists():
        logger.warning("No candidates found, returning PDF with 'No data' message.")
        elements.append(Paragraph("No data found for the selected criteria.", styles['h2']))
        doc.build(elements)
        response.write(buffer.getvalue())
        buffer.close()
        return response

    # 6. Get related objects
    occupation = Occupation.objects.get(pk=occupation_id)
    level = Level.objects.get(pk=level_id) if level_id else None
    
    structure_type = None
    if occupation and level:
        occ_level = OccupationLevel.objects.filter(occupation=occupation, level=level).first()
        if occ_level:
            structure_type = occ_level.structure_type
    logger.info(f"Processing with structure_type: '{structure_type}'")

    # 7. Group candidates by center
    candidates_by_center = defaultdict(list)
    for c in candidates:
        center_key = c.assessment_center.id if c.assessment_center else 'unassigned'
        candidates_by_center[center_key].append(c)

    # 8. Build PDF content
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ])

    first_center = True
    for center_id_key, candidates_in_center in sorted(candidates_by_center.items()):
        if not first_center:
            elements.append(PageBreak())
        first_center = False
        
        center = AssessmentCenter.objects.get(pk=center_id_key) if center_id_key != 'unassigned' else None
        center_name = center.center_name if center else "Unassigned Center"
        center_number = center.center_number if center else "N/A"

        # --- Modular ---
        if regcat.lower() == 'modular':
            modules_to_print = Module.objects.filter(id__in=module_ids)
            for print_module in modules_to_print:
                elements.append(Paragraph(f"<b>Centre:</b> {center_number} - {center_name}", styles['h2']))
                elements.append(Paragraph(f"<b>Occupation:</b> {occupation.name}", styles['Normal']))
                elements.append(Paragraph(f"<b>Module:</b> {print_module.name}", styles['Normal']))
                elements.append(Spacer(1, 12))
                data = [["SN", "Regno", "Names", "Mark"]]
                dynamic_styles = []
                for i, c in enumerate(candidates_in_center, 1):
                    res = Result.objects.filter(candidate=c, module=print_module, assessment_date__year=year, assessment_date__month=month).first()
                    mark_val = f"{res.mark:.0f}" if res and res.mark is not None else ''
                    if res and res.mark == -1:
                        row_index = i
                        col_index = 3 # Mark column
                        dynamic_styles.append(('BACKGROUND', (col_index, row_index), (col_index, row_index), colors.lightpink))
                        dynamic_styles.append(('TEXTCOLOR', (col_index, row_index), (col_index, row_index), colors.red))
                    data.append([i, c.reg_number, c.full_name, mark_val])
                
                final_table_style = TableStyle(table_style.getCommands() + dynamic_styles)
                elements.append(Table(data, style=final_table_style))
                elements.append(Spacer(1, 24))

        # --- Paper-Based (Formal & Informal) ---
        elif structure_type == 'papers':
            papers = Paper.objects.filter(occupation=occupation, level=level)
            elements.append(Paragraph(f"<b>Centre:</b> {center_number} - {center_name}", styles['h2']))
            elements.append(Paragraph(f"<b>Occupation:</b> {occupation.name} - {level.name if level else ''}", styles['Normal']))
            elements.append(Spacer(1, 12))
            for paper in papers:
                elements.append(Paragraph(f"<b>Paper:</b> {paper.name} ({paper.grade_type.title()})", styles['Normal']))
                data = [["SN", "Regno", "Names", "Mark"]]
                dynamic_styles = []
                for i, c in enumerate(candidates_in_center, 1):
                    res = Result.objects.filter(candidate=c, paper=paper, assessment_date__year=year, assessment_date__month=month).first()
                    mark_val = f"{res.mark:.0f}" if res and res.mark is not None else ''
                    if res and res.mark == -1:
                        row_index = i
                        col_index = 3 # Mark column
                        dynamic_styles.append(('BACKGROUND', (col_index, row_index), (col_index, row_index), colors.lightpink))
                        dynamic_styles.append(('TEXTCOLOR', (col_index, row_index), (col_index, row_index), colors.red))
                    data.append([i, c.reg_number, c.full_name, mark_val])

                final_table_style = TableStyle(table_style.getCommands() + dynamic_styles)
                elements.append(Table(data, style=final_table_style))
                elements.append(Spacer(1, 12))

        # --- Module-Based (Theory/Practical) ---
        elif structure_type == 'modules':
            elements.append(Paragraph(f"<b>Centre:</b> {center_number} - {center_name}", styles['h2']))
            elements.append(Paragraph(f"<b>Occupation:</b> {occupation.name} - {level.name if level else ''}", styles['Normal']))
            elements.append(Spacer(1, 12))
            data = [["SN", "Regno", "Names", "Theory", "Practical"]]
            dynamic_styles = []
            for i, c in enumerate(candidates_in_center, 1):
                theory = Result.objects.filter(candidate=c, level=level, assessment_type='theory', assessment_date__year=year, assessment_date__month=month).first()
                practical = Result.objects.filter(candidate=c, level=level, assessment_type='practical', assessment_date__year=year, assessment_date__month=month).first()
                
                theory_val = f"{theory.mark:.0f}" if theory and theory.mark is not None else ''
                practical_val = f"{practical.mark:.0f}" if practical and practical.mark is not None else ''
                
                row_index = i
                if theory and theory.mark == -1:
                    dynamic_styles.append(('BACKGROUND', (3, row_index), (3, row_index), colors.lightpink))
                    dynamic_styles.append(('TEXTCOLOR', (3, row_index), (3, row_index), colors.red))
                
                if practical and practical.mark == -1:
                    dynamic_styles.append(('BACKGROUND', (4, row_index), (4, row_index), colors.lightpink))
                    dynamic_styles.append(('TEXTCOLOR', (4, row_index), (4, row_index), colors.red))

                data.append([i, c.reg_number, c.full_name, theory_val, practical_val])

            final_table_style = TableStyle(table_style.getCommands() + dynamic_styles)
            elements.append(Table(data, style=final_table_style))
            elements.append(Spacer(1, 24))
        
        else:
             logger.error(f"Unknown structure type '{structure_type}' or category '{regcat}' for PDF generation.")
             elements.append(Paragraph(f"Error: Could not determine marksheet structure for {occupation.name}.", styles['Normal']))

    # 9. Build and return PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

@login_required
def download_marksheet(request):
    """
    Generates and streams the Excel marksheet in memory based on GET params.
    Supports all registration categories and structures (modular, formal module-based, formal paper-based, informal/worker's PAS).
    """
    from .models import Candidate, OccupationLevel, Module, Paper, Result, AssessmentCenter, Occupation, Level, CandidateModule, CandidateLevel, CandidatePaper
    from openpyxl import Workbook
    from io import BytesIO

    # Extract params
    month = request.GET.get('assessment_month')
    year = request.GET.get('assessment_year')
    regcat = request.GET.get('registration_category')
    # Normalize workers_pas and worker's pas to Informal for both filtering and logic
    if regcat and regcat.strip().lower() in ["workers_pas", "worker's pas"]:
        regcat = "Informal"
    occupation_id = request.GET.get('occupation')
    level_id = request.GET.get('level')
    center_id = request.GET.get('assessment_center')
    modules_param = request.GET.get('modules')  # comma-separated module IDs

    # Get occupation, level, center
    occupation = Occupation.objects.filter(pk=occupation_id).first() if occupation_id else None
    level = Level.objects.filter(pk=level_id).first() if level_id else None
    center = AssessmentCenter.objects.filter(pk=center_id).first() if center_id else None

    regcat_normalized = regcat.strip().lower() if regcat else ''
    modules = []
    papers = []
    enrolled_ids = set()
    enrolled_paper_ids = set()
    structure_type = None
    informal = False

    # --- Fetch modules/papers FIRST ---
    occ_level = None
    if occupation and level:
        occ_level = OccupationLevel.objects.filter(occupation=occupation, level=level).first()
        if occ_level:
            structure_type = occ_level.structure_type  # 'modules' or 'papers'

    # Modular: Only PR per selected module(s)
    if regcat_normalized == 'modular':
        # Use only selected modules if provided (filter by occupation only, not level)
        if modules_param:
            module_ids = [int(mid) for mid in modules_param.split(',') if mid.isdigit()]
            modules = list(Module.objects.filter(id__in=module_ids, occupation=occupation))
        else:
            modules = list(Module.objects.filter(occupation=occupation))
        module_ids = [m.id for m in modules]
        # Candidates enrolled in at least one of these modules
        enrolled_modules = CandidateModule.objects.filter(module__in=modules)
        enrolled_ids = set(enrolled_modules.values_list('candidate_id', flat=True))
        print(f"[DEBUG] Modular: modules={module_ids}, enrolled_ids={enrolled_ids}")

    # --- Candidate Query ---
    candidates = Candidate.objects.all()
    if regcat:
        candidates = candidates.filter(registration_category__iexact=regcat)
    # For formal (module-based), filter by CandidateLevel FIRST, do not apply occupation filter before this!
    if regcat_normalized == 'formal' and structure_type == 'modules' and level and occupation:
        from .models import CandidateLevel
        enrolled_ids = set(
            CandidateLevel.objects.filter(level=level, candidate__occupation=occupation)
            .values_list('candidate_id', flat=True)
        )
        candidates = candidates.filter(id__in=enrolled_ids)
    elif occupation_id:
        candidates = candidates.filter(occupation_id=occupation_id)
    elif regcat_normalized != 'modular' and hasattr(Candidate, 'level') and level:
        candidates = candidates.filter(candidatelevel__level_id=level_id)
    if center:
        candidates = candidates.filter(assessment_center=center)

    # --- Enrollment Filtering ---
    enrolled_ids = set()
    informal = False
    regcat_normalized = regcat.strip().lower() if regcat else ''
    # Modular: Only PR per module
    if regcat_normalized == 'modular':
        enrolled_ids = set(CandidateModule.objects.filter(module__in=modules).values_list('candidate_id', flat=True))
        candidates = candidates.filter(id__in=enrolled_ids)
        structure_type = 'modules'
    # Formal: Module-based (theory/practical per module)
    elif regcat_normalized == 'formal' and structure_type == 'modules':
        # For formal (level module-based): candidates enroll for a level, not modules
        candidate_levels_qs = CandidateLevel.objects.filter(level=level, candidate__occupation=occupation)
        print(f"[DEBUG] CandidateLevel entries for occupation {occupation.id if occupation else None}, level {level.id if level else None}: {[{'candidate_id': cl.candidate.id, 'candidate_occupation_id': cl.candidate.occupation_id} for cl in candidate_levels_qs]}")
        enrolled_level_ids = set(candidate_levels_qs.values_list('candidate_id', flat=True))
        print(f"[DEBUG] Enrolled candidate IDs for occupation {occupation.id if occupation else None}, level {level.id if level else None}: {enrolled_level_ids}")
        candidates = candidates.filter(id__in=enrolled_level_ids)
        modules = list(Module.objects.filter(occupation=occupation, level=level))
    # Formal: Paper-based (dynamic paper codes per occupation/level)
    elif regcat_normalized == 'formal' and structure_type == 'papers':
        enrolled_ids = set(
            CandidateLevel.objects.filter(level=level, candidate__occupation=occupation)
            .values_list('candidate_id', flat=True)
        )
        print(f"[DEBUG] Paper-based: enrolled_ids for occupation {occupation.id if occupation else None}, level {level.id if level else None}: {enrolled_ids}")
        candidates = candidates.filter(id__in=enrolled_ids)
        # Fetch all papers for this occupation/level
        papers = list(Paper.objects.filter(occupation=occupation, level=level))
        print(f"[DEBUG] Paper-based: papers for occupation {occupation.id if occupation else None}, level {level.id if level else None}: {[p.code for p in papers]}")
    # Informal/Worker's PAS: All papers for occupation/level (flatten, ignore module grouping)
    elif regcat_normalized in ['informal', "worker's pas"]:
        informal = True
        # Fetch modules for this occupation and level
        modules = list(Module.objects.filter(occupation_id=occupation.id, level_id=level.id))
        # Fetch papers both ways: directly by occupation/level, and by modules
        papers_direct = list(Paper.objects.filter(occupation_id=occupation.id, level_id=level.id))
        papers_via_modules = list(Paper.objects.filter(module__in=modules))
        # Combine and deduplicate by paper ID
        papers_dict = {p.id: p for p in papers_direct + papers_via_modules}
        papers = list(papers_dict.values())
        print(f"[DEBUG] Informal: papers_direct for occupation {occupation.id}, level {level.id}: {[{'id': p.id, 'code': p.code} for p in papers_direct]}")
        print(f"[DEBUG] Informal: papers_via_modules for modules {[m.id for m in modules]}: {[{'id': p.id, 'code': p.code} for p in papers_via_modules]}")
        print(f"[DEBUG] Informal: final papers for occupation {occupation.id}, level {level.id}: {[{'id': p.id, 'code': p.code} for p in papers]}")
        # All candidates enrolled for this level in this occupation
        enrolled_ids = set(CandidateLevel.objects.filter(level_id=level.id, candidate__occupation_id=occupation.id).values_list('candidate_id', flat=True))
        print(f"[DEBUG] Informal: enrolled_ids for occupation {occupation.id if occupation else None}, level {level.id if level else None}: {enrolled_ids}")
        candidates = candidates.filter(id__in=enrolled_ids)
    else:
        # fallback: no structure or unknown regcat
        modules = []
        papers = []

    print(f"Enrolled candidate IDs: {enrolled_ids}")
    print(f"Modules: {modules}")
    print(f"Papers: {papers}")

    if regcat_normalized == 'modular' and modules:
        # --- Build Modular Marksheet ---
        wb = Workbook()
        ws = wb.active
        ws.title = 'Marksheet'
        # Header
        ws.append(['SN', 'REGISTRATION NO.', 'FULL NAME', 'OCCUPATION CODE', 'CATEGORY', 'MODULE CODE', 'PRACTICAL'])
        sn = 1
        for module in modules:
            # Candidates enrolled in this module
            enrolled_cands = candidates.filter(id__in=CandidateModule.objects.filter(module=module).values_list('candidate_id', flat=True))
            for cand in enrolled_cands:
                ws.append([
                    sn,
                    cand.reg_number,
                    cand.full_name,
                    cand.occupation.code if cand.occupation else '',
                    'Modular',
                    module.code,
                    ''  # PR mark cell (to be filled)
                ])
                sn += 1
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        #filename = f"marksheet_{regcat_normalized or 'all'}_{month or ''}_{year or ''}.xlsx"
        occupation_name = occupation.name if occupation else 'Occupation'
        regcat_title = regcat_normalized.title() if regcat_normalized else 'All'
        month_str = calendar.month_name[int(month)] if month and month.isdigit() and int(month) in range(1, 13) else (month if month else '')
        year_str = year if year else ''
        filename = f"{occupation_name} Marksheet {month_str} {year_str} {regcat_title}.xlsx"
        response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    # --- Formal (module-based): SN, REGISTRATION NO., FULL NAME, OCCUPATION CODE, CATEGORY, LEVEL, THEORY, PRACTICAL ---
    if regcat_normalized == 'formal' and structure_type == 'modules':
        wb = Workbook()
        ws = wb.active
        ws.title = 'Marksheet'
        ws.append(['SN', 'REGISTRATION NO.', 'FULL NAME', 'OCCUPATION CODE', 'CATEGORY', 'LEVEL', 'THEORY', 'PRACTICAL'])
        sn = 1
        for cand in candidates:
            ws.append([
                sn,
                cand.reg_number,
                cand.full_name,
                cand.occupation.code if cand.occupation else '',
                'Formal',
                level.name if level else '',
                '',  # Theory mark
                '',  # Practical mark
            ])
            sn += 1
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        #filename = f"marksheet_{regcat_normalized or 'all'}_{month or ''}_{year or ''}.xlsx"
        occupation_name = occupation.name if occupation else 'Occupation'
        regcat_title = regcat_normalized.title() if regcat_normalized else 'All'
        month_str = calendar.month_name[int(month)] if month and month.isdigit() and int(month) in range(1, 13) else (month if month else '')
        year_str = year if year else ''
        filename = f"{occupation_name} Marksheet {month_str} {year_str} {regcat_title}.xlsx"    
        response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    if not modules and not papers:
        wb = Workbook()
        ws = wb.active
        ws.title = 'Marksheet'
        ws.append(['No modules or papers found for the selected occupation and level.'])
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        #filename = f"marksheet_{regcat_normalized or 'all'}_{month or ''}_{year or ''}.xlsx"
        occupation_name = occupation.name if occupation else 'Occupation'
        regcat_title = regcat_normalized.title() if regcat_normalized else 'All'
        month_str = calendar.month_name[int(month)] if month and month.isdigit() and int(month) in range(1, 13) else (month if month else '')
        year_str = year if year else ''
        filename = f"{occupation_name} Marksheet {month_str} {year_str} {regcat_title}.xlsx"
        response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    if not candidates.exists():
        wb = Workbook()
        ws = wb.active
        ws.title = 'Marksheet'
        ws.append(['No enrolled candidates found for the selected parameters.'])
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        filename = f"marksheet_{regcat_normalized or 'all'}_{month or ''}_{year or ''}.xlsx"
        response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    # --- Build Excel ---
    wb = Workbook()
    ws = wb.active
    ws.title = 'Marksheet'

    # --- Build Headers ---
    # For paper-based marksheets, use a minimal set of columns and always include LEVEL
    if regcat_normalized == 'formal' and structure_type == 'papers':
        base_headers = ['SN', 'REGISTRATION NO.', 'FULL NAME', 'OCCUPATION CODE', 'LEVEL', 'CATEGORY']
    else:
        # For informal/worker's PAS, match the Excel sample: include LEVEL after CATEGORY
        if informal:
            base_headers = ['SN', 'REGISTRATION NO.', 'FULL NAME', 'OCCUPATION CODE', 'CATEGORY', 'LEVEL']
        else:
            base_headers = ['REGISTRATION NO.', 'FULL NAME', 'OCCUPATION CODE', 'LEVEL', 'CATEGORY', 'ASSESSMENT CENTER', 'MONTH', 'YEAR']
    dynamic_headers = []
    if regcat_normalized == 'modular':
        for module in modules:
            dynamic_headers.append(f"{module.code} (PR)")
    elif regcat_normalized == 'formal' and structure_type == 'modules':
        for module in modules:
            dynamic_headers.append(f"{module.code} (TH)")
            dynamic_headers.append(f"{module.code} (PR)")
    elif (regcat_normalized == 'formal' and structure_type == 'papers') or informal:
        for paper in papers:
            dynamic_headers.append(f"{paper.code}")
    else:
        dynamic_headers.append('MARK')
    ws.append(base_headers + dynamic_headers)

    # --- Populate Rows ---
    sn = 1
    for candidate in candidates:
        # For paper-based marksheets, always include level name and only required columns
        if regcat_normalized == 'formal' and structure_type == 'papers':
            row = [
                sn,
                candidate.reg_number,
                candidate.full_name,
                getattr(candidate.occupation, 'code', '') if candidate.occupation else '',
                level.name if level else '',
                getattr(candidate, 'registration_category', ''),
            ]
        elif informal:
            row = [
                sn,
                candidate.reg_number,
                candidate.full_name,
                getattr(candidate.occupation, 'code', '') if candidate.occupation else '',
                getattr(candidate, 'registration_category', ''),
                level.name if level else '',
            ]
        else:
            row = [
                candidate.reg_number,
                candidate.full_name,
                getattr(candidate.occupation, 'code', '') if candidate.occupation else '',
                str(candidate.level) if hasattr(candidate, 'level') and candidate.level else '',
                getattr(candidate, 'registration_category', ''),
                str(candidate.assessment_center) if candidate.assessment_center else '',
                month or '',
                year or ''
            ]
        marks = []
        if regcat_normalized == 'modular':
            for module in modules:
                marks.append('')
        elif regcat_normalized == 'formal' and structure_type == 'modules':
            for module in modules:
                marks.append('')  # Theory
                marks.append('')  # Practical
        elif (regcat_normalized == 'formal' and structure_type == 'papers') or informal:
            for paper in papers:
                marks.append('')
        else:
            marks.append('')

        # Append the row and get the row number for formatting
        ws.append(row + marks)
        current_row = ws.max_row

        # --- Highlight enrolled papers for informal/worker's PAS ---
        if informal:
            from openpyxl.styles import PatternFill
            # Get enrolled paper IDs for this candidate (for this level)
            enrolled_paper_ids = set()
            for cp in CandidatePaper.objects.filter(candidate=candidate, level=level):
                enrolled_paper_ids.add(cp.paper_id)
            yellow_fill = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')
            # The paper columns start after the base headers
            paper_col_offset = len(row)
            for idx, paper in enumerate(papers):
                if paper.id in enrolled_paper_ids:
                    col_letter = ws.cell(row=current_row, column=paper_col_offset + idx + 1).column_letter
                    ws[f"{col_letter}{current_row}"].fill = yellow_fill

        if regcat_normalized == 'formal' and structure_type == 'papers':
            sn += 1
        elif informal:
            sn += 1

    # --- Stream to memory ---
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    #filename = f"marksheet_{regcat_normalized or 'all'}_{month or ''}_{year or ''}.xlsx"
    occupation_name = occupation.name if occupation else 'Occupation'
    regcat_title = regcat_normalized.title() if regcat_normalized else 'All'
    month_str = calendar.month_name[int(month)] if month and month.isdigit() and int(month) in range(1, 13) else (month if month else '')
    year_str = year if year else ''
    filename = f"{occupation_name} Marksheet {month_str} {year_str} {regcat_title}.xlsx"    
    
    response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse

import copy
import openpyxl
from openpyxl import Workbook
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.utils.html import format_html
from django.urls import reverse
from django.core.files.storage import FileSystemStorage
from .models import Candidate, Occupation, AssessmentCenter, District, Village
from .forms import CandidateForm
from datetime import datetime
import tempfile
import os
import zipfile
from django.core.files import File

@login_required
def candidate_import_dual(request):
    """
    Handle GET (show dual import page) and POST (process Excel + photo zip upload).
    """
    if request.method == 'GET':
        return render(request, 'candidates/import_dual.html')

    excel_file = request.FILES.get('excel_file')
    photo_zip = request.FILES.get('photo_zip')
    errors = []
    created = 0
    if not excel_file or not photo_zip:
        errors.append('Both Excel and photo ZIP files must be uploaded.')
        return render(request, 'candidates/import_dual.html', {'errors': errors, 'imported_count': 0})
    # Load Excel
    try:
        wb = openpyxl.load_workbook(excel_file)
        ws = wb.active
    except Exception:
        errors.append('Invalid Excel file.')
        return render(request, 'candidates/import_dual.html', {'errors': errors, 'imported_count': 0})
    headers = [str(cell.value).replace(u'\xa0', ' ').strip().lower() for cell in ws[1] if cell.value]

    # Unzip images to temp dir
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            with zipfile.ZipFile(photo_zip) as zf:
                image_files = [n for n in zf.namelist() if n.lower().endswith(('.jpg', '.jpeg', '.png'))]
                image_name_map = {}
                for image_name in image_files:
                    # Extracts '614956.Kajumba Ruth' from '.../614956.Kajumba Ruth.jpg'
                    image_name_only = os.path.splitext(os.path.basename(image_name))[0]
                    if '.' in image_name_only:
                        try:
                            # Extracts 'Kajumba Ruth'
                            name_part = image_name_only.split('.', 1)[1]
                            # Replaces '_' with ' ' -> 'Kajumba Ruth'
                            cleaned_name = name_part.replace('_', ' ').strip()
                            # Map 'kajumba ruth' to '.../614956.Kajumba_Ruth.jpg'
                            image_name_map[cleaned_name.lower()] = image_name
                        except IndexError:
                            # This handles cases like '.DS_Store' or filenames without a name part
                            continue
                zf.extractall(tmp_dir)
                # DEBUG: Log the keys to see what is being generated from filenames
                errors.append(f"DEBUG: Image name keys generated: {list(image_name_map.keys())}")
        except Exception as e:
            errors.append(f'Invalid ZIP file or unable to extract images: {e}')
            return render(request, 'candidates/import_dual.html', {'errors': errors, 'imported_count': 0})
        # Read Excel rows
        rows = [row for row in ws.iter_rows(min_row=2, values_only=True) if not all(cell is None for cell in row)]
        
        for idx, row in enumerate(rows, start=2):
            data = dict(zip(headers, row))
            candidate_name_full = data.get('full_name', '').strip()

            # Handle cases where Excel has 3 names but image has 2
            name_parts = candidate_name_full.split()
            if len(name_parts) >= 3:
                # Use only the first two names for matching
                candidate_name_for_match = " ".join(name_parts[:2])
            else:
                candidate_name_for_match = candidate_name_full
            
            img_name = image_name_map.get(candidate_name_for_match.lower())

            if not img_name:
                errors.append(f"Row {idx}: Image not found for candidate '{candidate_name_full}'.")
                continue
            # --- (reuse import logic from candidate_import) ---
            form_data = data.copy()
            # Normalize registration_category for modular candidates
            regcat = str(form_data.get('registration_category', '')).strip().capitalize()
            if regcat == 'Modular':
                form_data['registration_category'] = 'Modular'
            # Robust date parsing: handle string, datetime, and Excel serial (float/int)
            from openpyxl.utils.datetime import from_excel
            import datetime as dt
            for date_field in ['date_of_birth', 'start_date', 'finish_date', 'assessment_date']:
                val = form_data.get(date_field)
                if not val:
                    continue
                if isinstance(val, (dt.date, dt.datetime)):
                    form_data[date_field] = val.date() if isinstance(val, dt.datetime) else val
                elif isinstance(val, (float, int)):
                    try:
                        form_data[date_field] = from_excel(val).date()
                    except Exception:
                        errors.append(f"Row {idx}: Invalid Excel serial date in '{date_field}'.")
                        continue
                elif isinstance(val, str):
                    for fmt in ('%d/%m/%Y', '%-d/%-m/%Y', '%Y-%m-%d'):
                        try:
                            form_data[date_field] = dt.datetime.strptime(val, fmt).date()
                            break
                        except Exception:
                            continue
                    else:
                        errors.append(f"Row {idx}: Invalid date format in '{date_field}'. Use D/M/YYYY, DD/MM/YYYY, or YYYY-MM-DD.")
                        continue
            # DEBUG: Print nationality value before validation
            print(f"[DEBUG] Row {idx} nationality value: '{form_data.get('nationality', '')}'")
            from django_countries import countries
            import re
            def normalize_country(val):
                val = val.lower().replace('&', 'and')
                val = re.sub(r'[^a-z0-9 ]', '', val)
                val = re.sub(r'\s+', ' ', val).strip()
                return val
            nat_val = form_data.get('nationality', '')
            if not isinstance(nat_val, str):
                nat_val = str(nat_val)
            nat_val_norm = normalize_country(nat_val)
            # DEBUG: Print all allowed country codes and names
            print(f"[DEBUG] Allowed countries: {[c for c in countries]}")
            country_map = {}
            for code, name in countries:
                country_map[normalize_country(code)] = code
                country_map[normalize_country(name)] = code
            if nat_val_norm not in country_map:
                print(f"[DEBUG] Row {idx} nationality '{nat_val}' (normalized: '{nat_val_norm}') NOT in country_map")
                errors.append(f"Row {idx}: Nationality '{form_data.get('nationality')}' is not a valid country. Please use a country name or code from the dropdown.")
                continue
            form_data['nationality'] = country_map[nat_val_norm]

            # Occupation and assessment center: lookup by code
            occ_code = str(form_data.get('occupation')) if form_data.get('occupation') is not None else ''
            center_code = str(form_data.get('assessment_center')) if form_data.get('assessment_center') is not None else ''
            try:
                form_data['occupation'] = Occupation.objects.get(code=occ_code).id
            except Exception:
                errors.append(f"Row {idx}: Invalid occupation code '{occ_code}'.")
                continue
            try:
                form_data['assessment_center'] = AssessmentCenter.objects.get(center_number=center_code).id
            except Exception:
                errors.append(f"Row {idx}: Invalid assessment center code '{center_code}'.")
                continue
            # DEBUG: Print final form_data nationality value before form submission
            print(f"[DEBUG] Row {idx} final form_data['nationality']: '{form_data['nationality']}'")
            # Validate using CandidateForm
            form = CandidateForm(form_data)
            # Make district and village optional for bulk import
            for f in ['district', 'village']:
                if f in form.fields:
                    form.fields[f].required = False
            if not form.is_valid():
                print(f"[DEBUG] Row {idx} SKIPPED: CandidateForm errors: {form.errors}")
                errors.append(f"Row {idx}: Form errors: {form.errors}")
                continue
            # District and village: truly optional for import (skip if missing or blank)
            for loc_field, model_cls in [('district', District), ('village', Village)]:
                val = form_data.get(loc_field)
                if val is None or str(val).strip() == '':
                    form_data[loc_field] = None
                else:
                    val_str = str(val).strip()
                    obj = model_cls.objects.filter(name__iexact=val_str).first()
                    form_data[loc_field] = obj.id if obj else None
            # Debug: print after district/village assignment
            print(f"[DEBUG] Row {idx} after district/village assignment: district={form_data.get('district')}, village={form_data.get('village')}")

            # Define date and foreign key fields for use below
            date_fields = ['date_of_birth', 'start_date', 'finish_date', 'assessment_date']
            fk_fields = ['occupation', 'assessment_center', 'district', 'village']
            # Coerce every other field except dates and foreign keys to string
            for k in form_data:
                if k not in date_fields + fk_fields:
                    v = form_data[k]
                    if v is not None and not isinstance(v, str):
                        form_data[k] = str(v)
            # Debug: print types of all fields before form creation
            print(f"[IMPORT DEBUG] Row {idx} form_data types: " + ", ".join(f"{k}: {type(v).__name__}" for k,v in form_data.items()))
            # Remove reg_number if present
            form_data.pop('reg_number', None)
            # Use CandidateForm for validation, but patch required fields for import
            form = CandidateForm(form_data)
            for f in ['district', 'village']:
                if f in form.fields:
                    form.fields[f].required = False
            if not form.is_valid():
                error_list = '; '.join([f"{k}: {v[0]}" for k, v in form.errors.items()])
                errors.append(f"Row {idx}: {error_list}")
                continue
            # Convert date fields in form.cleaned_data from DD/MM/YYYY string to date objects
            from datetime import datetime
            for date_field in ['date_of_birth', 'start_date', 'finish_date', 'assessment_date']:
                val = form.cleaned_data.get(date_field)
                if isinstance(val, str) and val:
                    try:
                        form.cleaned_data[date_field] = datetime.strptime(val, '%d/%m/%Y').date()
                    except Exception:
                        pass  # Let model validation handle invalid dates
            # Duplicate check: skip if candidate with same name, dob, gender, and assessment_center exists
            exists = Candidate.objects.filter(
                full_name=form.cleaned_data['full_name'],
                date_of_birth=form.cleaned_data['date_of_birth'],
                gender=form.cleaned_data['gender'],
                assessment_center=form.cleaned_data['assessment_center']
            ).exists()
            if exists:
                print(f"[DEBUG] Row {idx} SKIPPED: Duplicate candidate '{form.cleaned_data['full_name']}' with same DOB, gender, and center.")
                errors.append(f"Row {idx}: Candidate '{form_data['full_name']}' with same DOB, gender, and center already exists. Skipped.")
                continue
            candidate = form.save(commit=False)
            candidate.reg_number = None  # Regenerate
            # Attach image
            img_path = os.path.join(tmp_dir, img_name)
            if not os.path.exists(img_path):
                print(f"[DEBUG] Row {idx} SKIPPED: Image file '{img_name}' not found after extraction.")
                errors.append(f"Row {idx}: Image file '{img_name}' not found after extraction.")
                continue
            from PIL import Image
            import io
            # Open and process the image
            with open(img_path, 'rb') as img_file:
                img = Image.open(img_file)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                from PIL import Image
                resample_method = getattr(Image, 'Resampling', Image).LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
                img = img.resize((300, 400), resample=resample_method)
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=80, optimize=True)
                buffer.seek(0)
                candidate.passport_photo.save(
                    os.path.splitext(img_name)[0] + '.jpg',
                    File(buffer),
                    save=False
                )
            candidate.save()
            created += 1
            print(f"[DEBUG] Row {idx} IMPORTED: Candidate '{candidate.full_name}' saved.")
    success_message = None
    if created > 0:
        success_message = f"{created} candidate{'s' if created != 1 else ''} imported successfully."
    return render(request, 'candidates/import_dual.html', {
        'errors': errors,
        'imported_count': created,
        'success_message': success_message
    })

@login_required
def candidate_import_template(request):
    """
    Serve an Excel template for candidate import including all required fields and a sample row.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Candidates"
    # Define headers (excluding RegNo and images)
    headers = [
        'full_name', 'gender', 'nationality', 'date_of_birth', 'occupation', 'registration_category',
        'assessment_center', 'entry_year', 'intake', 'start_date', 'finish_date', 'assessment_date'
    ]
    ws.append(headers)
    # Add a sample row
    sample_row = [
        'Jane Doe', 'F', 'Ugandan', '20/06/2000', 'OCC001', 'modular', 'CTR001', '2025', 'Jan', '01/01/2025', '31/12/2025', '15/06/2025'
    ]
    ws.append(sample_row)
    # Add notes row (for user guidance)
    ws.append([
        'Sample: Use DD/MM/YYYY for all dates. Use occupation code and center code as in system. RegNo will be generated.'
    ] + [''] * (len(headers)-1))
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        wb.save(tmp.name)
        tmp.seek(0)
        data = tmp.read()
    response = HttpResponse(data, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="candidate_import_template.xlsx"'
    os.unlink(tmp.name)
    return response

@login_required
def candidate_import(request):
    """
    Handle GET (show import page) and POST (process Excel upload) for candidate import.
    """
    if request.method == 'GET':
        return render(request, 'candidates/import.html')

    # POST: process uploaded Excel
    file = request.FILES.get('excel_file')
    errors = []
    created = 0
    if not file:
        errors.append('No file uploaded.')
        return render(request, 'candidates/import.html', {'errors': errors, 'imported_count': 0})
    try:
        wb = openpyxl.load_workbook(file)
        ws = wb.active
    except Exception:
        errors.append('Invalid Excel file.')
        return render(request, 'candidates/import.html', {'errors': errors, 'imported_count': 0})

    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    expected_headers = [
        'full_name', 'gender', 'nationality', 'date_of_birth', 'occupation', 'registration_category',
        'assessment_center', 'entry_year', 'intake', 'start_date', 'finish_date', 'assessment_date'
    ]
    if headers != expected_headers:
        errors.append('Excel headers do not match template. Please download the latest template.')
        return render(request, 'candidates/import.html', {'errors': errors, 'imported_count': 0})

    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if all(cell is None for cell in row):
            continue  # skip empty rows
        data = dict(zip(headers, row))
        # Convert and clean data for import
        form_data = data.copy()
        # Dates: convert DD/MM/YYYY to date objects
        for date_field in ['date_of_birth', 'start_date', 'finish_date', 'assessment_date']:
            val = form_data.get(date_field)
            if val:
                try:
                    form_data[date_field] = datetime.strptime(str(val), '%d/%m/%Y').date()
                except Exception:
                    errors.append(f"Row {idx}: Invalid date format in '{date_field}'. Use DD/MM/YYYY.")
                    continue
        # Nationality: must be a valid country name (case-insensitive)
        from django_countries import countries
        nat_val = form_data.get('nationality', '')
        if not isinstance(nat_val, str):
            nat_val = str(nat_val)
        nat_val = nat_val.strip()
        valid_countries = [c[0].lower() for c in countries] + [c[1].lower() for c in countries]
        if nat_val.lower() not in valid_countries:
            errors.append(f"Row {idx}: Nationality '{form_data.get('nationality')}' is not a valid country. Please use a country name from the dropdown.")
            continue
        # Store as country name (display value)
        for code, name in countries:
            if nat_val.lower() in (code.lower(), name.lower()):
                form_data['nationality'] = name
                break
        # Occupation and assessment center: lookup by code
        occ_code = str(form_data.get('occupation')) if form_data.get('occupation') is not None else ''
        center_code = str(form_data.get('assessment_center')) if form_data.get('assessment_center') is not None else ''
        try:
            form_data['occupation'] = Occupation.objects.get(code=occ_code).id
        except Exception:
            errors.append(f"Row {idx}: Invalid occupation code '{occ_code}'.")
            continue
        try:
            form_data['assessment_center'] = AssessmentCenter.objects.get(center_number=center_code).id
        except Exception:
            errors.append(f"Row {idx}: Invalid assessment center code '{center_code}'.")
            continue
        # District and village: optional for import
        for loc_field, model_cls in [('district', District), ('village', Village)]:
            val = form_data.get(loc_field)
            if val:
                obj = model_cls.objects.filter(name__iexact=str(val).strip()).first()
                form_data[loc_field] = obj.id if obj else None
            else:
                form_data[loc_field] = None
        # Coerce all other values to string except dates and foreign keys
        for k in form_data:
            if k not in ['date_of_birth', 'start_date', 'finish_date', 'assessment_date', 'occupation', 'assessment_center', 'district', 'village']:
                v = form_data[k]
                if v is not None:
                    form_data[k] = str(v)
        # Remove reg_number if present
        form_data.pop('reg_number', None)
        # Use CandidateForm for validation, but patch required fields for import
        form = CandidateForm(form_data)
        for f in ['district', 'village']:
            if f in form.fields:
                form.fields[f].required = False
        if not form.is_valid():
            error_list = '; '.join([f"{k}: {v[0]}" for k, v in form.errors.items()])
            errors.append(f"Row {idx}: {error_list}")
            continue
        candidate = form.save(commit=False)
        candidate.reg_number = None  # Regenerate
        candidate.save()
        created += 1
    return render(request, 'candidates/import.html', {
        'errors': errors,
        'imported_count': created
    })

from django.views.decorators.http import require_POST

@require_POST
def bulk_candidate_modules(request):
    import json
    from .models import Candidate, Module, Level
    try:
        data = json.loads(request.body.decode()) if request.body else request.POST
        ids = data.get('candidate_ids')
        if isinstance(ids, str):
            ids = ids.split(',')
        candidate_ids = [int(i) for i in ids if str(i).isdigit()]
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

    candidates = Candidate.objects.filter(id__in=candidate_ids)
    if not candidates.exists():
        return JsonResponse({'success': False, 'error': 'No candidates found.'}, status=400)

    occupations = set(c.occupation_id for c in candidates)
    regcats = set(c.registration_category for c in candidates)
    print("[DEBUG] Candidate IDs:", candidate_ids)
    print("[DEBUG] Occupations:", occupations)
    print("[DEBUG] Registration categories:", regcats)
    for c in candidates:
        print(f"[DEBUG] Candidate {c.id}: occupation_id={c.occupation_id}, registration_category={c.registration_category!r}")
    if len(occupations) != 1 or len(regcats) != 1 or list(regcats)[0] != 'Modular':
        return JsonResponse({'success': False, 'error': 'All candidates must be Modular and have the same occupation.'}, status=400)

    occupation_id = occupations.pop()
    occupation = Occupation.objects.get(id=occupation_id)
    level_name = f"Level 1 {occupation.code}"
    level = Level.objects.filter(name=level_name, occupation_id=occupation_id).first()
    print(f"[DEBUG] Occupation: {occupation.name} ({occupation.code}), Looking for level: '{level_name}', Found: {level.id if level else None}")
    if not level:
        return JsonResponse({'success': False, 'error': 'Level 1 not found.'}, status=400)
    modules = Module.objects.filter(occupation_id=occupation_id, level=level)
    module_list = [{'id': m.id, 'name': m.name, 'code': getattr(m, 'code', '')} for m in modules]
    print(f"[DEBUG] Returning module_list: {module_list}")
    return JsonResponse({'success': True, 'modules': module_list, 'level_id': level.id})

@login_required
@require_POST
def bulk_candidate_action(request):
    import json
    try:
        data = json.loads(request.body.decode()) if request.body else request.POST
        print(f"[DEBUG] bulk_candidate_action raw data: {data}")
        action = data.get('action')
        ids = data.get('candidate_ids')
        module_ids = data.get('module_ids')
        level_id = data.get('level_id')
        paper_ids = data.get('paper_ids')
        print(f"[DEBUG] action: {action}, candidate_ids: {ids}, module_ids: {module_ids}, level_id: {level_id}, paper_ids: {paper_ids}")
        if isinstance(ids, str):
            ids = ids.split(',')
        candidate_ids = [int(i) for i in ids if str(i).isdigit()]
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

    candidates = Candidate.objects.filter(id__in=candidate_ids)
    if not candidates.exists():
        return JsonResponse({'success': False, 'error': 'No candidates found.'}, status=400)

    if action == 'enroll':
        # Bulk enrollment for formal/informal/worker's pas/modular
        level_id = data.get('level_id')
        paper_ids = data.get('paper_ids', [])
        module_ids = data.get('module_ids', [])
        assessment_series_id = data.get('assessment_series_id')
    
        # Enforce same occupation and regcat for all candidates
        occupations = set(c.occupation_id for c in candidates)
        regcats = set((c.registration_category or '').strip().lower() for c in candidates)
        if len(occupations) != 1 or len(regcats) != 1:
            return JsonResponse({'success': False, 'error': 'All candidates must have the same occupation and registration category to enroll together.'}, status=400)
    
        regcat = regcats.pop()
    
        # Validate Assessment Series selection
        if not assessment_series_id:
            return JsonResponse({'success': False, 'error': 'Assessment Series is required for bulk enrollment.'}, status=400)
    
        try:
            assessment_series = AssessmentSeries.objects.get(id=assessment_series_id)
        except AssessmentSeries.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid Assessment Series selected.'}, status=400)
    
        from .models import Level, Module, Paper, CandidateLevel, CandidateModule, CandidatePaper
        enrolled = 0
    
         # --- FORMAL ---
        if regcat == 'formal':
            if not level_id:
                return JsonResponse({'success': False, 'error': 'Level is required.'})
            level = Level.objects.filter(id=level_id).first()
            if not level:
                return JsonResponse({'success': False, 'error': 'Invalid level.'})
            for c in candidates:
                CandidateLevel.objects.get_or_create(candidate=c, level=level)
                # Update candidate's assessment series
                c.assessment_series = assessment_series
                c.save()
                enrolled += 1
            return JsonResponse({'success': True, 'message': f'Enrolled {enrolled} candidates in {level.name}.'})
        
        # --- WORKER'S PAS / INFORMAL ---
        elif regcat in ['informal', "worker's pas", "workers pas"]:
            if not level_id:
                return JsonResponse({'success': False, 'error': 'Level is required.'})
            level = Level.objects.filter(id=level_id).first()
            if not level:
                return JsonResponse({'success': False, 'error': 'Invalid level.'})
            for c in candidates:
                CandidateLevel.objects.get_or_create(candidate=c, level=level)
                # Update candidate's assessment series
                c.assessment_series = assessment_series
                c.save()
                enrolled += 1
            # Assign selected papers (one per module)
            if paper_ids:
                papers = Paper.objects.filter(id__in=paper_ids).select_related('module')
                for c in candidates:
                    for paper in papers:
                        CandidateModule.objects.get_or_create(candidate=c, module=paper.module)
                        CandidatePaper.objects.get_or_create(candidate=c, module=paper.module, paper=paper, level=level)
                return JsonResponse({'success': True, 'message': f'Enrolled {enrolled} candidates in {level.name} and assigned selected papers.'})
            return JsonResponse({'success': True, 'message': f'Enrolled {enrolled} candidates in {level.name}.'})
        
        # --- MODULAR ---
        elif regcat == 'modular':
            if not (1 <= len(module_ids) <= 2):
                return JsonResponse({'success': False, 'error': 'Select 1 or 2 modules.'}, status=400)
            occupation_id = occupations.pop()
            level = Level.objects.filter(id=level_id).first() if level_id else Level.objects.filter(name__icontains='1').first()
            if not level:
                return JsonResponse({'success': False, 'error': 'Level not found.'}, status=400)
            modules = Module.objects.filter(id__in=module_ids, occupation_id=occupation_id, level=level)
            if modules.count() != len(module_ids):
                return JsonResponse({'success': False, 'error': 'Invalid module selection.'}, status=400)
            for c in candidates:
                CandidateModule.objects.filter(candidate=c).delete()
                for m in modules:
                    CandidateModule.objects.create(candidate=c, module=m)
                # Update candidate's assessment series
                c.assessment_series = assessment_series
                c.save()
                enrolled += 1
            return JsonResponse({'success': True, 'message': f'Successfully enrolled {enrolled} candidates in {modules.count()} module(s).'})
        else:
            return JsonResponse({'success': False, 'error': 'Bulk enroll only supported for Formal, Modular, or Worker\'s PAS/Informal registration categories.'}, status=400)
    if action == 'add_regno_photo':
        results = []
        from PIL import Image as PILImage, ImageDraw, ImageFont
        import glob
        from django.core.files import File
        for c in candidates:
            try:
                if not c.passport_photo or not c.reg_number:
                    results.append({'id': c.id, 'success': False, 'error': 'Missing photo or regno.'})
                    continue
                image_path = c.passport_photo.path
                img = PILImage.open(image_path).convert("RGBA")
                draw = ImageDraw.Draw(img)
                # Remove old regno-stamped images
                base_dir = os.path.dirname(image_path)
                base_name = os.path.splitext(os.path.basename(image_path))[0]
                regno_img_pattern = os.path.join(base_dir, f"{base_name}_regno*.png")
                for old in glob.glob(regno_img_pattern):
                    try:
                        os.remove(old)
                    except Exception:
                        pass
                text = c.reg_number
                width, height = img.size
                max_width = width - 32
                # Try to use system TrueType font (DejaVuSans-Bold), fallback to PIL default
                font = None
                truetype_paths = [
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                    '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
                    '/usr/local/share/fonts/DejaVuSans-Bold.ttf',
                    '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
                ]
                font_size = 40
                min_font_size = 10
                for path in truetype_paths:
                    if os.path.exists(path):
                        try:
                            font = ImageFont.truetype(path, size=font_size)
                            break
                        except Exception:
                            font = None
                if font is None:
                    font = ImageFont.load_default()
                    font_size = 12
                    min_font_size = 8
                # Dynamically shrink font size if needed
                while font_size >= min_font_size:
                    try:
                        text_w, text_h = font.getsize(text)
                    except AttributeError:
                        bbox = font.getbbox(text)
                        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    if text_w <= max_width:
                        break
                    font_size -= 2
                    if hasattr(font, 'path'):
                        try:
                            font = ImageFont.truetype(font.path, size=font_size)
                        except Exception:
                            font = ImageFont.load_default()
                            break
                # If still too wide, truncate
                if text_w > max_width:
                    ellipsis = '...'
                    for i in range(len(text)-1, 0, -1):
                        truncated = text[:i] + ellipsis
                        try:
                            text_w, text_h = font.getsize(truncated)
                        except AttributeError:
                            bbox = font.getbbox(truncated)
                            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                        if text_w <= max_width:
                            text = truncated
                            break
                padding_v = max(10, text_h // 4)
                strip_h = text_h + 2 * padding_v
                strip_y = height - strip_h
                overlay = PILImage.new('RGBA', (width, strip_h), (255, 255, 255, 255))  # Solid white
                img = img.convert('RGBA')
                img.alpha_composite(overlay, (0, strip_y))
                draw = ImageDraw.Draw(img)
                x = (width - text_w) // 2
                y = strip_y + (strip_h - text_h) // 2
                draw.text((x, y), text, font=font, fill=(0,0,0,255))
                new_filename = os.path.join(base_dir, f"{base_name}_regno.png")
                img.save(new_filename)
                with open(new_filename, 'rb') as f:
                    c.passport_photo_with_regno.save(os.path.basename(new_filename), File(f), save=True)
                results.append({'id': c.id, 'success': True})
            except Exception as e:
                results.append({'id': c.id, 'success': False, 'error': str(e)})
        return JsonResponse({'success': True, 'results': results})


    elif action == 'regenerate':
        updated = 0
        for c in candidates:
            c.reg_number = None
            c.save()
            updated += 1
        return JsonResponse({'success': True, 'message': f'Regenerated registration numbers for {updated} candidates.'})
    elif action == 'change_reg_cat':
        # Bulk change registration category with validation
        new_cat = data.get('registration_category')
        if not new_cat:
            return JsonResponse({'success': False, 'error': 'No registration category provided.'}, status=400)
        # Validate all candidates
        for candidate in candidates:
            occupation = candidate.occupation
            occ_cat = occupation.category.name if occupation and occupation.category else None
            has_modular = getattr(occupation, 'has_modular', False)
            if new_cat == 'Modular':
                if not has_modular:
                    return JsonResponse({'success': False, 'error': f"Candidate {candidate.full_name} occupation does not support Modular registration."}, status=400)
            elif new_cat == 'Formal':
                if occ_cat != 'Formal':
                    return JsonResponse({'success': False, 'error': f"Candidate {candidate.full_name} occupation is not in the 'Formal' category."}, status=400)
            elif new_cat == 'Informal':
                if occ_cat != "Worker's PAS":
                    return JsonResponse({'success': False, 'error': f"Candidate {candidate.full_name} occupation is not in the 'Worker's PAS' category."}, status=400)
            else:
                return JsonResponse({'success': False, 'error': 'Invalid registration category selected.'}, status=400)
        # If all valid, update
        updated = 0
        for candidate in candidates:
            candidate.registration_category = new_cat
            candidate.reg_number = None
            candidate.save(update_fields=["registration_category", "reg_number"])
            updated += 1
        return JsonResponse({'success': True, 'message': f'Changed registration category for {updated} candidates.'})
    elif action == 'mark_disabled':
        # Bulk mark as disabled
        nature_ids = data.get('nature_of_disability_ids', [])
        if isinstance(nature_ids, str):
            nature_ids = [nature_ids]
        if not isinstance(nature_ids, list):
            return JsonResponse({'success': False, 'error': 'Invalid nature_of_disability_ids.'}, status=400)
        if not nature_ids:
            return JsonResponse({'success': False, 'error': 'Please select at least one nature of disability.'}, status=400)
        from .models import NatureOfDisability
        natures = NatureOfDisability.objects.filter(id__in=nature_ids)
        if natures.count() != len(nature_ids):
            return JsonResponse({'success': False, 'error': 'One or more selected natures are invalid.'}, status=400)
        updated = 0
        for c in candidates:
            c.disability = True
            c.save()
            c.nature_of_disability.set(natures)
            updated += 1
        return JsonResponse({'success': True, 'message': f'Marked {updated} candidates as disabled with selected nature(s).'})
    else:
        return JsonResponse({'success': False, 'error': 'Unknown action.'}, status=400)

from django.urls import reverse
from .models import AssessmentCenter, Candidate, Occupation, AssessmentCenterCategory, Level, Module, Paper, CandidateLevel, CandidateModule, Village, District
from . import views_api
from .forms import AssessmentCenterForm, OccupationForm, ModuleForm, PaperForm, CandidateForm, EnrollmentForm, DistrictForm, VillageForm
from django.contrib import messages 
from reportlab.lib import colors    
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from io import BytesIO
from PIL import Image as PILImage
import os
from django.conf import settings
from django.contrib.auth.decorators import login_required
from .forms import ChangeOccupationForm, ChangeCenterForm
from .models import NatureOfDisability
from .forms import NatureOfDisabilityForm

from django.urls import reverse

@login_required
def natureofdisability_list(request):
    # Get filter parameters
    name = request.GET.get('name', '').strip()
    description = request.GET.get('description', '').strip()
    
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    disabilities = NatureOfDisability.objects.all()
    
    # Apply filters
    if name:
        disabilities = disabilities.filter(name__icontains=name)
    if description:
        disabilities = disabilities.filter(description__icontains=description)
    
    disabilities = disabilities.order_by('name')
    
    # Pagination: 20 per page
    paginator = Paginator(disabilities, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'configurations/natureofdisability_list.html', {
        'page_obj': page_obj,
        'paginator': paginator,
        'filters': {
            'name': name,
            'description': description,
        }
    })

@login_required
def natureofdisability_create(request):
    if request.method == 'POST':
        form = NatureOfDisabilityForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('natureofdisability_list')
    else:
        form = NatureOfDisabilityForm()
    return render(request, 'configurations/natureofdisability_form.html', {'form': form, 'create': True})

@login_required
def natureofdisability_view(request, pk):
    entry = get_object_or_404(NatureOfDisability, pk=pk)
    return render(request, 'configurations/natureofdisability_view.html', {'entry': entry})

@login_required
def natureofdisability_edit(request, pk):
    entry = get_object_or_404(NatureOfDisability, pk=pk)
    if request.method == 'POST':
        form = NatureOfDisabilityForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            return redirect('natureofdisability_view', pk=pk)
    else:
        form = NatureOfDisabilityForm(instance=entry)
    return render(request, 'configurations/natureofdisability_form.html', {'form': form, 'entry': entry, 'edit': True})
@login_required
def dashboard(request):
    logger = logging.getLogger(__name__)
    logger.info(f'Dashboard accessed by user: {request.user}')
    group_names = list(request.user.groups.values_list('name', flat=True))
    
    # Get user department if they are staff (using new Staff model)
    user_department = None
    try:
        staff = Staff.objects.get(user=request.user)  # Changed from SupportStaff to Staff
        user_department = staff.department
    except Staff.DoesNotExist:  # Changed from SupportStaff to Staff
        pass
    
    context = {
        'group_names': group_names,
        'user_department': user_department
    }
    
    return render(request, 'dashboard.html', context)
    
def district_villages_api(request, district_id):
    villages = Village.objects.filter(district_id=district_id).values('id', 'name')
    # returns [{"id": 3, "name": "Ntare"}, ...]
    return JsonResponse(list(villages), safe=False)


def assessment_center_list(request):
    centers = AssessmentCenter.objects.all()
    
    # Get filter parameters
    center_number = request.GET.get('center_number', '').strip()
    center_name = request.GET.get('center_name', '').strip()
    district = request.GET.get('district', '').strip()
    village = request.GET.get('village', '').strip()
    category = request.GET.get('category', '').strip()
    
    # Apply filters
    if center_number:
        centers = centers.filter(center_number__icontains=center_number)
    if center_name:
        centers = centers.filter(center_name__icontains=center_name)
    if district:
        centers = centers.filter(district__name__icontains=district)
    if village:
        centers = centers.filter(village__name__icontains=village)
    if category:
        centers = centers.filter(category_id=category)
    
    # Get all categories for the filter dropdown
    from .models import AssessmentCenterCategory
    categories = AssessmentCenterCategory.objects.all().order_by('name')
    
    # Pagination: 100 per page
    from django.core.paginator import Paginator
    paginator = Paginator(centers, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'assessment_centers/list.html', {
        'centers': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'categories': categories,
    })



def assessment_center_view(request, id):
    center = get_object_or_404(AssessmentCenter, id=id)
    candidates = Candidate.objects.filter(assessment_center=center)
    
    # Get unique occupations from candidates in this assessment center
    occupations = Occupation.objects.filter(candidate__assessment_center=center).distinct()

    return render(request, 'assessment_centers/view.html', {
        'center': center,
        'candidates': candidates,
        'occupations': occupations,
    })





def assessment_center_create(request):
    if request.method == 'POST':
        form = AssessmentCenterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('assessment_center_list')
    else:
        form = AssessmentCenterForm()

    return render(request, 'assessment_centers/create.html', {'form': form})


def edit_assessment_center(request, id):
    center = get_object_or_404(AssessmentCenter, id=id)
    if request.method == 'POST':
        form = AssessmentCenterForm(request.POST, instance=center)
        if form.is_valid():
            form.save()
            return redirect('assessment_center_view', id=center.id)
    else:
        form = AssessmentCenterForm(instance=center)
    
    return render(request, 'assessment_centers/edit.html', {
        'form': form,
        'center': center,
    })

def occupation_list(request):
    occupations = Occupation.objects.select_related('category', 'sector').all()
    code = request.GET.get('code', '').strip()
    name = request.GET.get('name', '').strip()
    category = request.GET.get('category', '').strip()
    sector = request.GET.get('sector', '').strip()

    if code:
        occupations = occupations.filter(code__icontains=code)
    if name:
        occupations = occupations.filter(name__icontains=name)
    if category:
        occupations = occupations.filter(category_id=category)
    if sector:
        occupations = occupations.filter(sector_id=sector)

    # Get all categories and sectors for the filter dropdowns
    from .models import OccupationCategory, Sector
    categories = OccupationCategory.objects.all().order_by('name')
    sectors = Sector.objects.all().order_by('name')

    # Pagination: 100 per page
    from django.core.paginator import Paginator
    paginator = Paginator(occupations, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'occupations/list.html', {
        'occupations': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'categories': categories,
        'sectors': sectors,
    })

def occupation_create(request):
    from .models import Level, OccupationLevel
    error = None
    if request.method == 'POST':
        form = OccupationForm(request.POST)
        if form.is_valid():
            occupation = form.save(commit=False)
            occupation.created_by = request.user
            occupation.updated_by = request.user
            occupation.save()
            # Handle dynamic levels
            num_levels = int(request.POST.get('num_levels', 0))
            level_names = set()
            for i in range(1, num_levels + 1):
                lname = request.POST.get(f'level_name_{i}', '').strip()
                stype = request.POST.get(f'structure_type_{i}', 'modules')
                if not lname:
                    error = 'All level names are required.'
                    break
                if lname in level_names:
                    error = f"Duplicate level name: {lname}"
                    break
                level_names.add(lname)
                # Enforce: If has_modular is checked, Level 1 must be modules
                if occupation.has_modular and lname.lower() == 'level 1' and stype == 'papers':
                    error = "If 'Has Modular' is checked, Level 1 must be set to Modules."
                    break
            if not error:
                for i in range(1, num_levels + 1):
                    lname = request.POST.get(f'level_name_{i}', '').strip()
                    stype = request.POST.get(f'structure_type_{i}', 'modules')
                    if lname:
                        # Compose level name as 'Level X OCC' for clarity
                        occ_code = occupation.code.upper() if occupation.code else ''
                        display_name = f"{lname} {occ_code}" if occ_code and occ_code not in lname else lname
                        level = Level.objects.create(name=display_name, occupation=occupation)
                        OccupationLevel.objects.create(occupation=occupation, level=level, structure_type=stype)
                return redirect('occupation_list')
    else:
        form = OccupationForm()
    return render(request, 'occupations/create.html', {'form': form, 'error': error})
    if request.method == 'POST':
        form = OccupationForm(request.POST)
        if form.is_valid():
            occupation = form.save(commit=False)
            occupation.created_by = request.user
            occupation.updated_by = request.user
            occupation.save()
            # Handle OccupationLevel creation
            selected_level_ids = request.POST.getlist('levels')
            # Enforce restriction: If has_modular is checked, Level 1 must be modules
            has_modular = occupation.has_modular
            level1 = levels.filter(name__icontains='1').first()
            error = None
            for level in levels:
                if str(level.id) in selected_level_ids:
                    if has_modular and level1 and level.id == level1.id:
                        # If user tries to set Level 1 to papers, error
                        if request.POST.get(f'structure_type_{level.id}') == 'papers':
                            error = "If 'Has Modular' is checked, Level 1 must be set to Modules."
                            break
                        structure_type = 'modules'
                    else:
                        structure_type = request.POST.get(f'structure_type_{level.id}', 'modules')
                    OccupationLevel.objects.create(
                        occupation=occupation,
                        level=level,
                        structure_type=structure_type
                    )
            if error:
                occupation.delete()
                return render(request, 'occupations/create.html', {'form': form, 'levels': levels, 'error': error})
            return redirect('occupation_list')
    else:
        form = OccupationForm()
    return render(request, 'occupations/create.html', {'form': form, 'levels': levels})


def occupation_view(request, pk):
    occupation = get_object_or_404(Occupation, pk=pk)
    return render(request, 'occupations/view.html', {'occupation': occupation})


def occupation_detail(request, pk):
    occupation = get_object_or_404(Occupation, pk=pk)
    from .models import OccupationLevel, Module, Paper
    occupation_levels = OccupationLevel.objects.filter(occupation=occupation).select_related('level')
    levels = [ol.level for ol in occupation_levels]

    level_data = []
    for ol in occupation_levels:
        if ol.structure_type == 'modules':
            modules = Module.objects.filter(occupation=occupation, level=ol.level)
            # Attach papers to each module
            for module in modules:
                module_papers = list(Paper.objects.filter(module=module))
                print(f"Module: {module.id} {module.name} has papers: {[p.code for p in module_papers]}")
                module.papers = module_papers
            content = modules
        else:
            content = Paper.objects.filter(occupation=occupation, level=ol.level)
        level_data.append({'level': ol.level, 'structure_type': ol.structure_type, 'content': content})

    return render(request, 'occupations/view.html', {
        'occupation': occupation,
        'levels': levels,
        'level_data': level_data
    })

@login_required
def update_occupation_fees(request, pk):
    """Update fees for all levels in an occupation via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    try:
        occupation = get_object_or_404(Occupation, pk=pk)
        from .models import OccupationLevel, Level
        from decimal import Decimal, InvalidOperation
        
        # Get all levels for this occupation
        occupation_levels = OccupationLevel.objects.filter(occupation=occupation).select_related('level')
        levels = [ol.level for ol in occupation_levels]
        
        updated_count = 0
        
        # Update modular fees (if occupation supports modular)
        if occupation.has_modular and levels:
            # All levels in an occupation share the same modular fees
            try:
                modular_single = request.POST.get('modular_fee_single')
                modular_double = request.POST.get('modular_fee_double')
                
                if modular_single is not None:
                    modular_single = Decimal(str(modular_single))
                if modular_double is not None:
                    modular_double = Decimal(str(modular_double))
                
                # Update modular fees for all levels in this occupation
                for level in levels:
                    if modular_single is not None:
                        level.modular_fee_single = modular_single
                    if modular_double is not None:
                        level.modular_fee_double = modular_double
                    level.save()
                    updated_count += 1
            except (InvalidOperation, ValueError) as e:
                return JsonResponse({'success': False, 'error': f'Invalid modular fee amount: {e}'})
        
        # Check occupation category to determine fee structure
        if occupation.category.name == 'Formal':
            # Update individual level fees for Formal occupations
            for level in levels:
                try:
                    formal_fee = request.POST.get(f'formal_fee_{level.id}')
                    
                    if formal_fee is not None:
                        level.formal_fee = Decimal(str(formal_fee))
                    
                    level.save()
                    
                except (InvalidOperation, ValueError) as e:
                    return JsonResponse({'success': False, 'error': f'Invalid fee amount for {level.name}: {e}'})
        
        elif occupation.category.name == 'Informal' or 'Worker' in occupation.category.name or 'PAS' in occupation.category.name:
            # Update single per-module fee for Worker's PAS occupations
            try:
                workers_pas_module_fee = request.POST.get('workers_pas_module_fee')
                
                if workers_pas_module_fee is not None:
                    module_fee = Decimal(str(workers_pas_module_fee))
                    # Apply the same per-module fee to all levels in this occupation
                    for level in levels:
                        level.workers_pas_module_fee = module_fee
                        level.save()
                        
            except (InvalidOperation, ValueError) as e:
                return JsonResponse({'success': False, 'error': f'Invalid per-module fee amount: {e}'})
        
        # Update candidate fees balances for all candidates in this occupation
        from .models import Candidate
        candidates_updated = 0
        for candidate in Candidate.objects.filter(occupation=occupation, candidatelevel__isnull=False).distinct():
            candidate.update_fees_balance()
            candidates_updated += 1
        
        return JsonResponse({
            'success': True, 
            'message': f'Successfully updated fees for {len(levels)} levels and {candidates_updated} candidate balances'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


#Add Module View

from django.http import JsonResponse
from .models import Occupation, Level, OccupationLevel

@login_required
def api_occupations(request):
    # Returns all occupations as JSON (id, name, has_modular, category)
    occupations = Occupation.objects.select_related('category').all()
    def map_category(cat):
        if not cat:
            return ''
        name = cat.name.lower()
        if name in ['informal', "worker's pas", "workers' pas", "workers pas", "worker pas"]:
            return 'informal'
        if name in ['formal', 'modular']:
            return 'formal'
        return name
    occ_list = [
        {
            'id': o.id,
            'name': o.name,
            'has_modular': o.has_modular,
            'category': map_category(o.category) if o.category else ''
        }
        for o in occupations
    ]
    return JsonResponse(occ_list, safe=False)

def api_levels_for_occupation(request):
    occ_id = request.GET.get('occupation_id')
    levels = []
    if occ_id:
        levels = list(Level.objects.filter(occupation_id=occ_id).values('id', 'name'))
    return JsonResponse({'levels': levels})

def api_levels_for_papers(request):
    """
    Returns levels for occupation, excluding Level 1 for modular occupations
    (since Level 1 is always module-based for modular occupations)
    """
    occ_id = request.GET.get('occupation_id')
    levels = []
    if occ_id:
        try:
            occupation = Occupation.objects.get(id=occ_id)
            level_filter = Level.objects.filter(occupation_id=occ_id)
            
            # For modular occupations, exclude Level 1 (it's always module-based)
            if occupation.has_modular:
                level_filter = level_filter.exclude(name__icontains='Level 1')
            
            levels = list(level_filter.values('id', 'name'))
        except Occupation.DoesNotExist:
            levels = []
    
    return JsonResponse({'levels': levels})

def api_levels(request):
    # Returns all levels as JSON (id, name, occupation_id)
    occ_levels = OccupationLevel.objects.select_related('level', 'occupation').all()
    levels = [
        {'id': ol.level.id, 'name': ol.level.name, 'occupation_id': ol.occupation.id}
        for ol in occ_levels
    ]
    return JsonResponse(levels, safe=False)

@login_required
def api_centers(request):
    # Returns all assessment centers as JSON (id, name)
    from .models import AssessmentCenter
    centers = AssessmentCenter.objects.all().order_by('center_name')
    data = [
        {'id': c.id, 'name': str(c)} for c in centers
    ]
    return JsonResponse(data, safe=False)

# --- AJAX API for dynamic paper creation form ---
from .models import OccupationLevel, Module
from django.views.decorators.http import require_GET

@require_GET
def api_occupation_level_structure(request):
    occupation_id = request.GET.get('occupation_id')
    level_id = request.GET.get('level_id')
    if not occupation_id or not level_id:
        return JsonResponse({'error': 'Missing occupation_id or level_id'}, status=400)
    occ_level = OccupationLevel.objects.filter(occupation_id=occupation_id, level_id=level_id).first()
    if not occ_level:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({'structure_type': occ_level.structure_type})

@require_GET
def api_modules(request):
    occupation_id = request.GET.get('occupation_id')
    level_id = request.GET.get('level_id')
    if not occupation_id:
        return JsonResponse({'modules': []})
    if level_id:
        modules = Module.objects.filter(occupation_id=occupation_id, level_id=level_id)
    else:
        modules = Module.objects.filter(occupation_id=occupation_id)
    data = [{'id': m.id, 'code': m.code, 'name': m.name} for m in modules]
    return JsonResponse({'modules': data})

@require_GET
def api_occupation_category(request):
    occupation_id = request.GET.get('occupation_id')
    if not occupation_id:
        return JsonResponse({'error': 'occupation_id is required'})
    
    try:
        occupation = Occupation.objects.select_related('category').get(id=occupation_id)
        return JsonResponse({
            'category_name': occupation.category.name,
            'category_id': occupation.category.id
        })
    except Occupation.DoesNotExist:
        return JsonResponse({'error': 'Occupation not found'})

def module_list(request):
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    # Get current filters from session
    current_filters = request.session.get('module_filters', {})
    
    # Handle filter actions
    if 'apply_filters' in request.GET:
        current_filters = {
            'occupation': request.GET.get('occupation', '').strip(),
            'level': request.GET.get('level', '').strip(),
            'search': request.GET.get('search', '').strip(),
        }
        request.session['module_filters'] = current_filters
    elif 'clear_filters' in request.GET:
        current_filters = {}
        request.session['module_filters'] = {}
    
    # Get items per page from request or default to 25
    items_per_page = int(request.GET.get('items_per_page', 25))
    
    # Base queryset
    modules = Module.objects.select_related('occupation', 'level').all()
    occupations = Occupation.objects.all()
    levels = Level.objects.all()
    
    # Apply filters
    if current_filters.get('occupation'):
        modules = modules.filter(occupation_id=current_filters['occupation'])
    
    if current_filters.get('level'):
        modules = modules.filter(level_id=current_filters['level'])
    
    if current_filters.get('search'):
        search_term = current_filters['search']
        modules = modules.filter(
            Q(name__icontains=search_term) | 
            Q(code__icontains=search_term)
        )
    
    # Order by occupation, level, then name
    modules = modules.order_by('occupation__name', 'level__name', 'name')
    
    # Add filter display names for template
    filter_names = {}
    if current_filters.get('level'):
        try:
            level_obj = Level.objects.get(id=current_filters['level'])
            filter_names['level_name'] = level_obj.name
        except Level.DoesNotExist:
            pass
    
    if current_filters.get('occupation'):
        try:
            occupation_obj = Occupation.objects.get(id=current_filters['occupation'])
            filter_names['occupation_name'] = f"{occupation_obj.code} - {occupation_obj.name}"
        except Occupation.DoesNotExist:
            pass
    
    # Pagination
    paginator = Paginator(modules, items_per_page)
    page_number = request.GET.get('page', 1)
    
    try:
        modules_page = paginator.page(page_number)
    except:
        modules_page = paginator.page(1)
    
    # Merge filters with display names
    current_filters.update(filter_names)
    
    context = {
        'modules': modules_page,
        'occupations': occupations,
        'levels': levels,
        'filters': current_filters,
        'items_per_page': items_per_page,
    }
    
    return render(request, 'modules/list.html', context)

@login_required
def module_create(request):
    if request.method == 'POST':
        form = ModuleForm(request.POST)
        if form.is_valid():
            module = form.save()
            messages.success(request, f'Module "{module.name}" was created successfully.')
            return redirect('module_list')
    else:
        form = ModuleForm()
    return render(request, 'modules/create.html', {'form': form})

@login_required
def module_detail(request, pk):
    module = get_object_or_404(Module, pk=pk)
    return render(request, 'modules/detail.html', {'module': module})

@login_required
def module_edit(request, pk):
    module = get_object_or_404(Module, pk=pk)
    if request.method == 'POST':
        form = ModuleForm(request.POST, instance=module)
        if form.is_valid():
            module = form.save()
            module_url = reverse('module_detail', args=[module.pk])
            success_message = format_html(
                'Module "{}" was updated successfully. <a href="{}">View Details</a>',
                module.name,
                module_url
            )
            messages.success(request, success_message)
            return redirect('module_list')
    else:
        form = ModuleForm(instance=module)
    return render(request, 'modules/edit.html', {
        'form': form,
        'module': module
    })

@login_required
def module_delete(request, pk):
    module = get_object_or_404(Module, pk=pk)
    if request.method == 'POST':
        module.delete()
        messages.success(request, 'Module deleted successfully.')
        return redirect('module_list')
    return render(request, 'modules/delete.html', {'module': module})
    return render(request, 'modules/edit.html', {'form': form, 'module': module})


def paper_list(request):
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    # Get current filters from session
    current_filters = request.session.get('paper_filters', {})
    
    # Handle filter actions
    if 'apply_filters' in request.GET:
        current_filters = {
            'search': request.GET.get('search', '').strip(),
            'occupation': request.GET.get('occupation', '').strip(),
            'level': request.GET.get('level', '').strip(),
        }
        request.session['paper_filters'] = current_filters
    elif 'clear_filters' in request.GET:
        current_filters = {}
        request.session['paper_filters'] = {}
    
    # Get items per page from request or default to 25
    items_per_page = int(request.GET.get('items_per_page', 25))
    
    # Base queryset
    papers = Paper.objects.select_related('level', 'occupation', 'module').all()
    occupations = Occupation.objects.all()
    levels = Level.objects.all()
    
    # Apply filters
    if current_filters.get('search'):
        search_term = current_filters['search']
        papers = papers.filter(
            Q(name__icontains=search_term) | 
            Q(code__icontains=search_term)
        )
    
    if current_filters.get('occupation'):
        papers = papers.filter(occupation_id=current_filters['occupation'])
    
    if current_filters.get('level'):
        papers = papers.filter(level_id=current_filters['level'])
    
    # Order by occupation, level, then name
    papers = papers.order_by('occupation__name', 'level__name', 'name')
    
    # Add filter display names for template
    filter_names = {}
    if current_filters.get('level'):
        try:
            level_obj = Level.objects.get(id=current_filters['level'])
            filter_names['level_name'] = level_obj.name
        except Level.DoesNotExist:
            pass
    
    if current_filters.get('occupation'):
        try:
            occupation_obj = Occupation.objects.get(id=current_filters['occupation'])
            filter_names['occupation_name'] = f"{occupation_obj.code} - {occupation_obj.name}"
        except Occupation.DoesNotExist:
            pass
    
    # Pagination
    paginator = Paginator(papers, items_per_page)
    page_number = request.GET.get('page', 1)
    
    try:
        papers_page = paginator.page(page_number)
    except:
        papers_page = paginator.page(1)
    
    # Merge filters with display names
    current_filters.update(filter_names)
    
    context = {
        'papers': papers_page,
        'occupations': occupations,
        'levels': levels,
        'filters': current_filters,
        'items_per_page': items_per_page,
    }
    
    return render(request, 'papers/list.html', context)

def paper_create(request):
    if request.method == 'POST':
        form = PaperForm(request.POST)
        if form.is_valid():
            paper = form.save()
            return redirect('paper_list')
    else:
        form = PaperForm()
    return render(request, 'papers/create.html', {'form': form})

def paper_detail(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    return render(request, 'papers/detail.html', {'paper': paper})


def paper_edit(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    if request.method == 'POST':
        form = PaperForm(request.POST, instance=paper)
        if form.is_valid():
            paper = form.save()
            paper_url = reverse('paper_detail', args=[paper.pk])
            success_message = format_html(
                'Paper "{}" was updated successfully. <a href="{}">View Details</a>',
                paper.name,
                paper_url
            )
            messages.success(request, success_message)
            return redirect('paper_list')
    else:
        form = PaperForm(instance=paper)
    # Add current module id as data-initial for JS selection
    if paper.module:
        form.fields['module'].widget.attrs['data-initial'] = str(paper.module.id)
    return render(request, 'papers/edit.html', {'form': form, 'paper': paper})


def report_list(request):
    """Main reports dashboard showing available reports"""
    group_names = list(request.user.groups.values_list('name', flat=True))
    return render(request, 'reports/list.html', {'group_names': group_names})

from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepInFrame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from django.conf import settings
import os
from PIL import Image as PILImage

def _create_photo_cell_content(candidate, styles, photo_width=0.8*inch, photo_height=0.8*inch):
    """Creates a list of flowables for the candidate photo cell, including image, name, and details."""
    cell_elements = []
    photo_image = None

    # Photo Styles
    photo_name_style = ParagraphStyle(
        'PhotoName',
        parent=styles['Normal'],
        fontSize=6,
        alignment=TA_CENTER,
        spaceBefore=1,
        leading=6
    )
    photo_detail_style = ParagraphStyle(
        'PhotoDetail',
        parent=styles['Normal'],
        fontSize=6,
        alignment=TA_CENTER,
        spaceBefore=1,
        leading=6
    )

    # Prefer regno-stamped photo if available
    photo_path = None
    if hasattr(candidate, 'passport_photo_with_regno') and candidate.passport_photo_with_regno and hasattr(candidate.passport_photo_with_regno, 'path') and os.path.exists(candidate.passport_photo_with_regno.path):
        photo_path = candidate.passport_photo_with_regno.path
    elif hasattr(candidate, 'passport_photo') and candidate.passport_photo and hasattr(candidate.passport_photo, 'path') and os.path.exists(candidate.passport_photo.path):
        photo_path = candidate.passport_photo.path
    if photo_path:
        try:
            img = PILImage.open(photo_path)
            scale_factor = min(photo_width / img.width, photo_height / img.height)
            scaled_width = img.width * scale_factor
            scaled_height = img.height * scale_factor
            if img.mode != 'RGB':
                img = img.convert('RGB')
                temp_path = os.path.join(settings.MEDIA_ROOT, f'temp_photo_cell_{candidate.id}.jpg')
                img.save(temp_path, 'JPEG')
                photo_image = Image(temp_path, width=scaled_width, height=scaled_height)
            else:
                photo_image = Image(photo_path, width=scaled_width, height=scaled_height)
        except Exception as e:
            print(f"Error processing photo for cell (ID: {candidate.id}): {e}")
            photo_image = Paragraph("[No Photo]", photo_detail_style)
    else:
        photo_image = Paragraph("[No Photo]", photo_detail_style)
    
    cell_elements.append(photo_image)
    # cell_elements.append(Paragraph(candidate.reg_number.upper(), photo_name_style))
    
    occupation_code = candidate.occupation.code if candidate.occupation else 'N/A'
    reg_category_short = candidate.registration_category.upper() if candidate.registration_category else 'N/A'
    # cell_elements.append(Paragraph(f"{reg_category_short} | {occupation_code}", photo_detail_style))
    
    return cell_elements

@login_required
def generate_album(request):
    logger = logging.getLogger(__name__)
    logger.info("generate_album view started.")

    centers = AssessmentCenter.objects.all()
    occupations = Occupation.objects.all()
    levels = Level.objects.all() # Though not directly used in this version's header/table structure as per screenshot

    if request.method == 'POST':
        try:
            center_id = request.POST.get('center')
            occupation_id = request.POST.get('occupation')
            reg_category_form = request.POST.get('registration_category', '') # Name from form
            level_id = request.POST.get('level') # Keep for filtering logic if needed
            assessment_month_str = request.POST.get('assessment_month')
            assessment_year_str = request.POST.get('assessment_year')

            logger.info(f"POST request received with params: center={center_id}, occupation={occupation_id}, category={reg_category_form}, level={level_id}, month={assessment_month_str}, year={assessment_year_str}")


            if not all([center_id, occupation_id, reg_category_form, assessment_month_str, assessment_year_str]):
                logger.warning("Missing required filter parameters.")
                return HttpResponse("All filter parameters are required.", status=400)

            try:
                assessment_month = int(assessment_month_str)
                assessment_year = int(assessment_year_str)
                center = AssessmentCenter.objects.get(id=center_id)
                occupation = Occupation.objects.get(id=occupation_id)
            except (ValueError, AssessmentCenter.DoesNotExist, Occupation.DoesNotExist) as e:
                logger.error(f"Invalid parameter provided: {e}")
                return HttpResponse(f"Invalid parameter: {e}", status=400)

            # Candidate Querying
            logger.info("Querying candidates...")
            candidate_qs = Candidate.objects.select_related('occupation', 'assessment_center').filter(
                assessment_center=center,
                occupation=occupation,
                registration_category__iexact=reg_category_form, # Use form value for filtering
                assessment_date__year=assessment_year,
                assessment_date__month=assessment_month
            ).order_by('reg_number')

            # Optional level filtering (if applicable for the registration category)
            if reg_category_form.lower() in ['formal', 'informal', 'workers pas'] and level_id:
                logger.info(f"Filtering by level_id: {level_id}")
                candidate_qs = candidate_qs.filter(
                    id__in=CandidateLevel.objects.filter(level_id=level_id).values('candidate_id')
                )
            
            final_candidates = list(candidate_qs)
            logger.info(f"Found {len(final_candidates)} candidates.")
            if not final_candidates:
                logger.warning("No candidates found matching the criteria.")
                return HttpResponse("No candidates found matching the criteria.", status=404)

            # PDF Generation
            logger.info("Starting PDF generation...")
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                                    title="UVTAB",
                                    rightMargin=0.4*inch, leftMargin=0.4*inch,
                                    topMargin=0.3*inch, bottomMargin=0.3*inch)
            elements = []
            styles = getSampleStyleSheet()

            # Define Styles
            contact_style = ParagraphStyle('ContactInfo', parent=styles['Normal'], fontSize=9, leading=11)
            board_title_style = ParagraphStyle('BoardTitle', parent=styles['h1'], fontSize=14, alignment=TA_CENTER, spaceBefore=6, spaceAfter=6, textColor=colors.HexColor('#000000'))
            report_title_style = ParagraphStyle('ReportTitle', parent=styles['h2'], fontSize=12, alignment=TA_CENTER, spaceAfter=4)
            center_info_style = ParagraphStyle('CenterInfo', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, spaceAfter=10)
            details_label_style = ParagraphStyle('DetailsLabel', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT, spaceAfter=2)
            
            # 1. Header Section
            logger.info("Generating PDF header.")
            # Top contact line
            logo_path = None
            possible_paths = [
                os.path.join(settings.BASE_DIR, 'eims', 'static', 'images', 'uvtab logo.png'),
                os.path.join(settings.BASE_DIR, 'static', 'images', 'uvtab logo.png'),
                os.path.join(settings.BASE_DIR, 'emis', 'static', 'images', 'uvtab logo.png'),
                os.path.join(settings.STATIC_ROOT or '', 'images', 'uvtab logo.png') # Check collected static too
            ]
            for path in possible_paths:
                if path and os.path.exists(path):
                    logo_path = path
                    logger.info(f"Found logo at: {logo_path}")
                    break
            
            if not logo_path:
                logger.warning("Logo image not found.")

            logo_image = Image(logo_path, width=1*inch, height=1*inch) if logo_path else Paragraph(" ", styles['Normal'])

            header_table_data = [
                [Paragraph("P.O.Box 1499<br/>Email: info@uvtab.go.ug", contact_style), 
                 logo_image, 
                 Paragraph("Tel: 256 414 289786", contact_style)]
            ]
            header_table = Table(header_table_data, colWidths=[3*inch, 3*inch, 3*inch]) # Adjusted for landscape
            header_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (0,0), (0,0), 'LEFT'),
                ('ALIGN', (1,0), (1,0), 'CENTER'),
                ('ALIGN', (2,0), (2,0), 'RIGHT'),
            ]))
            elements.append(header_table)
            elements.append(Spacer(1, 0.1*inch))

            elements.append(Paragraph("UGANDA VOCATIONAL AND TECHNICAL ASSESSMENT BOARD", board_title_style))
            
            month_names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
            assessment_period_str = f"{month_names[assessment_month-1]} {assessment_year}"
            elements.append(Paragraph(f"Registered Candidates for {assessment_period_str} Assessment", report_title_style))
            elements.append(Paragraph(f"Assessment Center: {center.center_number} - {center.center_name}", center_info_style))
            
            # Occupation Details Section (below Assessment Center info)
            elements.append(Paragraph(f"Occupation Name: {occupation.name.upper()}<br/>Occupation Code: {occupation.code.upper()}<br/>Registration Category: {reg_category_form.upper()}{(' - Level: ' + Level.objects.get(id=level_id).name.upper()) if reg_category_form.lower() in ['formal', 'informal'] and level_id else ''}", details_label_style))
            elements.append(Spacer(1, 0.2*inch))

            # 2. Candidate Table
            logger.info("Generating candidate table.")
            table_header_style = ParagraphStyle('TableHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, alignment=TA_CENTER, textColor=colors.white)
            table_cell_style = ParagraphStyle('TableCell', parent=styles['Normal'], fontSize=8, alignment=TA_LEFT, leading=10)
            table_cell_center_style = ParagraphStyle('TableCellCenter', parent=table_cell_style, alignment=TA_CENTER)

            data = []
            # Table Headers
            header_row = [Paragraph(h, table_header_style) for h in ['S/N', 'PHOTO', 'REG NO.', 'FULL NAME', 'OCCUPATION', 'REG TYPE', 'SIGNATURE']]
            data.append(header_row)

            for i, cand in enumerate(final_candidates):
                logger.debug(f"Processing candidate {i+1}: {cand.reg_number}")
                photo_cell_flowables = _create_photo_cell_content(cand, styles)
                row = [
                    Paragraph(str(i + 1), table_cell_center_style),
                    photo_cell_flowables, # This is a list of flowables
                    Paragraph(cand.reg_number or 'N/A', table_cell_style),
                    Paragraph(cand.full_name.upper(), table_cell_style),
                    Paragraph(cand.occupation.name.upper() if cand.occupation else 'N/A', table_cell_style),
                    Paragraph(cand.registration_category.upper() if cand.registration_category else 'N/A', table_cell_style),
                    Paragraph('', table_cell_style) # Empty for signature
                ]
                data.append(row)
            
            # Column widths (adjust as needed, total should be around 10.2 inch for landscape letter with 0.4 margins)
            col_widths = [0.4*inch, 1.3*inch, 1.8*inch, 2.7*inch, 1.5*inch, 1.2*inch, 1.3*inch] 

            candidate_table = Table(data, colWidths=col_widths, repeatRows=1)
            candidate_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4F81BD')), # Header background
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,0), 'CENTER'), # Header text alignment
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), # All cells middle aligned vertically
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 8),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('TOPPADDING', (0,0), (-1,0), 6),
                
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('BOX', (0,0), (-1,-1), 1, colors.black),
                
                # Data row styling
                ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,1), (-1,-1), 8),
                ('ALIGN', (0,1), (0,-1), 'CENTER'), # S/N centered
                ('ALIGN', (1,1), (1,-1), 'CENTER'), # Photo centered horizontally
                ('ALIGN', (2,1), (2,-1), 'LEFT'), # Reg No left
                ('ALIGN', (3,1), (3,-1), 'LEFT'), # Full Name left
                ('ALIGN', (4,1), (4,-1), 'LEFT'), # Occupation left
                ('ALIGN', (5,1), (5,-1), 'CENTER'), # Reg Type center
                ('TOPPADDING', (0,1), (-1,-1), 2), # Reduced padding
                ('BOTTOMPADDING', (0,1), (-1,-1), 2), # Reduced padding
            ]))
            elements.append(candidate_table)

            # --- First pass to count total pages ---
            logger.info("Starting first pass for page count.")
            # Use a deep copy of elements for the first pass to avoid consuming them
            first_pass_elements = copy.deepcopy(elements)
            count_buffer = BytesIO() # Temporary buffer for counting
            # Ensure all SimpleDocTemplate parameters match the final document for accurate page count
            count_doc = SimpleDocTemplate(count_buffer, pagesize=landscape(letter),
                                          rightMargin=0.4*inch, leftMargin=0.4*inch,
                                          topMargin=0.3*inch, bottomMargin=0.3*inch)
            
            def _count_pages_callback(canvas, doc): # Minimal callback for the first pass
                pass # We only care about the page count

            try:
                count_doc.build(first_pass_elements, onFirstPage=_count_pages_callback, onLaterPages=_count_pages_callback)
                total_pages = count_doc.page
                logger.info(f"Page count successful. Total pages: {total_pages}")
            except Exception as e:
                # Handle potential errors during the first pass, though less likely with a simple callback
                logger.error(f"Error during page count pass: {e}", exc_info=True)
                # Fallback to simple page numbering if counting fails
                total_pages = 0 # Indicates an issue, or use a flag

            # --- End of first pass ---

            # Helper function to add page numbers (includes total_pages if available)
            def _add_page_numbers(canvas, doc, total_pages_count):
                canvas.saveState()
                canvas.setFont('Helvetica', 9)
                if total_pages_count > 0:
                    page_number_text = f"Page {doc.page} of {total_pages_count}"
                else:
                    page_number_text = f"Page {doc.page}" # Fallback if total_pages is not available
                
                page_width = doc.pagesize[0] # doc.pagesize[0] is width for landscape
                canvas.drawCentredString(page_width / 2.0, 0.2 * inch, page_number_text)
                canvas.restoreState()

            # Build PDF (Second pass - actual PDF generation with 'Page X of Y')
            # The original 'doc', 'buffer', and 'elements' are used for the final output.
            logger.info("Starting second pass for final PDF build.")
            doc.build(elements, 
                      onFirstPage=lambda c, d: _add_page_numbers(c, d, total_pages), 
                      onLaterPages=lambda c, d: _add_page_numbers(c, d, total_pages))
            buffer.seek(0)
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="candidate_album_{center.center_number}_{occupation.code}_{assessment_year}_{assessment_month}.pdf"'
            logger.info("PDF generated successfully. Returning response.")
            return response
        except Exception as e:
            logger.critical(f"Unhandled exception in generate_album view: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return HttpResponse(f"Error generating PDF: {e}", status=500)

    # GET request or if form not submitted properly
    logger.info("GET request received, rendering form.")
    return render(request, 'reports/albums.html', {
        'centers': centers,
        'occupations': occupations,
        'levels': levels,
        'form_action': reverse('generate_album')
    })

def add_module(request, level_id):
    level = get_object_or_404(Level, id=level_id)
    occupation = level.occupation  # If Level has ForeignKey to Occupation

    if request.method == 'POST':
        form = ModuleForm(request.POST)
        if form.is_valid():
            module = form.save(commit=False)
            module.level = level
            module.occupation = occupation
            module.save()
            return redirect('occupation_detail', pk=occupation.pk)
    else:
        form = ModuleForm()

    return render(request, 'modules/create.html', {'form': form, 'level': level})


# Add Paper View
def add_paper(request, level_id):
    level = get_object_or_404(Level, id=level_id)
    occupation = level.occupation  # If Level has ForeignKey to Occupation

    if request.method == 'POST':
        form = PaperForm(request.POST)
        if form.is_valid():
            paper = form.save(commit=False)
            paper.level = level
            paper.occupation = occupation
            paper.save()
            return redirect('occupation_detail', pk=occupation.pk)
    else:
        form = PaperForm()

    return render(request, 'papers/create.html', {'form': form, 'level': level})

from django.core.paginator import Paginator

@login_required
def candidate_list(request):
    # Get current filters from session or initialize
    current_filters = request.session.get('candidate_filters', {})
    
    # Handle URL-based filters (for statistics clickable links)
    url_filters = {}
    if request.GET:
        # Extract filters from URL parameters
        url_filters = {
            'reg_number': request.GET.get('reg_number', '').strip(),
            'search': request.GET.get('search', '').strip(),
            'occupation': request.GET.get('occupation', '').strip(),
            'registration_category': request.GET.get('registration_category', '').strip(),
            'assessment_center': request.GET.get('assessment_center', '').strip(),
            'gender': request.GET.get('gender', '').strip(),
            'disability': request.GET.get('disability', '').strip(),
            'assessment_year': request.GET.get('assessment_year', '').strip(),
            'assessment_month': request.GET.get('assessment_month', '').strip(),
        }
        # Remove empty values
        url_filters = {k: v for k, v in url_filters.items() if v}
        
        # If URL filters exist, use them and update session
        if url_filters:
            current_filters.update(url_filters)
            request.session['candidate_filters'] = current_filters

    # If form is submitted, update filters in session
    if 'apply_filters' in request.GET:
        current_filters = {
            'reg_number': request.GET.get('reg_number', '').strip(),
            'search': request.GET.get('search', '').strip(),
            'occupation': request.GET.get('occupation', '').strip(),
            'registration_category': request.GET.get('registration_category', '').strip(),
            'assessment_center': request.GET.get('assessment_center', '').strip(),
        }
        # Remove empty values so they don't clutter the URL
        current_filters = {k: v for k, v in current_filters.items() if v}
        request.session['candidate_filters'] = current_filters
        # Redirect to a clean URL. The view will then use session filters.
        return redirect('candidate_list')

    # If reset is requested, clear filters and redirect
    if 'reset_filters' in request.GET:
        if 'candidate_filters' in request.session:
            del request.session['candidate_filters']
        return redirect('candidate_list')

    candidates = Candidate.objects.select_related('occupation', 'assessment_center').order_by('-created_at')
    
    # Restrict for Center Representatives
    if request.user.groups.filter(name='CenterRep').exists():
        from .models import CenterRepresentative
        try:
            center_rep = CenterRepresentative.objects.get(user=request.user)
            candidates = candidates.filter(assessment_center=center_rep.center)
        except CenterRepresentative.DoesNotExist:
            candidates = candidates.none()

    # Enhanced filtering logic from session filters
    if current_filters.get('reg_number'):
        candidates = candidates.filter(reg_number__icontains=current_filters.get('reg_number'))
    if current_filters.get('search'):
        candidates = candidates.filter(full_name__icontains=current_filters.get('search'))
    if current_filters.get('occupation'):
        candidates = candidates.filter(occupation_id=current_filters.get('occupation'))
    if current_filters.get('registration_category'):
        candidates = candidates.filter(registration_category=current_filters.get('registration_category'))
    if current_filters.get('assessment_center'):
        candidates = candidates.filter(assessment_center_id=current_filters.get('assessment_center'))
    
    # NEW: Additional filters for statistics integration
    if current_filters.get('gender'):
        candidates = candidates.filter(gender=current_filters.get('gender'))
    if current_filters.get('disability'):
        # Convert string to boolean
        disability_filter = current_filters.get('disability').lower() == 'true'
        candidates = candidates.filter(disability=disability_filter)
    if current_filters.get('assessment_year'):
        candidates = candidates.filter(assessment_date__year=current_filters.get('assessment_year'))
    if current_filters.get('assessment_month'):
        candidates = candidates.filter(assessment_date__month=current_filters.get('assessment_month'))

    def build_candidate_filter_url(base_filters=None, **additional_filters):
        """Build a URL for filtering candidates with given parameters"""
        from django.urls import reverse
        import urllib.parse
        
        filters = base_filters.copy() if base_filters else {}
        filters.update(additional_filters)
    
        # Remove empty values
        filters = {k: v for k, v in filters.items() if v}
    
        if filters:
            query_string = urllib.parse.urlencode(filters)
            return f"{reverse('candidate_list')}?{query_string}"
        else:
            return reverse('candidate_list')

    
    from .models import Occupation, AssessmentCenter
    occupations = Occupation.objects.all()
    centers = AssessmentCenter.objects.all()

    # Pagination: 100 per page
    paginator = Paginator(candidates, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    import urllib
    filter_params = urllib.parse.urlencode(current_filters)

    from .models import NatureOfDisability
    return render(request, 'candidates/list.html', {
        'candidates': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_candidates': paginator.count,
        'occupations': occupations,
        'centers': centers,
        'filters': current_filters,
        'filter_params': filter_params,
        'nature_of_disabilities': NatureOfDisability.objects.all(),
    })


from django.template.loader import render_to_string

from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .models import Candidate, Result, Module, CandidateLevel, CandidateModule, OccupationLevel
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
import os
from django.conf import settings

import qrcode

@login_required
def generate_transcript(request, id):
    """
    Generate a PDF transcript for a level-module-based candidate, following strict eligibility logic. Adds transcript serial and QR code.
    """
    candidate = Candidate.objects.select_related('occupation', 'assessment_center').get(id=id)
    reg_cat = getattr(candidate, 'registration_category', '').lower()

    # --- Transcript Serial Number ---
    org_code = candidate.assessment_center.center_number if candidate.assessment_center and hasattr(candidate.assessment_center, 'center_number') else "ORG"
    occ_code = candidate.occupation.code if candidate.occupation and hasattr(candidate.occupation, 'code') else "XX"
    serial_number = f"{org_code}/TR {occ_code}{str(candidate.id).zfill(6)}"

    # --- QR Code Data ---
    level_name = getattr(getattr(candidate, 'level', None), 'name', '')
    if not level_name:
        cl = CandidateLevel.objects.filter(candidate=candidate).first()
        if cl and cl.level:
            level_name = cl.level.name
    qr_data = {
        "name": candidate.full_name,
        "regno": candidate.reg_number,
        "occupation": candidate.occupation.name if candidate.occupation else '',
        "level": level_name,
        "serial": serial_number
    }
    import json
    qr_str = json.dumps(qr_data, ensure_ascii=False)
    qr_img = qrcode.make(qr_str)
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    qr_rl_img = RLImage(qr_buffer, width=1.0*inch, height=1.0*inch)
    qr_rl_img.hAlign = 'LEFT'

    # Only allow for module-based levels
    occ_level = None
    level = getattr(candidate, 'level', None)
    if not level:
        cl = CandidateLevel.objects.filter(candidate=candidate).first()
        if cl:
            level = cl.level
    # Only allow for module-based levels
    occ_level = None
    level = getattr(candidate, 'level', None)
    if not level:
        cl = CandidateLevel.objects.filter(candidate=candidate).first()
        if cl:
            level = cl.level
    if candidate.occupation and level:
        occ_level = OccupationLevel.objects.filter(occupation=candidate.occupation, level=level).first()
    # PDF generation (image2 style)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            title="Transcript",
                            rightMargin=0.4*inch, leftMargin=0.4*inch,
                            topMargin=0.3*inch, bottomMargin=0.3*inch)
    elements = []
    styles = getSampleStyleSheet()
    normal = styles['Normal']
    normal.fontSize = 10
    normal.leading = 12
    normal.spaceAfter = 0
    normal.spaceBefore = 0
    bold = ParagraphStyle('Bold', parent=normal, fontName='Helvetica-Bold')
    center = ParagraphStyle('Center', parent=normal, alignment=TA_CENTER)
    red_center = ParagraphStyle('RedCenter', parent=center, textColor=colors.red, fontSize=12, spaceAfter=6)
    # PDF generation (image2 style)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            title="Transcript",
                            rightMargin=0.4*inch, leftMargin=0.4*inch,
                            topMargin=0.3*inch, bottomMargin=0.3*inch)
    elements = []
    styles = getSampleStyleSheet()
    normal = styles['Normal']
    normal.fontSize = 10
    normal.leading = 12
    normal.spaceAfter = 0
    normal.spaceBefore = 0
    bold = ParagraphStyle('Bold', parent=normal, fontName='Helvetica-Bold')
    center = ParagraphStyle('Center', parent=normal, alignment=TA_CENTER)
    red_center = ParagraphStyle('RedCenter', parent=center, textColor=colors.red, fontSize=12, spaceAfter=6)

    # 0. Leave space for pre-printed header (about 1.5 inches)
    elements.append(Spacer(1, 1.5*inch))

    # 1. Top Heading (now lower, logic fixed)
    # Always define level_name safely
    level_name = getattr(level, 'name', None)
    if not level_name:
        level_name = str(level) if level else ''
    transcript_heading = ""
    if reg_cat == 'modular':
        transcript_heading = "Modular Transcript"
    elif level_name and level_name.lower() != 'none':
        # Avoid double 'Level' in heading
        if level_name.lower().startswith('level'):
            transcript_heading = f"{level_name} Transcript"
        else:
            transcript_heading = f"Level {level_name} Transcript"
    else:
        transcript_heading = "Transcript"

    # --- Top Row: Transcript Heading (left), QR code, Serial, and Photo (right, stacked) ---
    heading_para = Paragraph(transcript_heading, red_center)
    # Prepare QR code and serial number
    serial_style = ParagraphStyle('SerialSmall', parent=bold, fontSize=8, textColor=colors.blue, alignment=TA_RIGHT)
    serial_para = Paragraph(serial_number, serial_style)
    qr_rl_img.drawWidth = 0.65*inch
    qr_rl_img.drawHeight = 0.65*inch
    qr_rl_img.hAlign = 'RIGHT'

    # Prepare photo
    photo = None
    if getattr(candidate, 'passport_photo', None) and candidate.passport_photo.name:
        try:
            photo_path = candidate.passport_photo.path
            photo = RLImage(photo_path, width=1.0*inch, height=1.2*inch)
            photo.hAlign = 'RIGHT'
        except Exception:
            photo = Spacer(1, 1.2*inch)
    else:
        photo = Spacer(1, 1.2*inch)
    # Stack QR, serial, photo vertically in right col
    right_col = [qr_rl_img, Spacer(1, 0.02*inch), serial_para, Spacer(1, 0.06*inch), photo]
    top_row = Table([
        [heading_para, right_col]
    ], colWidths=[4.5*inch, 1.5*inch], hAlign='RIGHT')
    top_row.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(Spacer(1, 0.18*inch))
    elements.append(top_row)
    elements.append(Spacer(1, 0.035*inch))

    period = candidate.assessment_date.strftime('%d %B %Y') if getattr(candidate, 'assessment_date', None) else ""
    center_name = candidate.assessment_center.center_name if candidate.assessment_center else ""
    center_number = candidate.assessment_center.center_number if candidate.assessment_center else ""
    occupation = candidate.occupation.name if candidate.occupation else ""
    elements.append(Paragraph(f"<b>Occupation :</b> {occupation}", normal))
    elements.append(Paragraph(f"<b>Assessment Period:</b> {period}", normal))
    elements.append(Paragraph(f"<b>Assessment Centre:</b> {center_name}", normal))
    elements.append(Paragraph(f"<b>Centre Number:</b> {center_number}", normal))
    elements.append(Spacer(1, 0.08*inch))

    # 3. Personal data table
    dob = candidate.date_of_birth.strftime('%d %B %Y') if getattr(candidate, 'date_of_birth', None) else ""
    district = candidate.district.name if getattr(candidate, 'district', None) else ""
    # Always display full country name for nationality
    from django_countries import countries
    nationality = candidate.nationality if getattr(candidate, 'nationality', None) else ""
    # If nationality is a 2-letter code, convert to country name
    if nationality and len(nationality) == 2 and nationality.isupper():
        code_to_name = dict(countries)
        nationality = code_to_name.get(nationality, nationality)
    sex = candidate.get_gender_display() if hasattr(candidate, 'get_gender_display') else candidate.gender
    regno = candidate.reg_number
    name = candidate.full_name
    # --- Personal Data Table (image2 style) ---
    personal_table_data = [
        [Paragraph("<b>Name:</b>", normal), name, Paragraph("<b>District of Birth:</b>", normal), district],
        [Paragraph("<b>Date of Birth:</b>", normal), dob, Paragraph("<b>Nationality:</b>", normal), nationality],
        [Paragraph("<b>Sex:</b>", normal), sex, Paragraph("<b>Registration No:</b>", normal), regno],
    ]
    personal_table = Table(personal_table_data, colWidths=[1.1*inch, 1.7*inch, 1.3*inch, 2.0*inch], hAlign='LEFT')
    personal_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BOX', (0,0), (-1,-1), 0.7, colors.black),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0.5),
        ('TOPPADDING', (0,0), (-1,-1), 0.5),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
    ]))
    elements.append(personal_table)
    elements.append(Spacer(1, 0.08*inch))


    # 4. Assessment Result
    elements.append(Paragraph("<b>ASSESSMENT RESULT</b>", center))
    elements.append(Spacer(1, 0.025*inch))

    reg_cat = getattr(candidate, 'registration_category', '').lower()
    transcript_heading = None
    if reg_cat == 'modular':
        from .models import CandidateModule, Result
        candidate_modules = CandidateModule.objects.filter(candidate=candidate)
        result_headers = [Paragraph("Module", bold), Paragraph("Grade", bold)]
        result_table_data = [result_headers]
        all_passed = True
        for candidate_module in candidate_modules:
            module = candidate_module.module
            # Fetch all results for this candidate and module, newest first
            results = Result.objects.filter(candidate=candidate, module=module).order_by('-assessment_date')
            # Find the latest successful result, else fallback to latest result
            result = next((r for r in results if r.comment == 'Successful'), None)
            if not result:
                result = results.first() if results else None
            grade = result.grade if result else ''
            if not result or result.comment != 'Successful':
                all_passed = False
            result_table_data.append([module.name, grade])
        result_table = Table(result_table_data, hAlign='CENTER', colWidths=[3.5*inch, 1.5*inch])
        result_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.black),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('LEFTPADDING', (0,0), (-1,-1), 3),
            ('RIGHTPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        elements.append(result_table)
        elements.append(Spacer(1, 0.04*inch))
        overall_comp = "Successful" if all_passed else "Unsuccessful"
        elements.append(Paragraph(f"Overall Competence: {overall_comp}", bold))
        elements.append(Spacer(1, 0.03*inch))
        elements.append(Spacer(1, 0.015*inch))




    else:
        # Level-based: use the Level name (e.g., 'Level 1 Transcript')
        level_name = ''
        if level:
            level_name = str(level)
        elif occ_level and occ_level.level:
            level_name = str(occ_level.level)
        if level_name:
            transcript_heading = f'{level_name} Transcript'
        else:
            transcript_heading = 'Level Transcript'
        from .models import Paper, Result
        papers = Paper.objects.filter(level=level, occupation=candidate.occupation)
        is_module_based = occ_level and occ_level.structure_type == 'modules'
        is_paper_based = occ_level and occ_level.structure_type == 'papers'
        level_number = None
        if hasattr(level, 'name') and level.name:
            try:
                level_number = int(''.join(filter(str.isdigit, str(level.name))))
            except Exception:
                level_number = None
        if is_module_based:
            result_headers = [Paragraph("Paper", bold), Paragraph("Grade", bold)]
            result_table_data = [result_headers]
            theory_paper = papers.filter(grade_type='theory').first()
            practical_paper = papers.filter(grade_type='practical').first()
            theory_result = Result.objects.filter(candidate=candidate, paper=theory_paper).order_by('-assessment_date').first() if theory_paper else None
            practical_result = Result.objects.filter(candidate=candidate, paper=practical_paper).order_by('-assessment_date').first() if practical_paper else None
            eligible = False
            overall_comp = ''
            if level_number and level_number >= 3:
                if practical_result and practical_result.comment == 'Successful' and theory_result and theory_result.comment == 'Successful':
                    eligible = True
                    overall_comp = "Successful"
            else:
                if practical_result and practical_result.comment == 'Successful':
                    eligible = True
                    if not theory_result or theory_result.comment != 'Successful':
                        overall_comp = "Successful in Practical Only"
                    else:
                        overall_comp = "Successful"
            # Improved eligibility and display logic for level module-based candidates
            # Level 1/2: transcript issued if Practical is 'Successful' (Theory can be failed/CTR)
            # Level 3/4: both must be 'Successful'
            # If Practical is 'CTR', block transcript
            # Always show a row for each passed component as appropriate
            practical_status = practical_result.comment if practical_result else None
            theory_status = theory_result.comment if theory_result else None

            eligible = False
            overall_comp = ''
            show_theory = False
            show_practical = False

            if level_number and level_number >= 3:
                # Level 3/4: both must be 'Successful'
                if practical_status == 'Successful' and theory_status == 'Successful':
                    eligible = True
                    show_theory = True
                    show_practical = True
                    overall_comp = 'Successful'
            else:
                # Level 1/2: Practical must be 'Successful', Theory can be anything
                if practical_status == 'Successful':
                    eligible = True
                    show_practical = True
                    if theory_status == 'Successful':
                        show_theory = True
                        overall_comp = 'Successful'
                    else:
                        overall_comp = 'Successful in Practical Only'
                elif practical_status == 'CTR':
                    eligible = False
                else:
                    eligible = False

            if not eligible:
                return HttpResponse("Candidate doesn't qualify.")

            if show_theory:
                result_table_data.append([
                    Paragraph(theory_paper.code + " - " + theory_paper.name, normal),
                    Paragraph(theory_result.grade, normal)
                ])
            if show_practical:
                result_table_data.append([
                    Paragraph(practical_paper.code + " - " + practical_paper.name, normal),
                    Paragraph(practical_result.grade, normal)
                ])

            col_widths = [3.5*inch, 1.0*inch]
            result_table = Table(result_table_data, colWidths=col_widths, hAlign='LEFT')
            result_table.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 1, colors.black),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('LEFTPADDING', (0,0), (-1,-1), 3),
                ('RIGHTPADDING', (0,0), (-1,-1), 3),
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))
            elements.append(result_table)
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(f"Overall Competence: {overall_comp}", bold))
            elements.append(Spacer(1, 0.18*inch))  # Add extra space before grading table
        elif is_paper_based:
            result_headers = [Paragraph("Paper", bold), Paragraph("Grade", bold)]
            result_table_data = [result_headers]
            # For each paper, find the latest successful result (if any), else latest result
            from collections import defaultdict
            paper_results = defaultdict(list)
            for r in Result.objects.filter(candidate=candidate, paper__level=level, paper__occupation=candidate.occupation).order_by('-assessment_date'):
                if r.paper:
                    paper_results[r.paper.id].append(r)
            practical_results = []
            theory_results = []
            for paper_id, results in paper_results.items():
                paper = results[0].paper
                latest_success = next((r for r in results if r.comment == 'Successful'), None)
                result = latest_success if latest_success else results[0]
                if paper.grade_type == 'practical':
                    practical_results.append(result)
                elif paper.grade_type == 'theory':
                    theory_results.append(result)
            all_practical_successful = all(r.comment == 'Successful' for r in practical_results) and practical_results
            all_theory_successful = all(r.comment == 'Successful' for r in theory_results) and theory_results
            eligible = False
            overall_comp = ''
            if level_number and level_number >= 3:
                if all_practical_successful and all_theory_successful:
                    eligible = True
                    overall_comp = "Successful"
            else:
                if all_practical_successful:
                    eligible = True
                    if not all_theory_successful:
                        overall_comp = "Successful in Practical Only"
                    else:
                        overall_comp = "Successful"
            if not eligible:
                return HttpResponse("Candidate doesn't qualify.")
            for paper_id, results in paper_results.items():
                paper = results[0].paper
                latest_success = next((r for r in results if r.comment == 'Successful'), None)
                result = latest_success if latest_success else results[0]
                result_table_data.append([
                    Paragraph(f"{paper.code} - {paper.name}", normal),
                    Paragraph(result.grade, normal)
                ])
            col_widths = [3.5*inch, 1.0*inch]
            result_table = Table(result_table_data, colWidths=col_widths, hAlign='LEFT')
            result_table.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 1, colors.black),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('LEFTPADDING', (0,0), (-1,-1), 3),
                ('RIGHTPADDING', (0,0), (-1,-1), 3),
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))
            elements.append(result_table)
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(f"Overall Competence: {overall_comp}", bold))
            elements.append(Spacer(1, 0.18*inch))  # Add extra space before grading table

# Only one grading key table and pass mark note, based on candidate type
    theory_bands = [
        ('85-100', 'A+'),
        ('80-84', 'A'),
        ('70-79', 'B'),
        ('60-69', 'B-'),
        ('50-59', 'C'),
        ('40-49', 'C-'),
        ('30-39', 'D'),
        ('0-29', 'E'),
    ]
    practical_bands = [
        ('90-100', 'A+'),
        ('85-89', 'A'),
        ('75-84', 'B+'),
        ('65-74', 'B'),
        ('60-64', 'B-'),
        ('55-59', 'C'),
        ('50-54', 'C-'),
        ('40-49', 'D'),
        ('30-39', 'D-'),
        ('0-29', 'E'),
    ]
    grading_key_data = [
        [Paragraph('<b>KEY : GRADING</b>', normal), '', '', ''],
        [Paragraph('<b>THEORY SCORES</b>', normal), Paragraph('Score %', normal), Paragraph('<b>PRACTICAL SCORES</b>', normal), Paragraph('Score %', normal)],
        [Paragraph('Grade', normal), Paragraph('Scores%', normal), Paragraph('Grade', normal), Paragraph('Scores%', normal)],
    ]
    # Render the bands row by row, filling empty cells if needed
    max_rows = max(len(theory_bands), len(practical_bands))
    for i in range(max_rows):
        t_score, t_grade = theory_bands[i] if i < len(theory_bands) else ('', '')
        p_score, p_grade = practical_bands[i] if i < len(practical_bands) else ('', '')
        grading_key_data.append([
            Paragraph(f"{t_score}", normal), Paragraph(f"{t_grade}", normal),
            Paragraph(f"{p_score}", normal), Paragraph(f"{p_grade}", normal)
        ])

    grading_key_table = Table(grading_key_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch], hAlign='LEFT')
    grading_key_table.setStyle(TableStyle([
        ('SPAN', (0,0), (3,0)),  # Span the first row across all columns
        ('SPAN', (0,1), (1,1)),  # Span the second row across first two columns
        ('TOPPADDING', (0,0), (-1,-1), 0.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0.5),
        ('SPAN', (2,1), (3,1)),  # Span the second row across last two columns
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        # No BOX or INNERGRID: no visible borders
    ]))
    elements.append(grading_key_table)
    elements.append(Spacer(1, 0.08*inch))
    elements.append(Paragraph('Pass mark is 50% in theory and 65% in practical assessment', normal))
    # No trailing spacers after this point to prevent a blank second page
    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="transcript_{candidate.reg_number}.pdf"'
    return response


def candidate_create(request):
    reg_cat = request.GET.get('registration_category')
    form_kwargs = {'user': request.user}
    if reg_cat:
        form_kwargs['initial'] = {'registration_category': reg_cat}
        if request.method == 'POST':
            form = CandidateForm(request.POST, request.FILES, **form_kwargs)
        else:
            form = CandidateForm(**form_kwargs)
    else:
        if request.method == 'POST':
            form = CandidateForm(request.POST, request.FILES, user=request.user)
        else:
            form = CandidateForm(user=request.user)
    # AJAX: return only occupation field HTML for dynamic update
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and reg_cat:
        occupation_field_html = render_to_string('partials/occupation_field.html', {'form': form})
        return JsonResponse({'occupation_field_html': occupation_field_html})
    # --- Handle form submission ---
    if request.method == 'POST':
        if form.is_valid():
            candidate = form.save(commit=False)
            candidate.created_by = request.user
            candidate.updated_by = request.user
            candidate.save()
            form.save_m2m()  # Ensure ManyToMany fields like nature_of_disability are saved
            return redirect('candidate_view', id=candidate.id)
    return render(request, 'candidates/create.html', {'form': form})



from django.contrib.auth.decorators import user_passes_test

def edit_result(request, id):
    from .models import Candidate, Result, Module, CandidateLevel, OccupationLevel, Paper
    from .forms import ModularResultsForm, ResultForm, PaperResultsForm, WorkerPASPaperResultsForm
    candidate = get_object_or_404(Candidate, id=id)
    if not request.user.is_superuser:
        return redirect('candidate_view', id=candidate.id)
    reg_cat = getattr(candidate, 'registration_category', '').lower().strip()
    print('DEBUG edit_result: candidate', candidate, 'reg_cat', reg_cat)
    context = {'candidate': candidate, 'edit_mode': True}

    # --- Modular candidate edit logic ---
    if reg_cat == 'modular':
        from .models import Module
        enrolled_modules = Module.objects.filter(candidatemodule__candidate=candidate)
        if not enrolled_modules.exists():
            context['form'] = None
            context['error'] = 'Candidate is not enrolled in any modules.'
            return render(request, 'candidates/add_result.html', context)
        existing_results = Result.objects.filter(candidate=candidate, result_type='modular')
        if request.method == 'POST':
            form = ModularResultsForm(request.POST, candidate=candidate)
            if form.is_valid():
                month = int(form.cleaned_data['month'])
                year = int(form.cleaned_data['year'])
                assessment_date = f"{year}-{month:02d}-01"
                for module in form.modules:
                    mark = form.cleaned_data.get(f'mark_{module.id}')
                    # Only create a new result if the mark has changed
                    existing_result = Result.objects.filter(
                        candidate=candidate,
                        module=module,
                        assessment_date=assessment_date,
                        result_type='modular',
                    ).first()
                    if mark is not None and (not existing_result or existing_result.mark != mark):
                        Result.objects.create(
                            candidate=candidate,
                            module=module,
                            assessment_date=assessment_date,
                            result_type='modular',
                            assessment_type='practical',
                            mark=mark,
                            user=request.user,
                            status='Updated' if existing_result else ''
                        )
                return redirect('candidate_view', id=candidate.id)
        else:
            # Prepopulate with existing marks if present
            initial = {}
            results_by_module = {r.module_id: r for r in existing_results}
            for module in enrolled_modules:
                result = results_by_module.get(module.id)
                if result:
                    initial[f'mark_{module.id}'] = result.mark
            # Prepopulate month/year from latest modular result
            latest_result = existing_results.order_by('-assessment_date').first()
            if latest_result and latest_result.assessment_date:
                initial['month'] = str(latest_result.assessment_date.month)
                initial['year'] = str(latest_result.assessment_date.year)
            form = ModularResultsForm(candidate=candidate, initial=initial)
        context['form'] = form
        context['is_modular'] = True
        context['module_mark_fields'] = [(module, form[f'mark_{module.id}']) for module in form.modules]
        return render(request, 'candidates/add_result.html', context)

    # --- Paper-based FORMAL edit logic ---
    level = getattr(candidate, 'level', None)
    from django.contrib import messages
    cl = CandidateLevel.objects.filter(candidate=candidate).first()
    if not level and cl:
        level = cl.level
    if not cl:
        messages.error(request, f'Candidate "{candidate}" is not enrolled. Please enroll candidate to add marks.')
        return redirect('candidate_view', id=candidate.id)
    is_paper_based = False
    if level:
        occ_level = OccupationLevel.objects.filter(occupation=candidate.occupation, level=level, structure_type='papers').first()
        if occ_level:
            is_paper_based = True
    if is_paper_based:
        # Fetch existing paper results
        papers = Paper.objects.filter(occupation=candidate.occupation, level=level)
        initial = {}
        for paper in papers:
            result = Result.objects.filter(candidate=candidate, paper=paper, result_type='formal').order_by('-assessment_date').first()
            if result:
                initial[f'mark_{paper.id}'] = result.mark
        # Prepopulate month/year from latest result
        latest_result = Result.objects.filter(candidate=candidate, paper__in=papers, result_type='formal').order_by('-assessment_date').first()
        if latest_result and latest_result.assessment_date:
            initial['month'] = latest_result.assessment_date.month
            initial['year'] = latest_result.assessment_date.year
        if request.method == 'POST':
            form = PaperResultsForm(request.POST, candidate=candidate, initial=initial)
            if form.is_valid():
                assessment_date = form.cleaned_data['assessment_date']
                for paper in form.papers:
                    mark = form.cleaned_data.get(f'mark_{paper.id}')
                    # Only create a new result if the mark has changed
                    existing_result = Result.objects.filter(candidate=candidate, paper=paper, result_type='formal').order_by('-assessment_date').first()
                    if mark is not None and (not existing_result or existing_result.mark != mark):
                        Result.objects.create(
                            candidate=candidate,
                            level=level,
                            paper=paper,
                            assessment_type=paper.grade_type,
                            assessment_date=assessment_date,
                            result_type='formal',
                            mark=mark,
                            user=request.user,
                            status='Updated'
                        )
                return redirect('candidate_view', id=candidate.id)
        else:
            form = PaperResultsForm(candidate=candidate, initial=initial)
        context['form'] = form
        context['is_paper_based'] = True
        context['paper_mark_fields'] = [(paper, form[f'mark_{paper.id}']) for paper in getattr(form, 'papers', [])]
        return render(request, 'candidates/add_result.html', context)
    # --- END paper-based FORMAL edit logic ---

    # --- Informal/Worker's PAS edit logic ---
    if reg_cat == 'informal':
        from .forms import WorkerPASPaperResultsForm
        from .models import CandidatePaper, Level
        # Get level from GET param if present, else use first enrolled level
        level_id = request.GET.get('level')
        level = None
        if level_id:
            try:
                level = Level.objects.get(id=level_id)
            except Level.DoesNotExist:
                level = None
        if not level:
            cl = CandidateLevel.objects.filter(candidate=candidate).first()
            if cl:
                level = cl.level
        if not level:
            context['form'] = None
            context['error'] = 'Candidate is not enrolled in any level.'
            return render(request, 'candidates/add_result.html', context)
        # Get enrolled papers for this candidate/level
        enrolled_papers = CandidatePaper.objects.filter(candidate=candidate, level=level).select_related('paper', 'module')
        if not enrolled_papers.exists():
            context['form'] = None
            context['error'] = 'Candidate has no enrolled papers.'
            return render(request, 'candidates/add_result.html', context)
        # Prepopulate marks for each enrolled paper
        initial = {}
        for cp in enrolled_papers:
            result = Result.objects.filter(candidate=candidate, paper=cp.paper, level=level, result_type='informal').order_by('-assessment_date').first()
            if result:
                initial[f'mark_{cp.paper.id}'] = result.mark
        # Prepopulate month/year from latest result
        latest_result = Result.objects.filter(candidate=candidate, paper__in=[cp.paper for cp in enrolled_papers], level=level, result_type='informal').order_by('-assessment_date').first()
        if latest_result and latest_result.assessment_date:
            initial['month'] = latest_result.assessment_date.month
            initial['year'] = latest_result.assessment_date.year
        if request.method == 'POST':
            form = WorkerPASPaperResultsForm(request.POST, candidate=candidate, level=level, initial=initial)
            if form.is_valid():
                assessment_date = form.cleaned_data['assessment_date']
                for cp in enrolled_papers:
                    paper = cp.paper
                    mark = form.cleaned_data.get(f'mark_{paper.id}')
                    # Only update/create if mark is changed
                    existing_result = Result.objects.filter(candidate=candidate, paper=paper, level=level, result_type='informal').order_by('-assessment_date').first()
                    if mark is not None and (not existing_result or existing_result.mark != mark):
                        Result.objects.create(
                            candidate=candidate,
                            level=level,
                            module=cp.module,
                            paper=paper,
                            assessment_type='practical',
                            assessment_date=assessment_date,
                            result_type='informal',
                            mark=mark,
                            user=request.user,
                            status='Updated'
                        )
                return redirect('candidate_view', id=candidate.id)
        else:
            form = WorkerPASPaperResultsForm(candidate=candidate, level=level, initial=initial)
        context['form'] = form
        context['is_worker_pas'] = True
        context['paper_mark_fields'] = [(cp.paper, form[f'mark_{cp.paper.id}']) for cp in enrolled_papers]
        return render(request, 'candidates/add_result.html', context)
    # --- END Informal/Worker's PAS edit logic ---

    if reg_cat == 'modular':
        from .models import Module, CandidateModule
        # Get all enrolled modules for this candidate
        enrolled_modules = Module.objects.filter(candidatemodule__candidate=candidate)
        if not enrolled_modules.exists():
            context['form'] = None
            context['error'] = 'Candidate is not enrolled in any modules.'
            return render(request, 'candidates/add_result.html', context)
        existing_results = Result.objects.filter(candidate=candidate, result_type='modular')
        if request.method == 'POST':
            form = ModularResultsForm(request.POST, candidate=candidate)
            if form.is_valid():
                month = int(form.cleaned_data['month'])
                year = int(form.cleaned_data['year'])
                assessment_date = f"{year}-{month:02d}-01"
                for module in form.modules:
                    mark = form.cleaned_data.get(f'mark_{module.id}')
                    # Only create a new result if the mark has changed
                    existing_result = Result.objects.filter(
                        candidate=candidate,
                        module=module,
                        assessment_date=assessment_date,
                        result_type='modular',
                    ).first()
                    if mark is not None and (not existing_result or existing_result.mark != mark):
                        Result.objects.create(
                            candidate=candidate,
                            module=module,
                            assessment_date=assessment_date,
                            result_type='modular',
                            assessment_type='practical',
                            mark=mark,
                            user=request.user,
                            status='Updated' if existing_result else ''
                        )
                return redirect('candidate_view', id=candidate.id)
        else:
            # Prepopulate with existing marks if present
            initial = {}
            results_by_module = {r.module_id: r for r in existing_results}
            for module in enrolled_modules:
                result = results_by_module.get(module.id)
                if result:
                    initial[f'mark_{module.id}'] = result.mark
            form = ModularResultsForm(candidate=candidate, initial=initial)
        context['form'] = form
        context['is_modular'] = True
        context['module_mark_fields'] = [(module, form[f'mark_{module.id}']) for module in form.modules]
    elif reg_cat == 'formal':
        from .forms import FormalResultsForm
        from .models import Level, CandidateLevel
        # Find the candidate's enrolled level
        level_enrollment = CandidateLevel.objects.filter(candidate=candidate).first()
        level = level_enrollment.level if level_enrollment else None
        existing_theory = None
        existing_practical = None
        # Fetch latest theory/practical results for this candidate (not filtered by level)
        theory_result = Result.objects.filter(candidate=candidate, assessment_type='theory', result_type='formal').order_by('-assessment_date').first()
        practical_result = Result.objects.filter(candidate=candidate, assessment_type='practical', result_type='formal').order_by('-assessment_date').first()
        if theory_result:
            existing_theory = theory_result.mark
        if practical_result:
            existing_practical = practical_result.mark
        initial = {}
        # Prepopulate marks
        if existing_theory is not None:
            initial['theory_mark'] = existing_theory
        if existing_practical is not None:
            initial['practical_mark'] = existing_practical
        # Prepopulate month/year from the latest result (theory or practical)
        assessment_date = None
        if theory_result and getattr(theory_result, 'assessment_date', None):
            assessment_date = theory_result.assessment_date
        elif practical_result and getattr(practical_result, 'assessment_date', None):
            assessment_date = practical_result.assessment_date
        if assessment_date:
            initial['month'] = assessment_date.month
            initial['year'] = assessment_date.year
        if request.method == 'POST':
            form = FormalResultsForm(request.POST, candidate=candidate, initial=initial)
            if form.is_valid() and level:
                theory_mark = form.cleaned_data.get('theory_mark')
                practical_mark = form.cleaned_data.get('practical_mark')
                month = int(form.cleaned_data.get('month')) if 'month' in form.cleaned_data else None
                year = int(form.cleaned_data.get('year')) if 'year' in form.cleaned_data else None
                if month and year:
                    assessment_date_str = f"{year}-{month:02d}-01"
                else:
                    assessment_date_str = None
                # Only create a new Result if the mark has changed
                if theory_result and theory_result.mark != theory_mark:
                    Result.objects.create(
                        candidate=candidate,
                        level=level,
                        assessment_type='theory',
                        result_type='formal',
                        mark=theory_mark,
                        assessment_date=assessment_date_str,
                        status='Updated',
                        user=request.user
                    )
                elif not theory_result and theory_mark is not None:
                    Result.objects.create(
                        candidate=candidate,
                        level=level,
                        assessment_type='theory',
                        result_type='formal',
                        mark=theory_mark,
                        assessment_date=assessment_date_str,
                        status='',
                        user=request.user
                    )
                if practical_result and practical_result.mark != practical_mark:
                    Result.objects.create(
                        candidate=candidate,
                        level=level,
                        assessment_type='practical',
                        result_type='formal',
                        mark=practical_mark,
                        assessment_date=assessment_date_str,
                        status='Updated',
                        user=request.user
                    )
                elif not practical_result:
                    Result.objects.create(
                        candidate=candidate,
                        level=level,
                        assessment_type='practical',
                        result_type='formal',
                        mark=practical_mark,
                        assessment_date=assessment_date_str,
                        status='',
                        user=request.user
                    )
                return redirect('candidate_view', id=candidate.id)
        else:
            form = FormalResultsForm(candidate=candidate, initial=initial)
        context['form'] = form
        context['is_modular'] = False
        context['formal_mark_fields'] = [form['theory_mark'], form['practical_mark']]
    else:
        return render(request, 'candidates/add_result.html', context)

    # Fallback for unknown categories
    context['form'] = None
    context['error'] = f'Unknown or unsupported registration category: {reg_cat!r} for candidate {candidate}'
    print('DEBUG edit_result: unknown registration_category', reg_cat, 'for candidate', candidate)
    return render(request, 'candidates/add_result.html', context)


def add_result(request, id):
    from .models import Candidate, Result, Module, Paper, Level, OccupationLevel, CandidateLevel, CandidatePaper
    from .forms import ResultForm, ModularResultsForm, WorkerPASPaperResultsForm
    candidate = get_object_or_404(Candidate, id=id)
    reg_cat = getattr(candidate, 'registration_category', '').strip().lower()
    context = {'candidate': candidate}

    # Worker PAS/informal: mark per enrolled paper
    if reg_cat == "Informal":
        # Get level from GET param if present, else use first enrolled level
        level_id = request.GET.get('level')
        level = None
        if level_id:
            try:
                from .models import Level
                level = Level.objects.get(id=level_id)
            except Level.DoesNotExist:
                level = None
        if not level:
            cl = CandidateLevel.objects.filter(candidate=candidate).first()
            if cl:
                level = cl.level
        if not level:
            context['form'] = None
            context['error'] = 'Candidate is not enrolled in any level.'
            return render(request, 'candidates/add_result.html', context)
        # Get enrolled papers for this candidate/level
        enrolled_papers = CandidatePaper.objects.filter(candidate=candidate, level=level).select_related('paper', 'module')
        if not enrolled_papers.exists():
            context['form'] = None
            context['error'] = 'Candidate has no enrolled papers.'
            return render(request, 'candidates/add_result.html', context)
        if request.method == 'POST':
            form = WorkerPASPaperResultsForm(request.POST, candidate=candidate, level=level)
            if form.is_valid():
                assessment_date = form.cleaned_data['assessment_date']
                for cp in enrolled_papers:
                    paper = cp.paper
                    mark = form.cleaned_data.get(f'mark_{paper.id}')
                    if mark is not None:
                        Result.objects.update_or_create(
                            candidate=candidate,
                            level=level,
                            module=cp.module,
                            paper=paper,
                            assessment_type='practical',
                            assessment_date=assessment_date,
                            result_type='informal',
                            defaults={
                                'mark': mark,
                                'user': request.user,
                                'status': ''
                            }
                        )
                return redirect('candidate_view', id=candidate.id)
        else:
            # Default assessment month/year to candidate's enrolled period for this level
            initial = {}
            cl = CandidateLevel.objects.filter(candidate=candidate, level=level).first()
            if cl and cl.start_date:
                initial['month'] = str(cl.start_date.month)
                initial['year'] = str(cl.start_date.year)
            form = WorkerPASPaperResultsForm(candidate=candidate, level=level, initial=initial)
        context['form'] = form
        context['is_worker_pas'] = True
        context['paper_mark_fields'] = [(cp.paper, form[f'mark_{cp.paper.id}']) for cp in enrolled_papers]
        return render(request, 'candidates/add_result.html', context)



    if reg_cat == 'modular':
        if request.method == 'POST':
            form = ModularResultsForm(request.POST, candidate=candidate)
            if form.is_valid():
                month = int(form.cleaned_data['month'])
                year = int(form.cleaned_data['year'])
                assessment_date = f"{year}-{month:02d}-01"
                for module in form.modules:
                    mark = form.cleaned_data.get(f'mark_{module.id}')
                    if mark is not None:

                        result, created = Result.objects.update_or_create(
                            candidate=candidate,
                            module=module,
                            assessment_date=assessment_date,
                            result_type='modular',
                            defaults={
                                'level': None,  # Modular results are not tied to a level
                                'assessment_type': 'practical',
                                'mark': mark,
                                'user': request.user,
                                'status': ''
                            }
                        )
            return redirect('candidate_view', id=candidate.id)
        else:
            form = ModularResultsForm(candidate=candidate)
        context['form'] = form
        context['is_modular'] = True
        # Pass (module, field) pairs for template rendering
        context['module_mark_fields'] = [(module, form[f'mark_{module.id}']) for module in form.modules]
    else:
        from .forms import FormalResultsForm, PaperResultsForm
        from .models import OccupationLevel
        # Determine if candidate's level is paper-based
        from .models import CandidateLevel
        level = getattr(candidate, 'level', None)
        if not level:
            cl = CandidateLevel.objects.filter(candidate=candidate).first()
            if cl:
                level = cl.level
        is_paper_based = False
        if level:
            occ_level = OccupationLevel.objects.filter(occupation=candidate.occupation, level=level, structure_type='papers').first()
            if occ_level:
                is_paper_based = True
        if is_paper_based:
            if request.method == 'POST':
                form = PaperResultsForm(request.POST, candidate=candidate)
                if form.is_valid():
                    assessment_date = form.cleaned_data['assessment_date']
                    for paper in form.papers:
                        mark = form.cleaned_data.get(f'mark_{paper.id}')
                        if mark is not None:
                            from .models import Result
                            Result.objects.create(
                                candidate=candidate,
                                level=level,
                                paper=paper,
                                assessment_type=paper.grade_type,
                                assessment_date=assessment_date,
                                result_type='formal',
                                mark=mark,
                                user=request.user,
                                status=''
                            )
                    return redirect('candidate_view', id=candidate.id)
            else:
                form = PaperResultsForm(candidate=candidate)
            context['form'] = form
            context['is_paper_based'] = True
            context['paper_mark_fields'] = [(paper, form[f'mark_{paper.id}']) for paper in getattr(form, 'papers', [])]
        else:
            if request.method == 'POST':
                form = FormalResultsForm(request.POST, candidate=candidate)
                if form.is_valid():
                    from datetime import date
                    today = date.today()
                    assessment_date = today.strftime("%Y-%m-01")
                    theory_mark = form.cleaned_data.get('theory_mark')
                    practical_mark = form.cleaned_data.get('practical_mark')
                    # Save theory result (combined for the level)
                    if theory_mark is not None:
                        Result.objects.update_or_create(
                            candidate=candidate,
                            level=level,
                            assessment_date=assessment_date,
                            assessment_type='theory',
                            result_type='formal',
                            defaults={'mark': theory_mark}
                        )
                    # Save practical result (combined for the level)
                    if practical_mark is not None:
                        Result.objects.update_or_create(
                            candidate=candidate,
                            level=level,
                            assessment_date=assessment_date,
                            assessment_type='practical',
                            result_type='formal',
                            defaults={'mark': practical_mark}
                        )
                    return redirect('candidate_view', id=candidate.id)
            else:
                form = FormalResultsForm(candidate=candidate)
            context['form'] = form
            context['is_modular'] = False
            # Pass just the two fields for the template
            context['formal_mark_fields'] = [form['theory_mark'], form['practical_mark']]
    return render(request, 'candidates/add_result.html', context)



def edit_candidate(request, id):
    candidate = get_object_or_404(Candidate, id=id)

    if request.method == 'POST':
        form = CandidateForm(request.POST, request.FILES, instance=candidate, edit=True)
        if form.is_valid():
            candidate = form.save(commit=False)
            candidate.updated_by = request.user
            candidate.save()
            form.save_m2m()  # Ensure ManyToMany fields like nature_of_disability are saved
            return redirect('candidate_view', id=candidate.id)
    else:
        form = CandidateForm(instance=candidate, edit=True)

    return render(request, 'candidates/edit.html', {'form': form, 'candidate': candidate})


def enroll_candidate_view(request, id):
    candidate = get_object_or_404(Candidate, id=id)

    # Only enroll if POST and _enroll=1
    if request.method == 'POST' and request.POST.get('_enroll') == '1':
        form = EnrollmentForm(request.POST, candidate=candidate)
        if form.is_valid():
            # Get the selected assessment series
            assessment_series = form.cleaned_data.get('assessment_series')     

            # Update candidate's assessment series
            if assessment_series:
                candidate.assessment_series = assessment_series
                candidate.save() 

            registration_category = candidate.registration_category
            

            # Handle formal registration (level only)
            if registration_category == 'Formal':
                level = form.cleaned_data.get('level')
                if not level:
                    form.add_error('level', 'Please select a level.')
                    return render(request, 'candidates/enroll.html', {
                        'form': form,
                        'candidate': candidate,
                    })
                # Check if already enrolled in this level
                if CandidateLevel.objects.filter(candidate=candidate, level=level).exists():
                    messages.error(request, "Candidate already enrolled for this level.")
                    return render(request, 'candidates/enroll.html', {
                        'form': form,
                        'candidate': candidate,
                    })
                # Not already enrolled: enroll the candidate
                CandidateLevel.objects.create(candidate=candidate, level=level)
                # Update fees balance after enrollment
                candidate.update_fees_balance()
                messages.success(request, f'{candidate.full_name} successfully enrolled in {level.name}.')
            
            # Handle modular registration (must select 1–2 modules, Level 1 only)
            elif registration_category == 'Modular':
                modules = form.cleaned_data['modules']
                if len(modules) > 2:
                    messages.error(request, "You can only select up to 2 modules.")
                else:
                    # For modular candidates: enroll in modules only (NO level enrollment)
                    # Clear any existing enrollments first
                    CandidateModule.objects.filter(candidate=candidate).delete()
                    
                    # Enroll candidate in selected modules
                    for module in modules:
                        CandidateModule.objects.create(candidate=candidate, module=module)
                    
                    # Update fees balance after enrollment
                    candidate.update_fees_balance()
                    
                    messages.success(request, f"{candidate.full_name} enrolled for {len(modules)} module(s)")

            # Handle informal registration (level + one paper per module)
            elif registration_category in ['Informal', "Worker's PAS", 'Workers PAS', 'informal', "worker's pas"]:
                from .models import CandidatePaper
                level = form.cleaned_data['level']
                selected_papers = form.cleaned_data.get('selected_papers', {})
                # Remove previous enrollments for this candidate/level
                CandidateLevel.objects.filter(candidate=candidate, level=level).delete()
                CandidateModule.objects.filter(candidate=candidate, module__level=level).delete()
                CandidatePaper.objects.filter(candidate=candidate, level=level).delete()
                # Enroll in level
                CandidateLevel.objects.create(candidate=candidate, level=level)
                # Enroll in modules and papers
                for mod_id, paper in selected_papers.items():
                    module = paper.module
                    CandidateModule.objects.create(candidate=candidate, module=module)
                    CandidatePaper.objects.create(candidate=candidate, module=module, paper=paper, level=level)
                # Update fees balance after enrollment
                candidate.update_fees_balance()
                messages.success(request, f"{candidate.full_name} enrolled in {level.name} and selected {len(selected_papers)} paper(s)")

            messages.success(request, "Candidate enrolled successfully.")
    else:
        # Support dynamic module filtering by selected level (GET param)
        form = EnrollmentForm(request.GET, candidate=candidate)
    return render(request, 'candidates/enroll.html', {
        'form': form,
        'candidate': candidate,
    })


from .models import Candidate, CandidateLevel, CandidateModule, Occupation, CandidatePaper

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.views.decorators.http import require_POST

@login_required
@require_POST
def clear_enrollment(request, id):
    if not request.user.is_superuser:
        return redirect('candidate_view', id=id)
    candidate = get_object_or_404(Candidate, id=id)
    from .models import Result
    from django.contrib import messages
    if Result.objects.filter(candidate=candidate).exists():
        messages.error(request, 'Candidate has marks/results and cannot be de-enrolled.')
        return redirect('candidate_view', id=id)
    CandidateLevel.objects.filter(candidate=candidate).delete()
    CandidateModule.objects.filter(candidate=candidate).delete()
    CandidatePaper.objects.filter(candidate=candidate).delete()
    # Also clear the assessment series assignment
    candidate.assessment_series = None
    # Reset fees balance to zero after clearing enrollment
    candidate.fees_balance = 0.00
    candidate.save()
    messages.success(request, 'All enrollment records and assessment series assignment for this candidate have been cleared.')
    return redirect('candidate_view', id=id)


# Helper
def _blocked_if_enrolled(request, candidate, action_name):
    if candidate.is_enrolled():
        messages.error(
            request,
            f"Candidate is already enrolled – cannot {action_name.lower()}."
        )
        return True
    return False

import json

@require_POST
def change_occupation(request, id):
    candidate = get_object_or_404(Candidate, id=id)

    if candidate.is_enrolled():
        return JsonResponse({"success": False,
                             "error": "Enrolled candidates cannot be changed."})

    try:
        data       = json.loads(request.body or "{}")
        new_occ_id = int(data["occupation"])
        new_occ    = Occupation.objects.get(pk=new_occ_id)
    except (KeyError, ValueError, Occupation.DoesNotExist):
        return HttpResponseBadRequest("Invalid occupation")

    candidate.occupation = new_occ
    candidate.build_reg_number()     # helper that rebuilds reg_number
    candidate.save(update_fields=["occupation", "reg_number"])

    return JsonResponse({
        "success": True,
        "occupation_name": new_occ.name,
        "reg_number": candidate.reg_number
    })

@require_POST
def change_center(request, id):
    import json
    candidate = get_object_or_404(Candidate, id=id)

    if candidate.is_enrolled():
        return JsonResponse({"success": False,
                             "error": "Enrolled candidates cannot be changed."})

    try:
        data = json.loads(request.body or "{}")
        new_center_id = int(data["assessment_center"])
        new_center = AssessmentCenter.objects.get(pk=new_center_id)
    except (KeyError, ValueError, AssessmentCenter.DoesNotExist):
        return HttpResponseBadRequest("Invalid center")

    candidate.assessment_center = new_center
    candidate.build_reg_number()     # helper that rebuilds reg_number
    candidate.save(update_fields=["assessment_center", "reg_number"])

    return JsonResponse({
        "success": True,
        "center_name": new_center.center_name,
        "reg_number": candidate.reg_number
    })

@require_POST
def change_registration_category(request, id):
    candidate = get_object_or_404(Candidate, id=id)

    if hasattr(candidate, 'is_enrolled') and callable(candidate.is_enrolled):
        if candidate.is_enrolled():
            return JsonResponse({"success": False, "error": "Enrolled candidates cannot be changed."})
    elif getattr(candidate, 'is_enrolled', False):
        return JsonResponse({"success": False, "error": "Enrolled candidates cannot be changed."})

    try:
        data = json.loads(request.body or '{}')
        new_reg_cat = data["registration_category"]
    except (KeyError, ValueError, TypeError):
        return HttpResponseBadRequest("Invalid registration category")

    occupation = candidate.occupation
    occ_cat = occupation.category.name if occupation and occupation.category else None
    has_modular = getattr(occupation, 'has_modular', False)

    # Validate compatibility
    if new_reg_cat == 'Modular':
        if not has_modular:
            return JsonResponse({"success": False, "error": "This occupation does not support Modular registration."})
    elif new_reg_cat == 'Formal':
        if occ_cat != 'Formal':
            return JsonResponse({"success": False, "error": "Only occupations in the 'Formal' category can be registered as Formal."})
    elif new_reg_cat == 'Informal':
        if occ_cat != "Worker's PAS":
            return JsonResponse({"success": False, "error": "Only occupations in the 'Worker's PAS' category can be registered as Informal."})
    else:
        return JsonResponse({"success": False, "error": "Invalid registration category selected."})

    candidate.registration_category = new_reg_cat
    candidate.reg_number = None
    candidate.save(update_fields=["registration_category", "reg_number"])
    # Regenerate reg_number as in regenerate_candidate_reg_number
    candidate.reg_number = None
    candidate.save(update_fields=["reg_number"])

    return JsonResponse({
        "success": True,
        "registration_category": new_reg_cat,
        "reg_number": candidate.reg_number
    })

def candidate_view(request, id):
    print('DEBUG: candidate_view (ACTIVE) called for candidate', id)
    from .models import AssessmentCenter, Occupation, Result, CandidateLevel, CandidateModule, Paper, Module, CandidatePaper
    candidate = get_object_or_404(Candidate, id=id)

    reg_cat = candidate.registration_category
    reg_cat_normalized = reg_cat.strip().lower() if reg_cat else ''
    level_enrollment = CandidateLevel.objects.filter(candidate=candidate).first()

    # Multi-level enrollment summary for worker's PAS/informal
    enrollment_summary = []
    if reg_cat_normalized in ["informal", "worker's pas", "workers pas"]:
        level_enrollments = CandidateLevel.objects.filter(candidate=candidate)
        for lvl_enroll in level_enrollments:
            modules = CandidateModule.objects.filter(candidate=candidate, module__level=lvl_enroll.level)
            module_list = []
            for mod_enroll in modules:
                # Attach all papers for this candidate/module/level (may be >1 after bulk)
                papers = list(
                    CandidatePaper.objects.filter(candidate=candidate, module=mod_enroll.module, level=lvl_enroll.level).select_related('paper')
                )
                module_list.append({
                    'module': mod_enroll.module,
                    'papers': [cp.paper for cp in papers]
                })
            enrollment_summary.append({
                'level': lvl_enroll.level,
                'modules': module_list
            })
        # For backward compatibility, keep module_enrollments and level_enrollment as before
        module_enrollments = CandidateModule.objects.filter(candidate=candidate, module__level=level_enrollment.level) if level_enrollment else []
    else:
        # For formal/modular, keep old logic
        module_enrollments = CandidateModule.objects.filter(candidate=candidate)
        for mod_enroll in module_enrollments:
            mod_enroll.papers = list(Paper.objects.filter(module=mod_enroll.module))

    # Attach papers for each module_enrollment (for backward compatibility)
    if reg_cat_normalized in ["worker's pas", "workers pas", "informal"] and level_enrollment:
        for mod_enroll in module_enrollments:
            candidate_paper = CandidatePaper.objects.filter(
                candidate_id=candidate.id,
                module_id=mod_enroll.module.id,
                level_id=level_enrollment.level.id
            ).select_related('paper').first()
            mod_enroll.papers = [candidate_paper.paper] if candidate_paper else []
    else:
        for mod_enroll in module_enrollments:
            mod_enroll.papers = list(Paper.objects.filter(module=mod_enroll.module))

    # Only show results for currently enrolled levels/papers for Informal/Worker PAS
    if reg_cat_normalized in ["informal", "worker's pas", "workers pas"]:
        enrolled_level_ids = [row['level'].id for row in enrollment_summary]
        enrolled_paper_ids = set()
        for row in enrollment_summary:
            for mod in row['modules']:
                for paper in mod['papers']:
                    enrolled_paper_ids.add(paper.id)
        results = Result.objects.filter(candidate=candidate, level_id__in=enrolled_level_ids, paper_id__in=enrolled_paper_ids)
    else:
        results = Result.objects.filter(candidate=candidate).order_by('assessment_date', 'level', 'module', 'paper')
    level_has_results = {}
    for row in enrollment_summary:
        lvl = row['level']
        enrolled_paper_ids = set()
        for mod in row['modules']:
            for paper in mod['papers']:
                enrolled_paper_ids.add(paper.id)
        result_paper_ids = set(results.filter(level_id=lvl.id).values_list('paper_id', flat=True))
        # Only True if ALL enrolled papers have results for this level
        level_has_results[str(lvl.id)] = bool(enrolled_paper_ids) and enrolled_paper_ids == result_paper_ids and len(result_paper_ids) > 0
    # Convert all keys to string for template consistency
    # (already done above for lvl.id)

    context = {
        "candidate":          candidate,
        "level_enrollment":   level_enrollment,
        "module_enrollments": module_enrollments,
        "results":            results,
        "occupations": Occupation.objects.exclude(pk=candidate.occupation_id),
        "centers":     AssessmentCenter.objects.exclude(pk=candidate.assessment_center_id),
        "enrollment_summary": enrollment_summary,
        "level_has_results": level_has_results,
    }
    print('DEBUG reg_cat:', reg_cat)
    print('DEBUG enrollment_summary:', enrollment_summary)
    print('DEBUG module_enrollments:', module_enrollments)
    print('DEBUG results:', list(results))
    return render(request, "candidates/view.html", context)


@login_required
def regenerate_candidate_reg_number(request, id):
    candidate = get_object_or_404(Candidate, id=id)
    # Clear reg_number and save to regenerate
    candidate.reg_number = None
    candidate.save()
    messages.success(request, f"Registration number regenerated: {candidate.reg_number}")
    return redirect('candidate_view', id=candidate.id)

def district_list(request):
    # Get filter parameters
    name = request.GET.get('name', '').strip()
    region = request.GET.get('region', '').strip()
    
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    districts = District.objects.all()
    
    # Apply filters
    if name:
        districts = districts.filter(name__icontains=name)
    if region:
        districts = districts.filter(region__icontains=region)
    
    districts = districts.order_by('name')
    
    # Pagination: 20 per page
    paginator = Paginator(districts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'configurations/district_list.html', {
        'page_obj': page_obj,
        'paginator': paginator,
        'filters': {
            'name': name,
            'region': region,
        }
    })

def district_create(request):
    form = DistrictForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('district_list')
    return render(request, 'configurations/district_form.html', {'form': form})

def village_list(request):
    # Get filter parameters
    name = request.GET.get('name', '').strip()
    district_name = request.GET.get('district_name', '').strip()
    region = request.GET.get('region', '').strip()
    district_id = request.GET.get('district')
    
    from django.core.paginator import Paginator
    from django.db.models import Q, Count
    
    villages = Village.objects.select_related('district').all()
    
    # Apply filters
    if name:
        villages = villages.filter(name__icontains=name)
    if district_name:
        villages = villages.filter(district__name__icontains=district_name)
    if region:
        villages = villages.filter(district__region__icontains=region)
    
    if district_id:
        villages = villages.filter(district_id=district_id)
        district = District.objects.get(id=district_id)
        
        # Pagination for specific district view
        villages = villages.order_by('name')
        paginator = Paginator(villages, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'paginator': paginator,
            'current_district': district,
            'filters': {
                'name': name,
                'district_name': district_name,
                'region': region,
            }
        }
    else:
        # Get districts with village counts
        districts = District.objects.annotate(
            village_count=Count('village')
        ).order_by('name')
        
        context = {
            'villages': villages,
            'districts': districts,
            'filters': {
                'name': name,
                'district_name': district_name,
                'region': region,
            }
        }
    
    return render(request, 'configurations/village_list.html', context)

def village_create(request):
    district_id = request.GET.get('district')
    initial = {}
    
    if district_id:
        try:
            district = District.objects.get(id=district_id)
            initial['district'] = district
        except District.DoesNotExist:
            pass
    
    form = VillageForm(request.POST or None, initial=initial)
    if form.is_valid():
        village = form.save()
        if district_id:
            return redirect(f'{reverse("village_list")}?district={district_id}')
        return redirect('village_list')
    
    context = {'form': form}
    if district_id and 'district' in initial:
        context['district'] = initial['district']
    
    return render(request, 'configurations/village_form.html', context)

def config_home(request):
    """Configuration home page showing available settings"""
    return render(request, 'configurations/config_home.html')

from django.contrib.auth.decorators import login_required

@login_required
def occupation_edit(request, pk):
    from .models import Level, OccupationLevel
    occupation = get_object_or_404(Occupation, pk=pk)
    levels = Level.objects.filter(occupation=occupation)
    add_level_error = request.GET.get('add_level_error')
    if request.method == 'POST':
        form = OccupationForm(request.POST, instance=occupation)
        if form.is_valid():
            occupation = form.save(commit=False)
            occupation.updated_by = request.user
            occupation.save()
            # Update OccupationLevel assignments
            selected_level_ids = request.POST.getlist('levels')
            # Track selected_levels for error restoration
            selected_levels = {}
            # Remove old OccupationLevel objects for this occupation
            OccupationLevel.objects.filter(occupation=occupation).delete()
            # Enforce restriction: If has_modular is checked, Level 1 must be modules
            has_modular = occupation.has_modular
            level1 = levels.filter(name__icontains='1').first()
            error = None
            for level in levels:
                if str(level.id) in selected_level_ids:
                    if has_modular and level1 and level.id == level1.id:
                        # If user tries to set Level 1 to papers, error
                        if request.POST.get(f'structure_type_{level.id}') == 'papers':
                            error = "If 'Has Modular' is checked, Level 1 must be set to Modules."
                            selected_levels[str(level.id)] = 'papers'
                            break
                        structure_type = 'modules'
                    else:
                        structure_type = request.POST.get(f'structure_type_{level.id}', 'modules')
                    selected_levels[str(level.id)] = structure_type
                    OccupationLevel.objects.create(
                        occupation=occupation,
                        level=level,
                        structure_type=structure_type
                    )
            if error:
                # Restore old OccupationLevel assignments
                OccupationLevel.objects.filter(occupation=occupation).delete()
                for lid, stype in selected_levels.items():
                    OccupationLevel.objects.create(
                        occupation=occupation,
                        level=Level.objects.get(id=lid),
                        structure_type=stype
                    )
                return render(request, 'occupations/edit.html', {
                    'form': form,
                    'occupation': occupation,
                    'levels': levels,
                    'selected_levels': selected_levels,
                    'error': error
                })
            return redirect('occupation_detail', pk=occupation.pk)
    else:
        form = OccupationForm(instance=occupation)
    # For edit, build levels with stype attribute for template
    occupation_levels = OccupationLevel.objects.filter(occupation=occupation)
    level_stype_map = {ol.level_id: ol.structure_type for ol in occupation_levels}
    levels_with_stype = []
    for level in levels:
        level.stype = level_stype_map.get(level.id, '')
        levels_with_stype.append(level)
    # Always provide selected_levels for template
    selected_levels = {str(level.id): level.stype for level in levels_with_stype if level.stype}
    return render(request, 'occupations/edit.html', {
        'form': form,
        'occupation': occupation,
        'levels': levels_with_stype,
        'selected_levels': selected_levels
    })

def create_center_rep(request):
    if request.method == 'POST':
        form = CenterRepForm(request.POST)
        if form.is_valid():
            center_rep = form.save(commit=False)
            center_rep.created_by = request.user
            center_rep.updated_by = request.user
            center_rep.save()
            return redirect('view_center_reps')
    else:
        form = CenterRepForm()
    return render(request, 'users/center_representatives/create_center_rep.html', {'form': form})

from .forms import SupportStaffForm

def create_support_staff(request):
    if request.method == 'POST':
        form = SupportStaffForm(request.POST)
        if form.is_valid():
            staff = form.save(commit=False)
            staff.created_by = request.user
            staff.updated_by = request.user
            staff.save()
            return redirect('view_support_staff')
    else:
        form = SupportStaffForm()
    return render(request, 'users/support_staff/create_support_staff.html', {'form': form})


def user_home(request):
    return render(request, 'users/user_home.html')


def view_center_reps(request):
    from .models import CenterRepresentative
    center_reps = CenterRepresentative.objects.select_related('user', 'center').all()
    return render(request, 'users/center_representatives/list_center_rep.html', {'center_reps': center_reps})

def view_center_rep_detail(request, pk):
    from .models import CenterRepresentative
    rep = CenterRepresentative.objects.select_related('user', 'center').get(pk=pk)
    return render(request, 'users/center_representatives/view_center_rep.html', {'rep': rep})

def edit_center_rep(request, pk):
    from .models import CenterRepresentative
    from .forms import CenterRepForm
    rep = CenterRepresentative.objects.select_related('user', 'center').get(pk=pk)
    if request.method == 'POST':
        form = CenterRepForm(request.POST, instance=rep)
        if form.is_valid():
            center_rep = form.save(commit=False)
            center_rep.updated_by = request.user
            center_rep.save()
            return redirect('view_center_rep', pk=rep.pk)
    else:
        form = CenterRepForm(instance=rep)
    return render(request, 'users/center_representatives/edit_center_rep.html', {'form': form, 'rep': rep})

def view_support_staff(request):
    from .models import SupportStaff
    support_staff = SupportStaff.objects.select_related('user').all()
    return render(request, 'users/support_staff/list_support_staff.html', {'support_staff': support_staff})

def view_support_staff_detail(request, pk):
    from .models import SupportStaff
    staff = SupportStaff.objects.select_related('user').get(pk=pk)
    return render(request, 'users/support_staff/view_support_staff.html', {'staff': staff})

def edit_support_staff(request, pk):
    from .models import SupportStaff
    from .forms import SupportStaffForm, CenterRepForm
    staff = SupportStaff.objects.select_related('user').get(pk=pk)
    if request.method == 'POST':
        form = SupportStaffForm(request.POST, instance=staff)
        if form.is_valid():
            staff_obj = form.save(commit=False)
            staff_obj.updated_by = request.user
            staff_obj.save()
            return redirect('view_support_staff_detail', pk=staff.pk)
    else:
        form = SupportStaffForm(instance=staff)
    return render(request, 'users/support_staff/edit_support_staff.html', {'form': form, 'staff': staff})


from PIL import Image as PILImage, ImageDraw, ImageFont
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse
import os

from django.views.decorators.http import require_POST
from .models import Occupation, Level

@require_POST
def add_level(request, occupation_id):
    occupation = get_object_or_404(Occupation, pk=occupation_id)
    name = request.POST.get('level_name')
    error = None
    if name:
        if Level.objects.filter(name=name, occupation=occupation).exists():
            error = f"Level '{name}' already exists for this occupation."
        else:
            Level.objects.create(name=name, occupation=occupation)
    else:
        error = "Level name is required."
    if error:
        from django.urls import reverse
        return redirect(f"{reverse('occupation_edit', kwargs={'pk': occupation_id})}?add_level_error={error}")
    return redirect('occupation_edit', pk=occupation_id)

def add_regno_to_photo(request, id):
    candidate = get_object_or_404(Candidate, id=id)

    if not candidate.passport_photo or not candidate.reg_number:
        return HttpResponse("Candidate must have both a photo and regno.", status=400)

    image_path = candidate.passport_photo.path
    # Use PILImage to avoid import shadowing with ReportLab's Image
    img = PILImage.open(image_path).convert("RGBA")

    # Overlay text (regno)
    draw = ImageDraw.Draw(img)
    # Use default PIL font for portability
    text = candidate.reg_number
    width, height = img.size
    max_width = width - 32
    font = None
    truetype_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
        '/usr/local/share/fonts/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
    ]
    font_size = 40
    min_font_size = 10
    for path in truetype_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size=font_size)
                break
            except Exception:
                font = None
    if font is None:
        font = ImageFont.load_default()
        font_size = 12
        min_font_size = 8
    # Dynamically shrink font size if needed
    while font_size >= min_font_size:
        try:
            text_w, text_h = font.getsize(text)
        except AttributeError:
            bbox = font.getbbox(text)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if text_w <= max_width:
            break
        font_size -= 2
        if hasattr(font, 'path'):
            try:
                font = ImageFont.truetype(font.path, size=font_size)
            except Exception:
                font = ImageFont.load_default()
                break
    # If still too wide, truncate
    if text_w > max_width:
        ellipsis = '...'
        for i in range(len(text)-1, 0, -1):
            truncated = text[:i] + ellipsis
            try:
                text_w, text_h = font.getsize(truncated)
            except AttributeError:
                bbox = font.getbbox(truncated)
                text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if text_w <= max_width:
                text = truncated
                break
    padding_v = max(10, text_h // 4)
    strip_h = text_h + 2 * padding_v
    strip_y = height - strip_h
    overlay = PILImage.new('RGBA', (width, strip_h), (255, 255, 255, 255))  # Solid white
    img = img.convert('RGBA')
    img.alpha_composite(overlay, (0, strip_y))
    draw = ImageDraw.Draw(img)
    x = (width - text_w) // 2
    y = strip_y + (strip_h - text_h) // 2
    draw.text((x, y), text, font=font, fill=(0,0,0,255))
    # Save with a new filename
    base_dir = os.path.dirname(image_path)
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    new_filename = os.path.join(base_dir, f"{base_name}_regno.png")
    img.save(new_filename)
    # Save the stamped image to a separate field (passport_photo_with_regno)
    from django.core.files import File
    from django.http import JsonResponse
    with open(new_filename, 'rb') as f:
        candidate.passport_photo_with_regno.save(os.path.basename(new_filename), File(f), save=True)
    url = candidate.passport_photo_with_regno.url
    return JsonResponse({'success': True, 'url': url})


@login_required
def download_result_list_pdf(request):
    """
    Generate a PDF download for the result list that matches the HTML preview exactly
    by converting the rendered HTML to PDF for pixel-perfect fidelity.
    """
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    from .models import Candidate, Result, Occupation, OccupationLevel, AssessmentCenter
    from collections import defaultdict
    import calendar
    import os
    logger = logging.getLogger(__name__)
    
    try:
        import weasyprint
    except ImportError:
        # Fallback to xhtml2pdf if WeasyPrint is not available
        try:
            from xhtml2pdf import pisa
        except ImportError:
            # If neither is available, return an error
            return HttpResponse('PDF generation libraries not available. Please install WeasyPrint or xhtml2pdf.', status=500)
    
    # Use the same logic as the HTML preview to get the exact same data
    # Get parameters from either POST (form submission) or GET (download link)
    assessment_month = request.POST.get('assessment_month') or request.GET.get('assessment_month')
    assessment_year = request.POST.get('assessment_year') or request.GET.get('assessment_year')
    regcat = (request.POST.get('registration_category') or request.GET.get('registration_category', '')).lower()
    occupation_id = request.POST.get('occupation') or request.GET.get('occupation')
    level_id = request.POST.get('level') or request.GET.get('level')
    center_id = request.POST.get('assessment_center') or request.GET.get('assessment_center')
    
    # Validate required parameters
    if not assessment_month or not assessment_year or not occupation_id:
        return HttpResponse("Missing required parameters: assessment_month, assessment_year, and occupation are required.", status=400)
    
    # Convert empty strings to None for optional parameters
    level_id = level_id if level_id else None
    center_id = center_id if center_id else None
    
    logger.info(f"PDF Download - regcat: {regcat}, occupation: {occupation_id}, level: {level_id}, center: {center_id}")
    
    # Find logo path
    logo_path = None
    possible_paths = [
        os.path.join(settings.BASE_DIR, 'eims', 'static', 'images', 'uvtab_logo.png'),
        os.path.join(settings.BASE_DIR, 'static', 'images', 'uvtab_logo.png'),
        os.path.join(settings.BASE_DIR, 'emis', 'static', 'images', 'uvtab_logo.png'),
        os.path.join(settings.STATIC_ROOT or '', 'images', 'uvtab_logo.png')
    ]
    for path in possible_paths:
        if path and os.path.exists(path):
            logo_path = path
            logger.info(f"Found logo at: {logo_path}")
            print(f"DEBUG: Logo found at: {logo_path}")
            print(f"DEBUG: Logo exists: {os.path.exists(logo_path)}")
            break
    
    if not logo_path:
        print("DEBUG: Logo not found in any of the expected locations")
        logger.warning("Logo not found in any of the expected locations")
    
    # Get occupation for filename
    try:
        occupation = Occupation.objects.get(id=occupation_id)
        occupation_name = occupation.name.replace(' ', '_').replace('/', '_')
    except Occupation.DoesNotExist:
        occupation_name = 'Unknown'
    
    # Format registration category for filename
    regcat_display = regcat.replace('_', ' ').title() if regcat else 'All'
    regcat_filename = regcat_display.replace(' ', '_').replace("'", '')
    
    # Create filename
    assessment_period = f"{assessment_month}_{assessment_year}"
    filename = f"{regcat_filename}_{occupation_name}_{assessment_period}.pdf"
    
    # Query the data directly instead of using mock requests
    # Get the occupation and level objects
    try:
        occupation = Occupation.objects.get(id=occupation_id)
    except Occupation.DoesNotExist:
        return HttpResponse("Occupation not found", status=404)
    
    level = None
    if level_id:
        try:
            from .models import Level
            level = Level.objects.get(id=level_id)
        except Level.DoesNotExist:
            pass
    
    # Get assessment center if specified
    center = None
    if center_id:
        try:
            center = AssessmentCenter.objects.get(id=center_id)
        except AssessmentCenter.DoesNotExist:
            pass
    
    # Build the candidate filter
    candidate_filter = {
        'occupation': occupation,
        'registration_category__iexact': regcat,
    }
    if level:
        candidate_filter['candidatelevel__level'] = level
    if center:
        candidate_filter['assessment_center'] = center
    
    # Get candidates
    candidates = Candidate.objects.filter(**candidate_filter).order_by('reg_number')
    
    # Build result filter
    result_filter = {
        'assessment_date__year': int(assessment_year),
        'assessment_date__month': int(assessment_month),
    }
    
    # Add result_type filter based on registration category
    if regcat == 'formal':
        # For formal, check structure type
        if level and hasattr(level, 'structure_type'):
            if level.structure_type == 'modules':
                result_filter['result_type'] = 'modular'
            else:
                result_filter['result_type'] = 'formal'
        else:
            result_filter['result_type'] = 'formal'
    else:
        result_filter['result_type'] = regcat
    
    # Get results for these candidates
    candidate_ids = list(candidates.values_list('id', flat=True))
    results = Result.objects.filter(
        candidate_id__in=candidate_ids,
        **result_filter
    ).select_related('candidate', 'paper')
    
    # Group results by candidate and center
    centered_result_data = defaultdict(lambda: defaultdict(list))
    
    for result in results:
        candidate = result.candidate
        center_name = candidate.assessment_center.center_name if candidate.assessment_center else 'Unknown Center'
        
        # Add candidate photo URLs
        if hasattr(candidate, 'passport_photo_with_regno') and candidate.passport_photo_with_regno:
            candidate.photo_url = candidate.passport_photo_with_regno.url
        elif hasattr(candidate, 'passport_photo') and candidate.passport_photo:
            candidate.photo_url = candidate.passport_photo.url
        else:
            candidate.photo_url = None
        
        centered_result_data[center_name][candidate.reg_number].append(result)
    
    # Convert to regular dict
    centered_result_data = dict(centered_result_data)
    for center in centered_result_data:
        centered_result_data[center] = dict(centered_result_data[center])
    
    # For modular category, create module-based grouping for PDF
    module_result_data = None
    if regcat.lower() == 'modular':
        from collections import defaultdict
        from .models import CandidateModule, Module
        module_result_data = defaultdict(list)
        
        # Process all results to group by module
        for result in results:
            candidate = result.candidate
            candidate_id = candidate.id
            
            # Get all modules this candidate is enrolled in
            candidate_modules = CandidateModule.objects.filter(candidate_id=candidate_id).select_related('module')
            
            for cm in candidate_modules:
                module = cm.module
                module_key = f"{module.code} - {module.name}"
                
                # Check if this result belongs to this module
                if hasattr(result, 'module') and result.module == module:
                    # Create candidate entry for this module
                    candidate_entry = {
                        'id': candidate.id,
                        'reg_number': candidate.reg_number,
                        'full_name': candidate.full_name,
                        'gender': candidate.get_gender_display(),
                        'assessment_center': getattr(candidate.assessment_center, 'center_name', None),
                    }
                    
                    # Add result data
                    result_entry = {
                        'candidate': candidate_entry,
                        'results': [{
                            'grade': result.grade,
                            'comment': result.comment,
                            'mark': result.mark,
                        }],
                        'successful': result.comment != 'CTR',
                    }
                    
                    module_result_data[module_key].append(result_entry)
        
        # Convert to regular dict
        module_result_data = dict(module_result_data)
            # Enable module and paper grouping for informal category (same logic as HTML preview)
    informal_module_data = None
    if regcat.lower() in ['informal', "worker's pas", "workers pas"] and results:
        from collections import defaultdict
        from .models import Module, Paper
        
        informal_module_data = defaultdict(lambda: defaultdict(lambda: {'papers': [], 'candidates': []}))
        
        # Get all modules for this level to ensure we show all modules even if no results
        if level_id and occupation_id:
            all_modules = Module.objects.filter(occupation_id=occupation_id, level_id=level_id)
            for module in all_modules:
                module_key = f"{module.code} - {module.name}"
                # Get all papers for this module
                module_papers = Paper.objects.filter(module=module)
                # Initialize for all centers that have candidates
                centers_with_candidates = set(result.candidate.assessment_center.center_name if result.candidate.assessment_center else 'Unknown Center' for result in results)
                for center_name in centers_with_candidates:
                    informal_module_data[center_name][module_key]['papers'] = [{
                        'code': p.code,
                        'name': p.name,
                        'id': p.id
                    } for p in module_papers]
        
        # Process all results to group by center, then by module
        processed_candidates = set()
        for result in results:
            candidate = result.candidate
            candidate_id = candidate.id
            center_name = candidate.assessment_center.center_name if candidate.assessment_center else 'Unknown Center'
            
            # Get all results for this candidate
            candidate_results = results.filter(candidate=candidate)
            
            for candidate_result in candidate_results:
                if candidate_result.module:
                    module = candidate_result.module
                    module_key = f"{module.code} - {module.name}"
                    
                    # Check if we already processed this candidate for this module in this center
                    candidate_module_key = f"{candidate_id}_{module.id}_{center_name}"
                    if candidate_module_key not in processed_candidates:
                        processed_candidates.add(candidate_module_key)
                        
                        # Create candidate entry for this module in this center
                        candidate_entry = {
                            'id': candidate.id,
                            'reg_number': candidate.reg_number,
                            'full_name': candidate.full_name,
                            'gender': candidate.gender,
                            'passport_photo_with_regno': candidate.passport_photo_with_regno.url if candidate.passport_photo_with_regno else None,
                            'passport_photo': candidate.passport_photo.url if candidate.passport_photo else None,
                            'assessment_center': center_name,
                        }
                        
                        # Get all results for this candidate in this module
                        candidate_module_results = candidate_results.filter(module=module)
                        
                        # Create paper results mapping
                        paper_results = {}
                        for r in candidate_module_results:
                            if r.paper:
                                paper_results[r.paper.id] = {
                                    'grade': r.grade,
                                    'comment': r.comment,
                                    'mark': r.mark,
                                }
                        
                        candidate_entry['paper_results'] = paper_results
                        candidate_entry['has_ctr'] = any(r.comment == 'CTR' for r in candidate_module_results)
                        
                        informal_module_data[center_name][module_key]['candidates'].append(candidate_entry)
        
        # Convert to regular dict
        informal_module_data = dict(informal_module_data)
        for center_name in informal_module_data:
            informal_module_data[center_name] = dict(informal_module_data[center_name])
       
    # Get papers list for formal paper-based occupations (using same logic as HTML preview)
    papers_list = []
    if regcat.lower() == 'formal':
        # Determine structure type for occupation/level
        structure_type = 'modules'
        if occupation_id and level_id:
            from .models import OccupationLevel, Paper
            occ_level = OccupationLevel.objects.filter(occupation_id=occupation_id, level_id=level_id).first()
            if occ_level:
                structure_type = occ_level.structure_type
            if structure_type == 'papers':
                papers = Paper.objects.filter(occupation_id=occupation_id, level_id=level_id)
                papers_list = [p.code for p in papers]  # Use just codes for PDF
    
    # Build context
    context = {
        'preview': True,
        'centered_result_data': centered_result_data,
        'module_result_data': module_result_data,
        'informal_module_data': informal_module_data,
        'form_data': {
            'month': assessment_month,
            'year': assessment_year,
            'regcat': regcat,
            'occupation_id': occupation_id,
            'occupation_name': occupation.name,
            'level_id': level_id,
            'level_name': level.name if level else None,
            'center_id': center_id,
        },
        'assessment_month': calendar.month_name[int(assessment_month)],
        'assessment_year': assessment_year,
        'registration_category': regcat,
        'occupation': occupation,
        'level': level,
        'assessment_center': center,
        'papers_list': papers_list,
    }
    
    # Create custom PDF using ReportLab to match the preview template exactly
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from io import BytesIO
    import os
    
    # Create PDF buffer
    buffer = BytesIO()
    
    # Create PDF document in landscape orientation
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=16,
        spaceAfter=12,
        alignment=TA_CENTER,
        textColor=colors.black
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6,
        alignment=TA_CENTER,
        textColor=colors.black
    )
    
    # Build PDF content
    elements = []
    
    # Add logo if available
    logo_path = None
    possible_paths = [
        os.path.join(settings.BASE_DIR, 'eims', 'static', 'images', 'uvtab_logo.png'),
        os.path.join(settings.BASE_DIR, 'static', 'images', 'uvtab_logo.png'),
        os.path.join(settings.BASE_DIR, 'emis', 'static', 'images', 'uvtab_logo.png'),
    ]
    for path in possible_paths:
        if path and os.path.exists(path):
            logo_path = path
            break
            
    # Add general header for modular and formal categories (informal has its own center-specific headers)
    if regcat.lower() in ['modular', 'formal']:
        if logo_path:
            try:
                logo = Image(logo_path, width=1*inch, height=1*inch)
                elements.append(logo)
                elements.append(Spacer(1, 12))
            except:
                pass
        
        # Add header information
        elements.append(Paragraph("UGANDA VOCATIONAL AND TECHNICAL ASSESSMENT BOARD", title_style))
        elements.append(Paragraph("PROVISIONAL ASSESSMENT RESULT LIST FOR", header_style))
        elements.append(Paragraph("ASSESSMENT PERIOD:", header_style))
        elements.append(Paragraph(f"{calendar.month_name[int(assessment_month)]} {assessment_year}", header_style))
        elements.append(Spacer(1, 12))
        
        # Add occupation and category info
        elements.append(Paragraph(f"Category: {regcat.title()}", header_style))
        elements.append(Paragraph(f"Occupation: {occupation.name}", header_style))
        if level:
            elements.append(Paragraph(f"Level: {level.name}", header_style))
        elements.append(Spacer(1, 20))

    # Handle modular category with module grouping
    if regcat.lower() == 'modular' and module_result_data:
        # Process each module
        for module_name, module_entries in module_result_data.items():
            if elements:  # Add page break between modules (except for first)
                elements.append(PageBreak())
                
                # Repeat header for new page
                if logo_path:
                    try:
                        logo = Image(logo_path, width=1*inch, height=1*inch)
                        elements.append(logo)
                        elements.append(Spacer(1, 12))
                    except:
                        pass
                
                elements.append(Paragraph("UGANDA VOCATIONAL AND TECHNICAL ASSESSMENT BOARD", title_style))
                elements.append(Paragraph("PROVISIONAL ASSESSMENT RESULT LIST FOR", header_style))
                elements.append(Paragraph("ASSESSMENT PERIOD:", header_style))
                elements.append(Paragraph(f"{calendar.month_name[int(assessment_month)]} {assessment_year}", header_style))
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(f"Category: {regcat.title()}", header_style))
                elements.append(Paragraph(f"Occupation: {occupation.name}", header_style))
                if level:
                    elements.append(Paragraph(f"Level: {level.name}", header_style))
                elements.append(Spacer(1, 20))
            
            # Module header
            elements.append(Paragraph(f"Module: {module_name}", header_style))
            elements.append(Spacer(1, 12))
            
            # Create table data for this module
            table_data = []
            headers = ['S/N', 'Photo', 'Reg No', 'Name', 'Gender', 'Practical', 'Comment']
            table_data.append(headers)
            
            # Add candidate data for this module
            sn = 1
            for entry in module_entries:
                candidate = entry['candidate']
                results = entry['results']
                
                row = [str(sn)]
                
                # Photo cell with fallback logic
                photo_cell = "No Photo"
                # For module entries, we need to get the actual candidate object for photo
                try:
                    actual_candidate = Candidate.objects.get(id=candidate['id'])
                    photo_path = None
                    
                    if hasattr(actual_candidate, 'passport_photo_with_regno') and actual_candidate.passport_photo_with_regno and hasattr(actual_candidate.passport_photo_with_regno, 'path') and os.path.exists(actual_candidate.passport_photo_with_regno.path):
                        photo_path = actual_candidate.passport_photo_with_regno.path
                    elif hasattr(actual_candidate, 'passport_photo') and actual_candidate.passport_photo and hasattr(actual_candidate.passport_photo, 'path') and os.path.exists(actual_candidate.passport_photo.path):
                        photo_path = actual_candidate.passport_photo.path
                    
                    if photo_path:
                        try:
                            photo_img = Image(photo_path, width=0.8*inch, height=0.8*inch)
                            photo_cell = photo_img
                        except Exception as e:
                            photo_cell = "No Photo"
                except:
                    photo_cell = "No Photo"
                
                row.append(photo_cell)
                row.append(candidate['reg_number'] or 'N/A')
                row.append(candidate['full_name'] or 'N/A')
                row.append(candidate['gender'] or 'N/A')
                
                # Practical grade
                practical_grade = 'N/A'
                if results and len(results) > 0:
                    practical_grade = str(results[0]['grade']) if results[0]['grade'] else 'N/A'
                
                # Comment: "Fail" if any result has comment "CTR", otherwise "Successful"
                has_ctr = any(r['comment'] == 'CTR' for r in results if r.get('comment'))
                comment = "Fail" if has_ctr else "Successful"
                
                row.extend([practical_grade, comment])
                table_data.append(row)
                sn += 1
            
            # Create and style the table for this module
            if len(table_data) > 1:  # Only create table if there are candidates
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)
                elements.append(Spacer(1, 20))
    # Handle informal category with module and paper grouping
        # Handle informal category with module and paper grouping
    elif regcat.lower() in ['informal', "worker's pas", "workers pas"] and informal_module_data:
        # Process each center
        first_center = True
        for center_name, center_modules in informal_module_data.items():
            if not first_center:  # Add page break between centers (except for first)
                elements.append(PageBreak())
            
            # Center header for each center
            if logo_path:
                try:
                    logo = Image(logo_path, width=1*inch, height=1*inch)
                    elements.append(logo)
                    elements.append(Spacer(1, 12))
                except:
                    pass
            
            elements.append(Paragraph("UGANDA VOCATIONAL AND TECHNICAL ASSESSMENT BOARD", title_style))
            elements.append(Paragraph("PROVISIONAL ASSESSMENT RESULT LIST FOR", header_style))
            elements.append(Paragraph("ASSESSMENT PERIOD:", header_style))
            elements.append(Paragraph(f"{calendar.month_name[int(assessment_month)]} {assessment_year}", header_style))
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(f"Category: {regcat.title()}", header_style))
            elements.append(Paragraph(f"Occupation: {occupation.name}", header_style))
            if level:
                elements.append(Paragraph(f"Level: {level.name}", header_style))
            elements.append(Paragraph(f"Assessment Center: {center_name}", header_style))
            elements.append(Spacer(1, 20))
            
            first_center = False
            
            # Process each module within this center
            first_module = True
            for module_name, module_info in center_modules.items():
                if module_info['candidates']:
                    if not first_module:  # Add page break between modules within same center
                        elements.append(PageBreak())
                        
                        # Add header for new module page
                        if logo_path:
                            try:
                                logo = Image(logo_path, width=1*inch, height=1*inch)
                                elements.append(logo)
                                elements.append(Spacer(1, 12))
                            except:
                                pass
    
                        elements.append(Paragraph("UGANDA VOCATIONAL AND TECHNICAL ASSESSMENT BOARD", title_style))
                        elements.append(Paragraph("PROVISIONAL ASSESSMENT RESULT LIST FOR", header_style))
                        elements.append(Paragraph("ASSESSMENT PERIOD:", header_style))
                        elements.append(Paragraph(f"{calendar.month_name[int(assessment_month)]} {assessment_year}", header_style))
                        elements.append(Spacer(1, 12))
                        elements.append(Paragraph(f"Category: {regcat.title()}", header_style))
                        elements.append(Paragraph(f"Occupation: {occupation.name}", header_style))
                        if level:
                            elements.append(Paragraph(f"Level: {level.name}", header_style))
                        elements.append(Paragraph(f"Assessment Center: {center_name}", header_style))
                        elements.append(Spacer(1, 20))
                    
                    
                    first_module = False
                    
                    # Module header
                    elements.append(Paragraph(f"MODULE: {module_name}", header_style))
                    elements.append(Spacer(1, 12))
                    
                    # Create table data for this module
                    table_data = []
                    
                    # Table headers - dynamic based on papers in this module
                    headers = ['S/N', 'Photo', 'Reg No', 'Name', 'Gender']
                    for paper in module_info['papers']:
                        headers.append(paper['code'])
                    headers.append('Comment')
                    
                    table_data.append(headers)
                    
                    # Add candidate data for this module
                    sn = 1

                for candidate in module_info['candidates']:
                    row = [str(sn)]

                    # Add photo cell with actual image
                    photo_cell = None
                    if candidate.get('passport_photo_with_regno'):
                        try:
                            photo_path = candidate['passport_photo_with_regno']
                            if photo_path.startswith('/media/'):
                                # Convert URL to file path
                                photo_file_path = os.path.join(settings.MEDIA_ROOT, photo_path[7:])  # Remove /media/ prefix
                                if os.path.exists(photo_file_path):
                                    photo_cell = Image(photo_file_path, width=0.8*inch, height=0.8*inch)
                        except:
                            pass

                    if not photo_cell and candidate.get('passport_photo'):
                        try:
                            photo_path = candidate['passport_photo']
                            if photo_path.startswith('/media/'):
                                # Convert URL to file path
                                photo_file_path = os.path.join(settings.MEDIA_ROOT, photo_path[7:])  # Remove /media/ prefix
                                if os.path.exists(photo_file_path):
                                    photo_cell = Image(photo_file_path, width=0.8*inch, height=0.8*inch)
                        except:
                            pass

                    if not photo_cell:
                            photo_cell = 'No Photo'

                    row.append(photo_cell)
                    
                    # Add candidate info
                    row.append(candidate['reg_number'])
                    row.append(candidate['full_name'])
                    row.append(candidate['gender'])
                    
                    # Add grades for each paper
                    for paper in module_info['papers']:
                        paper_result = candidate['paper_results'].get(paper['id'])
                        if paper_result:
                            row.append(paper_result['grade'])
                        else:
                            row.append('N/A')
                    
                    # Add comment
                    comment = 'Fail' if candidate['has_ctr'] else 'Successful'
                    row.append(comment)
                    
                    table_data.append(row)
                    sn += 1
                
                # Create and style the table
                if len(table_data) > 1:  # Only create table if there are candidates
                    table = Table(table_data)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    elements.append(table)
                    elements.append(Spacer(1, 20))
    else:
    
        # Process each center (non-modular or fallback)
        for center_name, candidates_data in centered_result_data.items():
            if elements:  # Add page break between centers (except for first)
                elements.append(PageBreak())
                
                # Repeat header for new page
                if logo_path:
                    try:
                        logo = Image(logo_path, width=1*inch, height=1*inch)
                        elements.append(logo)
                        elements.append(Spacer(1, 12))
                    except:
                        pass
                
                elements.append(Paragraph("UGANDA VOCATIONAL AND TECHNICAL ASSESSMENT BOARD", title_style))
                elements.append(Paragraph("PROVISIONAL ASSESSMENT RESULT LIST FOR", header_style))
                elements.append(Paragraph("ASSESSMENT PERIOD:", header_style))
                elements.append(Paragraph(f"{calendar.month_name[int(assessment_month)]} {assessment_year}", header_style))
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(f"Category: {regcat.title()}", header_style))
                elements.append(Paragraph(f"Occupation: {occupation.name}", header_style))
                if level:
                    elements.append(Paragraph(f"Level: {level.name}", header_style))
                elements.append(Spacer(1, 20))
            
            # Center header
            elements.append(Paragraph(f"Assessment Center: {center_name}", header_style))
            elements.append(Spacer(1, 12))
            
            # Create table data for this center
            table_data = []
            
            # Table headers
            if papers_list and len(papers_list) > 0:
                # Paper-based formal occupation
                headers = ['S/N', 'Photo', 'Reg No', 'Name', 'Gender']
                headers.extend(papers_list)  # Add paper codes
                headers.append('Comment')
            elif regcat.lower() == 'modular':
                # Modular: only practical, no theory
                headers = ['S/N', 'Photo', 'Reg No', 'Name', 'Gender', 'Practical', 'Comment']
            else:
                # Formal module-based: theory + practical
                headers = ['S/N', 'Photo', 'Reg No', 'Name', 'Gender', 'Theory', 'Practical', 'Comment']
            
            table_data.append(headers)
            
            # Add candidate data for this center
            sn = 1
            for reg_number, results in candidates_data.items():
                if not results:
                    continue
                    
                candidate = results[0].candidate
                row = [str(sn)]
                
                # Photo cell with fallback logic (copying working formal photo logic)
                photo_cell = "No Photo"
                photo_path = None
                
                # Use the same logic that works for formal PDFs - check .path instead of .url
                if hasattr(candidate, 'passport_photo_with_regno') and candidate.passport_photo_with_regno and hasattr(candidate.passport_photo_with_regno, 'path') and os.path.exists(candidate.passport_photo_with_regno.path):
                    photo_path = candidate.passport_photo_with_regno.path
                elif hasattr(candidate, 'passport_photo') and candidate.passport_photo and hasattr(candidate.passport_photo, 'path') and os.path.exists(candidate.passport_photo.path):
                    photo_path = candidate.passport_photo.path
                
                if photo_path:
                    try:
                        photo_img = Image(photo_path, width=0.8*inch, height=0.8*inch)
                        photo_cell = photo_img
                    except Exception as e:
                        photo_cell = "No Photo"
                
                row.append(photo_cell)
                row.append(candidate.reg_number or 'N/A')
                row.append(candidate.full_name if candidate.full_name else 'N/A')
                row.append(candidate.gender or 'N/A')
                
                if papers_list and len(papers_list) > 0:
                    # Paper-based: add grade for each paper
                    result_dict = {r.paper.code: r for r in results if r.paper}
                    for paper_code in papers_list:
                        if paper_code in result_dict:
                            result = result_dict[paper_code]
                            grade = getattr(result, 'grade', None) or getattr(result, 'marks', None) or 'N/A'
                            row.append(str(grade))
                        else:
                            row.append('N/A')
                    
                    # Comment: "Fail" if any result has comment "CTR", otherwise "Successful"
                    has_ctr = any(r.comment == 'CTR' for r in results if hasattr(r, 'comment'))
                    comment = "Fail" if has_ctr else "Successful"
                    row.append(comment)
                elif regcat.lower() == 'modular':
                    # Modular: only practical grade, no theory
                    practical_grade = 'N/A'
                    
                    for result in results:
                        # For modular, just get the grade (which is practical)
                        if hasattr(result, 'grade') and result.grade:
                            practical_grade = str(result.grade)
                            break  # Take the first grade found
                    
                    # Comment: "Fail" if any result has comment "CTR", otherwise "Successful"
                    has_ctr = any(getattr(r, 'comment', '') == 'CTR' for r in results)
                    comment = "Fail" if has_ctr else "Successful"
                    
                    row.extend([practical_grade, comment])
                else:
                    # Formal module-based: show theory/practical with proper grade extraction
                    theory_grade = 'N/A'
                    practical_grade = 'N/A'
                    
                    for result in results:
                        # Check for theory results
                        if hasattr(result, 'assessment_type'):
                            if result.assessment_type == 'theory':
                                if hasattr(result, 'grade') and result.grade:
                                    theory_grade = str(result.grade)
                            elif result.assessment_type == 'practical':
                                if hasattr(result, 'grade') and result.grade:
                                    practical_grade = str(result.grade)
                        else:
                            # Fallback: try different grade fields
                            if hasattr(result, 'theory_grade') and result.theory_grade:
                                theory_grade = str(result.theory_grade)
                            if hasattr(result, 'practical_grade') and result.practical_grade:
                                practical_grade = str(result.practical_grade)
                            if hasattr(result, 'grade') and result.grade and theory_grade == 'N/A':
                                theory_grade = str(result.grade)
                    
                    # Comment: "Fail" if any result has comment "CTR", otherwise "Successful"
                    has_ctr = any(getattr(r, 'comment', '') == 'CTR' for r in results)
                    comment = "Fail" if has_ctr else "Successful"
                    
                    row.extend([theory_grade, practical_grade, comment])
                
                table_data.append(row)
                sn += 1
            
            # Create and style table for this center
            if len(table_data) > 1:  # Only create table if there's data
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 20))
            else:
                elements.append(Paragraph("No results found for this center.", styles['Normal']))
                elements.append(Spacer(1, 20))
    
    # Build PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    
    # Return PDF response
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    logger.info(f"Generated custom PDF: {filename}")
    return response


def _create_photo_cell_content(candidate, styles, photo_width=0.8*inch, photo_height=0.8*inch):
    """Creates a list of flowables for the candidate photo cell, including image, name, and details."""
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus.flowables import Image
    from reportlab.platypus import Paragraph
    
    cell_elements = []
    photo_image = None

    # Photo Styles
    photo_name_style = ParagraphStyle(
        'PhotoName',
        parent=styles['Normal'],
        fontSize=6,
        alignment=TA_CENTER,
        spaceBefore=1,
        leading=6
    )
    photo_detail_style = ParagraphStyle(
        'PhotoDetail',
        parent=styles['Normal'],
        fontSize=5,
        alignment=TA_CENTER,
        spaceBefore=1,
        leading=5
    )
    
    # Handle photo with fallback logic
    if hasattr(candidate, 'passport_photo_with_regno') and candidate.passport_photo_with_regno:
        try:
            photo_image = Image(candidate.passport_photo_with_regno.path, width=photo_width, height=photo_height)
        except:
            pass
    elif hasattr(candidate, 'passport_photo') and candidate.passport_photo:
        try:
            photo_image = Image(candidate.passport_photo.path, width=photo_width, height=photo_height)
        except:
            pass
    
    if not photo_image:
        photo_image = Paragraph('No Photo', ParagraphStyle('NoPhoto', fontSize=6, alignment=TA_CENTER))
    
    cell_elements.append(photo_image)
    
    occupation_code = candidate.occupation.code if candidate.occupation else 'N/A'
    reg_category_short = candidate.registration_category.upper() if candidate.registration_category else 'N/A'
    
    return cell_elements
    
    return render(request, 'statistics/home.html', context)
@login_required
def statistics_home(request):
    """Enhanced statistics dashboard showing system overview and detailed metrics including assessment series"""
    
    # Get basic counts
    total_candidates = Candidate.objects.count()
    total_occupations = Occupation.objects.count()
    total_centers = AssessmentCenter.objects.count()
    total_results = Result.objects.count()
    
    # Gender breakdown
    gender_data = Candidate.objects.values('gender').annotate(
        count=Count('id')
    ).order_by('-count')
    
    gender_breakdown = []
    gender_colors = {'M': '#3B82F6', 'F': '#EC4899'}  # Blue for Male, Pink for Female
    total_candidates_for_percentage = total_candidates if total_candidates > 0 else 1
    
    for gender in gender_data:
        gender_code = gender['gender']
        count = gender['count']
        percentage = (count / total_candidates_for_percentage) * 100
        
        gender_breakdown.append({
            'code': gender_code,
            'name': 'Male' if gender_code == 'M' else 'Female' if gender_code == 'F' else 'Unknown',
            'count': count,
            'percentage': round(percentage, 1),
            'color': gender_colors.get(gender_code, '#6B7280')
        })
    
    # Registration categories breakdown
    registration_categories = []
    reg_cat_data = Candidate.objects.values('registration_category').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Define colors for different registration categories
    reg_colors = {
        'Formal': '#3B82F6',      # Blue
        'Modular': '#10B981',     # Green
        'Informal': '#F59E0B',    # Yellow
        'Worker\'s PAS': '#EF4444', # Red
    }
    
    for category in reg_cat_data:
        reg_cat = category['registration_category']
        count = category['count']
        percentage = (count / total_candidates_for_percentage) * 100
        
        registration_categories.append({
            'name': reg_cat or 'Unknown',
            'count': count,
            'percentage': round(percentage, 1),
            'color': reg_colors.get(reg_cat, '#6B7280')  # Default gray
        })
    
    # Special needs breakdown
    total_with_special_needs = Candidate.objects.filter(disability=True).count()
    total_without_special_needs = Candidate.objects.filter(disability=False).count()
    
    special_needs_breakdown = [
        {
            'name': 'With Special Needs',
            'count': total_with_special_needs,
            'percentage': round((total_with_special_needs / total_candidates_for_percentage) * 100, 1),
            'color': '#EF4444'  # Red
        },
        {
            'name': 'Without Special Needs',
            'count': total_without_special_needs,
            'percentage': round((total_without_special_needs / total_candidates_for_percentage) * 100, 1),
            'color': '#10B981'  # Green
        }
    ]
    
    # Special needs by Gender breakdown
    special_needs_by_gender = []
    
    # Male with special needs
    male_with_special_needs = Candidate.objects.filter(gender='M', disability=True).count()
    # Female with special needs
    female_with_special_needs = Candidate.objects.filter(gender='F', disability=True).count()
    # Male without special needs
    male_without_special_needs = Candidate.objects.filter(gender='M', disability=False).count()
    # Female without special needs
    female_without_special_needs = Candidate.objects.filter(gender='F', disability=False).count()
    
    special_needs_by_gender = [
        {
            'category': 'Male with Special Needs',
            'count': male_with_special_needs,
            'percentage': round((male_with_special_needs / total_candidates_for_percentage) * 100, 1),
            'color': '#DC2626'  # Dark red
        },
        {
            'category': 'Female with Special Needs',
            'count': female_with_special_needs,
            'percentage': round((female_with_special_needs / total_candidates_for_percentage) * 100, 1),
            'color': '#BE185D'  # Dark pink
        }
    ]
    
    # Registration Category by Gender
    reg_cat_by_gender = []
    for category in reg_cat_data:
        reg_cat = category['registration_category']
        if reg_cat:
            male_count = Candidate.objects.filter(registration_category=reg_cat, gender='M').count()
            female_count = Candidate.objects.filter(registration_category=reg_cat, gender='F').count()
            
            reg_cat_by_gender.append({
                'category': reg_cat,
                'male_count': male_count,
                'female_count': female_count,
                'total_count': male_count + female_count,
                'male_percentage': round((male_count / total_candidates_for_percentage) * 100, 1),
                'female_percentage': round((female_count / total_candidates_for_percentage) * 100, 1),
                'color': reg_colors.get(reg_cat, '#6B7280')
            })
    
    # Assessment Series breakdown (grouped by month and year from CANDIDATE assessment_date)
    assessment_series = []
    
    # Get distinct enrollment periods from CANDIDATES based on enrollment dates
    enrollment_periods = Candidate.objects.values(
        'created_at__year', 
        'created_at__month'
    ).annotate(
        total_candidates=Count('id')
    ).order_by('-created_at__year', '-created_at__month')
    
    for period in enrollment_periods:
        year = period['created_at__year']
        month = period['created_at__month']
        
        if year and month:
            # Get candidates who have assessment_date in this period
            candidates_in_period = Candidate.objects.filter(
                created_at__year=year,
                created_at__month=month
            )
            
            # Count by gender
            male_count = candidates_in_period.filter(gender='M').count()
            female_count = candidates_in_period.filter(gender='F').count()
            
            # Count with special needs
            special_needs_count = candidates_in_period.filter(disability=True).count()
            
            # Count distinct occupations
            occupation_count = candidates_in_period.values('occupation').distinct().count()
            
            # Get month name
            month_name = calendar.month_name[month]
            
            assessment_series.append({
                'year': year,
                'month': month,
                'period_name': f"{month_name} {year}",
                'total_candidates': period['total_candidates'],
                'male_count': male_count,
                'female_count': female_count,
                'special_needs_count': special_needs_count,
                'occupation_count': occupation_count
            })
    
    context = {
        'total_candidates': total_candidates,
        'total_occupations': total_occupations,
        'total_centers': total_centers,
        'total_results': total_results,
        'gender_breakdown': gender_breakdown,
        'registration_categories': registration_categories,
        'special_needs_breakdown': special_needs_breakdown,
        'special_needs_by_gender': special_needs_by_gender,
        'reg_cat_by_gender': reg_cat_by_gender,
        'assessment_series': assessment_series,
    }
    
    return render(request, 'statistics/home.html', context)


@login_required
def assessment_series_detail(request, year, month):
    """Detailed breakdown for a specific assessment period (month/year) using CANDIDATE assessment_date"""
    
    # Get candidates who have assessment_date in this period (not result assessment_date)
    candidates_in_period = Candidate.objects.filter(
        created_at__year=year,
        created_at__month=month
    )
    
    total_candidates = candidates_in_period.count()
    total_candidates_for_percentage = total_candidates if total_candidates > 0 else 1
    
    # Month name for display
    month_name = calendar.month_name[int(month)]
    period_name = f"{month_name} {year}"
    
    # Gender breakdown
    gender_breakdown = []
    gender_colors = {'M': '#3B82F6', 'F': '#EC4899'}
    
    gender_data = candidates_in_period.values('gender').annotate(count=Count('id'))
    for gender in gender_data:
        gender_code = gender['gender']
        count = gender['count']
        percentage = (count / total_candidates_for_percentage) * 100
        
        gender_breakdown.append({
            'code': gender_code,
            'name': 'Male' if gender_code == 'M' else 'Female' if gender_code == 'F' else 'Unknown',
            'count': count,
            'percentage': round(percentage, 1),
            'color': gender_colors.get(gender_code, '#6B7280')
        })
    
    # Registration category breakdown
    reg_cat_breakdown = []
    reg_colors = {
        'Formal': '#3B82F6',
        'Modular': '#10B981',
        'Informal': '#F59E0B',
        'Worker\'s PAS': '#EF4444',
    }
    
    reg_cat_data = candidates_in_period.values('registration_category').annotate(count=Count('id'))
    for category in reg_cat_data:
        reg_cat = category['registration_category']
        count = category['count']
        percentage = (count / total_candidates_for_percentage) * 100
        
        reg_cat_breakdown.append({
            'name': reg_cat or 'Unknown',
            'count': count,
            'percentage': round(percentage, 1),
            'color': reg_colors.get(reg_cat, '#6B7280')
        })
    
    # Occupation breakdown
    occupation_breakdown = []
    occupation_colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#84CC16', '#F97316']
    
    occupation_data = candidates_in_period.values('occupation__name').annotate(count=Count('id')).order_by('-count')
    for i, occupation in enumerate(occupation_data):
        occ_name = occupation['occupation__name']
        count = occupation['count']
        percentage = (count / total_candidates_for_percentage) * 100
        
        occupation_breakdown.append({
            'name': occ_name or 'Unknown',
            'count': count,
            'percentage': round(percentage, 1),
            'color': occupation_colors[i % len(occupation_colors)]
        })
    
    # Special needs breakdown
    special_needs_breakdown = []
    with_special_needs = candidates_in_period.filter(disability=True).count()
    without_special_needs = candidates_in_period.filter(disability=False).count()
    
    special_needs_breakdown = [
        {
            'name': 'With Special Needs',
            'count': with_special_needs,
            'percentage': round((with_special_needs / total_candidates_for_percentage) * 100, 1),
            'color': '#EF4444'
        },
        {
            'name': 'Without Special Needs',
            'count': without_special_needs,
            'percentage': round((without_special_needs / total_candidates_for_percentage) * 100, 1),
            'color': '#10B981'
        }
    ]
    
    # Special needs by gender
    special_needs_by_gender = []
    male_with_special_needs = candidates_in_period.filter(gender='M', disability=True).count()
    female_with_special_needs = candidates_in_period.filter(gender='F', disability=True).count()
    male_without_special_needs = candidates_in_period.filter(gender='M', disability=False).count()
    female_without_special_needs = candidates_in_period.filter(gender='F', disability=False).count()
    
    special_needs_by_gender = [
        {
            'category': 'Male with Special Needs',
            'count': male_with_special_needs,
            'percentage': round((male_with_special_needs / total_candidates_for_percentage) * 100, 1),
            'color': '#DC2626'
        },
        {
            'category': 'Female with Special Needs',
            'count': female_with_special_needs,
            'percentage': round((female_with_special_needs / total_candidates_for_percentage) * 100, 1),
            'color': '#BE185D'
        },
        {
            'category': 'Male without Special Needs',
            'count': male_without_special_needs,
            'percentage': round((male_without_special_needs / total_candidates_for_percentage) * 100, 1),
            'color': '#2563EB'
        },
        {
            'category': 'Female without Special Needs',
            'count': female_without_special_needs,
            'percentage': round((female_without_special_needs / total_candidates_for_percentage) * 100, 1),
            'color': '#DB2777'
        }
    ]
    
    # Registration category by gender
    reg_cat_by_gender = []
    for category in reg_cat_data:
        reg_cat = category['registration_category']
        if reg_cat:
            male_count = candidates_in_period.filter(registration_category=reg_cat, gender='M').count()
            female_count = candidates_in_period.filter(registration_category=reg_cat, gender='F').count()
            
            reg_cat_by_gender.append({
                'category': reg_cat,
                'male_count': male_count,
                'female_count': female_count,
                'total_count': male_count + female_count,
                'male_percentage': round((male_count / total_candidates_for_percentage) * 100, 1),
                'female_percentage': round((female_count / total_candidates_for_percentage) * 100, 1),
                'color': reg_colors.get(reg_cat, '#6B7280')
            })
    
    context = {
        'period_name': period_name,
        'year': year,
        'month': month,
        'total_candidates': total_candidates,
        'gender_breakdown': gender_breakdown,
        'reg_cat_breakdown': reg_cat_breakdown,
        'occupation_breakdown': occupation_breakdown,
        'special_needs_breakdown': special_needs_breakdown,
        'special_needs_by_gender': special_needs_by_gender,
        'reg_cat_by_gender': reg_cat_by_gender,
    }
    
    return render(request, 'statistics/assessment_series_detail.html', context)

    def get_candidate_filter_urls(assessment_year=None, assessment_month=None):
        """Generate common filter URLs for statistics templates"""
        base_filters = {}
        if assessment_year:
            base_filters['assessment_year'] = assessment_year
        if assessment_month:
            base_filters['assessment_month'] = assessment_month
    
        return {
            'male_url': build_candidate_filter_url(base_filters, gender='M'),
            'female_url': build_candidate_filter_url(base_filters, gender='F'),
            'special_needs_url': build_candidate_filter_url(base_filters, disability='true'),
            'no_special_needs_url': build_candidate_filter_url(base_filters, disability='false'),
            'male_special_needs_url': build_candidate_filter_url(base_filters, gender='M', disability='true'),
            'female_special_needs_url': build_candidate_filter_url(base_filters, gender='F', disability='true'),
            'formal_url': build_candidate_filter_url(base_filters, registration_category='Formal'),
            'modular_url': build_candidate_filter_url(base_filters, registration_category='Modular'),
            'informal_url': build_candidate_filter_url(base_filters, registration_category='Informal'),
            'workers_pas_url': build_candidate_filter_url(base_filters, registration_category="Worker's PAS"),
        }

@login_required
def assessment_series_list(request):
    """Display list of all assessment series with pagination"""
    series_list = AssessmentSeries.objects.all().order_by('-is_current', '-start_date')
    
    # Add pagination
    paginator = Paginator(series_list, 10)  # Show 10 series per page
    page_number = request.GET.get('page')
    series = paginator.get_page(page_number)
    
    context = {
        'series': series,
        'total_count': series_list.count(),
        'current_series': series_list.filter(is_current=True).first()
    }
    
    return render(request, 'Assessment_series/list.html', context)


@login_required
def assessment_series_create(request):
    """Create a new assessment series"""
    if request.method == 'POST':
        form = AssessmentSeriesForm(request.POST)
        if form.is_valid():
            series = form.save()
            messages.success(request, f'Assessment Series "{series.name}" created successfully!')
            return redirect('assessment_series_view', pk=series.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AssessmentSeriesForm()
    
    context = {
        'form': form,
        'title': 'Create Assessment Series'
    }
    
    return render(request, 'Assessment_series/create.html', context)


@login_required
def assessment_series_view(request, pk):
    """View details of a specific assessment series"""
    series = get_object_or_404(AssessmentSeries, pk=pk)
    
    # Calculate some statistics for this series
    from datetime import datetime
    
    # Get candidates enrolled during this series period
    candidates_in_period = Candidate.objects.filter(
        assessment_date__gte=series.start_date,
        assessment_date__lte=series.end_date
    )
    
    # Get results for this period
    results_in_period = Result.objects.filter(
        assessment_date__gte=series.start_date,
        assessment_date__lte=series.end_date
    )
    
    # Calculate statistics
    total_candidates = candidates_in_period.count()
    total_results = results_in_period.count()
    male_candidates = candidates_in_period.filter(gender='M').count()
    female_candidates = candidates_in_period.filter(gender='F').count()
    special_needs_candidates = candidates_in_period.filter(disability=True).count()
    
    # Check if series is active (current date is within series period)
    today = datetime.now().date()
    is_active = series.start_date <= today <= series.end_date
    
    # Check if results can be released (current date is past release date)
    can_release_results = today >= series.date_of_release
    
    context = {
        'series': series,
        'total_candidates': total_candidates,
        'total_results': total_results,
        'male_candidates': male_candidates,
        'female_candidates': female_candidates,
        'special_needs_candidates': special_needs_candidates,
        'is_active': is_active,
        'can_release_results': can_release_results,
        'today': today
    }
    
    return render(request, 'Assessment_series/view.html', context)


@login_required
def assessment_series_edit(request, pk):
    """Edit an existing assessment series"""
    series = get_object_or_404(AssessmentSeries, pk=pk)
    
    if request.method == 'POST':
        form = AssessmentSeriesForm(request.POST, instance=series)
        if form.is_valid():
            updated_series = form.save()
            messages.success(request, f'Assessment Series "{updated_series.name}" updated successfully!')
            return redirect('assessment_series_view', pk=updated_series.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AssessmentSeriesForm(instance=series)
    
    context = {
        'form': form,
        'series': series,
        'title': f'Edit Assessment Series: {series.name}'
    }
    
    return render(request, 'Assessment_series/create.html', context)


@login_required
def assessment_series_delete(request, pk):
    """Delete an assessment series"""
    series = get_object_or_404(AssessmentSeries, pk=pk)
    
    if request.method == 'POST':
        series_name = series.name
        series.delete()
        messages.success(request, f'Assessment Series "{series_name}" deleted successfully!')
        return redirect('assessment_series_list')
    
    context = {
        'series': series,
        'title': f'Delete Assessment Series: {series.name}'
    }
    
    return render(request, 'Assessment_series/delete.html', context)


@login_required
def assessment_series_set_current(request, pk):
    """Set a specific assessment series as current"""
    series = get_object_or_404(AssessmentSeries, pk=pk)
    
    if request.method == 'POST':
        # Set this series as current (the model's save method will handle unsetting others)
        series.is_current = True
        series.save()
        messages.success(request, f'Assessment Series "{series.name}" is now set as current!')
        return redirect('assessment_series_view', pk=series.pk)
    
    context = {
        'series': series,
        'title': f'Set as Current: {series.name}'
    }
    
    return render(request, 'Assessment_series/set_current.html', context)


@login_required
def assessment_series_years(request):
    """Display available years with series counts"""
    # Get all years that have assessment series
    years_data = []
    
    # Get distinct years from start_date field
    series_years = AssessmentSeries.objects.dates('start_date', 'year', order='DESC')
    
    for year_date in series_years:
        year = year_date.year
        series_count = AssessmentSeries.objects.filter(
            start_date__year=year
        ).count()
        
        current_series_count = AssessmentSeries.objects.filter(
            start_date__year=year,
            is_current=True
        ).count()
        
        years_data.append({
            'year': year,
            'series_count': series_count,
            'current_series_count': current_series_count,
            'has_current': current_series_count > 0
        })
    
    # If no years exist, show current year
    if not years_data:
        current_year = datetime.now().year
        years_data.append({
            'year': current_year,
            'series_count': 0,
            'current_series_count': 0,
            'has_current': False
        })
    
    context = {
        'years_data': years_data,
        'total_series': AssessmentSeries.objects.count(),
        'current_year': datetime.now().year
    }
    
    return render(request, 'Assessment_series/years.html', context)


@login_required
def assessment_series_year_detail(request, year):
    """Display all assessment series for a specific year"""
    # Get all series for the specified year
    series_list = AssessmentSeries.objects.filter(
        start_date__year=year
    ).order_by('-is_current', 'start_date')
    
    # Add pagination
    paginator = Paginator(series_list, 12)  # Show 12 series per page (monthly)
    page_number = request.GET.get('page')
    series = paginator.get_page(page_number)
    
    # Get year statistics
    current_series = series_list.filter(is_current=True).first()
    total_count = series_list.count()
    
    # Get months with series for this year
    months_with_series = series_list.dates('start_date', 'month')
    month_names = [date.strftime('%B') for date in months_with_series]
    
    context = {
        'series': series,
        'year': year,
        'total_count': total_count,
        'current_series': current_series,
        'months_with_series': month_names,
        'prev_year': year - 1,
        'next_year': year + 1,
        'current_year': datetime.now().year
    }
    
    return render(request, 'Assessment_series/year_detail.html', context)


@login_required
def assessment_series_create_for_year(request, year=None):
    """Create a new assessment series, optionally pre-filled for a specific year"""
    if request.method == 'POST':
        form = AssessmentSeriesForm(request.POST)
        if form.is_valid():
            series = form.save()
            messages.success(request, f'Assessment Series "{series.name}" created successfully!')
            # Redirect to the year detail page
            series_year = series.start_date.year
            return redirect('assessment_series_year_detail', year=series_year)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AssessmentSeriesForm()
        # If year is provided, pre-fill the form with January 1st of that year
        if year:
            from datetime import date
            form.initial = {
                'start_date': date(year, 1, 1),
                'end_date': date(year, 1, 31),
                'date_of_release': date(year, 2, 1)
            }
    
    context = {
        'form': form,
        'title': f'Create Assessment Series{f" for {year}" if year else ""}',
        'year': year
    }
    
    return render(request, 'Assessment_series/create.html', context)

@login_required
def assessment_series_toggle_results(request, pk):
    """Toggle the results release status for an assessment series"""
    series = get_object_or_404(AssessmentSeries, pk=pk)
    
    if request.method == 'POST':
        # Toggle the results_released status
        series.results_released = not series.results_released
        series.save()
        
        status = "released" if series.results_released else "hidden"
        messages.success(request, f'Results for "{series.name}" have been {status}.')
        
        return redirect('assessment_series_view', pk=pk)
    
    # If not POST, redirect back to view
    return redirect('assessment_series_view', pk=pk)

@login_required
def assessment_series_statistical_report(request, pk):
    """Generate a statistical PDF report for a specific Assessment Series"""
    series = get_object_or_404(AssessmentSeries, pk=pk)
    
    # Get candidates enrolled during this series period
    candidates = Candidate.objects.filter(
        assessment_date__gte=series.start_date,
        assessment_date__lte=series.end_date
    )
    
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Assessment_Series_Report_{series.name.replace(" ", "_")}.pdf"'
    
    # Create the PDF object
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#4A5568')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.HexColor('#2D3748')
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
    )
    
    # Title
    title = Paragraph(f"Assessment Series Statistical Report<br/>{series.name}", title_style)
    elements.append(title)
    
    # Series Information
    series_info = f"""
    <b>Series Period:</b> {series.start_date.strftime('%B %d, %Y')} - {series.end_date.strftime('%B %d, %Y')}<br/>
    <b>Results Release Date:</b> {series.date_of_release.strftime('%B %d, %Y')}<br/>
    <b>Report Generated:</b> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br/>
    <b>Total Enrolled Candidates:</b> {candidates.count()}
    """
    elements.append(Paragraph(series_info, normal_style))
    elements.append(Spacer(1, 20))
    
    # 1. GENDER DISTRIBUTION
    elements.append(Paragraph("1. GENDER DISTRIBUTION", heading_style))
    
    gender_stats = candidates.values('gender').annotate(count=Count('gender')).order_by('gender')
    gender_data = [['Gender', 'Count', 'Percentage']]
    
    total_candidates = candidates.count()
    for stat in gender_stats:
        gender_name = 'Male' if stat['gender'] == 'M' else 'Female'
        percentage = (stat['count'] / total_candidates * 100) if total_candidates > 0 else 0
        gender_data.append([gender_name, str(stat['count']), f"{percentage:.1f}%"])
    
    if total_candidates == 0:
        gender_data.append(['No candidates enrolled', '-', '-'])
    
    gender_table = Table(gender_data, colWidths=[2*inch, 1*inch, 1*inch])
    gender_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A5568')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(gender_table)
    elements.append(Spacer(1, 20))
    
    # 2. SPECIAL NEEDS DISTRIBUTION
    elements.append(Paragraph("2. SPECIAL NEEDS DISTRIBUTION", heading_style))
    
    special_needs_count = candidates.filter(disability=True).count()
    no_special_needs_count = candidates.filter(disability=False).count()
    
    special_needs_data = [['Category', 'Count', 'Percentage']]
    
    if total_candidates > 0:
        special_needs_percentage = (special_needs_count / total_candidates * 100)
        no_special_needs_percentage = (no_special_needs_count / total_candidates * 100)
        
        special_needs_data.append(['Candidates with Special Needs', str(special_needs_count), f"{special_needs_percentage:.1f}%"])
        special_needs_data.append(['Candidates without Special Needs', str(no_special_needs_count), f"{no_special_needs_percentage:.1f}%"])
    else:
        special_needs_data.append(['No candidates enrolled', '-', '-'])
    
    special_needs_table = Table(special_needs_data, colWidths=[3*inch, 1*inch, 1*inch])
    special_needs_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A5568')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(special_needs_table)
    
    # Nature of Disabilities breakdown (if any special needs candidates exist)
    if special_needs_count > 0:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("2.1 Nature of Disabilities", ParagraphStyle('SubHeading', parent=styles['Heading3'], fontSize=12, spaceAfter=8)))
        
        # Get all disability natures for candidates in this series
        disability_stats = []
        special_needs_candidates = candidates.filter(disability=True)
        
        for candidate in special_needs_candidates:
            for disability in candidate.nature_of_disability.all():
                disability_stats.append(disability.name)
        
        # Count occurrences
        disability_counts = Counter(disability_stats)
        
        disability_data = [['Nature of Disability', 'Count']]
        for disability_name, count in disability_counts.most_common():
            disability_data.append([disability_name, str(count)])
        
        if not disability_counts:
            disability_data.append(['No specific disabilities recorded', '-'])
        
        disability_table = Table(disability_data, colWidths=[3*inch, 1*inch])
        disability_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A5568')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(disability_table)
    
    elements.append(Spacer(1, 20))
    
    # 3. OCCUPATIONS ENROLLED
    elements.append(Paragraph("3. OCCUPATIONS ENROLLED", heading_style))
    
    occupation_stats = candidates.values(
        'occupation__name', 
        'occupation__category__name'
    ).annotate(
        count=Count('occupation')
    ).order_by('occupation__category__name', 'occupation__name')
    
    occupation_data = [['Occupation Category', 'Occupation', 'Count', 'Percentage']]
    
    for stat in occupation_stats:
        if stat['occupation__name']:  # Only include if occupation is not null
            percentage = (stat['count'] / total_candidates * 100) if total_candidates > 0 else 0
            occupation_data.append([
                stat['occupation__category__name'] or 'Uncategorized',
                stat['occupation__name'],
                str(stat['count']),
                f"{percentage:.1f}%"
            ])
    
    if len(occupation_data) == 1:  # Only header row
        occupation_data.append(['No occupations recorded', '-', '-', '-'])
    
    occupation_table = Table(occupation_data, colWidths=[1.5*inch, 2.5*inch, 0.8*inch, 0.8*inch])
    occupation_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A5568')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(occupation_table)
    
    # Summary section
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("SUMMARY", heading_style))
    
    # Calculate special needs percentage safely
    special_needs_percentage = (special_needs_count/total_candidates*100) if total_candidates > 0 else 0
    
    summary_text = f"""
    This report provides a comprehensive statistical analysis of the {series.name} assessment series.
    The data shows enrollment patterns across gender, special needs requirements, and occupational categories.
    
    <b>Key Highlights:</b><br/>
    - Total candidates enrolled: {total_candidates}<br/>
    - Candidates with special needs: {special_needs_count} ({special_needs_percentage:.1f}% of total)<br/>
    - Number of different occupations: {len([stat for stat in occupation_stats if stat['occupation__name']])}<br/>
    - Series duration: {(series.end_date - series.start_date).days + 1} days
    """
    
    elements.append(Paragraph(summary_text, normal_style))
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response


@login_required
def statistical_reports_home(request):
    """Home page for statistical reports - shows available assessment series"""
    series_list = AssessmentSeries.objects.all().order_by('-start_date')
    
    context = {
        'series_list': series_list,
        'title': 'Statistical Reports'
    }
    
    return render(request, 'statistical_reports/home.html', context)

@login_required
def api_assessment_series(request):
    """API endpoint to get Assessment Series data for bulk enrollment"""
    from django.http import JsonResponse
    
    # Get all assessment series, ordered by most recent first
    series = AssessmentSeries.objects.all().order_by('-start_date')
    
    series_data = []
    for s in series:
        series_data.append({
            'id': s.id,
            'name': s.name,
            'start_date': s.start_date.strftime('%Y-%m-%d'),
            'end_date': s.end_date.strftime('%Y-%m-%d'),
            'is_current': s.is_current,
        })
    
    return JsonResponse({
        'assessment_series': series_data
    })

