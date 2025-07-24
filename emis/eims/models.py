from django.db import models
from django.contrib.auth.models import User
from django.db import transaction
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from django.core.files.base import ContentFile
import os



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

class NatureOfDisability(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class AssessmentCenterCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Assessment Center Category"
        verbose_name_plural = "Assessment Center Categories"
class OccupationCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class RegistrationCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Registration Category"
        verbose_name_plural = "Registration Categories"

class FeesType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    fee = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.fee})"

    class Meta:
        verbose_name = "Fees Type"
        verbose_name_plural = "Fees Types"



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
        return f"{self.center_number} - {self.center_name}"

    class Meta:
        ordering = ['center_number']
        verbose_name = "Assessment Center"
        verbose_name_plural = "Assessment Centers"


class Occupation(models.Model):
    from django.contrib.auth import get_user_model
    STRUCTURE_CHOICES = [
        ('modules', 'Modules'),
        ('papers', 'Papers'),
    ]

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey('OccupationCategory', on_delete=models.CASCADE)

    has_modular = models.BooleanField(
        default=False,
        help_text="Tick if this occupation allows Modular registration (Level 1 only)"
    )

    # Audit trail fields
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(get_user_model(), related_name='created_occupations', null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(get_user_model(), related_name='updated_occupations', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.code} - {self.name}"


class Level(models.Model):
    name = models.CharField(max_length=100)
    occupation = models.ForeignKey('Occupation', on_delete=models.CASCADE, related_name='levels')

    def __str__(self):
        return f"{self.name} ({self.occupation.code})"

    class Meta:
        unique_together = ('name', 'occupation')

class OccupationLevel(models.Model):
    STRUCTURE_CHOICES = [
        ('modules', 'Modules'),
        ('papers', 'Papers'),
    ]
    occupation = models.ForeignKey('Occupation', on_delete=models.CASCADE, related_name='occupation_levels')
    level = models.ForeignKey('Level', on_delete=models.CASCADE, related_name='occupation_levels')
    structure_type = models.CharField(
        max_length=10,
        choices=STRUCTURE_CHOICES,
        default='modules',
        help_text="Specify whether this level for this occupation uses modules or papers"
    )

    class Meta:
        unique_together = ('occupation', 'level')

    def __str__(self):
        return f"{self.occupation} - {self.level} ({self.structure_type})"

class Module(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    occupation = models.ForeignKey('Occupation', on_delete=models.CASCADE)
    level = models.ForeignKey(Level, on_delete=models.CASCADE)


    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        ordering = ['name']


    
class Paper(models.Model):
    PAPER_TYPE_CHOICES = [
        ('theory', 'Theory'),
        ('practical', 'Practical'),
    ]

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    occupation = models.ForeignKey('Occupation', on_delete=models.CASCADE)
    level = models.ForeignKey(Level, on_delete=models.CASCADE)
    module = models.ForeignKey('Module', on_delete=models.SET_NULL, null=True, blank=True, help_text="(Optional) Link this paper to a module for informal/worker's pas occupations.")
    grade_type = models.CharField(max_length=10, choices=PAPER_TYPE_CHOICES)

    def __str__(self):
        return f"{self.code} - {self.name} ({self.grade_type})"


class Result(models.Model):
    RESULT_TYPE_CHOICES = [
        ('modular', 'Modular'),
        ('formal', 'Formal'),
    ]
    ASSESSMENT_TYPE_CHOICES = [
        ('practical', 'Practical'),
        ('theory', 'Theory'),
    ]
    candidate = models.ForeignKey('Candidate', on_delete=models.CASCADE)
    level = models.ForeignKey('Level', on_delete=models.CASCADE, null=True, blank=True)
    module = models.ForeignKey('Module', on_delete=models.CASCADE, null=True, blank=True)
    paper = models.ForeignKey('Paper', on_delete=models.CASCADE, null=True, blank=True)
    assessment_date = models.DateField()
    result_type = models.CharField(max_length=10, choices=RESULT_TYPE_CHOICES)
    assessment_type = models.CharField(max_length=10, choices=ASSESSMENT_TYPE_CHOICES)
    mark = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=5)
    comment = models.CharField(max_length=32)
    status = models.CharField(max_length=16, blank=True, default='')
    date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = 'Result'
        verbose_name_plural = 'Results'
        ordering = ['assessment_date', 'candidate', 'level', 'module', 'paper']

    def __str__(self):
        return f"{self.candidate} - {self.level} - {self.module or self.paper} - {self.mark}"

    def save(self, *args, **kwargs):
        # Auto-calculate grade and comment based on mark
        from .models import Grade
        grade_type = self.assessment_type
        grade_obj = Grade.objects.filter(type=grade_type, min_score__lte=self.mark, max_score__gte=self.mark).first()
        if grade_obj:
            self.grade = grade_obj.grade
            # Set passmark per type
            if grade_type == 'practical':
                passmark = 65
            else:
                passmark = 50
            if self.mark >= passmark:
                self.comment = 'Successful'
            else:
                self.comment = 'CTR'
        else:
            self.grade = ''
            self.comment = ''
        # For modular results, ensure level is blank/null
        if self.result_type == 'modular':
            self.level = None
        super().save(*args, **kwargs)



# models.py

class Candidate(models.Model):
    from django.contrib.auth import get_user_model
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]
    # Section 1 - Personal Information
    full_name = models.CharField(max_length=255)
    passport_photo = models.ImageField(upload_to='candidate_photos/', blank=True, null=True)
    # Stores the regno-stamped version of the passport photo (do not overwrite the original)
    passport_photo_with_regno = models.ImageField(upload_to='candidate_photos/regno/', blank=True, null=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    nationality = models.CharField(max_length=64, help_text="Specify country of nationality (e.g. Ugandan, Kenyan, Rwandan, etc.)")

    # Section 2 - Contact and Location
    contact = models.CharField(max_length=20, blank=True)
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True)
    village = models.ForeignKey(Village, on_delete=models.SET_NULL, null=True)

    # Section 3 - Assessment Info (without modules or levels yet)
    assessment_center = models.ForeignKey(AssessmentCenter, on_delete=models.SET_NULL, null=True)
    entry_year = models.PositiveIntegerField()
    intake = models.CharField(max_length=6, choices=[('M', 'March'), ('A', 'August')])
    occupation = models.ForeignKey('Occupation', on_delete=models.SET_NULL, null=True)
    registration_category = models.CharField(max_length=10, choices=[
        ('Formal', 'Formal'),
        ('Modular', 'Modular'),
        ('Informal', "Worker's PAS")
    ])

    # Section 4 - Assessment Dates
    start_date = models.DateField()
    finish_date = models.DateField()
    assessment_date = models.DateField()

    # Audit trail fields
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(get_user_model(), related_name='created_candidates', null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(get_user_model(), related_name='updated_candidates', null=True, blank=True, on_delete=models.SET_NULL)

    def is_enrolled(self):
        return self.candidatelevel_set.exists() or self.candidatemodule_set.exists()

    enrollment_label = models.CharField(max_length=100, blank=True, null=True)

    reg_number = models.CharField(max_length=100, unique=True, blank=True, null=True)


    # Disability fields
    disability = models.BooleanField(default=False, help_text="Check if candidate has a disability")
    nature_of_disability = models.ManyToManyField('NatureOfDisability', blank=True, help_text="Select nature(s) of disability if applicable")

    # models.py  (inside Candidate)
# --------------------------------
    def build_reg_number(self):
        """
        Build a registration number in the format
        N/YY/I/OC_CODE/###-CENTER_NO
        Serial is always unique for (center, intake, year, occupation, reg cat).
        """
        from django.db import transaction
        # Use 'U' for Uganda (robust), 'X' for any other country
        UGANDA_VALUES = {"uganda", "ugandan", "ug", "256"}
        nat_val = str(self.nationality).strip().lower()
        nat = 'U' if nat_val in UGANDA_VALUES else 'X'
        year     = str(self.entry_year)[-2:]    # last 2 digits
        intake   = self.intake.upper()          # “M” or “A”
        occ_code = self.occupation.code if self.occupation else "XXX"
        reg_type = self.registration_category[0].upper() if self.registration_category else "X"
        center_code = self.assessment_center.center_number if self.assessment_center else "NOCNTR"

        # Find max serial for this group
        with transaction.atomic():
            qs = Candidate.objects.filter(
                assessment_center=self.assessment_center, 
                intake=self.intake,
                entry_year=self.entry_year,
                occupation=self.occupation,
                registration_category=self.registration_category
            ).exclude(pk=self.pk)  # Exclude self if updating
            max_serial = 0
            for c in qs.only('reg_number'):
                try:
                    last_part = c.reg_number.split('/')[-1]
                    serial_part = last_part.split('-')[0]
                    serial_int = int(serial_part)
                    if serial_int > max_serial:
                        max_serial = serial_int
                except (ValueError, IndexError, AttributeError):
                    continue
            next_serial = max_serial + 1
            serial_str = str(next_serial).zfill(3)

        self.reg_number = f"{nat}/{year}/{intake}/{occ_code}/{reg_type}/{serial_str}-{center_code}"

    def save(self, *args, **kwargs):
            # regenerate if reg_number is empty
        if not self.reg_number:
            self.build_reg_number()
        super().save(*args, **kwargs)

        # --- Start of Image Resizing Logic ---
    def resize_passport_photo(self):
        if self.passport_photo and hasattr(self.passport_photo, 'file') and self.passport_photo.file and hasattr(self.passport_photo.file, 'size'):
            MAX_SIZE_KB = 500
            if self.passport_photo.file.size > MAX_SIZE_KB * 1024:
                try:
                    self.passport_photo.file.seek(0)
                    img = Image.open(self.passport_photo.file)
                    original_format = img.format if img.format else 'JPEG'

                    if img.mode in ('RGBA', 'P', 'LA'):
                        img = img.convert('RGB')

                    output_buffer = BytesIO()
                    max_pixels = 800 
                    if img.width > max_pixels or img.height > max_pixels:
                        try:
                            resampling_filter = Image.Resampling.LANCZOS
                        except AttributeError:
                            resampling_filter = Image.LANCZOS
                        img.thumbnail((max_pixels, max_pixels), resampling_filter)

                    if original_format.upper() == 'PNG':
                        img.save(output_buffer, format='PNG', optimize=True)
                        if output_buffer.tell() > MAX_SIZE_KB * 1024:
                            output_buffer.seek(0); output_buffer.truncate(0)
                            img.save(output_buffer, format='JPEG', quality=85)
                    else:
                        img.save(output_buffer, format='JPEG', quality=85)

                    current_buffer_check_img = Image.open(BytesIO(output_buffer.getvalue()))
                    if output_buffer.tell() > MAX_SIZE_KB * 1024 and current_buffer_check_img.format == 'JPEG':
                        quality = 80
                        while output_buffer.tell() > MAX_SIZE_KB * 1024 and quality >= 10:
                            output_buffer.seek(0); output_buffer.truncate(0)
                            img.save(output_buffer, format='JPEG', quality=quality)
                            quality -= 5
                    
                    if output_buffer.tell() <= MAX_SIZE_KB * 1024:
                        final_img_in_buffer = Image.open(BytesIO(output_buffer.getvalue()))
                        final_format = final_img_in_buffer.format
                        
                        original_filename = os.path.basename(self.passport_photo.name)
                        name_part, _ = os.path.splitext(original_filename)
                        
                        new_extension = '.jpg'
                        if final_format == 'JPEG': new_extension = '.jpg'
                        elif final_format == 'PNG': new_extension = '.png'
                            
                        new_filename = name_part + new_extension
                        self.passport_photo.file = ContentFile(output_buffer.getvalue(), name=new_filename)
                    else:
                        print(f"Warning: Image {self.passport_photo.name} could not be resized to under {MAX_SIZE_KB}KB. Current size: {output_buffer.tell()/1024:.2f}KB. Original will be saved.")
                        self.passport_photo.file.seek(0)

                except (IOError, FileNotFoundError, UnidentifiedImageError, ValueError, TypeError, AttributeError) as e:
                    print(f"Error resizing image {self.passport_photo.name if self.passport_photo and self.passport_photo.name else 'N/A'}: {e}")
                    if hasattr(self.passport_photo, 'file') and self.passport_photo.file and hasattr(self.passport_photo.file, 'seek') and callable(self.passport_photo.file.seek):
                        try:
                            self.passport_photo.file.seek(0)
                        except Exception as seek_e:
                            print(f"Error seeking file pointer for {self.passport_photo.name}: {seek_e}")
        # --- End of Image Resizing Logic ---

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reg_number} - {self.full_name}"

    class Meta:
        ordering = ['reg_number']

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

class CandidatePaper(models.Model):
    candidate = models.ForeignKey('Candidate', on_delete=models.CASCADE)
    module = models.ForeignKey('Module', on_delete=models.CASCADE)
    paper = models.ForeignKey('Paper', on_delete=models.CASCADE)
    level = models.ForeignKey('Level', on_delete=models.CASCADE)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.candidate.full_name} | {self.module.name} | {self.paper.name} | {self.level.name}"

class CenterRepresentative(models.Model):
    from django.contrib.auth import get_user_model
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    center = models.ForeignKey(AssessmentCenter, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=15)

    # Audit trail fields
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(get_user_model(), related_name='created_centerreps', null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(get_user_model(), related_name='updated_centerreps', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.name} ({self.center.center_number})"


class SupportStaff(models.Model):
    from django.contrib.auth import get_user_model
    DEPARTMENT_CHOICES = [
        ('Data', 'Data'),
        ('Accounts', 'Accounts'),
        ('Research', 'Research'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=15)
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES)

    # Audit trail fields
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(get_user_model(), related_name='created_supportstaff', null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(get_user_model(), related_name='updated_supportstaff', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.name} - {self.department}"

class Staff(models.Model):
    """Departmental staff with module access control (separate from SupportStaff)"""
    from django.contrib.auth import get_user_model
    
    DEPARTMENT_CHOICES = [
        ('Research', 'Research'),
        ('Data', 'Data'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=15)
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES)
    
    # Audit trail fields
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(get_user_model(), related_name='created_staff', null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(get_user_model(), related_name='updated_staff', null=True, blank=True, on_delete=models.SET_NULL)
    
    def __str__(self):
        return f"{self.name} - {self.department} Department"
    
    class Meta:
        verbose_name = "Staff Member"
        verbose_name_plural = "Staff Members"

