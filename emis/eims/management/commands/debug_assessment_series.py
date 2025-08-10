from django.core.management.base import BaseCommand
from eims.models import Candidate, CandidateModule, AssessmentSeries


class Command(BaseCommand):
    help = 'Debug assessment series assignment for candidates and modules'

    def handle(self, *args, **options):
        self.stdout.write('=== Assessment Series Debug ===')
        
        # Check if assessment series field exists on Candidate model
        candidate_fields = [f.name for f in Candidate._meta.get_fields()]
        self.stdout.write(f'Candidate model fields: {candidate_fields}')
        self.stdout.write(f'Has assessment_series field: {"assessment_series" in candidate_fields}')
        
        # Check if assessment series field exists on CandidateModule model
        try:
            module_fields = [f.name for f in CandidateModule._meta.get_fields()]
            self.stdout.write(f'CandidateModule model fields: {module_fields}')
            self.stdout.write(f'Has assessment_series field: {"assessment_series" in module_fields}')
        except Exception as e:
            self.stdout.write(f'Error checking CandidateModule fields: {e}')
        
        # Check recent candidates and their assessment series
        recent_candidates = Candidate.objects.filter(registration_category='Modular').order_by('-id')[:5]
        self.stdout.write(f'\n=== Recent Modular Candidates ===')
        
        for candidate in recent_candidates:
            self.stdout.write(f'Candidate {candidate.id}: {candidate.full_name}')
            
            # Check candidate's assessment series
            try:
                assessment_series = getattr(candidate, 'assessment_series', None)
                self.stdout.write(f'  Candidate assessment_series: {assessment_series}')
            except Exception as e:
                self.stdout.write(f'  Error getting candidate assessment_series: {e}')
            
            # Check candidate's modules and their assessment series
            try:
                modules = CandidateModule.objects.filter(candidate=candidate)
                self.stdout.write(f'  Number of modules: {modules.count()}')
                
                for module in modules:
                    try:
                        module_assessment_series = getattr(module, 'assessment_series', None)
                        self.stdout.write(f'    Module {module.module.name}: assessment_series = {module_assessment_series}')
                    except Exception as e:
                        self.stdout.write(f'    Module {module.module.name}: Error getting assessment_series = {e}')
                        
            except Exception as e:
                self.stdout.write(f'  Error getting modules: {e}')
            
            self.stdout.write('')
        
        # Check available assessment series
        self.stdout.write('=== Available Assessment Series ===')
        assessment_series_list = AssessmentSeries.objects.all().order_by('-id')[:3]
        for series in assessment_series_list:
            self.stdout.write(f'ID {series.id}: {series.name} (Current: {series.is_current})')
        
        self.stdout.write('=== Debug Complete ===')
