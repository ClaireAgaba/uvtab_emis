from django.contrib import admin
from django import forms  # ✅ this is the missing line

from .models import (
    SupportStaff, CenterRepresentative, Occupation, Module, Paper, Grade, AssessmentCenter,
    District, Village, AssessmentCenterCategory, OccupationCategory,
    RegistrationCategory, Level, Candidate
)

# Paper form limited to occupations with structure_type='papers'
class PaperAdminForm(forms.ModelForm):
    class Meta:
        model = Paper
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['occupation'].queryset = Occupation.objects.filter(occupation_levels__structure_type='papers').distinct()

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
        self.fields['occupation'].queryset = Occupation.objects.filter(occupation_levels__structure_type='modules').distinct()

class ModuleAdmin(admin.ModelAdmin):
    form = ModuleAdminForm

class CandidateAdminForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Occupation, OccupationCategory
        reg_cat = None
        # Prefer form data, then initial, then instance (admin edit)
        if self.data.get('registration_category'):
            reg_cat = self.data.get('registration_category')
        elif self.initial.get('registration_category'):
            reg_cat = self.initial.get('registration_category')
        elif hasattr(self, 'instance') and getattr(self.instance, 'registration_category', None):
            reg_cat = self.instance.registration_category
        self.fields['occupation'].queryset = Occupation.objects.none()
        self.fields['occupation'].widget.attrs['disabled'] = True
        if reg_cat and str(reg_cat).strip():
            self.fields['occupation'].widget.attrs.pop('disabled', None)
            reg_cat_val = str(reg_cat).strip().lower()
            if reg_cat_val == 'modular':
                self.fields['occupation'].queryset = Occupation.objects.filter(has_modular=True)
            elif reg_cat_val in ['formal', "worker's pas", 'workers pas']:
                try:
                    cat = OccupationCategory.objects.get(name__iexact=reg_cat)
                    self.fields['occupation'].queryset = Occupation.objects.filter(category=cat)
                except OccupationCategory.DoesNotExist:
                    self.fields['occupation'].queryset = Occupation.objects.none()

class CandidateAdmin(admin.ModelAdmin):
    form = CandidateAdminForm
    list_display = ('full_name', 'reg_number', 'registration_category', 'occupation', 'assessment_center')
    search_fields = ('full_name', 'reg_number')
    list_filter = ('registration_category', 'occupation', 'assessment_center')

    def save_model(self, request, obj, form, change):
        # Save the object first to get the ID
        obj.save()
        # Now handle the many-to-many relationships
        form.save_m2m()




# Register others normally
admin.site.register(Grade)
admin.site.register(AssessmentCenter)
admin.site.register(District)
admin.site.register(Village)
admin.site.register(AssessmentCenterCategory)
admin.site.register(OccupationCategory)
admin.site.register(RegistrationCategory)
from .models import OccupationLevel
from .forms import LevelForm, OccupationLevelForm

class OccupationLevelInline(admin.TabularInline):
    model = OccupationLevel
    form = OccupationLevelForm
    extra = 1

class LevelAdmin(admin.ModelAdmin):
    form = LevelForm
    list_display = ('name',)
    search_fields = ('name',)

class OccupationAdmin(admin.ModelAdmin):
    inlines = [OccupationLevelInline]
    # No fields for structure_type or levels here; handled by inline only

admin.site.register(Level, LevelAdmin)
admin.site.register(Occupation, OccupationAdmin)
admin.site.register(Module, ModuleAdmin)
admin.site.register(Candidate, CandidateAdmin)
from django.contrib import messages
from django.contrib.auth.models import User, Group

class CenterRepresentativeAdminForm(forms.ModelForm):
    class Meta:
        model = CenterRepresentative
        fields = ['name', 'center', 'contact']

    def save(self, commit=True):
        # Create the user with the email pattern and default password
        center_number = self.cleaned_data['center'].center_number
        email = f"{center_number}@uvtab.go.ug"
        password = "Uvtab@2025"
        user, created = User.objects.get_or_create(username=email, defaults={
            'email': email,
            'first_name': self.cleaned_data['name'],
        })
        if created:
            user.set_password(password)
            user.save()
            group, _ = Group.objects.get_or_create(name='CenterRep')
            user.groups.add(group)
        instance = super().save(commit=False)
        instance.user = user
        if commit:
            instance.save()
        return instance

class CenterRepresentativeAdmin(admin.ModelAdmin):
    form = CenterRepresentativeAdminForm
    list_display = ('name', 'center', 'contact', 'user')

class SupportStaffAdminForm(forms.ModelForm):
    class Meta:
        model = SupportStaff
        fields = ['name', 'contact', 'department']

    def save(self, commit=True):
        email = "support@uvtab.go.ug"
        password = "uvtab"
        user, created = User.objects.get_or_create(username=email, defaults={
            'email': email,
            'first_name': self.cleaned_data['name'],
        })
        if created:
            user.set_password(password)
            user.save()
            group, _ = Group.objects.get_or_create(name='SupportStaff')
            user.groups.add(group)
        instance = super().save(commit=False)
        instance.user = user
        if commit:
            instance.save()
        return instance

class SupportStaffAdmin(admin.ModelAdmin):
    form = SupportStaffAdminForm
    list_display = ('name', 'department', 'contact', 'user')

admin.site.register(SupportStaff, SupportStaffAdmin)
admin.site.register(CenterRepresentative, CenterRepresentativeAdmin)
