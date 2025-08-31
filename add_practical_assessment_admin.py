#!/usr/bin/env python3
"""
Script to add Practical Assessment module to Admin department section in dashboard.html
"""

import re

def add_practical_assessment_to_admin():
    dashboard_file = '/home/claire/Desktop/projects/emis/emis/eims/templates/dashboard.html'
    
    # Read the file
    with open(dashboard_file, 'r') as f:
        content = f.read()
    
    # Define the Practical Assessment module HTML
    practical_assessment_module = '''        
        <!-- Practical Assessment Module -->
        <a href="#" class="transform hover:scale-105 transition-all duration-200 flex flex-col items-center touch-target">
          <div class="bg-teal-600 shadow-md rounded-xl p-4 mb-2 hover:shadow-lg w-16 h-16 sm:w-20 sm:h-20 flex items-center justify-center">
            <svg class="w-8 h-8 sm:w-10 sm:h-10 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd"/>
            </svg>
          </div>
          <div class="text-xs sm:text-sm font-normal text-white text-center px-1">Practical Assessment</div>
        </a>
'''
    
    # Find the Admin department section and locate the Awards module
    admin_section_pattern = r'({% elif user_department == "Admin" %}.*?<!-- Admin Department Modules \(All including Users\) -->.*?Awards</div>\s*</a>)\s*(\s*<a href="{% url \'config_home\' %}")'
    
    # Replace with the Awards module + Practical Assessment module + Configuration module
    replacement = r'\1' + practical_assessment_module + r'\2'
    
    # Apply the replacement
    new_content = re.sub(admin_section_pattern, replacement, content, flags=re.DOTALL)
    
    # Check if replacement was made
    if new_content != content:
        # Write back to file
        with open(dashboard_file, 'w') as f:
            f.write(new_content)
        print("Successfully added Practical Assessment module to Admin department section!")
        return True
    else:
        print("No changes made - pattern not found or already exists")
        return False

if __name__ == "__main__":
    add_practical_assessment_to_admin()
