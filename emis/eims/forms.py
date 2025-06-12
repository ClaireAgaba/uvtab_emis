from django import forms
from django.contrib.auth.models import User, Group
from .models import AssessmentCenter, Occupation, Module, Paper, Candidate, Level, District, Village, CenterRepresentative, SupportStaff
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
        fields = ['code', 'name', 'category', 'structure_type', 'levels']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'name': forms.TextInput(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'category': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'structure_type': forms.Select(attrs={'class': 'border rounded px-3 py-2 w-full'}),
            'levels': forms.CheckboxSelectMultiple(attrs={'class': 'space-y-2'}),
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
        super().__init__(*args, **kwargs)
        if user and user.groups.filter(name='CenterRep').exists():
            from .models import CenterRepresentative
            try:
                center_rep = CenterRepresentative.objects.get(user=user)
                self.fields['assessment_center'].queryset = self.fields['assessment_center'].queryset.filter(pk=center_rep.center.pk)
                self.fields['assessment_center'].initial = center_rep.center.pk
                self.fields['assessment_center'].disabled = True
            except CenterRepresentative.DoesNotExist:
                self.fields['assessment_center'].queryset = self.fields['assessment_center'].queryset.none()
    class Meta:
        model = Candidate
        fields = '__all__'
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'border rounded px-3 py-2 w-full'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'border rounded px-3 py-2 w-full'}),
            'finish_date': forms.DateInput(attrs={'type': 'date', 'class': 'border rounded px-3 py-2 w-full'}),
            'assessment_date': forms.DateInput(attrs={'type': 'date', 'class': 'border rounded px-3 py-2 w-full'}),
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
        occupation = cleaned_data.get("occupation")
        reg_cat = cleaned_data.get("registration_category")
        modules = cleaned_data.get("modules")
        level = cleaned_data.get("level")

        if reg_cat == 'modular':
            if occupation.structure_type == 'papers':
                raise ValidationError("Modular candidates cannot register for paper-based occupations.")
            if not level or level.name != "1":
                raise ValidationError("Modular candidates can only register for Level 1.")
            if modules.count() == 0 or modules.count() > 2:
                raise ValidationError("Modular candidates must select 1 or 2 modules only.")
        elif reg_cat == 'formal':
            if modules.exists():
                raise ValidationError("Formal candidates should not select modules.")
        elif reg_cat == 'informal':
            if occupation.structure_type == 'papers':
                raise ValidationError("Informal candidates cannot be registered for paper-based occupations.")


class EnrollmentForm(forms.Form):
    level = forms.ModelChoiceField(queryset=Level.objects.all(), required=False, label='Level')
    modules = forms.ModelMultipleChoiceField(
        queryset=Module.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Select Modules"
    )

    def __init__(self, *args, **kwargs):
        candidate = kwargs.pop('candidate', None)
        super().__init__(*args, **kwargs)

        if candidate:
            occupation = candidate.occupation

            if candidate.registration_category == 'Modular':
                # Hide level field
                self.fields.pop('level', None)

                # Filter to Level 1 modules only
                level_1 = occupation.levels.filter(name__icontains='Level 1').first()
                self.fields['modules'].queryset = Module.objects.filter(occupation=occupation, level=level_1)

            elif candidate.registration_category == 'Informal':
                # Allow both level and modules
                self.fields['level'].queryset = occupation.levels.all()
                self.fields['modules'].queryset = Module.objects.filter(occupation=occupation)

            else:  # Formal (Level only)
                self.fields['level'].queryset = occupation.levels.all()
                self.fields['modules'].widget = forms.HiddenInput()  # Hide modules for formal candidates

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
