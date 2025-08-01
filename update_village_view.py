#!/usr/bin/env python3
"""
Script to update the village_list view with pagination and filters
"""

import re

# Read the current views.py file
with open('/home/claire/Desktop/projects/emis/emis/eims/views.py', 'r') as f:
    content = f.read()

# Define the new village_list function with pagination and filters
new_function = '''def village_list(request):
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
    
    return render(request, 'configurations/village_list.html', context)'''

# Find and replace the old function
pattern = r'def village_list\(request\):.*?return render\(request, \'configurations/village_list\.html\', context\)'

updated_content = re.sub(pattern, new_function, content, flags=re.MULTILINE | re.DOTALL)

# Write the updated content back
with open('/home/claire/Desktop/projects/emis/emis/eims/views.py', 'w') as f:
    f.write(updated_content)

print("Successfully updated village_list view with pagination and filters!")
