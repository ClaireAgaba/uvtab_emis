#!/usr/bin/env python3
"""
Script to update the natureofdisability_list view with pagination and filters
"""

import re

# Read the current views.py file
with open('/home/claire/Desktop/projects/emis/emis/eims/views.py', 'r') as f:
    content = f.read()

# Define the new natureofdisability_list function with pagination and filters
new_function = '''@login_required
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
    })'''

# Find and replace the old function
pattern = r'@login_required\ndef natureofdisability_list\(request\):.*?return render\(request, \'configurations/natureofdisability_list\.html\', \{[^}]*\}\)'

updated_content = re.sub(pattern, new_function, content, flags=re.MULTILINE | re.DOTALL)

# Write the updated content back
with open('/home/claire/Desktop/projects/emis/emis/eims/views.py', 'w') as f:
    f.write(updated_content)

print("Successfully updated natureofdisability_list view with pagination and filters!")
