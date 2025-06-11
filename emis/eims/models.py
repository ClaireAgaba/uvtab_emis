from django.db import models



GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]
INTAKE_CHOICES = [
    ('March', 'March'),
    ('August', 'August'),
]

# Create your models here.

class District(models.Model):
    REGION_CHOICES = [
        ('Central', 'Central'),
        ('Western', 'Western'),
        ('Eastern', 'Eastern'),
        ('Northern', 'Northern'),
    ]
    name = models.CharField(max_length=100, unique=True)
    region = models.CharField(max_length=50, choices=REGION_CHOICES)

    def __str__(self):
        return self.name

class Village(models.Model):
    name = models.CharField(max_length=100)
    district = models.ForeignKey(District, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('name', 'district')
        ordering = ['district', 'name']

    def __str__(self):
        return f"{self.name} ({self.district.name})"

class AssessmentCenterCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class OccupationCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class RegistrationCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name



class Grade(models.Model):
    GRADE_TYPE_CHOICES = [
        ('theory', 'Theory'),
        ('practical', 'Practical'),
    ]

    grade = models.CharField(max_length=5)  # e.g. A+, C-
    min_score = models.IntegerField()
    max_score = models.IntegerField()
    type = models.CharField(max_length=10, choices=GRADE_TYPE_CHOICES)

    class Meta:
        unique_together = ('grade', 'type')
        ordering = ['-type', '-min_score']  # sort descending by score

    def __str__(self):
        return f"{self.grade} ({self.type.upper()} {self.min_score}-{self.max_score}%)"




class AssessmentCenter(models.Model):
    center_number = models.CharField(max_length=50, unique=True)
    center_name = models.CharField(max_length=255)
    category = models.ForeignKey('AssessmentCenterCategory', on_delete=models.CASCADE)
    district = models.ForeignKey('District', on_delete=models.CASCADE)
    village = models.ForeignKey('Village', on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.center_name} ({self.center_number})"


class Occupation(models.Model):
    STRUCTURE_CHOICES = [
        ('modules', 'Modules'),
        ('papers', 'Papers'),
    ]

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey('OccupationCategory', on_delete=models.CASCADE)
    structure_type = models.CharField(
        max_length=10,
        choices=STRUCTURE_CHOICES,
        help_text="Specify whether this occupation uses modules or papers"
    )
    levels = models.ManyToManyField('Level', related_name='occupations')

    def __str__(self):
        return self.name



class Level(models.Model):
    name = models.CharField(max_length=100, unique=True)
    #occupation = models.ForeignKey(Occupation, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

class Module(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    occupation = models.ForeignKey('Occupation', on_delete=models.CASCADE)
    level = models.ForeignKey(Level, on_delete=models.CASCADE)


    def __str__(self):
        return f"{self.code} - {self.name}"


    
class Paper(models.Model):
    PAPER_TYPE_CHOICES = [
        ('theory', 'Theory'),
        ('practical', 'Practical'),
    ]

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    occupation = models.ForeignKey('Occupation', on_delete=models.CASCADE)
    level = models.ForeignKey(Level, on_delete=models.CASCADE)
    grade_type = models.CharField(max_length=10, choices=PAPER_TYPE_CHOICES)

    def __str__(self):
        return f"{self.code} - {self.name} ({self.type})"


# models.py

class Candidate(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]
    NATIONALITY_CHOICES = [('U', 'Ugandan'), ('X', 'Foreigner')]

    # Section 1 - Personal Information
    full_name = models.CharField(max_length=255)
    passport_photo = models.ImageField(upload_to='candidate_photos/', blank=True, null=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    nationality = models.CharField(max_length=1, choices=NATIONALITY_CHOICES)

    # Section 2 - Contact and Location
    contact = models.CharField(max_length=20, blank=True)
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True)
    village = models.ForeignKey(Village, on_delete=models.SET_NULL, null=True)

    # Section 3 - Assessment Info (without modules or levels yet)
    assessment_center = models.ForeignKey(AssessmentCenter, on_delete=models.SET_NULL, null=True)
    entry_year = models.PositiveIntegerField()
    intake = models.CharField(max_length=6, choices=[('M', 'March'), ('A', 'August')])
    occupation = models.ForeignKey(Occupation, on_delete=models.SET_NULL, null=True)
    registration_category = models.CharField(max_length=10, choices=[
        ('Formal', 'Formal'),
        ('Modular', 'Modular'),
        ('Informal', "Worker's PAS")
    ])

    # Section 4 - Assessment Dates
    start_date = models.DateField()
    finish_date = models.DateField()
    assessment_date = models.DateField()


    def is_enrolled(self):
        return self.candidatelevel_set.exists() or self.candidatemodule_set.exists()

    enrollment_label = models.CharField(max_length=100, blank=True, null=True)

    reg_number = models.CharField(max_length=100, unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.reg_number:
            occ_code = self.occupation.code if self.occupation else "XXX"
            reg_type = self.registration_category[0].upper()
            intake_str = self.intake.upper()
            year_suffix = str(self.entry_year)[-2:]
            unique_num = Candidate.objects.count() + 1
            self.reg_number = f"{self.nationality}/{year_suffix}/{intake_str}/{occ_code}/{reg_type}/{str(unique_num).zfill(3)}-{self.assessment_center.center_number}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.reg_number})"

class CandidateLevel(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    level = models.ForeignKey(Level, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.candidate.full_name} - {self.level.name}"

class CandidateModule(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.candidate.full_name} - {self.module.name}"


