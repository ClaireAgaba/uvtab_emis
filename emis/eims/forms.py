from django import forms
from django.contrib.auth.models import User, Group
from .models import AssessmentCenter, Occupation, Module, Paper, Candidate, Level, District, Village, CenterRepresentative, SupportStaff, OccupationLevel, FeesType, Result
from datetime import datetime   

CURRENT_YEAR = datetime.now().year
YEAR_CHOICES = [(year, year) for year in range(CURRENT_YEAR, CURRENT_YEAR - 30, -1)]


class AssessmentCenterForm(forms.ModelForm):
    class Meta:
        model = AssessmentCenter
        fields = ['center_number', 'center_name', 'category', 'district', 'village']
        widgets = {
            'center_number': forms.TextInput(attrs={'class':'border rounded px-3 py-2 w-full'}),
            'center_name': forms.TextInput(attrs={'class':'border rounded px-3 py-2 w-full'}),
            'category':    forms.Select(attrs={'class':'border rounded px-3 py-2 w-full'}),
            'district':    forms.Select(attrs={'class':'border rounded px-3 py-2 w-full'}),
            'village':     forms.Select(attrs={'class':'border rounded px-3 py-2 w-full'}),
        }


class OccupationForm(forms.ModelForm):
    class Meta:
        model = Occupation
        fields = ['code', 'name', 'category', 'has_modular']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'name': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'category': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'has_modular': forms.CheckboxInput(attrs={'class': 'ml-2'}),
        }

class LevelForm(forms.ModelForm):
    class Meta:
        model = Level
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
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
                        # For informal/worker's pas, force grade_type to practical
                        self.fields['grade_type'].initial = 'practical'
                    else:
                        self.fields['module'].required = False
                else:
                    # If no level, show no modules
                    self.fields['module'].required = False
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

class FeesTypeForm(forms.ModelForm):
    class Meta:
        model = FeesType
        fields = ['name', 'fee']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter fee type name'
            }),
            'fee': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
            }),
        }


class CandidateForm(forms.ModelForm):
    entry_year = forms.ChoiceField(
        choices=YEAR_CHOICES,
        widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        edit = kwargs.pop('edit', False)
        super().__init__(*args, **kwargs)
        # Accept DD/MM/YYYY for all date fields
        for field in ['date_of_birth', 'start_date', 'finish_date', 'assessment_date']:
            if field in self.fields:
                self.fields[field].input_formats = ['%d/%m/%Y']
        if user and user.groups.filter(name='CenterRep').exists():
            from .models import CenterRepresentative
            try:
                center_rep = CenterRepresentative.objects.get(user=user)
                self.fields['assessment_center'].queryset = self.fields['assessment_center'].queryset.filter(pk=center_rep.center.pk)
                self.fields['assessment_center'].initial = center_rep.center.pk
                self.fields['assessment_center'].disabled = True
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
        # Default: Occupation field is empty and disabled
        self.fields['occupation'].queryset = Occupation.objects.none()
        self.fields['occupation'].widget.attrs['disabled'] = True
        if reg_cat and str(reg_cat).strip():
            # Enable occupation field
            self.fields['occupation'].widget.attrs.pop('disabled', None)
            reg_cat_val = str(reg_cat).strip().lower()
            # Modular: has_modular occupations
            if reg_cat_val == 'modular':
                self.fields['occupation'].queryset = Occupation.objects.filter(has_modular=True)
            # Formal: occupation category 'Formal'
            elif reg_cat_val == 'formal':
                try:
                    cat = OccupationCategory.objects.get(name__iexact='Formal')
                    self.fields['occupation'].queryset = Occupation.objects.filter(category=cat)
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
                    self.fields['occupation'].queryset = Occupation.objects.filter(category=cat)
                else:
                    self.fields['occupation'].queryset = Occupation.objects.none()
        # Disable occupation, assessment dates, and center fields in edit mode
        if edit:
            for fname in [
                'occupation', 'assessment_center', 'assessment_date', 'start_date', 'finish_date',
                'registration_category', 'level', 'modules', 'reg_number', 'entry_year', 'intake', 'created_by',
                'enrollment_label', 'updated_by'
            ]:
                if fname in self.fields:
                    self.fields[fname].disabled = True

        # Dependent dropdown for village based on district
        self.fields['village'].queryset = Village.objects.none() # Start with an empty queryset

        if 'district' in self.data: # If form is submitted with data
            try:
                district_id = int(self.data.get('district'))
                self.fields['village'].queryset = Village.objects.filter(district_id=district_id).order_by('name')
            except (ValueError, TypeError):
                pass  # invalid input from browser; ignore and fallback to an empty queryset
        elif self.instance.pk and self.instance.district: # If form is for an existing instance
            self.fields['village'].queryset = Village.objects.filter(district=self.instance.district).order_by('name')
        # If it's a new form or no district selected, village queryset remains Village.objects.none()
        # JavaScript will populate it on district change.
    class Meta:
        model = Candidate
        fields = '__all__'
        widgets = {
            'date_of_birth': forms.DateInput(format='%d/%m/%Y', attrs={'type': 'text', 'placeholder': 'DD/MM/YYYY', 'class': 'border rounded px-3 py-2 w-full'}),
            'start_date': forms.DateInput(format='%d/%m/%Y', attrs={'type': 'text', 'placeholder': 'DD/MM/YYYY', 'class': 'border rounded px-3 py-2 w-full'}),
            'finish_date': forms.DateInput(format='%d/%m/%Y', attrs={'type': 'text', 'placeholder': 'DD/MM/YYYY', 'class': 'border rounded px-3 py-2 w-full'}),
            'assessment_date': forms.DateInput(format='%d/%m/%Y', attrs={'type': 'text', 'placeholder': 'DD/MM/YYYY', 'class': 'border rounded px-3 py-2 w-full'}),
            'full_name': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'passport_photo': forms.ClearableFileInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'contact': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'district': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'village': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'assessment_center': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            #'entry_year': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full', 'choices': YEAR_CHOICES }),
            'intake': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'occupation': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'registration_category': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),  
            # ...add others similarly

            }

    def clean(self):
        cleaned_data = super().clean()
        occupation = cleaned_data.get('occupation')
        level = cleaned_data.get('level')
        modules = cleaned_data.get('modules')
        reg_cat = cleaned_data.get('registration_category')

        if not occupation or not level:
            return cleaned_data

        # Fetch OccupationLevel instance for occupation and level
        occ_level = None
        try:
            occ_level = occupation.occupation_levels.get(level=level)
        except Exception:
            raise forms.ValidationError("Selected level is not configured for this occupation.")

        structure_type = occ_level.structure_type if occ_level else None

        if reg_cat == 'modular':
            if not occupation.has_modular:
                raise forms.ValidationError("This occupation does not allow Modular registration.")
            if structure_type == 'papers':
                raise forms.ValidationError("Modular candidates cannot register for paper-based levels.")
            if level and level.name != 'Level 1':
                raise forms.ValidationError("Modular candidates can only register for Level 1.")
            if modules.count() == 0 or modules.count() > 2:
                raise forms.ValidationError("Modular candidates must select 1 or 2 modules only.")
        elif reg_cat == 'formal':
            if modules is not None and hasattr(modules, 'exists') and modules.exists():
                raise forms.ValidationError("Formal candidates should not select modules.")
        elif reg_cat == 'informal':
            if structure_type == 'papers':
                raise forms.ValidationError("Informal candidates cannot be registered for paper-based levels.")

        return cleaned_data


# forms.py  (only the EnrollmentForm needs to change)
# … top of forms.py (imports and other forms unchanged) …

class EnrollmentForm(forms.Form):
    """
    Refactored: For worker's PAS/informal, after level selection, dynamically generate a radio group per module (listing that module's papers).
    """
    level = forms.ModelChoiceField(queryset=Level.objects.all(), required=True, widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))
    # modules field for modular/formal; for informal, we'll dynamically add paper fields per module in __init__
    modules = forms.ModelMultipleChoiceField(queryset=Module.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, candidate=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.candidate = candidate
        occupation = getattr(candidate, 'occupation', None)
        reg_cat = getattr(candidate, 'registration_category', '').strip().lower() if candidate else None
        self.is_informal = reg_cat in ["worker's pas", 'workers pas', 'informal']

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

        # For informal/worker's PAS: dynamically add paper fields per module
        if self.is_informal and occupation and level:
            print("[DEBUG] EnrollmentForm: occupation=", occupation)
            print("[DEBUG] EnrollmentForm: level=", level)
            # Remove modules field (not used for informal)
            if 'modules' in self.fields:
                self.fields.pop('modules')
            # Get all modules for this occupation/level
            modules = Module.objects.filter(occupation=occupation, level=level)
            print(f"[DEBUG] EnrollmentForm: Found {modules.count()} modules for occupation={occupation}, level={level}")
            for module in modules:
                papers = Paper.objects.filter(module=module, occupation=occupation, level=level)
                print(f"[DEBUG] Module: {module} (ID={module.id}) - Papers found: {papers.count()}")
                for paper in papers:
                    print(f"    [DEBUG] Paper: {paper} (ID={paper.id}) - occupation={paper.occupation_id}, level={paper.level_id}, module={paper.module_id}")
                field_name = f"paper_module_{module.id}"
                self.fields[field_name] = forms.ModelChoiceField(
                    queryset=papers,
                    required=False,  # Make paper selection per module optional
                    widget=forms.RadioSelect,
                    label=f"{module.name} ({module.code})"
                )
                self.fields[field_name].module = module
            self.module_field_names = [f"paper_module_{m.id}" for m in modules]
            self.module_fields = [self[name] for name in self.module_field_names]
        else:
            self.module_fields = []
            # Modular: modules field as checkboxes
            if reg_cat == 'modular' and occupation and level:
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
        # Informal/worker's PAS: allow zero or more module paper selections, but only one per module
        if self.is_informal and occupation and level:
            selected_papers = {}
            for fname in getattr(self, 'module_field_names', []):
                paper = cleaned_data.get(fname)
                if paper:
                    mod_id = int(fname.split('_')[-1])
                    selected_papers[mod_id] = paper
            # No longer require at least one paper per module; allow user to skip modules
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
        name = self.cleaned_data.get('name')
        if District.objects.filter(name__iexact=name).exclude(id=self.instance.id if self.instance else None).exists():
            raise forms.ValidationError('A district with this name already exists.')
        return name

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
        name = self.cleaned_data.get('name')
        district = self.cleaned_data.get('district')
        if district and Village.objects.filter(name__iexact=name, district=district).exclude(id=self.instance.id if self.instance else None).exists():
            raise forms.ValidationError('A village with this name already exists in the selected district.')
        return name


class CenterRepForm(forms.ModelForm):
    class Meta:
        model = CenterRepresentative
        fields = ['name', 'contact', 'center']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-green-400'}),
            'contact': forms.TextInput(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-green-400'}),
            'center': forms.Select(attrs={'class': 'block w-full border border-gray-300 rounded-md px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-green-400'})
        }

    def save(self, commit=True):
        profile = super().save(commit=False)
        name = self.cleaned_data.get('name', '')
        center = self.cleaned_data['center']
        center_number = center.center_number
        email = f"{center_number}@uvtab.go.ug"
        if not profile.pk or not getattr(profile, 'user', None):
            # Creating new CenterRep and User
            password = "Uvtab@2025"
            user = User.objects.create_user(
                username=email,
                email=email,
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


import calendar

class FormalResultsForm(forms.Form):
    MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]
    YEAR_CHOICES = [(y, y) for y in range(2020, 2031)]
    month = forms.ChoiceField(choices=MONTH_CHOICES, label="Assessment Month", widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))
    year = forms.ChoiceField(choices=YEAR_CHOICES, label="Assessment Year", widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))
    theory_mark = forms.DecimalField(
        label="Theory Mark",
        min_value=0, max_value=100, decimal_places=2, required=True,
        widget=forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'step': '0.01'})
    )
    practical_mark = forms.DecimalField(
        label="Practical Mark",
        min_value=0, max_value=100, decimal_places=2, required=True,
        widget=forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'step': '0.01'})
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
        candidate = kwargs.pop('candidate', None)
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
                    min_value=0,
                    max_value=100,
                    decimal_places=2,
                    required=True,
                    widget=forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'step': '0.01'}),
                    initial=value
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
    MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]
    YEAR_CHOICES = [(y, y) for y in range(2020, 2031)]
    month = forms.ChoiceField(choices=MONTH_CHOICES, label="Assessment Month", widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))
    year = forms.ChoiceField(choices=YEAR_CHOICES, label="Assessment Year", widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))

    def __init__(self, *args, **kwargs):
        candidate = kwargs.pop('candidate', None)
        super().__init__(*args, **kwargs)
        self.papers = []
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
                        min_value=0,
                        max_value=100,
                        decimal_places=2,
                        required=True,
                        widget=forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'step': '0.01'})
                    )

    def clean(self):
        cleaned_data = super().clean()
        month = int(cleaned_data.get('month'))
        year = int(cleaned_data.get('year'))
        cleaned_data['assessment_date'] = f"{year}-{month:02d}-01"
        return cleaned_data


class WorkerPASPaperResultsForm(forms.Form):
    MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]
    YEAR_CHOICES = [(y, y) for y in range(2020, 2031)]
    month = forms.ChoiceField(choices=MONTH_CHOICES, label="Assessment Month", widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))
    year = forms.ChoiceField(choices=YEAR_CHOICES, label="Assessment Year", widget=forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}))

    def __init__(self, *args, **kwargs):
        candidate = kwargs.pop('candidate', None)
        level = kwargs.pop('level', None)
        super().__init__(*args, **kwargs)
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
                        min_value=0,
                        max_value=100,
                        decimal_places=2,
                        required=True,
                        widget=forms.NumberInput(attrs={'class': 'border rounded px-3 py-2 w-full', 'step': '0.01'})
                    )

    def clean(self):
        cleaned_data = super().clean()
        month = int(cleaned_data.get('month'))
        year = int(cleaned_data.get('year'))
        cleaned_data['assessment_date'] = f"{year}-{month:02d}-01"
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


