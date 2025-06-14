from django import forms
from django.contrib.auth.models import User, Group
from .models import AssessmentCenter, Occupation, Module, Paper, Candidate, Level, District, Village, CenterRepresentative, SupportStaff, OccupationLevel
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
        fields = ['code', 'name', 'occupation', 'level', 'grade_type']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter paper code'
            }),
            'name': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter paper name'
            }),
            'occupation': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            'level': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            'grade_type': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            })
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
            # Informal/Worker's PAS: occupation category 'Worker\'s PAS'
            elif reg_cat_val in ["worker's pas", 'workers pas', 'informal']:
                try:
                    cat = OccupationCategory.objects.get(name__iexact="Worker's PAS")
                    self.fields['occupation'].queryset = Occupation.objects.filter(category=cat)
                except OccupationCategory.DoesNotExist:
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
    level = forms.ModelChoiceField(
        queryset=Level.objects.none(),
        required=False,
        label='Level'
    )
    modules = forms.ModelMultipleChoiceField(
        queryset=Module.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Select Modules'
    )

    def __init__(self, *args, **kwargs):
        candidate = kwargs.pop('candidate', None)
        super().__init__(*args, **kwargs)

        if not candidate:
            return  # Defensive

        occupation = candidate.occupation
        reg_cat = candidate.registration_category

        if reg_cat == "Modular":
            # Show placeholder level note instead of dropdown
            self.fields["level"] = forms.CharField(
                label="Level",
                initial="Not applicable for Modular candidates",
                required=False,
                widget=forms.TextInput(attrs={
                    'readonly': True,
                    'class': 'border-0 bg-transparent italic text-gray-500'
                })
            )

            # Set only Level 1 modules for Modular candidates, fallback to all occupation modules if not found
            occ_level1 = occupation.occupation_levels.select_related('level').filter(level__name__icontains="1").first()
            if occ_level1:
                modules_qs = Module.objects.filter(occupation=occupation, level=occ_level1.level)
                if not modules_qs.exists():
                    # Fallback: show all modules for occupation
                    modules_qs = Module.objects.filter(occupation=occupation)
                self.fields["modules"].queryset = modules_qs
            else:
                # Fallback: show all modules for occupation
                self.fields["modules"].queryset = Module.objects.filter(occupation=occupation)

        elif reg_cat == "Informal" or reg_cat == "Workers PAS":
            # Use OccupationLevel join model to get levels for this occupation
            occ_levels = occupation.occupation_levels.select_related('level').all()
            levels_qs = Level.objects.filter(id__in=[ol.level.id for ol in occ_levels])
            self.fields["level"].queryset = levels_qs
            # Dynamically filter modules by selected level (if present)
            level = None
            data = self.data
            if data is not None:
                level_id = data.get("level")
                if level_id:
                    try:
                        level = Level.objects.get(pk=level_id)
                    except Level.DoesNotExist:
                        level = None
            if level:
                self.fields["modules"].queryset = Module.objects.filter(occupation=occupation, level=level)
            else:
                self.fields["modules"].queryset = Module.objects.none()

        else:  # Formal
            # Use OccupationLevel join model to get levels for this occupation
            occ_levels = occupation.occupation_levels.select_related('level').all()
            levels_qs = Level.objects.filter(id__in=[ol.level.id for ol in occ_levels])
            self.fields["level"].queryset = levels_qs
            self.fields.pop("modules", None)


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


# --------------------------------------------------
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


