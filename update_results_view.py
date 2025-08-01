#!/usr/bin/env python3
"""
Script to update the results_home view in views.py
"""

import re

# Read the current views.py file
with open('/home/claire/Desktop/projects/emis/emis/eims/views.py', 'r') as f:
    content = f.read()

# Define the new results_home function
new_function = '''@login_required
def results_home(request):
    logger = logging.getLogger(__name__)
    logger.info(f'Results home accessed by user: {request.user}')
    
    # Fetch enrolled candidates with their marks status
    enrolled_candidates = Candidate.objects.filter(
        status='enrolled'
    ).select_related('occupation', 'assessment_center').order_by('reg_number')
    
    # Add upload status annotation
    candidates_with_status = []
    for candidate in enrolled_candidates:
        # Check if candidate has any results/marks
        has_marks = Result.objects.filter(candidate=candidate).exists()
        
        candidates_with_status.append({
            'candidate': candidate,
            'upload_status': 'Uploaded' if has_marks else 'Not Uploaded'
        })
    
    return render(request, 'results/home.html', {
        'candidates_with_status': candidates_with_status
    })'''

# Replace the old function with the new one
pattern = r'@login_required\ndef results_home\(request\):\s+logger = logging\.getLogger\(__name__\)\s+logger\.info\(f\'Results home accessed by user: \{request\.user\}\'\)\s+return render\(request, \'results/home\.html\'\)'

updated_content = re.sub(pattern, new_function, content, flags=re.MULTILINE | re.DOTALL)

# Write the updated content back
with open('/home/claire/Desktop/projects/emis/emis/eims/views.py', 'w') as f:
    f.write(updated_content)

print("Successfully updated results_home view!")
