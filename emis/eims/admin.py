from django.contrib import admin
from django import forms  # ✅ this is the missing line

from .models import (
    Occupation, Module, Paper, Grade, AssessmentCenter, 
    District, Village, AssessmentCenterCategory, OccupationCategory, 
    RegistrationCategory, Level, Candidate,
)

# Paper form limited to occupations with structure_type='papers'
class PaperAdminForm(forms.ModelForm):
    class Meta:
        model = Paper
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['occupation'].queryset = Occupation.objects.filter(structure_type='papers')

class PaperAdmin(admin.ModelAdmin):
    form = PaperAdminForm

admin.site.register(Paper, PaperAdmin)

# Module form limited to occupations with structure_type='modules'
class ModuleAdminForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['occupation'].queryset = Occupation.objects.filter(structure_type='modules')

class ModuleAdmin(admin.ModelAdmin):
    form = ModuleAdminForm

class CandidateAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'reg_number', 'registration_category', 'occupation', 'assessment_center')
    search_fields = ('full_name', 'reg_number')
    list_filter = ('registration_category', 'occupation', 'assessment_center')

    def save_model(self, request, obj, form, change):
        # Save the object first to get the ID
        obj.save()
        # Now handle the many-to-many relationships
        form.save_m2m()




# Register others normally
admin.site.register(Occupation)
admin.site.register(Grade)
admin.site.register(AssessmentCenter)
admin.site.register(District)
admin.site.register(Village)
admin.site.register(AssessmentCenterCategory)
admin.site.register(OccupationCategory)
admin.site.register(RegistrationCategory)
admin.site.register(Level)
admin.site.register(Module, ModuleAdmin)
admin.site.register(Candidate, CandidateAdmin)
