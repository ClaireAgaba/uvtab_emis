from django.contrib import admin
from django import forms  # ✅ this is the missing line

from .models import (
    SupportStaff, CenterRepresentative, Staff, Occupation, Module, Paper, Grade, AssessmentCenter,
    District, Village, AssessmentCenterCategory, OccupationCategory,
    RegistrationCategory, Level, Candidate, NatureOfDisability, AssessmentSeries
)

# Paper form limited to occupations with structure_type='papers'

admin.site.register(NatureOfDisability)

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
        # Disability logic for admin form
        disability_value = False
        if self.data.get('disability') in ['on', 'true', 'True', True]:
            disability_value = True
        elif hasattr(self.instance, 'disability'):
            disability_value = getattr(self.instance, 'disability', False)
        if not disability_value:
            self.fields['nature_of_disability'].widget.attrs['disabled'] = True
            self.fields['nature_of_disability'].required = False
        else:
            self.fields['nature_of_disability'].widget.attrs.pop('disabled', None)
            self.fields['nature_of_disability'].required = True


class CandidateAdmin(admin.ModelAdmin):
    form = CandidateAdminForm
    list_display = ('full_name', 'reg_number', 'registration_category', 'occupation', 'assessment_center', 'disability', 'get_nature_of_disability', 'payment_cleared_status')
    search_fields = ('full_name', 'reg_number')
    list_filter = ('registration_category', 'occupation', 'assessment_center', 'disability', 'payment_cleared')
    filter_horizontal = ('nature_of_disability',)
    readonly_fields = ('payment_cleared', 'payment_cleared_date', 'payment_cleared_by', 'payment_amount_cleared', 'payment_center_series_ref')

    def get_nature_of_disability(self, obj):
        return ", ".join([str(n) for n in obj.nature_of_disability.all()])
    get_nature_of_disability.short_description = 'Nature of Disability'
    
    def payment_cleared_status(self, obj):
        if obj.payment_cleared:
            return "🔒 PAID - CANNOT DELETE"
        return "Not Paid"
    payment_cleared_status.short_description = 'Payment Status'

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of paid candidates"""
        if obj and obj.payment_cleared:
            return False
        return super().has_delete_permission(request, obj)
    
    def delete_model(self, request, obj):
        """Additional safety check when deleting individual candidate"""
        if obj.payment_cleared:
            messages.error(request, f'Cannot delete {obj.full_name} ({obj.reg_number}). This candidate was included in a payment clearance and cannot be deleted to maintain audit trail.')
            return
        super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        """Prevent bulk deletion of paid candidates"""
        paid_candidates = queryset.filter(payment_cleared=True)
        if paid_candidates.exists():
            paid_count = paid_candidates.count()
            messages.error(request, f'Cannot delete {paid_count} candidate(s) who have been included in payment clearances. These candidates are protected to maintain payment audit trail.')
            # Delete only non-paid candidates
            queryset.filter(payment_cleared=False).delete()
        else:
            super().delete_queryset(request, queryset)

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
admin.site.register(AssessmentSeries)
from .models import OccupationLevel
from .forms import LevelForm, OccupationLevelForm

class OccupationLevelInline(admin.TabularInline):
    model = OccupationLevel
    form = OccupationLevelForm
    extra = 1

class LevelAdmin(admin.ModelAdmin):
    form = LevelForm
    list_display = ('name_with_occupation', 'occupation')
    search_fields = ('name', 'occupation__code')

    def name_with_occupation(self, obj):
        return f"{obj.name} ({obj.occupation.code})"
    name_with_occupation.short_description = 'Level Name (Occupation)'


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

class StaffAdminForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = ['name', 'contact', 'department', 'status']

    def save(self, commit=True):
        from django.contrib.auth.models import User, Group
        from django.utils.text import slugify
        
        # Save staff profile
        instance = super().save(commit=False)
        
        # Only create user if this is a new staff member (no existing user)
        if not hasattr(instance, 'user') or not instance.user:
            # Generate unique username
            base_username = slugify(self.cleaned_data['name'])
            username = f"{base_username}.staff"
            email = f"{username}@uvtab.go.ug"
            
            # Ensure uniqueness
            counter = 1
            original_username = username
            while User.objects.filter(username=username).exists():
                username = f"{original_username}{counter}"
                email = f"{username}@uvtab.go.ug"
                counter += 1
            
            # Set password
            password = "uvtab"
            
            user, created = User.objects.get_or_create(username=username, defaults={
                'email': email,
                'first_name': self.cleaned_data['name'],
            })
            if created:
                user.set_password(password)
                user.save()
                group, _ = Group.objects.get_or_create(name='Staff')
                user.groups.add(group)
            
            instance.user = user
        
        if commit:
            instance.save()
        return instance

class StaffAdmin(admin.ModelAdmin):
    form = StaffAdminForm
    list_display = ('name', 'department', 'contact', 'status', 'user')

admin.site.register(SupportStaff, SupportStaffAdmin)
admin.site.register(CenterRepresentative, CenterRepresentativeAdmin)
admin.site.register(Staff, StaffAdmin)
