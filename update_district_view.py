#!/usr/bin/env python3
"""
Script to update the district_list view with pagination and filters
"""

import re

# Read the current views.py file
with open('/home/claire/Desktop/projects/emis/emis/eims/views.py', 'r') as f:
    content = f.read()

# Define the new district_list function with pagination and filters
new_function = '''def district_list(request):
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
    })'''

# Find and replace the old function
pattern = r'def district_list\(request\):.*?return render\(request, \'configurations/district_list\.html\', \{[^}]*\}\)'

updated_content = re.sub(pattern, new_function, content, flags=re.MULTILINE | re.DOTALL)

# Write the updated content back
with open('/home/claire/Desktop/projects/emis/emis/eims/views.py', 'w') as f:
    f.write(updated_content)

print("Successfully updated district_list view with pagination and filters!")
