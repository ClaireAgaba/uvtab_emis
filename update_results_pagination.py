#!/usr/bin/env python3
"""
Script to update the results_home view with pagination and filters
"""

import re

# Read the current views.py file
with open('/home/claire/Desktop/projects/emis/emis/eims/views.py', 'r') as f:
    content = f.read()

# Define the new results_home function with pagination and filters
new_function = '''@login_required
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
    })'''

# Find and replace the old function
pattern = r'@login_required\ndef results_home\(request\):.*?return render\(request, \'results/home\.html\', \{[^}]*\}\)'

updated_content = re.sub(pattern, new_function, content, flags=re.MULTILINE | re.DOTALL)

# Write the updated content back
with open('/home/claire/Desktop/projects/emis/emis/eims/views.py', 'w') as f:
    f.write(updated_content)

print("Successfully updated results_home view with pagination and filters!")
