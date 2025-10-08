from django import forms
from django.contrib.auth.models import User, Group
from .models import (
    Candidate, District, Village, Level, Module, Paper, Occupation, OccupationLevel,
    AssessmentCenter, AssessmentCenterBranch, AssessmentSeries, Result, Staff, SupportStaff,
    RegistrationCategory, NatureOfDisability, PracticalMarksheet, 
    PracticalMark, PracticalAssessor, PracticalAssessorAssignment,
    HelpdeskTeam, ComplaintCategory, Complaint, CenterRepresentative, Sector
)
from datetime import datetime   

from django_countries.fields import CountryField
from django_countries.widgets import CountrySelectWidget

CURRENT_YEAR = datetime.now().year
YEAR_CHOICES = [(year, year) for year in range(CURRENT_YEAR, CURRENT_YEAR - 30, -1)]


class NatureOfDisabilityForm(forms.ModelForm):
    class Meta:
        model = NatureOfDisability
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'description': forms.Textarea(attrs={'class': 'border rounded px-3 py-2 w-full', 'rows': 3}),
        }


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class ComplaintForm(forms.ModelForm):
    attachments = MultipleFileField(
        required=False,
        help_text='Select multiple files (PNG, JPG, JPEG, PDF, DOC, DOCX). Max 20MB per file.'
    )

    class Meta:
        model = Complaint
        fields = [
            'category', 'assessment_center', 'registration_category', 'occupation',
            'assessment_series', 'helpdesk_team', 'phone', 'issue_description',
            'team_response', 'status'
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'assessment_center': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'registration_category': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'occupation': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'assessment_series': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'helpdesk_team': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'phone': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'placeholder': 'e.g. +256 7XX XXX XXX'}),
            'issue_description': forms.Textarea(attrs={'class': 'border rounded px-3 py-2 w-full', 'rows': 4, 'placeholder': 'Provide the issue in detail'}),
            'team_response': forms.Textarea(attrs={'class': 'border rounded px-3 py-2 w-full', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Ensure phone field is always available and enabled
        if 'phone' in self.fields:
            self.fields['phone'].widget.attrs.update({
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'e.g. +256 7XX XXX XXX'
            })
            self.fields['phone'].required = False
        
        # Assessment center must be selected
        if 'assessment_center' in self.fields:
            self.fields['assessment_center'].required = True
        
        # Center reps: lock to their center if available
        if user and hasattr(user, 'centerrepresentative') and user.centerrepresentative.center:
            self.fields['assessment_center'].initial = user.centerrepresentative.center
            self.fields['assessment_center'].queryset = AssessmentCenter.objects.filter(pk=user.centerrepresentative.center.pk)
        
        # Status and helpdesk team hidden for center reps on create
        if not (user and (user.is_staff or user.is_superuser or hasattr(user, 'supportstaff') or hasattr(user, 'staff_profile'))):
            self.fields['status'].widget.attrs['disabled'] = True
            self.fields['status'].required = False
            # Center users cannot assign helpdesk teams - only staff can do this
            self.fields['helpdesk_team'].widget.attrs['disabled'] = True
            self.fields['helpdesk_team'].required = False


class AssessmentCenterForm(forms.ModelForm):
    class Meta:
        model = AssessmentCenter
        fields = ['center_number', 'center_name', 'category', 'district', 'village', 'contact', 'has_branches']
        widgets = {
            'center_number': forms.TextInput(attrs={'class':'border rounded px-3 py-2 w-full'}),
            'center_name': forms.TextInput(attrs={'class':'border rounded px-3 py-2 w-full'}),
            'category':    forms.Select(attrs={'class':'border rounded px-3 py-2 w-full'}),
            'district':    forms.Select(attrs={'class':'border rounded px-3 py-2 w-full'}),
            'village':     forms.Select(attrs={'class':'border rounded px-3 py-2 w-full'}),
            'contact':     forms.TextInput(attrs={'class':'border rounded px-3 py-2 w-full', 'placeholder': 'e.g., +256701234567'}),
            'has_branches': forms.CheckboxInput(attrs={'class':'rounded'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make village field optional with helpful placeholder
        self.fields['village'].required = False
        self.fields['village'].empty_label = "Select village (optional)"
        self.fields['village'].help_text = "You can add the village later during editing if needed"
        
        # Add helpful placeholders and help text for other fields
        self.fields['center_number'].help_text = "Enter a unique center number (e.g., UVT001)"
        self.fields['center_name'].help_text = "Enter the full name of the assessment center"
        self.fields['contact'].help_text = "Phone number or contact information for the center (optional)"
        self.fields['has_branches'].help_text = "Check this if the center will have multiple branches in different locations"
    
    def clean_center_number(self):
        """Validate that center number is unique"""
        center_number = self.cleaned_data.get('center_number')
        if center_number:
            # Check if this center number already exists (excluding current instance for edit)
            existing_center = AssessmentCenter.objects.filter(center_number=center_number)
            if self.instance.pk:
                existing_center = existing_center.exclude(pk=self.instance.pk)
            
            if existing_center.exists():
                raise forms.ValidationError(
                    f'Assessment Center with number "{center_number}" already exists. '
                    'Please choose a different center number.'
                )
        return center_number
    
    def clean_center_name(self):
        """Validate center name and format to proper sentence case"""
        center_name = self.cleaned_data.get('center_name')
        if center_name:
            # Convert to proper sentence case with articles in lowercase
            words = center_name.strip().split()
            formatted_words = []
            
            # Articles and prepositions to keep lowercase (except at start)
            lowercase_words = {'in', 'and', 'for', 'of', 'the', 'at', 'on', 'by', 'with', 'to'}
            
            for i, word in enumerate(words):
                if i == 0:  # First word is always capitalized
                    formatted_words.append(word.capitalize())
                elif word.lower() in lowercase_words:
                    formatted_words.append(word.lower())
                else:
                    formatted_words.append(word.capitalize())
            
            center_name = ' '.join(formatted_words)
            
            # Check for exact duplicate names (case-insensitive)
            existing_center = AssessmentCenter.objects.filter(center_name__iexact=center_name)
            if self.instance.pk:
                existing_center = existing_center.exclude(pk=self.instance.pk)
            
            if existing_center.exists():
                # For name duplicates, we'll just add a warning in the view, not block creation
                # This allows for legitimate cases where centers might have similar names
                pass
        return center_name


class AssessmentCenterBranchForm(forms.ModelForm):
    class Meta:
        model = AssessmentCenterBranch
        fields = ['branch_code', 'district', 'village']
        widgets = {
            'branch_code': forms.TextInput(attrs={'class':'border rounded px-3 py-2 w-full'}),
            'district': forms.Select(attrs={'class':'border rounded px-3 py-2 w-full'}),
            'village': forms.Select(attrs={'class':'border rounded px-3 py-2 w-full'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.assessment_center = kwargs.pop('assessment_center', None)
        super().__init__(*args, **kwargs)
        
        # Add helpful placeholders and help text
        self.fields['branch_code'].help_text = "Enter a unique branch code (e.g., UVT001-Leju)"
        self.fields['district'].help_text = "Select the district where this branch is located"
        self.fields['village'].help_text = "Select the village where this branch is located"
        
        # Filter villages based on selected district if editing
        if self.instance.pk and self.instance.district:
            self.fields['village'].queryset = Village.objects.filter(district=self.instance.district)
    
    def clean_branch_code(self):
        """Validate that branch code is unique"""
        branch_code = self.cleaned_data.get('branch_code')
        if branch_code:
            # Check if this branch code already exists (excluding current instance for edit)
            existing_branch = AssessmentCenterBranch.objects.filter(branch_code=branch_code)
            if self.instance.pk:
                existing_branch = existing_branch.exclude(pk=self.instance.pk)
            
            if existing_branch.exists():
                raise forms.ValidationError(
                    f'Branch with code "{branch_code}" already exists. '
                    'Please choose a different branch code.'
                )
        return branch_code
    
    def clean_village(self):
        """Validate that the center doesn't already have a branch in this village"""
        village = self.cleaned_data.get('village')
        if village and self.assessment_center:
            # Check if this center already has a branch in this village
            existing_branch = AssessmentCenterBranch.objects.filter(
                assessment_center=self.assessment_center, 
                village=village
            )
            if self.instance.pk:
                existing_branch = existing_branch.exclude(pk=self.instance.pk)
            
            if existing_branch.exists():
                raise forms.ValidationError(
                    f'This assessment center already has a branch in {village.name}. '
                    'Each center can have only one branch per village.'
                )
        return village
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.assessment_center:
            instance.assessment_center = self.assessment_center
        if commit:
            instance.save()
        return instance


class OccupationForm(forms.ModelForm):
    class Meta:
        model = Occupation
        fields = ['code', 'name', 'category', 'sector', 'has_modular']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'name': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'category': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'sector': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'has_modular': forms.CheckboxInput(attrs={'class': 'ml-2'}),
        }

class LevelForm(forms.ModelForm):
    class Meta:
        model = Level
        fields = ['name', 'formal_fee', 'workers_pas_fee', 'workers_pas_module_fee', 'modular_fee_single', 'modular_fee_double']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter level name'
            }),
            'formal_fee': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'min': '0'
            }),
            'workers_pas_fee': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'min': '0'
            }),
            'workers_pas_module_fee': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'min': '0'
            }),
            'modular_fee_single': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'min': '0'
            }),
            'modular_fee_double': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'min': '0'
            })
        }
        labels = {
            'name': 'Level Name',
            'formal_fee': 'Formal Fee (UGX)',
            'workers_pas_fee': 'Worker\'s PAS Base Fee (UGX)',
            'workers_pas_module_fee': 'Worker\'s PAS Per-Module Fee (UGX)',
            'modular_fee_single': 'Modular Fee - Single Module (UGX)',
            'modular_fee_double': 'Modular Fee - Double Module (UGX)'
        }

class OccupationLevelForm(forms.ModelForm):
    class Meta:
        model = OccupationLevel
        fields = ['level', 'structure_type']
        widgets = {
            'level': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'structure_type': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        }


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ['code', 'name', 'level', 'occupation']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter module code'
            }),
            'name': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter module name'
            }),
            'level': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            'occupation': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order occupations alphabetically by code
        self.fields['occupation'].queryset = Occupation.objects.all().order_by('code')

class PaperForm(forms.ModelForm):
    class Meta:
        model = Paper
        fields = ['occupation', 'level', 'module', 'code', 'name', 'grade_type']
        widgets = {
            'occupation': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            'level': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            'module': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            'code': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter paper code'
            }),
            'name': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter paper name'
            }),
            'grade_type': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order occupations alphabetically by code
        self.fields['occupation'].queryset = Occupation.objects.all().order_by('code')
        self.fields['module'].queryset = Module.objects.none()
        occupation_id = None
        level_id = None

        if 'occupation' in self.data:
            occupation_id = self.data.get('occupation')
        elif self.instance and self.instance.pk and self.instance.occupation:
            occupation_id = self.instance.occupation.pk

        if 'level' in self.data:
            level_id = self.data.get('level')
        elif self.instance and self.instance.pk and self.instance.level:
            level_id = self.instance.level.pk

        if occupation_id:
            try:
                occupation = Occupation.objects.get(pk=occupation_id)
                # Find structure type for this occupation/level
                if level_id:
                    occ_level = OccupationLevel.objects.filter(occupation=occupation, level_id=level_id).first()
                    if occ_level and occ_level.structure_type == 'modules':
                        self.fields['module'].queryset = Module.objects.filter(occupation=occupation, level_id=level_id)
                        self.fields['module'].required = True
                        self.fields['module'].widget.attrs.pop('hidden', None)
                        self.fields['module'].widget.attrs.pop('style', None)
                        # For informal/worker's pas, force grade_type to practical
                        self.fields['grade_type'].initial = 'practical'
                    elif (occupation.category and occupation.category.name.strip().lower() in ["worker's pas", "informal", "workers pas"]):
                        # Always show module field for informal/worker's PAS
                        self.fields['module'].queryset = Module.objects.filter(occupation=occupation, level_id=level_id)
                        self.fields['module'].required = True
                        self.fields['module'].widget.attrs.pop('hidden', None)
                        self.fields['module'].widget.attrs.pop('style', None)
                        self.fields['grade_type'].initial = 'practical'
                    else:
                        self.fields['module'].required = False
                        self.fields['module'].widget.attrs['style'] = 'display:none;'
                        self.fields['module'].widget.attrs['tabindex'] = '-1'
            except (ValueError, Occupation.DoesNotExist):
                self.fields['module'].required = False
        else:
            self.fields['module'].required = False

    def clean(self):
        cleaned_data = super().clean()
        occupation = cleaned_data.get('occupation')
        level = cleaned_data.get('level')
        module = cleaned_data.get('module')
        grade_type = cleaned_data.get('grade_type')
        # Enforce: If occupation/level structure is modules, module is required and grade_type must be practical
        if occupation and level:
            occ_level = OccupationLevel.objects.filter(occupation=occupation, level=level).first()
            if occ_level and occ_level.structure_type == 'modules':
                if not module:
                    self.add_error('module', 'Module is required for this occupation/level.')
                if grade_type != 'practical':
                    self.add_error('grade_type', 'Only practical papers are allowed for this occupation/level.')
        return cleaned_data


class CandidateForm(forms.ModelForm):
    entry_year = forms.ChoiceField(
        choices=YEAR_CHOICES,
        widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'})
    )
    # Use a country list for nationality
    nationality = CountryField(blank_label='(Select country)').formfield(
        widget=CountrySelectWidget(attrs={'class': 'border rounded px-3 py-2 w-full'})
    )
    
    # Override the model's BooleanField with a ChoiceField for proper dropdown rendering
    is_refugee = forms.ChoiceField(
        choices=[('', '--------'), ('True', 'Yes'), ('False', 'No')],
        required=False,
        widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        label="Is refugee",
        help_text="Is this candidate a refugee?"
    )

    disability = forms.BooleanField(
        required=False,
        label="Disability",
        widget=forms.CheckboxInput(attrs={'class': 'ml-2'})
    )
    nature_of_disability = forms.ModelMultipleChoiceField(
        queryset=NatureOfDisability.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'ml-2'}),
        label="Nature of Disability",
        help_text="Select nature(s) of disability if applicable"
    )
    disability_specification = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'rows': 3,
            'placeholder': 'Please specify details about the disability and any assistance needed during exams...'
        }),
        label="Specify Details",
        help_text="Provide additional details about the disability and any assistance needed during exams"
    )

    def __init__(self, *args, user=None, edit=False, **kwargs):
        super().__init__(*args, **kwargs)
        # Accept DD/MM/YYYY for all date fields
        for field in ['date_of_birth', 'start_date', 'finish_date', 'assessment_date']:
            if field in self.fields:
                self.fields[field].input_formats = ['%d/%m/%Y']
        # Make start/finish date optional at form level
        if 'start_date' in self.fields:
            self.fields['start_date'].required = False
        if 'finish_date' in self.fields:
            self.fields['finish_date'].required = False

        # Preferred assessment language: optional, default to English when blank
        if 'preferred_assessment_language' in self.fields:
            self.fields['preferred_assessment_language'].required = False
            # If no value on instance or form data, set initial to English for UX
            try:
                current_lang = (
                    self.data.get('preferred_assessment_language') or
                    getattr(self.instance, 'preferred_assessment_language', '') or
                    self.initial.get('preferred_assessment_language', '')
                )
            except Exception:
                current_lang = ''
            if not (str(current_lang).strip()):
                self.fields['preferred_assessment_language'].initial = 'English'
        # Show/hide nature_of_disability and disability_specification based on disability field value
        disability_value = False
        if self.data.get('disability') in ['on', 'true', 'True', True]:
            disability_value = True
        elif hasattr(self.instance, 'disability'):
            disability_value = getattr(self.instance, 'disability', False)
        if not disability_value:
            self.fields['nature_of_disability'].required = False
            self.fields['disability_specification'].required = False
        else:
            self.fields['nature_of_disability'].required = True
            self.fields['disability_specification'].required = False  # Keep optional but show when disability is True
        
        # Handle refugee fields visibility based on nationality
        nationality_value = None
        if self.data.get('nationality'):
            nationality_value = self.data.get('nationality')
        elif hasattr(self.instance, 'nationality'):
            nationality_value = getattr(self.instance, 'nationality', None)
        
        # Refugee field visibility is controlled entirely by JavaScript
        # Remove any server-side hiding to prevent conflicts with JavaScript show/hide logic
        
        # Refugee number field visibility is also controlled entirely by JavaScript
        # This ensures consistent behavior and prevents server/client conflicts
        branch_locked = False
        rep_branch_id = None
        if user and user.groups.filter(name='CenterRep').exists():
            from .models import CenterRepresentative
            try:
                center_rep = CenterRepresentative.objects.get(user=user)
                self.fields['assessment_center'].queryset = self.fields['assessment_center'].queryset.filter(pk=center_rep.center.pk)
                self.fields['assessment_center'].initial = center_rep.center.pk
                self.fields['assessment_center'].required = False
                # Use HiddenInput so the value is submitted; do not disable (disabled fields are not submitted)
                self.fields['assessment_center'].widget = forms.HiddenInput()
                # Branch scoping: if this user is tied to a specific branch, restrict and lock the branch field
                if getattr(center_rep, 'assessment_center_branch_id', None):
                    branch_locked = True
                    rep_branch_id = center_rep.assessment_center_branch_id
                    self.fields['assessment_center_branch'].queryset = AssessmentCenterBranch.objects.filter(pk=center_rep.assessment_center_branch_id)
                    self.fields['assessment_center_branch'].initial = center_rep.assessment_center_branch_id
                    self.fields['assessment_center_branch'].required = False
                    # Hidden input so it posts; not disabled
                    self.fields['assessment_center_branch'].widget = forms.HiddenInput()
                    self.fields['assessment_center_branch'].help_text = "Your account is scoped to this branch."
                else:
                    # Main center (no branch): hide branch field and keep empty
                    self.fields['assessment_center_branch'].queryset = AssessmentCenterBranch.objects.none()
                    self.fields['assessment_center_branch'].initial = None
                    self.fields['assessment_center_branch'].required = False
                    self.fields['assessment_center_branch'].widget = forms.HiddenInput()
                    self.fields['assessment_center_branch'].help_text = "Main Center account (no specific branch)."
            except CenterRepresentative.DoesNotExist:
                self.fields['assessment_center'].queryset = self.fields['assessment_center'].queryset.none()
        from .models import Occupation, OccupationCategory
        reg_cat = None
        # Prefer form data, then initial, then instance (admin edit)
        if self.data.get('registration_category'):
            reg_cat = self.data.get('registration_category')
        elif self.initial.get('registration_category'):
            reg_cat = self.initial.get('registration_category')
        elif hasattr(self, 'instance') and getattr(self.instance, 'registration_category', None):
            reg_cat = self.instance.registration_category

        # UX: Show occupation dropdown enabled by default with all occupations,
        # then narrow results if a registration category is chosen
        self.fields['occupation'].queryset = Occupation.objects.all().order_by('code')
        reg_cat_val = str(reg_cat).strip().lower() if reg_cat and str(reg_cat).strip() else None
        if reg_cat_val:
            # Modular: has_modular occupations
            if reg_cat_val == 'modular':
                self.fields['occupation'].queryset = Occupation.objects.filter(has_modular=True).order_by('code')
            # Formal: occupation category 'Formal'
            elif reg_cat_val == 'formal':
                try:
                    cat = OccupationCategory.objects.get(name__iexact='Formal')
                    self.fields['occupation'].queryset = Occupation.objects.filter(category=cat).order_by('code')
                except OccupationCategory.DoesNotExist:
                    self.fields['occupation'].queryset = Occupation.objects.none()
            # Informal/Worker's PAS: occupation category 'Worker's PAS'
            elif reg_cat_val in ["worker's pas", 'workers pas', 'informal']:
                from django.db.models import Q
                cat = OccupationCategory.objects.filter(
                    Q(name__iexact="Worker's PAS") | Q(name__iexact="Worker PAS")
                ).first()
                if not cat:
                    # Try regex for even more flexibility
                    cat = OccupationCategory.objects.filter(name__iregex=r"worker('?s)? pas").first()
                if cat:
                    self.fields['occupation'].queryset = Occupation.objects.filter(category=cat).order_by('code')
                else:
                    self.fields['occupation'].queryset = Occupation.objects.none()
        # Disable some fields in edit mode ONLY if candidate is verified; otherwise keep editable
        if edit:
            is_verified = False
            try:
                is_verified = getattr(self.instance, 'verification_status', '').lower() == 'verified'
            except Exception:
                is_verified = False
            fields_to_lock_if_verified = [
                'assessment_center', 'start_date', 'finish_date',
                'level', 'modules', 'reg_number', 'created_by',
                'enrollment_label', 'updated_by'
            ]
            # Note: registration_category and occupation REMAIN editable if not verified
            if is_verified:
                fields_to_lock_if_verified += ['registration_category', 'occupation']
            for fname in fields_to_lock_if_verified:
                if fname in self.fields:
                    try:
                        # Mark not required to avoid validation errors on POST (disabled fields are not submitted)
                        self.fields[fname].required = False
                        self.fields[fname].widget.attrs['readonly'] = True
                        self.fields[fname].widget.attrs['disabled'] = True
                    except Exception:
                        pass
            # Intake and Entry Year must remain editable and required
            for fname in ['intake', 'entry_year']:
                if fname in self.fields:
                    self.fields[fname].required = True
                    # Remove any leftover disabling flags
                    try:
                        self.fields[fname].widget.attrs.pop('disabled', None)
                        self.fields[fname].widget.attrs.pop('readonly', None)
                    except Exception:
                        pass
        # Order districts alphabetically for easier searching
        self.fields['district'].queryset = District.objects.all().order_by('name')
        
        # Make village field not mandatory
        self.fields['village'].required = False
        
        # Dependent dropdown for village based on district
        self.fields['village'].queryset = Village.objects.none() # Start with an empty queryset

        if 'district' in self.data: # If form is submitted with data
            try:
                district_id = int(self.data.get('district'))
                self.fields['village'].queryset = Village.objects.filter(district_id=district_id).order_by('name')
            except (ValueError, TypeError):
                pass  # invalid input from browser; ignore and fallback to an empty queryset
        elif self.instance.pk and self.instance.district: # If form is for an editing existing instance
            self.fields['village'].queryset = Village.objects.filter(district=self.instance.district).order_by('name')
        elif self.initial.get('district'): # If initial data has district (form re-render after error)
            try:
                district_id = int(self.initial.get('district'))
                self.fields['village'].queryset = Village.objects.filter(district_id=district_id).order_by('name')
            except (ValueError, TypeError):
                pass
        # If it's a new form or no district selected, village queryset remains Village.objects.none()
        # JavaScript will populate it on district change.
        
        # Handle assessment center branch selection
        self.fields['assessment_center_branch'].required = False  # Always optional to allow main center assignment
        self.fields['assessment_center_branch'].empty_label = "Main Center (no specific branch)"

        # If the user is branch-locked, do NOT overwrite the queryset/initial above
        if not branch_locked:
            self.fields['assessment_center_branch'].queryset = AssessmentCenterBranch.objects.none()  # Start with empty queryset
            if 'assessment_center' in self.data:  # If form is submitted with data
                try:
                    center_id = int(self.data.get('assessment_center'))
                    center = AssessmentCenter.objects.get(pk=center_id)
                    if center.has_branches:
                        self.fields['assessment_center_branch'].queryset = AssessmentCenterBranch.objects.filter(assessment_center_id=center_id).order_by('branch_code')
                        self.fields['assessment_center_branch'].help_text = "This center has branches. Select a specific branch or leave blank for main center."
                    else:
                        self.fields['assessment_center_branch'].help_text = "This center does not have branches."
                except (ValueError, TypeError, AssessmentCenter.DoesNotExist):
                    pass
            elif self.instance.pk and self.instance.assessment_center:  # If editing existing instance
                center = self.instance.assessment_center
                if center.has_branches:
                    self.fields['assessment_center_branch'].queryset = AssessmentCenterBranch.objects.filter(assessment_center=center).order_by('branch_code')
                    self.fields['assessment_center_branch'].help_text = "This center has branches. Select a specific branch or leave blank for main center."
                else:
                    self.fields['assessment_center_branch'].help_text = "This center does not have branches."
            elif self.initial.get('assessment_center'):  # If initial data has assessment center
                try:
                    center_id = int(self.initial.get('assessment_center'))
                    center = AssessmentCenter.objects.get(pk=center_id)
                    if center.has_branches:
                        self.fields['assessment_center_branch'].queryset = AssessmentCenterBranch.objects.filter(assessment_center_id=center_id).order_by('branch_code')
                        self.fields['assessment_center_branch'].help_text = "This center has branches. Select a specific branch or leave blank for main center."
                    else:
                        self.fields['assessment_center_branch'].help_text = "This center does not have branches."
                except (ValueError, TypeError, AssessmentCenter.DoesNotExist):
                    pass
    class Meta:
        model = Candidate
        exclude = ['status', 'fees_balance', 'verification_status', 'verification_date', 'verified_by', 'decline_reason']
        widgets = {
            'date_of_birth': forms.DateInput(format='%d/%m/%Y', attrs={'type': 'text', 'placeholder': 'DD/MM/YYYY', 'class': 'border rounded px-3 py-2 w-full'}),
            'start_date': forms.DateInput(format='%d/%m/%Y', attrs={'type': 'text', 'placeholder': 'DD/MM/YYYY', 'class': 'border rounded px-3 py-2 w-full'}),
            'finish_date': forms.DateInput(format='%d/%m/%Y', attrs={'type': 'text', 'placeholder': 'DD/MM/YYYY', 'class': 'border rounded px-3 py-2 w-full'}),
            'assessment_date': forms.DateInput(format='%d/%m/%Y', attrs={'type': 'text', 'placeholder': 'DD/MM/YYYY', 'class': 'border rounded px-3 py-2 w-full'}),
            'preferred_assessment_language': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'placeholder': 'e.g., English, Luganda, Runyakitara'}),
            'full_name': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'passport_photo': forms.ClearableFileInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'contact': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'district': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'village': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'assessment_center': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'assessment_center_branch': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            #'entry_year': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full', 'choices': YEAR_CHOICES }),
            'intake': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'occupation': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'registration_category': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'identification_document': forms.ClearableFileInput(attrs={
                'class': 'border rounded px-3 py-2 w-full',
                'accept': '.png,.jpg,.jpeg,.pdf'
            }),
            'qualification_document': forms.ClearableFileInput(attrs={
                'class': 'border rounded px-3 py-2 w-full',
                'accept': '.png,.jpg,.jpeg,.pdf'
            }),

            'refugee_number': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'placeholder': 'Enter refugee number (optional)'}),
            # ...add others similarly

            }

    def clean_full_name(self):
        """Format name to standard format: SURNAME Other Names (sentence case)"""
        full_name = self.cleaned_data.get('full_name')
        if not full_name:
            return full_name
            
        # Split the name into parts
        name_parts = full_name.strip().split()
        if not name_parts:
            return full_name
            
        # Format: First part (surname) in UPPERCASE, rest in sentence case
        formatted_parts = []
        for i, part in enumerate(name_parts):
            if i == 0:  # First part (surname) - all uppercase
                formatted_parts.append(part.upper())
            else:  # Other parts - sentence case (first letter upper, rest lower)
                formatted_parts.append(part.capitalize())
                
        return ' '.join(formatted_parts)

    def clean_is_refugee(self):
        """Convert string refugee status to boolean for model"""
        is_refugee = self.cleaned_data.get('is_refugee')
        if is_refugee == 'True':
            return True
        elif is_refugee == 'False':
            return False
        else:
            return False  # Default to False instead of None to satisfy NOT NULL constraint

    def clean(self):
        cleaned_data = super().clean()
        # Ensure branch-locked values are present even if browser didn't submit hidden inputs
        try:
            user = getattr(self, 'user', None)
        except Exception:
            user = None
        try:
            # Fallback: we passed user via __init__ kwarg, store it on self for reuse
            if not user and hasattr(self, 'initial'):
                user = None
        except Exception:
            user = None
        try:
            req_user = None
        except Exception:
            req_user = None
        # Our __init__ doesn't store user on self; read from closure via local var passed to __init__.
        # Instead, re-derive from request by checking for a hidden field we set; if absent, pull from CenterRepresentative.
        try:
            from .models import CenterRepresentative
            if hasattr(self, 'data') and isinstance(self.data, (dict,)):
                pass
        except Exception:
            pass
        # Explicitly set assessment_center/branch from CenterRep if field is blank
        try:
            if hasattr(self, 'initial') and hasattr(self, 'fields'):
                # When the form was constructed we set hidden inputs; if not in POST, force values here
                if 'assessment_center' in self.fields and not cleaned_data.get('assessment_center'):
                    # Try to derive from field queryset initial
                    ac_initial = self.fields['assessment_center'].initial
                    if ac_initial:
                        try:
                            from .models import AssessmentCenter
                            if isinstance(ac_initial, AssessmentCenter):
                                cleaned_data['assessment_center'] = ac_initial
                            else:
                                cleaned_data['assessment_center'] = AssessmentCenter.objects.get(pk=ac_initial)
                        except Exception:
                            pass
                if 'assessment_center_branch' in self.fields and not cleaned_data.get('assessment_center_branch'):
                    acb_initial = self.fields['assessment_center_branch'].initial
                    if acb_initial:
                        try:
                            from .models import AssessmentCenterBranch
                            if isinstance(acb_initial, AssessmentCenterBranch):
                                cleaned_data['assessment_center_branch'] = acb_initial
                            else:
                                cleaned_data['assessment_center_branch'] = AssessmentCenterBranch.objects.get(pk=acb_initial)
                        except Exception:
                            pass
        except Exception:
            pass
        disability = cleaned_data.get('disability')
        nature_of_disability = cleaned_data.get('nature_of_disability')
        # Enforce: If disability is checked, nature_of_disability must be selected
        if disability:
            if not nature_of_disability or len(nature_of_disability) == 0:
                self.add_error('nature_of_disability', 'Please select at least one nature of disability.')
        else:
            cleaned_data['nature_of_disability'] = []
        
        # Date validation (new rules):
        # - assessment_date remains required
        # - start_date and finish_date are OPTIONAL for all categories
        # - if both start_date and finish_date are provided, ensure start_date <= finish_date
        reg_cat = cleaned_data.get('registration_category')
        start_date = cleaned_data.get('start_date')
        finish_date = cleaned_data.get('finish_date')
        assessment_date = cleaned_data.get('assessment_date')

        # Assessment date is required for everyone
        if not assessment_date:
            self.add_error('assessment_date', 'Assessment date is required.')

        # Optional consistency check when both dates are provided
        try:
            if start_date and finish_date and start_date > finish_date:
                self.add_error('finish_date', 'Finish date cannot be before start date.')
        except Exception:
            # If parsing fails, let field-level validation handle format errors
            pass
        
        # --- Existing logic below ---
        occupation = cleaned_data.get('occupation')
        level = cleaned_data.get('level')
        modules = cleaned_data.get('modules')

        if not occupation or not level:
            return cleaned_data

        # Fetch OccupationLevel instance for occupation and level
        occ_level = None
        try:
            occ_level = occupation.occupation_levels.get(level=level)
        except Exception:
            raise forms.ValidationError("Selected level is not configured for this occupation.")

        structure_type = occ_level.structure_type if occ_level else None



# forms.py  (only the EnrollmentForm needs to change)
# … top of forms.py (imports and other forms unchanged) …

class EnrollmentForm(forms.Form):
    """
    Refactored: For worker's PAS/informal, after level selection, dynamically generate a radio group per module (listing that module's papers).
    Now includes Assessment Series selection filtered by candidate's entry year.
    """
    assessment_series = forms.ModelChoiceField(
        queryset=AssessmentSeries.objects.none(), 
        required=True, 
        widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        help_text="Select the Assessment Series for this enrollment"
    )
    level = forms.ModelChoiceField(queryset=Level.objects.all(), required=True, widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))
    # modules field for modular/formal; for informal, we'll dynamically add paper fields per module in __init__
    modules = forms.ModelMultipleChoiceField(queryset=Module.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, candidate=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.candidate = candidate
        occupation = getattr(candidate, 'occupation', None)
        reg_cat = getattr(candidate, 'registration_category', '').strip().lower() if candidate else None
        self.is_informal = reg_cat in ["worker's pas", 'workers pas', 'informal']
        self.is_modular = reg_cat == 'modular'

        # Determine if the logged-in user is a Center Representative
        is_center_rep = False
        try:
            if user is not None and hasattr(user, 'groups'):
                is_center_rep = user.groups.filter(name='CenterRep').exists()
        except Exception:
            is_center_rep = False

        # Assessment Series queryset rules
        if is_center_rep:
            # Centers: Only current assessment series should be visible
            qs = AssessmentSeries.objects.filter(is_current=True).order_by('-start_date')
        else:
            # Staff: Use year-based filtering with safe fallback
            if candidate and hasattr(candidate, 'entry_year') and candidate.entry_year:
                # Get series from the candidate's entry year
                entry_year = candidate.entry_year
                qs = AssessmentSeries.objects.filter(
                    start_date__year=entry_year
                ).order_by('-start_date')
            elif candidate and hasattr(candidate, 'assessment_date') and candidate.assessment_date:
                # Fallback: use assessment date year if entry_year not available
                assessment_year = candidate.assessment_date.year
                qs = AssessmentSeries.objects.filter(
                    start_date__year=assessment_year
                ).order_by('-start_date')
            else:
                # Show current series as initial fallback
                qs = AssessmentSeries.objects.filter(
                    is_current=True
                ).order_by('-start_date')

            # Production-safe fallback for staff: if empty, show all series
            if not qs.exists():
                qs = AssessmentSeries.objects.all().order_by('-is_current', '-start_date')

        self.fields['assessment_series'].queryset = qs

        # If candidate already has an assessment series, pre-select it
        if candidate and hasattr(candidate, 'assessment_series') and candidate.assessment_series:
            self.fields['assessment_series'].initial = candidate.assessment_series

        # Dynamically filter levels by occupation
        if occupation:
            occ_levels = occupation.occupation_levels.select_related('level').all()
            levels_qs = Level.objects.filter(id__in=[ol.level.id for ol in occ_levels])
            self.fields['level'].queryset = levels_qs

        # On GET, level may come from initial or data
        level_id = self.data.get('level') or self.initial.get('level')
        level = None
        if level_id:
            try:
                level = Level.objects.get(pk=level_id)
            except Level.DoesNotExist:
                pass

        # For Modular candidates: hide level field and auto-select Level 1
        if self.is_modular:
            # Hide level field for modular candidates
            self.fields['level'].widget = forms.HiddenInput()
            self.fields['level'].required = False
            # Auto-select Level 1 for modular candidates - filter by occupation
            if occupation:
                from .models import OccupationLevel
                occupation_levels = OccupationLevel.objects.filter(occupation=occupation)
                level_1 = None
                for ol in occupation_levels:
                    if '1' in ol.level.name:
                        level_1 = ol.level
                        break
                if level_1:
                    self.fields['level'].initial = level_1.id
                    level = level_1  # Use Level 1 for module filtering below
                    print(f"[DEBUG] Auto-selected level for modular: {level}")
        # Enhanced modular enrollment logic
        if self.is_modular and candidate:
            print(f"[DEBUG] Enhanced Modular form - occupation: {occupation}, level: {level}")
            if occupation and level:
                # Get available modules for enrollment (not already enrolled)
                available_modules = candidate.get_available_modules_for_enrollment()
                enrolled_modules = candidate.get_enrolled_modules()
                
                print(f"[DEBUG] Available modules: {available_modules.count()}")
                print(f"[DEBUG] Already enrolled modules: {enrolled_modules.count()}")
                
                # Check if candidate can enroll in more modules
                can_enroll_more = candidate.can_enroll_in_more_modules()
                print(f"[DEBUG] Can enroll in more modules: {can_enroll_more}")
                
                # Populate the modules field with available modules only
                if 'modules' in self.fields:
                    self.fields['modules'].queryset = available_modules
                    
                    # Add help text showing enrollment status
                    enrolled_count = enrolled_modules.count()
                    total_count = candidate.get_total_modules_for_occupation()
                    
                    help_text = f"Select 1-2 modules to enroll in. "
                    help_text += f"Currently enrolled: {enrolled_count}/{total_count} modules. "
                    # If billed, show remaining slots
                    chosen = getattr(candidate, 'modular_module_count', None)
                    if chosen in (1, 2):
                        remaining = max(0, chosen - enrolled_count)
                        help_text += f"Remaining allowed by billing: {remaining} module(s). "
                    
                    if not can_enroll_more:
                        help_text += "You have reached the maximum concurrent enrollments (2 modules)."
                        self.fields['modules'].widget.attrs['disabled'] = True
                    
                    self.fields['modules'].help_text = help_text
                    
                    # Store module status for template display
                    self.enrolled_modules = enrolled_modules
                    self.available_modules = available_modules
                    self.can_enroll_more = can_enroll_more
        # For informal/worker's PAS: dynamically add paper fields for ALL levels, modules, and papers
        if self.is_informal and occupation:
            print("[DEBUG] EnrollmentForm: occupation=", occupation)
            # Remove modules field and level field (not used for cross-level informal selection)
            if 'modules' in self.fields:
                self.fields.pop('modules')
            
            # Hide level field since we're showing all levels
            self.fields['level'].widget = forms.HiddenInput()
            self.fields['level'].required = False
            
            # Get ALL levels for this occupation
            from .models import OccupationLevel, CandidatePaper, Result
            from django.db import models
            occupation_levels = OccupationLevel.objects.filter(occupation=occupation).select_related('level')
            all_levels = [ol.level for ol in occupation_levels]
            
            print(f"[DEBUG] EnrollmentForm: Found {len(all_levels)} levels for occupation={occupation}")
            
            # Get candidate's enrollment and result history for eligibility checking
            enrolled_papers = set()
            failed_or_missing_papers = set()
            
            if candidate:
                # Get all papers the candidate has ever enrolled for
                candidate_papers = CandidatePaper.objects.filter(candidate=candidate).values_list('paper_id', flat=True)
                enrolled_papers = set(candidate_papers)
                
                # Get papers with failed or missing results (eligible for re-enrollment)
                failed_results = Result.objects.filter(
                    candidate=candidate,
                    paper_id__in=enrolled_papers
                ).filter(
                    # Failed: CTR comment OR Missing: Ms grade
                    models.Q(comment='CTR') | models.Q(grade='Ms')
                ).values_list('paper_id', flat=True)
                failed_or_missing_papers = set(failed_results)
                
                print(f"[DEBUG] Candidate {candidate.id}: enrolled_papers={len(enrolled_papers)}, failed_or_missing={len(failed_or_missing_papers)}")
            
            # Store level and module information for template rendering
            self.level_module_data = []
            self.all_paper_fields = []
            self.ineligible_papers = []  # Track papers that are not eligible for enrollment
            
            for level in all_levels:
                # Get all modules for this occupation/level
                modules = Module.objects.filter(occupation=occupation, level=level)
                print(f"[DEBUG] Level: {level} - Found {modules.count()} modules")
                
                level_data = {
                    'level': level,
                    'modules': []
                }
                
                for module in modules:
                    papers = Paper.objects.filter(module=module, occupation=occupation, level=level)
                    print(f"[DEBUG] Module: {module} (ID={module.id}) - Papers found: {papers.count()}")
                    
                    module_data = {
                        'module': module,
                        'papers': []
                    }
                    
                    for paper in papers:
                        print(f"    [DEBUG] Paper: {paper} (ID={paper.id})")
                        field_name = f"paper_{level.id}_{module.id}_{paper.id}"
                        
                        # Determine eligibility for this paper
                        is_eligible = True
                        eligibility_reason = ""
                        
                        if candidate and paper.id in enrolled_papers:
                            # Candidate has enrolled for this paper before
                            if paper.id in failed_or_missing_papers:
                                # Paper was failed or missing - eligible for re-enrollment
                                is_eligible = True
                                eligibility_reason = "Re-enrollment (failed/missing)"
                            else:
                                # Paper was passed - not eligible for re-enrollment
                                is_eligible = False
                                eligibility_reason = "Already passed"
                        else:
                            # Never enrolled for this paper - eligible
                            is_eligible = True
                            eligibility_reason = "Never attempted"
                        
                        # Create checkbox field for each paper (only if eligible)
                        if is_eligible:
                            self.fields[field_name] = forms.BooleanField(
                                required=False,
                                label=f"{paper.name} ({paper.code})",
                                widget=forms.CheckboxInput(attrs={
                                    'class': 'paper-checkbox',
                                    'data-level': level.id,
                                    'data-module': module.id,
                                    'data-paper': paper.id
                                })
                            )
                            self.all_paper_fields.append(field_name)
                        else:
                            # Track ineligible papers for UI display
                            self.ineligible_papers.append({
                                'paper': paper,
                                'reason': eligibility_reason
                            })
                        
                        # Store paper info for template
                        paper_info = {
                            'paper': paper,
                            'field_name': field_name if is_eligible else None,
                            'field': self[field_name] if is_eligible and field_name in self.fields else None,
                            'is_eligible': is_eligible,
                            'eligibility_reason': eligibility_reason
                        }
                        module_data['papers'].append(paper_info)
                    
                    if module_data['papers']:  # Only add modules that have papers
                        level_data['modules'].append(module_data)
                
                if level_data['modules']:  # Only add levels that have modules with papers
                    self.level_module_data.append(level_data)
        else:
            self.module_fields = [] 
            # Modular: modules field as checkboxes
            if self.is_modular and occupation and level:
                self.fields['modules'].queryset = Module.objects.filter(occupation=occupation, level=level)
                self.fields['modules'].required = True
            
            # Formal: no modules field
            elif reg_cat == 'formal':
                if 'modules' in self.fields:
                    self.fields.pop('modules')

    def clean(self):
        cleaned_data = super().clean()
        occupation = getattr(self.candidate, 'occupation', None)
        reg_cat = getattr(self.candidate, 'registration_category', '').strip().lower() if self.candidate else None
        level = cleaned_data.get('level')
        assessment_series = cleaned_data.get('assessment_series')
        
        # Validate that assessment series is selected
        if not assessment_series:
            raise forms.ValidationError("Please select an Assessment Series for this enrollment.")

        # Modular: enforce billed count and selection size (server-side)
        if reg_cat == 'modular' and occupation:
            modules = cleaned_data.get('modules')
            if modules is None:
                selected = 0
            else:
                try:
                    selected = modules.count()
                except Exception:
                    # modules may be a list-like
                    try:
                        selected = len(modules)
                    except Exception:
                        selected = 0
            chosen = getattr(self.candidate, 'modular_module_count', None)
            already_enrolled = 0
            try:
                already_enrolled = self.candidate.get_enrolled_modules().count()
            except Exception:
                pass
            if chosen in (1, 2):
                remaining = chosen - already_enrolled
                if remaining <= 0:
                    raise forms.ValidationError(
                        "This candidate has already enrolled in the maximum number of modules billed by the center."
                    )
                if selected == 0 or selected > remaining:
                    raise forms.ValidationError(
                        f"You can only enroll up to {remaining} remaining module(s) for this candidate."
                    )
            else:
                # Fallback: ensure 1 or 2 on first-time without billed count
                if selected == 0 or selected > 2:
                    raise forms.ValidationError("Modular candidates must select 1 or 2 modules only.")
        
        # Informal/worker's PAS: require minimum 2 and maximum 4 papers across all levels and modules
        if self.is_informal and occupation:
            selected_papers = []
            module_paper_count = {}  # Track papers per module to enforce one paper per module
            
            # Check all paper fields for selections
            for field_name in getattr(self, 'all_paper_fields', []):
                is_selected = cleaned_data.get(field_name, False)
                if is_selected:
                    # Parse field name: paper_{level_id}_{module_id}_{paper_id}
                    parts = field_name.split('_')
                    if len(parts) == 4:
                        level_id = int(parts[1])
                        module_id = int(parts[2])
                        paper_id = int(parts[3])
                        
                        # Check if we already have a paper selected for this module
                        if module_id in module_paper_count:
                            # Get module name for error message
                            try:
                                from .models import Module
                                module = Module.objects.get(id=module_id)
                                raise forms.ValidationError(
                                    f"You can only select one paper per module. "
                                    f"You have selected multiple papers for module '{module.name} ({module.code})'. "
                                    f"Please select only one paper per module."
                                )
                            except Module.DoesNotExist:
                                raise forms.ValidationError(
                                    "You can only select one paper per module. "
                                    "Please select only one paper per module."
                                )
                        
                        # Get the paper object
                        try:
                            from .models import Paper
                            paper = Paper.objects.get(id=paper_id)
                            selected_papers.append({
                                'paper': paper,
                                'level_id': level_id,
                                'module_id': module_id,
                                'paper_id': paper_id
                            })
                            module_paper_count[module_id] = 1
                        except Paper.DoesNotExist:
                            raise forms.ValidationError(f"Invalid paper selection: {field_name}")
            
            # Check if this is the candidate's first sitting or a subsequent sitting
            from .models import Result
            
            # Ensure we have a candidate object
            if not self.candidate:
                raise forms.ValidationError("No candidate specified for enrollment validation.")
            
            has_previous_results = Result.objects.filter(candidate=self.candidate).exists()
            

            
            if has_previous_results:
                # Subsequent sitting: No minimum restriction, only maximum of 4 papers
                if len(selected_papers) > 4:
                    raise forms.ValidationError(
                        "Worker's PAS/Informal candidates can select a maximum of 4 papers at any given sitting. "
                        f"You have selected {len(selected_papers)} paper(s). Please select no more than 4 papers from different modules."
                    )
                # Allow any number of papers (including 1) for re-enrollment
            else:
                # First sitting: Enforce minimum of 2 and maximum of 4 papers
                if len(selected_papers) < 2:
                    raise forms.ValidationError(
                        "Worker's PAS/Informal candidates must select a minimum of 2 papers for their first sitting. "
                        f"You have selected {len(selected_papers)} paper(s). Please select at least 2 papers from different modules."
                    )
                elif len(selected_papers) > 4:
                    raise forms.ValidationError(
                        "Worker's PAS/Informal candidates can select a maximum of 4 papers at any given sitting. "
                        f"You have selected {len(selected_papers)} paper(s). Please select no more than 4 papers from different modules."
                    )
            
            cleaned_data['selected_papers'] = selected_papers
        return cleaned_data



class DistrictForm(forms.ModelForm):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Enter district name'
        }),
        help_text='Enter the name of the district (max 100 characters)'
    )
    # REMOVE this:
    # region = forms.CharField(...)

    class Meta:
        model = District
        fields = ['name', 'region']
        widgets = {
            'region': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            })
        }

    def clean_name(self):
        """Format district name to proper sentence case and validate uniqueness"""
        name = self.cleaned_data.get('name')
        if name:
            # Convert to proper sentence case with articles in lowercase
            words = name.strip().split()
            formatted_words = []
            
            # Articles and prepositions to keep lowercase (except at start)
            lowercase_words = {'in', 'and', 'for', 'of', 'the', 'at', 'on', 'by', 'with', 'to'}
            
            for i, word in enumerate(words):
                if i == 0:  # First word is always capitalized
                    formatted_words.append(word.capitalize())
                elif word.lower() in lowercase_words:
                    formatted_words.append(word.lower())
                else:
                    formatted_words.append(word.capitalize())
            
            name = ' '.join(formatted_words)
            
            # Check for duplicates
            if District.objects.filter(name__iexact=name).exclude(id=self.instance.id if self.instance else None).exists():
                raise forms.ValidationError('A district with this name already exists.')
        return name


class PracticalAssessorForm(forms.ModelForm):
    class Meta:
        model = PracticalAssessor
        fields = ['fullname', 'contact', 'email', 'district', 'village', 'status']
        widgets = {
            'fullname': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'placeholder': 'Enter full name'}),
            'contact': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'placeholder': 'e.g., +256701234567'}),
            'email': forms.EmailInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'placeholder': 'Enter email address'}),
            'district': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'village': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'status': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        }
        help_texts = {
            'fullname': 'Full name of the practical assessor',
            'contact': 'Phone number or contact information',
            'email': 'Email address for communication (will be used as username)',
            'district': 'District where assessor is based',
            'village': 'Village where assessor is based',
            'status': 'Account status - Active or Inactive',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set up district and village filtering
        self.fields['village'].queryset = Village.objects.none()
        
        if 'district' in self.data:
            try:
                district_id = int(self.data.get('district'))
                self.fields['village'].queryset = Village.objects.filter(district_id=district_id).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.district:
            self.fields['village'].queryset = Village.objects.filter(district=self.instance.district).order_by('name')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check if email is already used as username (excluding current instance)
            existing_user = User.objects.filter(username=email)
            if self.instance.pk and self.instance.user:
                existing_user = existing_user.exclude(pk=self.instance.user.pk)
            
            if existing_user.exists():
                raise forms.ValidationError('A user with this email already exists.')
        return email


class PracticalAssessorAssignmentForm(forms.ModelForm):
    registration_category = forms.ModelChoiceField(
        queryset=RegistrationCategory.objects.all(),
        widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        help_text='Select registration category (Formal or Modular)'
    )
    occupation = forms.ModelChoiceField(
        queryset=Occupation.objects.all(),
        widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        help_text='Select the occupation for marksheet generation'
    )
    level = forms.ModelChoiceField(
        queryset=Level.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        help_text='Select level (for Formal category)'
    )
    module = forms.ModelChoiceField(
        queryset=Module.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        help_text='Select module (for Modular category)'
    )
    
    class Meta:
        model = PracticalAssessorAssignment
        fields = ['assessment_center', 'assessment_series', 'registration_category', 'occupation', 'level', 'module']
        widgets = {
            'assessment_center': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'assessment_series': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        }
        help_texts = {
            'assessment_center': 'Select the assessment center to assign',
            'assessment_series': 'Select the assessment series for this assignment',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show all occupations for now - we'll filter based on practical marksheets existence
        self.fields['occupation'].queryset = Occupation.objects.all()
        # Show all modules - form validation will handle the filtering
        self.fields['module'].queryset = Module.objects.all()
    
    def clean(self):
        cleaned_data = super().clean()
        registration_category = cleaned_data.get('registration_category')
        level = cleaned_data.get('level')
        module = cleaned_data.get('module')
        
        # Debug: Print what we're getting
        print(f"DEBUG - Registration Category: {registration_category}")
        print(f"DEBUG - Level: {level}")
        print(f"DEBUG - Module: {module}")
        
        if registration_category and registration_category.name == 'Formal' and not level:
            raise forms.ValidationError('Level is required for Formal registration category.')
        elif registration_category and registration_category.name == 'Modular' and not module:
            raise forms.ValidationError('Module is required for Modular registration category.')
        
        return cleaned_data


class VillageForm(forms.ModelForm):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Enter village name'
        }),
        help_text='Enter the name of the village (max 100 characters)'
    )
    district = forms.ModelChoiceField(
        queryset=District.objects.all(),
        widget=forms.Select(attrs={
            'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
        }),
        help_text='Select the district where this village is located'
    )

    class Meta:
        model = Village
        fields = ['name', 'district']

    def clean_name(self):
        """Format village name to proper sentence case and validate uniqueness"""
        name = self.cleaned_data.get('name')
        district = self.cleaned_data.get('district')
        
        if name:
            # Convert to proper sentence case with articles in lowercase
            words = name.strip().split()
            formatted_words = []
            
            # Articles and prepositions to keep lowercase (except at start)
            lowercase_words = {'in', 'and', 'for', 'of', 'the', 'at', 'on', 'by', 'with', 'to'}
            
            for i, word in enumerate(words):
                if i == 0:  # First word is always capitalized
                    formatted_words.append(word.capitalize())
                elif word.lower() in lowercase_words:
                    formatted_words.append(word.lower())
                else:
                    formatted_words.append(word.capitalize())
            
            name = ' '.join(formatted_words)
            
            # Check for duplicates within the same district
            if district and Village.objects.filter(name__iexact=name, district=district).exclude(id=self.instance.id if self.instance else None).exists():
                raise forms.ValidationError('A village with this name already exists in the selected district.')
        return name


class CenterRepForm(forms.ModelForm):
    class Meta:
        model = CenterRepresentative
        fields = ['name', 'contact', 'center', 'assessment_center_branch']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-green-400'}),
            'contact': forms.TextInput(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-green-400'}),
            'center': forms.Select(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-green-400'}),
            'assessment_center_branch': forms.Select(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-green-400'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Branch is optional; empty means Main Center login
        self.fields['assessment_center_branch'].required = False
        self.fields['assessment_center_branch'].empty_label = 'Main Center (no specific branch)'
        self.fields['assessment_center_branch'].help_text = 'Optional: select a specific branch to restrict this account to that branch only.'

        # Default queryset for branches
        from .models import AssessmentCenterBranch, AssessmentCenter
        branches_qs = AssessmentCenterBranch.objects.none()

        # Determine chosen center: POST data > instance > None
        center_obj = None
        if self.data.get('center'):
            try:
                center_obj = AssessmentCenter.objects.get(pk=int(self.data.get('center')))
            except (ValueError, TypeError, AssessmentCenter.DoesNotExist):
                center_obj = None
        elif self.instance and getattr(self.instance, 'center_id', None):
            center_obj = self.instance.center

        if center_obj and center_obj.has_branches:
            branches_qs = AssessmentCenterBranch.objects.filter(assessment_center=center_obj).order_by('branch_code')
        self.fields['assessment_center_branch'].queryset = branches_qs

    def save(self, commit=True):
        profile = super().save(commit=False)
        name = self.cleaned_data.get('name', '')
        center = self.cleaned_data['center']
        center_number = center.center_number
        # When a branch is selected, include it in the username/email so branch reps can log in independently
        branch = self.cleaned_data.get('assessment_center_branch')
        base_username = center_number if not branch else f"{center_number}-{branch.branch_code}"
        # Normalize username/email (lowercase)
        base_username = base_username.strip().lower()
        email = f"{base_username}@uvtab.go.ug"
        if not profile.pk or not getattr(profile, 'user', None):
            # Creating new CenterRep and User
            password = "Uvtab@2025"
            # Ensure uniqueness of username
            username = email
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}@uvtab.go.ug"
                counter += 1
            user = User.objects.create_user(
                username=username,
                email=username,
                password=password,
                first_name=name
            )
            group = Group.objects.get(name='CenterRep')
            user.groups.add(group)
            profile.user = user
        else:
            # Editing existing CenterRep: update user fields, but do not change username/email
            user = profile.user
            user.first_name = name
            # If branch assignment changed, update username/email to branch-based (or main center based)
            try:
                current_base = user.username.split('@')[0] if '@' in user.username else user.username
                desired_base = base_username
                if current_base != desired_base:
                    desired_username = f"{desired_base}@uvtab.go.ug"
                    counter = 1
                    new_username = desired_username
                    while User.objects.filter(username=new_username).exclude(pk=user.pk).exists():
                        new_username = f"{desired_base}{counter}@uvtab.go.ug"
                        counter += 1
                    user.username = new_username
                    user.email = new_username
            except Exception:
                # If anything goes wrong, keep existing username/email
                pass
            user.save()
        if commit:
            profile.save()
        return profile

class SupportStaffForm(forms.ModelForm):
    class Meta:
        model = SupportStaff
        fields = ['name', 'contact', 'department']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-green-400'}),
            'contact': forms.TextInput(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-green-400'}),
            'department': forms.Select(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-green-400'})
        }

    def save(self, commit=True):
        from django.utils.text import slugify
        base_username = slugify(self.cleaned_data.get('name', 'support'))
        if not base_username:
            base_username = 'support'
        username = f"{base_username}.support"
        email = f"{username}@uvtab.go.ug"
        # Ensure uniqueness
        original_username = username
        original_email = email
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{original_username}{counter}"
            email = f"{username}@uvtab.go.ug"
            counter += 1
        password = "uvtab"
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=self.cleaned_data.get('name', '')
        )
        group = Group.objects.get(name='SupportStaff')
        user.groups.add(group)
        profile = super().save(commit=False)
        profile.user = user
        if commit:
            profile.save()
        return profile

class StaffForm(forms.ModelForm):
    """Form for departmental staff management (separate from SupportStaff)"""
    class Meta:
        model = Staff
        fields = ['name', 'contact', 'department', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400'}),
            'contact': forms.TextInput(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400'}),
            'department': forms.Select(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400'}),
            'status': forms.Select(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400'}),
        }
        labels = {
            'name': 'Full Name',
            'contact': 'Phone Number',
            'department': 'Department',
            'status': 'Account Status',
        }

    def save(self, commit=True):
        """Create user account and assign to Staff group (only for new staff)"""
        from django.contrib.auth.models import User, Group
        import random
        
        # Save staff profile
        profile = super().save(commit=False)
        
        # Only create new user if this is a new staff member (no existing user)
        if not hasattr(profile, 'user') or not profile.user:
            try:
                # Generate unique username
                base_username = self.cleaned_data['name'].lower().replace(' ', '.')
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                # Generate unique email
                email = f"{username}@uvtab.go.ug"
                counter = 1
                while User.objects.filter(email=email).exists():
                    email = f"{username}{counter}@uvtab.go.ug"
                    counter += 1
                
                # Create user account
                password = "uvtab"
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=self.cleaned_data.get('name', '')
                )
                
                # Add to Staff group (create if doesn't exist)
                staff_group, created = Group.objects.get_or_create(name='Staff')
                user.groups.add(staff_group)
                
                # Assign user to profile
                profile.user = user
                
            except Exception as e:
                print(f"[DEBUG] Error creating user for staff: {e}")
                raise forms.ValidationError(f"Error creating user account: {e}")
        else:
            # For existing staff, just update the name in the User model
            if profile.user:
                profile.user.first_name = self.cleaned_data.get('name', '')
                profile.user.save()
        
        if commit:
            profile.save()
        return profile

import calendar

class FormalResultsForm(forms.Form):
    MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]
    YEAR_CHOICES = [(y, y) for y in range(2020, 2031)]
    month = forms.ChoiceField(choices=MONTH_CHOICES, label="Assessment Month", widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))
    year = forms.ChoiceField(choices=YEAR_CHOICES, label="Assessment Year", widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))
    theory_mark = forms.DecimalField(
        label="Theory Mark",
        min_value=-1, max_value=100, decimal_places=2, required=True,
        widget=forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'step': '0.01'}),
        help_text="Enter -1 for missing paper (candidate didn't sit)"
    )
    practical_mark = forms.DecimalField(
        label="Practical Mark",
        min_value=-1, max_value=100, decimal_places=2, required=True,
        widget=forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'step': '0.01'}),
        help_text="Enter -1 for missing paper (candidate didn't sit)"
    )

    def __init__(self, *args, **kwargs):
        candidate = kwargs.pop('candidate', None)
        super().__init__(*args, **kwargs)
        # Optionally, set initial values or validation based on candidate/level if needed

    def clean(self):
        cleaned_data = super().clean()
        # Add cross-field validation if needed
        return cleaned_data


class ModularResultsForm(forms.Form):
    MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]
    YEAR_CHOICES = [(y, y) for y in range(2020, 2031)]
    month = forms.ChoiceField(choices=MONTH_CHOICES, label="Assessment Month", widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))
    year = forms.ChoiceField(choices=YEAR_CHOICES, label="Assessment Year", widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))

    def __init__(self, *args, **kwargs):
        import datetime
        candidate = kwargs.pop('candidate', None)
        # Set initial month/year from candidate.assessment_date if available
        initial = kwargs.get('initial', {}) or {}
        if candidate and getattr(candidate, 'assessment_date', None):
            adate = candidate.assessment_date
            initial.setdefault('month', adate.month)
            initial.setdefault('year', adate.year)
        else:
            today = datetime.date.today()
            initial.setdefault('month', today.month)
            initial.setdefault('year', today.year)
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)
        self.modules = []
        if candidate:
            from .models import Module
            # Get all registered modules for the candidate
            modules = Module.objects.filter(candidatemodule__candidate=candidate).distinct()
            self.modules = modules
            for module in modules:
                field_name = f'mark_{module.id}'
                # Check if initial value is provided in self.initial
                value = self.initial.get(field_name)
                self.fields[field_name] = forms.DecimalField(
                    label=f"{module.code} - {module.name} Mark",
                    min_value=-1,
                    max_value=100,
                    decimal_places=2,
                    required=True,
                    widget=forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'step': '0.01'}),
                    initial=value,
                    help_text="Enter -1 for missing paper (candidate didn't sit)"
                )

    def clean(self):
        cleaned_data = super().clean()
        # You can add cross-field validation here if needed
        return cleaned_data

class ResultForm(forms.ModelForm):
    MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]
    YEAR_CHOICES = [(y, y) for y in range(2020, 2031)]
    month = forms.ChoiceField(choices=MONTH_CHOICES, label="Assessment Month", widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))
    year = forms.ChoiceField(choices=YEAR_CHOICES, label="Assessment Year", widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))

    class Meta:
        model = Result
        fields = ['level', 'module', 'paper', 'assessment_type', 'mark']
        widgets = {
            'level': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'module': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'paper': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'assessment_type': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'mark': forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'step': '0.01', 'min': '0', 'max': '100'}),
        }

    def __init__(self, *args, **kwargs):
        candidate = kwargs.pop('candidate', None)
        super().__init__(*args, **kwargs)
        if candidate:
            # Filter level/module/paper fields based on candidate registration
            self.fields['level'].queryset = Level.objects.filter(candidatelevel__candidate=candidate)
            self.fields['module'].queryset = Module.objects.filter(candidatemodule__candidate=candidate)
            self.fields['paper'].queryset = Paper.objects.none()  # Set dynamically if needed
            reg_cat = getattr(candidate, 'registration_category', '').lower()
            if reg_cat == 'modular':
                self.fields['paper'].widget = forms.HiddenInput()
                self.fields['assessment_type'].initial = 'practical'
                self.fields['assessment_type'].widget.attrs['readonly'] = True
            elif reg_cat == 'formal':
                # For formal, decide based on level structure (modules or papers)
                levels = Level.objects.filter(candidatelevel__candidate=candidate)
                if levels.exists():
                    occ_levels = OccupationLevel.objects.filter(occupation=candidate.occupation, level__in=levels)
                    if occ_levels.filter(structure_type='modules').exists():
                        self.fields['module'].queryset = Module.objects.filter(candidatemodule__candidate=candidate)
                        self.fields['paper'].widget = forms.HiddenInput()
                    elif occ_levels.filter(structure_type='papers').exists():
                        self.fields['paper'].queryset = Paper.objects.filter(occupation=candidate.occupation, level__in=levels)
                        self.fields['module'].widget = forms.HiddenInput()
            else:
                self.fields['module'].widget = forms.HiddenInput()
                self.fields['paper'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        month = int(cleaned_data.get('month'))
        year = int(cleaned_data.get('year'))
        # Set assessment_date to first of the month (for storage)
        cleaned_data['assessment_date'] = f"{year}-{month:02d}-01"
        return cleaned_data

# --------------------------------------------------

class PaperResultsForm(forms.Form):
    assessment_series = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        label="Assessment Series",
        widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        help_text="Select the assessment series for these results"
    )

    def __init__(self, *args, **kwargs):
        candidate = kwargs.pop('candidate', None)
        super().__init__(*args, **kwargs)
        self.papers = []
        
        # Set up assessment series queryset
        from .models import AssessmentSeries
        self.fields['assessment_series'].queryset = AssessmentSeries.objects.all().order_by('-is_current', '-start_date')
        
        if candidate:
            from .models import Paper, Level, CandidateLevel
            # Get candidate's enrolled level
            level = getattr(candidate, 'level', None)
            if not level:
                cl = CandidateLevel.objects.filter(candidate=candidate).first()
                if cl:
                    level = cl.level
            # Find all papers for this occupation and level
            if level:
                papers = Paper.objects.filter(occupation=candidate.occupation, level=level)
                self.papers = papers
                for paper in papers:
                    field_name = f'mark_{paper.id}'
                    self.fields[field_name] = forms.DecimalField(
                        label=f"{paper.code} - {paper.name} ({paper.get_grade_type_display()}) Mark",
                        min_value=-1,
                        max_value=100,
                        decimal_places=2,
                        required=True,
                        widget=forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'step': '0.01'}),
                        help_text="Enter -1 for missing paper (candidate didn't sit)"
                    )

    def clean(self):
        cleaned_data = super().clean()
        assessment_series = cleaned_data.get('assessment_series')
        if assessment_series:
            # Use the assessment series start date as the assessment date
            cleaned_data['assessment_date'] = assessment_series.start_date.strftime('%Y-%m-%d')
        return cleaned_data


class WorkerPASPaperResultsForm(forms.Form):
    assessment_series = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        label="Assessment Series",
        widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
        required=True
    )

    def __init__(self, *args, **kwargs):
        candidate = kwargs.pop('candidate', None)
        level = kwargs.pop('level', None)
        super().__init__(*args, **kwargs)
        
        # Set up assessment series queryset
        from .models import AssessmentSeries
        self.fields['assessment_series'].queryset = AssessmentSeries.objects.all().order_by('-is_current', '-start_date')
        
        self.papers = []
        if candidate:
            from .models import CandidateLevel, CandidatePaper, Level
            # Use explicit level if provided
            if not level:
                # Try to get from candidate.level, else first CandidateLevel
                level = getattr(candidate, 'level', None)
                if not level:
                    cl = CandidateLevel.objects.filter(candidate=candidate).first()
                    if cl:
                        level = cl.level
            if level:
                # Get only the enrolled papers for this candidate and level
                enrolled_papers = CandidatePaper.objects.filter(candidate=candidate, level=level).select_related('paper', 'module')
                self.papers = [cp.paper for cp in enrolled_papers]
                for cp in enrolled_papers:
                    paper = cp.paper
                    field_name = f'mark_{paper.id}'
                    self.fields[field_name] = forms.DecimalField(
                        label=f"{paper.code} - {paper.name} (Module: {cp.module.name}) Mark",
                        min_value=-1,
                        max_value=100,
                        decimal_places=2,
                        required=True,
                        widget=forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'step': '0.01'}),
                        help_text="Enter -1 for missing paper (candidate didn't sit)"
                    )

    def clean(self):
        cleaned_data = super().clean()
        assessment_series = cleaned_data.get('assessment_series')
        if assessment_series:
            # Use the assessment series start_date as the assessment_date
            cleaned_data['assessment_date'] = assessment_series.start_date.strftime('%Y-%m-%d')
        return cleaned_data

class ChangeOccupationForm(forms.ModelForm):
    class Meta:
        model  = Candidate
        fields = ['occupation']
        widgets = {
            'occupation': forms.Select(
                attrs={'class': 'w-full border rounded-md px-3 py-2'}
            )
        }

class ChangeCenterForm(forms.ModelForm):
    class Meta:
        model  = Candidate
        fields = ['assessment_center']
        widgets = {
            'assessment_center': forms.Select(
                attrs={'class': 'w-full border rounded-md px-3 py-2'}
            )
        }

class AssessmentSeriesForm(forms.ModelForm):
    class Meta:
        model = AssessmentSeries
        fields = ['name', 'start_date', 'end_date', 'date_of_release', 'is_current', 'results_released']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'w-full border rounded-md px-3 py-2',
                    'placeholder': 'Enter assessment series name'
                }
            ),
            'start_date': forms.DateInput(
                attrs={
                    'class': 'w-full border rounded-md px-3 py-2',
                    'type': 'date'
                }
            ),
            'end_date': forms.DateInput(
                attrs={
                    'class': 'w-full border rounded-md px-3 py-2',
                    'type': 'date'
                }
            ),
            'date_of_release': forms.DateInput(
                attrs={
                    'class': 'w-full border rounded-md px-3 py-2',
                    'type': 'date'
                }
            ),
            'is_current': forms.CheckboxInput(
                attrs={
                    'class': 'rounded border-gray-300 text-purple-600 shadow-sm focus:border-purple-300 focus:ring focus:ring-purple-200 focus:ring-opacity-50'
                }
            ),
            'results_released': forms.CheckboxInput(
                attrs={
                    'class': 'rounded border-gray-300 text-green-600 shadow-sm focus:border-green-300 focus:ring focus:ring-green-200 focus:ring-opacity-50'
                }
            )
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        date_of_release = cleaned_data.get('date_of_release')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise forms.ValidationError("End date must be after start date.")
        
        if end_date and date_of_release:
            if date_of_release < end_date:
                raise forms.ValidationError("Date of release must be on or after the end date.")
        
        return cleaned_data

class SectorForm(forms.ModelForm):
    """Form for creating and editing sectors"""
    
    class Meta:
        model = Sector
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500',
                'placeholder': 'Enter sector name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500',
                'placeholder': 'Enter sector description (optional)',
                'rows': 4
            }),
        }
        labels = {
            'name': 'Sector Name',
            'description': 'Description',
        }
        help_texts = {
            'name': 'Enter a unique name for this sector (max 100 characters)',
            'description': 'Provide a brief description of this sector (optional)',
        }

    def clean_name(self):
        """Validate sector name uniqueness (case-insensitive)"""
        name = self.cleaned_data.get('name')
        if name:
            # Check for duplicate names (case-insensitive)
            existing = Sector.objects.filter(name__iexact=name)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise forms.ValidationError(
                    f'A sector with the name "{name}" already exists. Please choose a different name.'
                )
        return name
