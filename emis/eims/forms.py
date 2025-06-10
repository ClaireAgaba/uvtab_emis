from django import forms
from .models import AssessmentCenter, Occupation, OccupationCategory, Module, Paper, Candidate, Level   
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
    level = forms.ModelChoiceField(queryset=Level.objects.none(), required=False)
    modules = forms.ModelMultipleChoiceField(queryset=Module.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        candidate = kwargs.pop('candidate')  # This is where the error came from
        super().__init__(*args, **kwargs)

        if candidate.registration_category == 'Formal':
            self.fields['level'].queryset = Level.objects.filter(occupations=candidate.occupation)
            self.fields['level'].required = True
            self.fields['modules'].widget = forms.HiddenInput()


        elif candidate.registration_category == 'Modular':
            level = Level.objects.get(name='Level 1')  # since modular is always Level 1
            modules = Module.objects.filter(level=level, occupation=candidate.occupation)
            self.fields['modules'].queryset = modules
            self.fields['modules'].required = True


        elif candidate.registration_category == 'Informal':
            self.fields['level'].queryset = Level.objects.filter(occupations=candidate.occupation)
            self.fields['level'].required = True
            self.fields['modules'].required = True