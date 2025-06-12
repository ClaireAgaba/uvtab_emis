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
