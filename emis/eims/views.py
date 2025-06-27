from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from reportlab.platypus import Image as RLImage


@login_required
def results_home(request):
    return render(request, 'results/home.html')

from django.views.decorators.http import require_POST
from django.http import JsonResponse
from openpyxl import Workbook
from io import BytesIO

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
    if regcat and regcat.lower() == 'modular':
        candidates = candidates.filter(occupation__has_modular=True)
        print('[DEBUG] After has_modular filter:', candidates.count())
        # Filter by selected modules if provided
        if modules:
            module_objs = Module.objects.filter(id__in=modules)
            from .models import CandidateModule
            enrolled_ids = set(CandidateModule.objects.filter(module__in=module_objs).values_list('candidate_id', flat=True))
            print('[DEBUG] Modular enrolled_ids:', enrolled_ids)
            candidates = candidates.filter(id__in=enrolled_ids)
            print('[DEBUG] After module enrollment filter:', candidates.count())
    elif regcat:
        candidates = candidates.filter(occupation__has_modular=False)
        print('[DEBUG] After NOT has_modular filter:', candidates.count())
    if regcat:
        candidates = candidates.filter(registration_category__iexact=regcat)
        print(f'[DEBUG] After regcat ({regcat}) filter:', candidates.count())
    print('[DEBUG] Candidate IDs and occupation IDs:', list(candidates.values_list('id', 'occupation_id')))
    if occupation:
        candidates = candidates.filter(occupation_id=occupation)
        print(f'[DEBUG] After occupation ({occupation}) filter:', candidates.count())
    # For formal (module-based), filter by CandidateLevel
    if regcat and regcat.lower() == 'formal' and level:
        from .models import CandidateLevel
        enrolled_ids = set(CandidateLevel.objects.filter(level=level).values_list('candidate_id', flat=True))
        print(f'[DEBUG] CandidateLevel enrolled_ids for level {level}:', enrolled_ids)
        candidates = candidates.filter(id__in=enrolled_ids)
        print('[DEBUG] After CandidateLevel filter:', candidates.count())
    if center:
        candidates = candidates.filter(assessment_center=center)
        print(f'[DEBUG] After center ({center}) filter:', candidates.count())
    if not occ:
        return JsonResponse({'success': False, 'error': 'Please select an occupation.'})
    if lvl is None and regcat and regcat.lower() != 'modular':
        return JsonResponse({'success': False, 'error': 'Please select a level.'})
    if regcat and regcat.lower() == 'modular' and (not modules or not Module.objects.filter(id__in=modules).exists()):
        return JsonResponse({'success': False, 'error': 'Please select at least one module for Modular marksheet generation.'})
    if not candidates.exists():
        return JsonResponse({'success': False, 'error': 'No enrolled candidates found for the selected parameters.'})

    url = reverse('download_marksheet') + '?' + urllib.parse.urlencode(params)
    return JsonResponse({'success': True, 'download_url': url})

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
    if occupation_id:
        candidates = candidates.filter(occupation_id=occupation_id)
    # Only filter by level for non-modular, and only if Candidate has level field
    # For formal (module-based), filter by CandidateLevel
    if regcat_normalized == 'formal' and structure_type == 'modules' and level:
        from .models import CandidateLevel
        enrolled_ids = set(CandidateLevel.objects.filter(level=level).values_list('candidate_id', flat=True))
        candidates = candidates.filter(id__in=enrolled_ids)
    elif regcat_normalized != 'modular' and hasattr(Candidate, 'level') and level:
        candidates = candidates.filter(level=level)
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
        enrolled_level_ids = set(CandidateLevel.objects.filter(level=level).values_list('candidate_id', flat=True))
        candidates = candidates.filter(id__in=enrolled_level_ids)
        modules = list(Module.objects.filter(occupation=occupation, level=level))
    # Formal: Paper-based (dynamic paper codes per occupation/level)
    elif regcat_normalized == 'formal' and structure_type == 'papers':
        enrolled_ids = set(CandidateLevel.objects.filter(level=level).values_list('candidate_id', flat=True))
        candidates = candidates.filter(id__in=enrolled_ids)
    # Informal/Worker's PAS: Only papers, not modules
    elif regcat_normalized in ['informal', "worker's pas"]:
        informal = True
        # Only include enrolled papers (CandidatePaper)
        enrolled_papers = CandidatePaper.objects.filter(candidate__in=candidates, level=level)
        paper_ids = enrolled_papers.values_list('paper_id', flat=True).distinct()
        papers = list(Paper.objects.filter(id__in=paper_ids))
        enrolled_ids = set(enrolled_papers.values_list('candidate_id', flat=True))
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
        response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="marksheet_{regcat}_{occupation.code if occupation else ""}_{year}_{month}.xlsx"'
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
        response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="marksheet_{regcat}_{occupation.code if occupation else ""}_{year}_{month}.xlsx"'
        return response

    if not modules and not papers:
        wb = Workbook()
        ws = wb.active
        ws.title = 'Marksheet'
        ws.append(['No modules or papers found for the selected occupation and level.'])
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        filename = f"marksheet_{regcat_normalized or 'all'}_{month or ''}_{year or ''}.xlsx"
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
    for candidate in candidates:
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
        ws.append(row + marks)

    # --- Stream to memory ---
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"marksheet_{regcat_normalized or 'all'}_{month or ''}_{year or ''}.xlsx"
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
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    expected_headers = [
        'full_name', 'gender', 'nationality', 'date_of_birth', 'occupation', 'registration_category',
        'assessment_center', 'entry_year', 'intake', 'start_date', 'finish_date', 'assessment_date'
    ]
    if headers != expected_headers:
        errors.append('Excel headers do not match template. Please download the latest template.')
        return render(request, 'candidates/import_dual.html', {'errors': errors, 'imported_count': 0})
    # Unzip images to temp dir
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            with zipfile.ZipFile(photo_zip) as zf:
                image_names = sorted([n for n in zf.namelist() if n.lower().endswith(('.jpg', '.jpeg', '.png'))])
                zf.extractall(tmp_dir)
        except Exception:
            errors.append('Invalid ZIP file or unable to extract images.')
            return render(request, 'candidates/import_dual.html', {'errors': errors, 'imported_count': 0})
        # Read Excel rows
        rows = [row for row in ws.iter_rows(min_row=2, values_only=True) if not all(cell is None for cell in row)]
        if len(rows) != len(image_names):
            errors.append(f"Number of images ({len(image_names)}) does not match number of candidates ({len(rows)}).")
            return render(request, 'candidates/import_dual.html', {'errors': errors, 'imported_count': 0})
        for idx, (row, img_name) in enumerate(zip(rows, image_names), start=2):
            data = dict(zip(headers, row))
            # --- (reuse import logic from candidate_import) ---
            form_data = data.copy()
            # Dates: convert DD/MM/YYYY to date objects
            for date_field in ['date_of_birth', 'start_date', 'finish_date', 'assessment_date']:
                val = form_data.get(date_field)
                if val:
                    try:
                        # Accept both D/M/YYYY and DD/MM/YYYY
                        form_data[date_field] = datetime.strptime(str(val), '%d/%m/%Y').date()
                    except Exception:
                        try:
                            form_data[date_field] = datetime.strptime(str(val), '%-d/%-m/%Y').date()
                        except Exception:
                            errors.append(f"Row {idx}: Invalid date format in '{date_field}'. Use D/M/YYYY or DD/MM/YYYY.")
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
                if val is not None:
                    val_str = str(val).strip()
                    obj = model_cls.objects.filter(name__iexact=val_str).first()
                    form_data[loc_field] = obj.id if obj else None
                else:
                    form_data[loc_field] = None
            # Parse and normalize date fields to zero-padded DD/MM/YYYY
            date_fields = ['date_of_birth', 'start_date', 'finish_date', 'assessment_date']
            fk_fields = ['occupation', 'assessment_center', 'district', 'village']
            from datetime import date, datetime
            try:
                from dateutil import parser as dateparser
            except ImportError:
                import dateutil.parser as dateparser
            for k in date_fields:
                v = form_data.get(k)
                if v is not None and v != '':
                    dt_obj = None
                    # Try parsing as date/datetime/int/float/string
                    if isinstance(v, (date, datetime)):
                        dt_obj = v
                    else:
                        try:
                            dt_obj = dateparser.parse(str(v), dayfirst=True, yearfirst=False)
                        except Exception:
                            dt_obj = None
                    if dt_obj:
                        form_data[k] = dt_obj.strftime('%d/%m/%Y')
                    else:
                        form_data[k] = ''  # Invalid date, let form validation handle

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
                errors.append(f"Row {idx}: Candidate '{form_data['full_name']}' with same DOB, gender, and center already exists. Skipped.")
                continue
            candidate = form.save(commit=False)
            candidate.reg_number = None  # Regenerate
            # Attach image
            img_path = os.path.join(tmp_dir, img_name)
            if os.path.exists(img_path):
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
                    # Save processed image as JPEG
                    candidate.passport_photo.save(
                        os.path.splitext(img_name)[0] + '.jpg',
                        File(buffer),
                        save=False
                    )
            else:
                errors.append(f"Row {idx}: Image file '{img_name}' not found after extraction.")
                continue
            candidate.save()
            created += 1
    return render(request, 'candidates/import_dual.html', {
        'errors': errors,
        'imported_count': created
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
    if len(occupations) != 1 or len(regcats) != 1 or regcats.pop() != 'Modular':
        return JsonResponse({'success': False, 'error': 'All candidates must be Modular and have the same occupation.'}, status=400)

    occupation_id = occupations.pop()
    level = Level.objects.filter(name__icontains='1').first()
    if not level:
        return JsonResponse({'success': False, 'error': 'Level 1 not found.'}, status=400)
    modules = Module.objects.filter(occupation_id=occupation_id, level=level)
    module_list = [{'id': m.id, 'name': m.name} for m in modules]
    return JsonResponse({'success': True, 'modules': module_list})

@login_required
@require_POST
def bulk_candidate_action(request):
    import json
    try:
        data = json.loads(request.body.decode()) if request.body else request.POST
        action = data.get('action')
        ids = data.get('candidate_ids')
        if isinstance(ids, str):
            ids = ids.split(',')
        candidate_ids = [int(i) for i in ids if str(i).isdigit()]
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

    candidates = Candidate.objects.filter(id__in=candidate_ids)
    if not candidates.exists():
        return JsonResponse({'success': False, 'error': 'No candidates found.'}, status=400)

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

    if action == 'enroll':
        # Enforce same occupation and reg category
        occupations = set(c.occupation_id for c in candidates)
        regcats = set(c.registration_category for c in candidates)
        if len(occupations) != 1 or len(regcats) != 1:
            return JsonResponse({'success': False, 'error': 'All candidates must have the same occupation and registration category to enroll together.'}, status=400)
        regcat = regcats.pop()
        from .models import Level, CandidateLevel, CandidateModule, Module
        if regcat == 'Formal':
            # Enroll each candidate in Level 1 (or add TODO for level selection)
            level = Level.objects.filter(name__icontains='1').first()
            if not level:
                return JsonResponse({'success': False, 'error': 'Level 1 not found.'}, status=400)
            enrolled = 0
            for c in candidates:
                # Remove previous
                CandidateLevel.objects.filter(candidate=c).delete()
                CandidateLevel.objects.create(candidate=c, level=level)
                enrolled += 1
            return JsonResponse({'success': True, 'message': f'Enrolled {enrolled} candidates in Level 1.'})
        elif regcat == 'Modular':
            # Modular: use provided module_ids
            occupation_id = occupations.pop()
            level = Level.objects.filter(name__icontains='1').first()
            if not level:
                return JsonResponse({'success': False, 'error': 'Level 1 not found.'}, status=400)
            try:
                data = json.loads(request.body.decode()) if request.body else request.POST
                module_ids = data.get('module_ids', [])
                if isinstance(module_ids, str):
                    module_ids = module_ids.split(',')
                module_ids = [int(mid) for mid in module_ids if str(mid).isdigit()]
            except Exception:
                return JsonResponse({'success': False, 'error': 'Could not read selected modules.'}, status=400)
            if not (1 <= len(module_ids) <= 2):
                return JsonResponse({'success': False, 'error': 'Select 1 or 2 modules.'}, status=400)
            modules = Module.objects.filter(id__in=module_ids, occupation_id=occupation_id, level=level)
            if modules.count() != len(module_ids):
                return JsonResponse({'success': False, 'error': 'Invalid module selection.'}, status=400)
            enrolled = 0
            for c in candidates:
                # Remove previous
                CandidateModule.objects.filter(candidate=c).delete()
                for m in modules:
                    CandidateModule.objects.create(candidate=c, module=m)
                enrolled += 1
            return JsonResponse({'success': True, 'message': f'Successfully enrolled {enrolled} candidates in {modules.count()} module(s).'})
        else:
            return JsonResponse({'success': False, 'error': 'Bulk enroll only supported for Formal or Modular registration categories.'}, status=400)

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
    else:
        return JsonResponse({'success': False, 'error': 'Unknown action.'}, status=400)

from django.urls import reverse
from .models import AssessmentCenter, Candidate, Occupation, AssessmentCenterCategory, Level, Module, Paper, CandidateLevel, CandidateModule, Village, District
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



@login_required
def dashboard(request):
    group_names = list(request.user.groups.values_list('name', flat=True))
    return render(request, 'dashboard.html', {'group_names': group_names})

def district_villages_api(request, district_id):
    villages = Village.objects.filter(district_id=district_id).values('id', 'name')
    # returns [{"id": 3, "name": "Ntare"}, ...]
    return JsonResponse(list(villages), safe=False)


def assessment_center_list(request):
    centers = AssessmentCenter.objects.all()
    return render(request, 'assessment_centers/list.html', {'centers': centers})



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


def assessment_center_list(request):
    centers = AssessmentCenter.objects.all()
    search = request.GET.get('search')
    category_id = request.GET.get('category')

    if search:
        centers = centers.filter(center_name__icontains=search)
    if category_id:
        centers = centers.filter(category_id=category_id)

    categories = AssessmentCenterCategory.objects.all()

    return render(request, 'assessment_centers/list.html', {
        'centers': centers,
        'categories': categories
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
    occupations = Occupation.objects.all()
    code = request.GET.get('code', '').strip()
    name = request.GET.get('name', '').strip()
    structure = request.GET.get('structure', '').strip()

    if code:
        occupations = occupations.filter(code__icontains=code)
    if name:
        occupations = occupations.filter(name__icontains=name)
    if structure:
        occupations = occupations.filter(structure_type=structure)

    return render(request, 'occupations/list.html', {
        'occupations': occupations,
        'structure_choices': Occupation.STRUCTURE_CHOICES,
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

@login_required
def api_levels_for_occupation(request):
    occ_id = request.GET.get('occupation_id')
    levels = []
    if occ_id:
        levels = list(Level.objects.filter(occupation_id=occ_id).values('id', 'name'))
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

def module_list(request):
    modules = Module.objects.all()
    occupations = Occupation.objects.all()
    levels = Level.objects.all()
    
    # Filter by occupation if specified
    occupation_id = request.GET.get('occupation')
    if occupation_id:
        modules = modules.filter(occupation_id=occupation_id)
    
    # Filter by level if specified
    level_id = request.GET.get('level')
    if level_id:
        modules = modules.filter(level_id=level_id)
    
    context = {
        'modules': modules,
        'occupations': occupations,
        'levels': levels,
        'selected_occupation': occupation_id,
        'selected_level': level_id
    }
    
    return render(request, 'modules/list.html', context)

def module_create(request):
    if request.method == 'POST':
        form = ModuleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('module_list')
    else:
        form = ModuleForm()
    return render(request, 'modules/create.html', {'form': form})


def module_detail(request, pk):
    module = get_object_or_404(Module, pk=pk)
    return render(request, 'modules/detail.html', {'module': module})


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
    papers = Paper.objects.select_related('level', 'occupation').all()
    occupations = Occupation.objects.all()
    levels = Level.objects.all()

    occupation_id_str = request.GET.get('occupation')
    level_id_str = request.GET.get('level')

    selected_occupation = None
    if occupation_id_str and occupation_id_str.isdigit():
        selected_occupation = int(occupation_id_str)
        papers = papers.filter(occupation_id=selected_occupation)

    selected_level = None
    if level_id_str and level_id_str.isdigit():
        selected_level = int(level_id_str)
        papers = papers.filter(level_id=selected_level)

    context = {
        'papers': papers,
        'occupations': occupations,
        'levels': levels,
        'selected_occupation': selected_occupation,
        'selected_level': selected_level,
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

# --- Fees Type Views ---
from .models import FeesType
from .forms import FeesTypeForm
from django.contrib import messages

def fees_type_list(request):
    fees_types = FeesType.objects.all()
    return render(request, 'fees_type/list.html', {'fees_types': fees_types})

def fees_type_create(request):
    if request.method == 'POST':
        form = FeesTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fees Type created successfully.')
            return redirect('fees_type_list')
    else:
        form = FeesTypeForm()
    return render(request, 'fees_type/create.html', {'form': form})

def fees_type_edit(request, pk):
    fees_type = get_object_or_404(FeesType, pk=pk)
    if request.method == 'POST':
        form = FeesTypeForm(request.POST, instance=fees_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fees Type updated successfully.')
            return redirect('fees_type_list')
    else:
        form = FeesTypeForm(instance=fees_type)
    return render(request, 'fees_type/edit.html', {'form': form, 'fees_type': fees_type})

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
    centers = AssessmentCenter.objects.all()
    occupations = Occupation.objects.all()
    levels = Level.objects.all() # Though not directly used in this version's header/table structure as per screenshot

    if request.method == 'POST':
        center_id = request.POST.get('center')
        occupation_id = request.POST.get('occupation')
        reg_category_form = request.POST.get('registration_category', '') # Name from form
        level_id = request.POST.get('level') # Keep for filtering logic if needed
        assessment_month_str = request.POST.get('assessment_month')
        assessment_year_str = request.POST.get('assessment_year')

        if not all([center_id, occupation_id, reg_category_form, assessment_month_str, assessment_year_str]):
            return HttpResponse("All filter parameters are required.", status=400)

        try:
            assessment_month = int(assessment_month_str)
            assessment_year = int(assessment_year_str)
            center = AssessmentCenter.objects.get(id=center_id)
            occupation = Occupation.objects.get(id=occupation_id)
        except (ValueError, AssessmentCenter.DoesNotExist, Occupation.DoesNotExist) as e:
            return HttpResponse(f"Invalid parameter: {e}", status=400)

        # Candidate Querying lets limit candididate_qs to 5 candidates
        candidate_qs = Candidate.objects.select_related('occupation', 'assessment_center').filter(
            assessment_center=center,
            occupation=occupation,
            registration_category__iexact=reg_category_form, # Use form value for filtering
            assessment_date__year=assessment_year,
            assessment_date__month=assessment_month
        ).order_by('reg_number')

        # Optional level filtering (if applicable for the registration category)
        if reg_category_form.lower() in ['formal', 'informal', 'workers pas'] and level_id:
            candidate_qs = candidate_qs.filter(
                id__in=CandidateLevel.objects.filter(level_id=level_id).values('candidate_id')
            )
        
        final_candidates = list(candidate_qs)
        if not final_candidates:
            return HttpResponse("No candidates found matching the criteria.", status=404)

        # PDF Generation
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
                break
        
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
        table_header_style = ParagraphStyle('TableHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, alignment=TA_CENTER, textColor=colors.white)
        table_cell_style = ParagraphStyle('TableCell', parent=styles['Normal'], fontSize=8, alignment=TA_LEFT, leading=10)
        table_cell_center_style = ParagraphStyle('TableCellCenter', parent=table_cell_style, alignment=TA_CENTER)

        data = []
        # Table Headers
        header_row = [Paragraph(h, table_header_style) for h in ['S/N', 'PHOTO', 'REG NO.', 'FULL NAME', 'OCCUPATION', 'REG TYPE', 'SIGNATURE']]
        data.append(header_row)

        for i, cand in enumerate(final_candidates):
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
        except Exception as e:
            # Handle potential errors during the first pass, though less likely with a simple callback
            print(f"Error during page count pass: {e}")
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
        try:
            doc.build(elements, 
                      onFirstPage=lambda c, d: _add_page_numbers(c, d, total_pages), 
                      onLaterPages=lambda c, d: _add_page_numbers(c, d, total_pages))
            buffer.seek(0)
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="candidate_album_{center.center_number}_{occupation.code}_{assessment_year}_{assessment_month}.pdf"'
            return response
        except Exception as e:
            print(f"Error building PDF: {e}")
            import traceback
            traceback.print_exc()
            return HttpResponse(f"Error generating PDF: {e}", status=500)

    # GET request or if form not submitted properly
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

def candidate_list(request):
    # Get current filters from session or initialize
    current_filters = request.session.get('candidate_filters', {})

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

    # Filtering logic from session filters
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

    from .models import Occupation, AssessmentCenter
    occupations = Occupation.objects.all()
    centers = AssessmentCenter.objects.all()

    # Pagination: 100 per page
    paginator = Paginator(candidates, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    import urllib
    filter_params = urllib.parse.urlencode(current_filters)

    return render(request, 'candidates/list.html', {
        'candidates': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_candidates': paginator.count,
        'occupations': occupations,
        'centers': centers,
        'filters': current_filters,
        'filter_params': filter_params,
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
                # Not already enrolled: clear previous enrollments and enroll
                CandidateLevel.objects.filter(candidate=candidate).delete()
                CandidateModule.objects.filter(candidate=candidate).delete()
                CandidateLevel.objects.create(candidate=candidate, level=level)
                messages.success(request, f"{candidate.full_name} enrolled in {level.name}")

            # Handle modular registration (must select 1–2 modules, Level 1 only)
            elif registration_category == 'Modular':
                modules = form.cleaned_data['modules']
                if len(modules) > 2:
                    messages.error(request, "You can only select up to 2 modules.")
                else:
                    for module in modules:
                        CandidateModule.objects.create(candidate=candidate, module=module)
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
    messages.success(request, 'All enrollment records for this candidate have been cleared.')
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
                papers = [cp.paper for cp in CandidatePaper.objects.filter(candidate=candidate, module=mod_enroll.module, level=lvl_enroll.level).select_related('paper')]
                module_list.append({
                    'module': mod_enroll.module,
                    'papers': papers
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
    districts = District.objects.all()
    return render(request, 'configurations/district_list.html', {'districts': districts})

def district_create(request):
    form = DistrictForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('district_list')
    return render(request, 'configurations/district_form.html', {'form': form})

def village_list(request):
    district_id = request.GET.get('district')
    villages = Village.objects.select_related('district').all()
    
    if district_id:
        villages = villages.filter(district_id=district_id)
        district = District.objects.get(id=district_id)
        context = {
            'villages': villages,
            'current_district': district
        }
    else:
        districts = District.objects.all()
        context = {
            'villages': villages,
            'districts': districts
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
    return render(request, 'occupations/edit.html', {
        'form': form,
        'occupation': occupation,
        'levels': levels_with_stype
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



