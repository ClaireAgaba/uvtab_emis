from django.shortcuts import render, get_object_or_404, redirect
from .forms import SupportStaffForm, CenterRepForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, QueryDict

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

""" def assessment_center_detail(request, pk):
    center = get_object_or_404(AssessmentCenter, pk=pk)
    candidates = Candidate.objects.filter(assessment_center=center)
    context = {
        'center': center,
        'candidates': candidates
    }
    return render(request, 'assessment_centers/view.html', context) """


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
    if request.method == 'POST':
        form = OccupationForm(request.POST)
        if form.is_valid():
            occupation = form.save(commit=False)
            occupation.created_by = request.user
            occupation.updated_by = request.user
            occupation.save()
            return redirect('occupation_list')
    else:
        form = OccupationForm()
    return render(request, 'occupations/create.html', {'form': form})

def occupation_view(request, pk):
    occupation = get_object_or_404(Occupation, pk=pk)
    return render(request, 'occupations/view.html', {'occupation': occupation})


def occupation_detail(request, pk):
    occupation = get_object_or_404(Occupation, pk=pk)
    levels = occupation.levels.all()

    level_data = []
    for level in levels:
        if occupation.structure_type == 'modules':
            content = Module.objects.filter(occupation=occupation, level=level)
        else:
            content = Paper.objects.filter(occupation=occupation, level=level)
        level_data.append({'level': level, 'content': content})

    return render(request, 'occupations/view.html', {
        'occupation': occupation,
        'levels': levels,
        'level_data': level_data
    })    


#Add Module View

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


def paper_list(request):
    papers = Paper.objects.all()
    occupations = Occupation.objects.all()
    levels = Level.objects.all()
    
    # Filter by occupation if specified
    occupation_id = request.GET.get('occupation')
    if occupation_id:
        papers = papers.filter(occupation_id=occupation_id)
    
    # Filter by level if specified
    level_id = request.GET.get('level')
    if level_id:
        papers = papers.filter(level_id=level_id)
    
    context = {
        'papers': papers,
        'occupations': occupations,
        'levels': levels,
        'selected_occupation': occupation_id,
        'selected_level': level_id
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

def paper_edit(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    if request.method == 'POST':
        form = PaperForm(request.POST, instance=paper)
        if form.is_valid():
            paper = form.save()
            return redirect('paper_list')
    else:
        form = PaperForm(instance=paper)
    return render(request, 'papers/edit.html', {'form': form, 'paper': paper})

def report_list(request):
    """Main reports dashboard showing available reports"""
    group_names = list(request.user.groups.values_list('name', flat=True))
    return render(request, 'reports/list.html', {'group_names': group_names})

def _get_candidate_photo(candidate, photo_width=1*inch, photo_height=1.2*inch):
    """Helper function to get and format candidate photo for PDF"""
    if candidate.passport_photo and os.path.exists(candidate.passport_photo.path):
        try:
            # Open and resize image to fit in cell
            img = PILImage.open(candidate.passport_photo.path)
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # Calculate aspect ratio and resize
            aspect = img.height / float(img.width)
            desired_width = photo_width
            desired_height = min(photo_height, desired_width * aspect)
            # Create ReportLab Image object
            img_reader = BytesIO()
            img.save(img_reader, 'JPEG')
            img_reader.seek(0)
            return Image(img_reader, width=desired_width, height=desired_height)
        except Exception as e:
            print(f"Error processing image for {candidate.full_name}: {e}")
            return 'No Photo'
    return 'No Photo'

@login_required
def generate_album(request):
    """Generate registration list (album) PDF based on selected parameters"""
    # Get all centers and occupations for the form
    centers = AssessmentCenter.objects.all()
    occupations = Occupation.objects.all()
    levels = Level.objects.all()
    
    if request.method == 'POST':
        # Debug form data
        print('POST data:', request.POST)
        
        center_id = request.POST.get('center')
        occupation_id = request.POST.get('occupation')
        reg_category = request.POST.get('registration_category', '')
        level_id = request.POST.get('level')
        assessment_month = request.POST.get('assessment_month')
        assessment_year = request.POST.get('assessment_year')
        
        # Debug query parameters
        print('Query params:', {
            'center_id': center_id,
            'occupation_id': occupation_id,
            'registration_category': reg_category,
            'level_id': level_id,
            'assessment_month': assessment_month,
            'assessment_year': assessment_year
        })
        
        # Query candidates based on parameters
        print('Checking candidates with category:', repr(reg_category))
        # First get all candidates for debugging
        from datetime import datetime
        
        # Handle assessment month and year
        print('Received assessment month/year:', assessment_month, assessment_year)
        if not assessment_month or not assessment_year:
            return HttpResponse('Assessment month and year are required', status=400)

        try:
            # Convert to integers
            month = int(assessment_month)
            year = int(assessment_year)
            
            print(f'Using month: {month}, year: {year}')

            # Filter candidates
            candidates = Candidate.objects.filter(
                assessment_center_id=center_id,
                occupation_id=occupation_id,
                registration_category__iexact=reg_category
            )

            # Debug candidate query
            print('Initial candidate count:', candidates.count())
            print('SQL Query:', candidates.query)

            # Add date filtering
            candidates = candidates.filter(
                assessment_date__year=year,
                assessment_date__month=month
            )

            print('Final candidate count:', candidates.count())
            print('Assessment dates:', [c.assessment_date for c in candidates])

        except ValueError as e:
            print(f'Error parsing date: {e}')
            print(f'Raw values - Month: {assessment_month!r}, Year: {assessment_year!r}')
            return HttpResponse(f'Invalid date format: {e}', status=400)
        print('All candidates before category filter:', candidates.count())
        print('Their categories:', [c.registration_category for c in candidates])
        
        # Debug query results
        print('SQL Query:', candidates.query)
        print('Found candidates:', candidates.count())
        for candidate in candidates:
            print(f'- {candidate.full_name} ({candidate.registration_category})')
        
        # Add level filter for formal/informal
        if reg_category in ['formal', 'informal'] and level_id:
            candidates = candidates.filter(level_id=level_id)
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                               rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.3*inch, bottomMargin=0.5*inch)
        elements = []
        
        # Create header styles
        styles = getSampleStyleSheet()
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=1,  # Center alignment
            spaceAfter=6
        )
        subheader_style = ParagraphStyle(
            'CustomSubHeader',
            parent=styles['Normal'],
            fontSize=12,
            alignment=1,  # Center alignment
            spaceAfter=20
        )
        
        # First row: Contact info and logo
        contact_table_data = [
            [
                Paragraph('P.O.Box 1499<br/>Email: info@uvtab.go.ug', styles['Normal']),
                '',  # Logo will go here
                Paragraph('Tel: 256 414 289786', styles['Normal'])
            ]
        ]
        
        # Find and add logo
        logo_path = None
        possible_paths = [
            os.path.join(settings.BASE_DIR, 'eims', 'static', 'images', 'uvtab logo.png'),
            os.path.join(settings.BASE_DIR, 'static', 'images', 'uvtab logo.png'),
            os.path.join(settings.BASE_DIR, 'emis', 'static', 'images', 'uvtab logo.png')
        ]
        for path in possible_paths:
            if os.path.exists(path):
                logo_path = path
                break
        
        if logo_path:
            logo = Image(logo_path, width=1.2*inch, height=1.2*inch)
            contact_table_data[0][1] = logo
        
        # Create contact info table
        contact_table = Table(contact_table_data, colWidths=[2.5*inch, 2*inch, 2.5*inch])
        contact_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(contact_table)
        # Reduced or removed spacer to save vertical space
        # elements.append(Spacer(1, 0.3*inch))  # Space after logo/contact
        
        # Second row: UVTAB full name
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=12
        )
        elements.append(Paragraph('UGANDA VOCATIONAL AND TECHNICAL ASSESSMENT BOARD', title_style))
        
        # Third row: Assessment period
        month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']
        formatted_date = f"{month_names[int(assessment_month)-1]} {assessment_year}"
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=12
        )
        elements.append(Paragraph(f"Registered Candidates for {formatted_date} Assessment", subtitle_style))
        
        # Fourth row: Assessment Center
        center = AssessmentCenter.objects.get(id=center_id)
        center_style = ParagraphStyle(
            'CenterInfo',
            parent=styles['Normal'],
            fontSize=12,
            alignment=TA_CENTER,
            spaceAfter=12
        )
        elements.append(Paragraph(f"Assessment Center: {center.center_number} - {center.center_name}", center_style))
        
        # Add spacer before details
        elements.append(Spacer(1, 20))
        
        # Details section
        occupation = Occupation.objects.get(id=occupation_id)
        details_style = ParagraphStyle(
            'Details',
            parent=styles['Normal'],
            fontSize=11,
            alignment=TA_LEFT,
            spaceAfter=6
        )
        
        # Occupation details
        elements.append(Paragraph(f"Occupation Name: {occupation.name}", details_style))
        elements.append(Paragraph(f"Occupation Code: {occupation.code}", details_style))
        elements.append(Paragraph(f"Registration Category: {reg_category.title()}", details_style))
        
        # Add level for formal/informal
        if reg_category.lower() in ['formal', 'informal'] and level_id:
            level = Level.objects.get(id=level_id)
            elements.append(Paragraph(f"Level: {level.name}", details_style))
        
        # Add spacer before table
        elements.append(Spacer(1, 20))
        
        # Table headers
        headers = ['S/N', 'Photo', 'Reg No.', 'Full Name', 'Occupation', 'Reg Type']
        if reg_category in ['formal', 'informal']:
            headers.append('Level')
        if reg_category in ['informal', 'modular']:
            headers.append('No. of Modules')
        headers.append('Signature')
        
        # Prepare table data with word wrapping
        styles = getSampleStyleSheet()
        normal_style = styles['Normal']
        normal_style.wordWrap = 'CJK'  # Better word wrapping
        normal_style.fontSize = 8  # Smaller font for better fit

        def chunked(lst, n):
            for i in range(0, len(lst), n):
                yield lst[i:i + n]

        # Estimate how many candidates fit per page (experimentally, 8-12)
        candidates_per_page = 1000
        candidate_rows = []
        for index, candidate in enumerate(candidates, 1):
            row = [
                str(index),  # Serial number
                _get_candidate_photo(candidate, photo_width=0.7*inch, photo_height=0.7*inch),
                Paragraph(candidate.reg_number, normal_style),
                Paragraph(candidate.full_name, normal_style),
                Paragraph(candidate.occupation.name, normal_style),
                Paragraph(candidate.registration_category, normal_style)
            ]
            if reg_category in ['formal', 'informal']:
                row.append(candidate.level.name)
            if reg_category in ['informal', 'modular']:
                module_count = candidate.candidatemodule_set.count()
                row.append(str(module_count))
            row.append('')  # Empty signature field
            candidate_rows.append(row)

        # Calculate page width and margins
        page_width = landscape(letter)[0]
        left_margin = right_margin = 0.5*inch
        available_width = page_width - (left_margin + right_margin)

        col_widths = [
            0.4*inch,   # S/N
            0.7*inch,   # Photo
            1.8*inch,   # Reg No
            2.2*inch,   # Full Name
            1.4*inch,   # Occupation
            1.0*inch,   # Reg Type
        ]
        if reg_category in ['Formal', 'Informal']:
            col_widths.append(1.0*inch)  # Level
        if reg_category in ['Informal', 'Modular']:
            col_widths.append(0.8*inch)  # No. of Modules
        col_widths.append(1.0*inch)  # Signature

        total_col_width = sum(col_widths)
        if total_col_width > available_width:
            scale_factor = available_width / total_col_width
            col_widths = [w * scale_factor for w in col_widths]

        # Defensive: ensure all candidate rows have the same length as headers
        for r in candidate_rows:
            while len(r) < len(headers):
                r.append('')
            while len(r) > len(headers):
                r.pop()

        # Paginate candidate rows into pages
        pages = list(chunked(candidate_rows, candidates_per_page))
        for page_num, page_rows in enumerate(pages):
            # Always prepend headers to every page (fix for missing middle headers)
            data = [headers] + page_rows
            table = Table(data, colWidths=col_widths)
            table.setStyle(TableStyle([
                # Header styling (always for first row on every page)
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('TOPPADDING', (0, 0), (-1, 0), 5),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
                # Row style
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('TOPPADDING', (0, 1), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 1),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                # Alignment
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # Borders
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#2563eb')),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                # Specific column alignments
                ('ALIGN', (2, 1), (2, -1), 'LEFT'),
                ('ALIGN', (3, 1), (3, -1), 'LEFT'),
                # Alternating row colors
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
            ]))
            elements.append(table)
            # Add page break except after last page
            if page_num < len(pages) - 1:
                from reportlab.platypus import PageBreak
                elements.append(PageBreak())

        # Build PDF
        doc.build(elements)

        
        # Get the value of the BytesIO buffer and return the PDF as a response
        pdf = buffer.getvalue()
        buffer.close()
        response = HttpResponse(content_type='application/pdf')
        filename = f'Registration List - {center.center_name} - {occupation.name} - {reg_category.title()}'
        if reg_category in ['FORMAL', 'INFORMAL'] and level_id:
            level = Level.objects.get(id=level_id)
            filename += f' - {level.name}'
        filename = filename.replace(' ', '_') + '.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write(pdf)
        return response
    
    pages = None
    if request.method == 'POST':
        candidates = Candidate.objects.all()
        def chunked(lst, n):
            for i in range(0, len(lst), n):
                yield lst[i:i + n]
        pages = list(chunked(list(candidates), 5))
    return render(request, 'reports/albums.html', {
        'centers': centers,
        'occupations': occupations,
        'levels': levels,
        'pages': pages,
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
    candidates = Candidate.objects.select_related('occupation', 'assessment_center')
    # Restrict for Center Representatives
    if request.user.groups.filter(name='CenterRep').exists():
        from .models import CenterRepresentative
        try:
            center_rep = CenterRepresentative.objects.get(user=request.user)
            candidates = candidates.filter(assessment_center=center_rep.center)
        except CenterRepresentative.DoesNotExist:
            candidates = candidates.none()

    # Filtering logic
    reg_number = request.GET.get('reg_number', '').strip()
    search = request.GET.get('search', '').strip()
    occupation = request.GET.get('occupation', '').strip()
    registration_category = request.GET.get('registration_category', '').strip()
    assessment_center = request.GET.get('assessment_center', '').strip()

    if reg_number:
        candidates = candidates.filter(reg_number__icontains=reg_number)
    if search:
        candidates = candidates.filter(full_name__icontains=search)
    if occupation:
        candidates = candidates.filter(occupation_id=occupation)
    if registration_category:
        candidates = candidates.filter(registration_category=registration_category)
    if assessment_center:
        candidates = candidates.filter(assessment_center_id=assessment_center)

    from .models import Occupation, AssessmentCenter
    occupations = Occupation.objects.all()
    centers = AssessmentCenter.objects.all()

    # Pagination: 20 per page
    paginator = Paginator(candidates, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'candidates/list.html', {
        'candidates': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_candidates': paginator.count,
        'occupations': occupations,
        'centers': centers,
    })


def candidate_create(request):
    if request.method == 'POST':
        form = CandidateForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            candidate = form.save(commit=False)
            candidate.created_by = request.user
            candidate.updated_by = request.user
            candidate.save()
            return redirect('candidate_list')
    else:
        form = CandidateForm(user=request.user)
    return render(request, 'candidates/create.html', {'form': form})

def candidate_view(request, id):
    from .models import AssessmentCenter, Occupation
    candidate = get_object_or_404(Candidate, id=id)
    centers = AssessmentCenter.objects.all()
    occupations = Occupation.objects.all()
    return render(request, 'candidates/view.html', {'candidate': candidate, 'centers': centers, 'occupations': occupations})

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

    if request.method == 'POST':
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

            # Handle informal registration (level + any number of modules)
            elif registration_category == 'Informal':
                level = form.cleaned_data['level']
                modules = form.cleaned_data['modules']
                CandidateLevel.objects.create(candidate=candidate, level=level)
                for module in modules:
                    CandidateModule.objects.create(candidate=candidate, module=module)
                messages.success(request, f"{candidate.full_name} enrolled in {level.name} and selected {len(modules)} module(s)")

            messages.success(request, "Candidate enrolled successfully.")
            return redirect('candidate_view', id=candidate.id)

    else:
        form = EnrollmentForm(candidate=candidate)

    return render(request, 'candidates/enroll.html', {
        'form': form,
        'candidate': candidate,
    })



from .models import Candidate, CandidateLevel, CandidateModule, Occupation

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

@login_required
@require_POST
def change_candidate_occupation(request, id):
    import json
    candidate = get_object_or_404(Candidate, id=id)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body.decode())
            occupation_id = data.get('occupation')
            if not occupation_id:
                return JsonResponse({'success': False, 'error': 'No occupation selected.'}, status=400)
            new_occupation = Occupation.objects.filter(id=occupation_id).first()
            if not new_occupation:
                return JsonResponse({'success': False, 'error': 'Occupation not found.'}, status=404)
            if candidate.is_enrolled():
                return JsonResponse({'success': False, 'error': 'Occupation cannot be changed for enrolled/registered candidates.'}, status=400)
            if new_occupation.id == candidate.occupation.id:
                return JsonResponse({'success': False, 'error': 'Candidate already has this occupation.'}, status=400)
            candidate.occupation = new_occupation
            candidate.reg_number = None  # triggers regeneration
            candidate.save()
            return JsonResponse({
                'success': True,
                'occupation_name': new_occupation.name,
                'occupation_id': new_occupation.id,
                'reg_number': candidate.reg_number
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    # For GET, redirect to candidate view
    return redirect('candidate_view', id=id)

def candidate_view(request, id):
    candidate = get_object_or_404(Candidate, id=id)

    # Get enrolled level (if any)
    level_enrollment = CandidateLevel.objects.filter(candidate=candidate).first()

    # Get enrolled modules (if any)
    module_enrollments = CandidateModule.objects.filter(candidate=candidate)

    context = {
        'candidate': candidate,
        'level_enrollment': level_enrollment,
        'module_enrollments': module_enrollments,
    }

    return render(request, 'candidates/view.html', context)

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

@login_required
def change_candidate_center(request, id):
    from .models import AssessmentCenter
    import json
    candidate = get_object_or_404(Candidate, id=id)
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body.decode())
            center_id = data.get('assessment_center')
            if not center_id:
                return JsonResponse({'success': False, 'error': 'No center selected.'}, status=400)
            new_center = AssessmentCenter.objects.filter(id=center_id).first()
            if not new_center:
                return JsonResponse({'success': False, 'error': 'Assessment center not found.'}, status=404)
            if new_center.id == candidate.assessment_center.id:
                return JsonResponse({'success': False, 'error': 'Candidate is already in this center.'}, status=400)
            candidate.assessment_center = new_center
            candidate.reg_number = None  # triggers regeneration
            candidate.save()
            return JsonResponse({
                'success': True,
                'center_name': new_center.center_name,
                'center_id': new_center.id,
                'reg_number': candidate.reg_number
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    # For GET: render candidate view with all centers for modal
    from .models import AssessmentCenter
    centers = AssessmentCenter.objects.all()
    return render(request, 'candidates/view.html', {
        'candidate': candidate,
        'centers': centers,
    })

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
    occupation = get_object_or_404(Occupation, pk=pk)
    if request.method == 'POST':
        form = OccupationForm(request.POST, instance=occupation)
        if form.is_valid():
            occupation = form.save(commit=False)
            occupation.updated_by = request.user
            occupation.save()
            return redirect('occupation_detail', pk=occupation.pk)
    else:
        form = OccupationForm(instance=occupation)
    return render(request, 'occupations/edit.html', {'form': form, 'occupation': occupation})

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

