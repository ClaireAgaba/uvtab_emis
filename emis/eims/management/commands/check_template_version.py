from django.core.management.base import BaseCommand
import os


class Command(BaseCommand):
    help = 'Check if enrollment_list template has the pagination fix'

    def handle(self, *args, **options):
        from django.conf import settings
        
        # Find the template file
        template_path = None
        for template_dir in settings.TEMPLATES[0]['DIRS']:
            potential_path = os.path.join(template_dir, 'candidates', 'enrollment_list.html')
            if os.path.exists(potential_path):
                template_path = potential_path
                break
        
        if not template_path:
            # Try app directories
            import eims
            app_dir = os.path.dirname(eims.__file__)
            potential_path = os.path.join(app_dir, 'templates', 'candidates', 'enrollment_list.html')
            if os.path.exists(potential_path):
                template_path = potential_path
        
        if not template_path:
            self.stdout.write(self.style.ERROR('Template file not found!'))
            return
        
        self.stdout.write(f'Template path: {template_path}')
        
        # Read the file and check for the fix
        with open(template_path, 'r') as f:
            content = f.read()
        
        # Check if the new pagination code is present
        if 'for key, value in request.GET.items' in content:
            self.stdout.write(self.style.SUCCESS('✓ Template has the pagination fix!'))
        else:
            self.stdout.write(self.style.ERROR('✗ Template does NOT have the pagination fix!'))
            self.stdout.write('The old manual parameter building is still in use.')
        
        # Show a snippet of the pagination code
        if '?page={{ page_num }}' in content:
            start = content.find('?page={{ page_num }}')
            snippet = content[start:start+200]
            self.stdout.write(f'\nPagination code snippet:\n{snippet}...')
