from django.db import models
from django.contrib.auth.models import User
from django_countries.fields import CountryField
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime
import os
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from django.core.files.base import ContentFile
from django.db import transaction
from django.contrib.auth import get_user_model

def validate_document_file(value):
    """Validate that uploaded file is PNG, JPG, or PDF"""
    if value:
        ext = os.path.splitext(value.name)[1].lower()
        valid_extensions = ['.png', '.jpg', '.jpeg', '.pdf']
        if ext not in valid_extensions:
            raise ValidationError(
                f'File must be PNG, JPG, or PDF format. Got: {ext}'
            )
        # Check file size (max 10MB)
        if value.size > 10 * 1024 * 1024:
            raise ValidationError(
                'File size must be less than 10MB'
            )


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
    village = models.ForeignKey('Village', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.center_number} - {self.center_name}"

    def get_total_fees_balance(self):
        """
        Calculate the total fees balance for all enrolled candidates in this center
        """
        from decimal import Decimal
        total_balance = Decimal('0.00')
        
        # Get all candidates registered at this center who have enrollment
        candidates = self.candidate_set.filter(fees_balance__gt=0)
        
        for candidate in candidates:
            total_balance += candidate.fees_balance
            
        return total_balance
    
    def get_formatted_total_fees_balance(self):
        """
        Get the total fees balance formatted with commas (e.g., 1,250,000.00)
        """
        total_balance = self.get_total_fees_balance()
        return f"{total_balance:,.2f}"
    
    def get_enrolled_candidates_count(self):
        """
        Get the count of candidates who are enrolled and have fees balance > 0
        """
        return self.candidate_set.filter(fees_balance__gt=0).count()

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
    sector = models.ForeignKey('Sector', null=True, blank=True, on_delete=models.CASCADE, help_text="Industry sector this occupation belongs to")
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
    
    # Fees fields for different registration types
    formal_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Fee for Formal registration (varies by level)"
    )
    workers_pas_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Fee for Worker's PAS registration (flat rate across levels)"
    )
    workers_pas_module_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Fee per module for Worker's PAS registration (multiplied by modules enrolled)"
    )
    modular_fee_single = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Fee for Modular registration with 1 module"
    )
    modular_fee_double = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Fee for Modular registration with 2 modules"
    )

    def get_fee_for_registration(self, registration_category, module_count=1):
        """
        Get the appropriate fee based on registration category and module count
        """
        if registration_category == 'Formal':
            return self.formal_fee
        elif registration_category == 'Informal':  # Informal = Worker's PAS
            if self.workers_pas_module_fee > 0:
                return self.workers_pas_module_fee * module_count
            else:
                return self.workers_pas_fee
        elif registration_category == 'Modular':
            if module_count >= 2:
                return self.modular_fee_double
            else:
                return self.modular_fee_single
        return 0.00

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


class Sector(models.Model):
    name = models.CharField(max_length=255, unique=True, help_text="Name of the sector")
    description = models.TextField(blank=True, help_text="Description of the sector")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='created_sectors', null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, related_name='updated_sectors', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


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
    assessment_series = models.ForeignKey('AssessmentSeries', on_delete=models.SET_NULL, null=True, blank=True, help_text="Assessment series this candidate is enrolled in")
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
    disability_specification = models.TextField(
        blank=True, 
        null=True, 
        help_text="Please specify details about the disability and any assistance needed during exams"
    )

    # Account status field
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='Active',
        help_text="Account status - Active users can login, Inactive users cannot login"
    )
    
    # Fees balance field
    fees_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Outstanding fees balance for this candidate"
    )
    
    # Document attachments (optional)
    identification_document = models.FileField(
        upload_to='candidate_documents/identification/',
        blank=True,
        null=True,
        validators=[validate_document_file],
        help_text="Attach identification document (National ID, Birth Certificate) - PNG, JPG, or PDF (max 10MB)"
    )
    qualification_document = models.FileField(
        upload_to='candidate_documents/qualifications/',
        blank=True,
        null=True,
        validators=[validate_document_file],
        help_text="Attach relevant qualification documents (for Full Occupation candidates) - PNG, JPG, or PDF (max 10MB)"
    )
    
    # Verification fields
    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('declined', 'Declined'),
    ]
    verification_status = models.CharField(
        max_length=10,
        choices=VERIFICATION_STATUS_CHOICES,
        default='pending',
        help_text="Quality assurance verification status"
    )
    verification_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Date when verification status was last changed"
    )
    verified_by = models.ForeignKey(
        get_user_model(),
        related_name='verified_candidates',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Admin/staff user who verified or declined this candidate"
    )
    decline_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for declining candidate (required when status is declined)"
    )

    def calculate_fees_balance(self):
        """
        Calculate the fees balance for this candidate based on their enrollment
        """
        from decimal import Decimal
        total_fees = Decimal('0.00')
        
        if self.registration_category == 'Modular':
            # For modular candidates: calculate based on modules enrolled (no level enrollment)
            module_count = self.candidatemodule_set.count()
            if module_count > 0:
                # Get the level from the first module (all modules should be from same level)
                first_module = self.candidatemodule_set.first()
                if first_module and first_module.module:
                    level = first_module.module.level
                    total_fees = level.get_fee_for_registration('Modular', module_count)
                    
        elif self.registration_category == 'Formal':
            # For formal candidates: calculate based on level enrolled
            enrolled_levels = self.candidatelevel_set.all()
            for candidate_level in enrolled_levels:
                level = candidate_level.level
                fee = level.get_fee_for_registration('Formal', 1)
                total_fees += fee
                
        elif self.registration_category in ['Informal', "Worker's PAS", 'Workers PAS', 'informal', "worker's pas"]:
            # For Worker's PAS candidates: calculate based on modules enrolled (charged per module)
            module_count = self.candidatemodule_set.count()
            if module_count > 0:
                # Get the level from the first module
                first_module = self.candidatemodule_set.first()
                if first_module and first_module.module:
                    level = first_module.module.level
                    total_fees = level.get_fee_for_registration('Informal', module_count)
        
        return total_fees

    def update_fees_balance(self):
        """
        Update the fees_balance field with the calculated balance
        """
        self.fees_balance = self.calculate_fees_balance()
        self.save(update_fields=['fees_balance'])
    
    def get_formatted_fees_balance(self):
        """
        Get the fees balance formatted with commas (e.g., 75,000.00)
        """
        return f"{self.fees_balance:,.2f}"

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
    
    # Modular enrollment helper methods
    def get_enrolled_modules(self):
        """Get all modules this candidate is enrolled in"""
        return self.candidatemodule_set.select_related('module').all()
    
    def get_available_modules_for_enrollment(self):
        """Get modules available for enrollment (not already enrolled)"""
        if not self.occupation:
            return Module.objects.none()
        
        # Get all modules for this occupation
        all_modules = Module.objects.filter(occupation=self.occupation)
        
        # Get already enrolled module IDs
        enrolled_module_ids = self.candidatemodule_set.values_list('module_id', flat=True)
        
        # Return modules not yet enrolled
        return all_modules.exclude(id__in=enrolled_module_ids)
    
    def get_completed_modules(self):
        """Get modules that have been completed (passed or failed)"""
        return self.candidatemodule_set.filter(
            status__in=['completed', 'failed']
        ).select_related('module')
    
    def get_passed_modules(self):
        """Get modules that have been passed based on actual results"""
        from .models import Result
        
        # Get all enrolled modules
        enrolled_modules = self.candidatemodule_set.all().select_related('module')
        passed_modules = []
        
        for candidate_module in enrolled_modules:
            # Check if there are results for this module
            module_results = Result.objects.filter(
                candidate=self,
                module=candidate_module.module
            )
            
            if module_results.exists():
                # Check if any result meets the passing criteria
                # Assuming pass mark is 50 or could be defined per module
                pass_mark = getattr(candidate_module, 'pass_mark', 50)
                
                for result in module_results:
                    try:
                        mark = float(result.mark) if result.mark else 0
                        if mark >= pass_mark:
                            passed_modules.append(candidate_module)
                            break  # Found a passing mark, no need to check other results
                    except (ValueError, TypeError):
                        continue
        
        # Return a queryset-like object for compatibility
        passed_module_ids = [cm.id for cm in passed_modules]
        return self.candidatemodule_set.filter(id__in=passed_module_ids)
    
    def get_total_modules_for_occupation(self):
        """Get total number of modules required for this candidate's occupation"""
        if not self.occupation:
            return 0
        return Module.objects.filter(occupation=self.occupation).count()
    
    def get_modular_completion_status(self):
        """Get completion status for modular candidates"""
        if self.registration_category != 'Modular':
            return None
        
        total_modules = self.get_total_modules_for_occupation()
        passed_modules = self.get_passed_modules().count()
        
        return {
            'total_modules': total_modules,
            'passed_modules': passed_modules,
            'remaining_modules': total_modules - passed_modules,
            'is_qualified': passed_modules >= total_modules,
            'completion_percentage': (passed_modules / total_modules * 100) if total_modules > 0 else 0
        }
    
    def is_qualified_for_level_1(self):
        """Check if modular candidate is qualified for Level 1"""
        if self.registration_category != 'Modular':
            return False
        
        status = self.get_modular_completion_status()
        return status and status['is_qualified']
    
    def can_enroll_in_more_modules(self):
        """Check if modular candidate can enroll in more modules"""
        if self.registration_category != 'Modular':
            return False
        
        # Check if there are available modules
        available_modules = self.get_available_modules_for_enrollment()
        if not available_modules.exists():
            return False
        
        # Check current active enrollments (not completed)
        active_enrollments = self.candidatemodule_set.exclude(
            status__in=['completed', 'failed']
        ).count()
        
        # Can enroll if less than 2 active enrollments
        return active_enrollments < 2

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
    
    # Enrollment tracking
    enrolled_at = models.DateTimeField(auto_now_add=True)
    assessment_series = models.ForeignKey('AssessmentSeries', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Marks and completion tracking
    marks = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Marks obtained in this module (0-100)"
    )
    
    STATUS_CHOICES = [
        ('enrolled', 'Enrolled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default='enrolled',
        help_text="Current status of this module enrollment"
    )
    
    # Completion tracking
    completed_at = models.DateTimeField(null=True, blank=True)
    pass_mark = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=50.00,
        help_text="Minimum marks required to pass this module"
    )
    
    class Meta:
        unique_together = ['candidate', 'module']
        ordering = ['enrolled_at']
    
    def __str__(self):
        return f"{self.candidate.full_name} - {self.module.name} ({self.get_status_display()})"
    
    def is_passed(self):
        """Check if candidate has passed this module"""
        return self.marks is not None and self.marks >= self.pass_mark
    
    def is_completed(self):
        """Check if this module is completed (passed or failed)"""
        return self.status in ['completed', 'failed'] or (self.marks is not None)
    
    def save(self, *args, **kwargs):
        # Auto-update status based on marks
        if self.marks is not None:
            if self.marks >= self.pass_mark:
                self.status = 'completed'
                if not self.completed_at:
                    from django.utils import timezone
                    self.completed_at = timezone.now()
            else:
                self.status = 'failed'
                if not self.completed_at:
                    from django.utils import timezone
                    self.completed_at = timezone.now()
        
        super().save(*args, **kwargs)

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
    
    # Account status field
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=15)
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES)
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='Active',
        help_text="Account status - Active users can login, Inactive users cannot login"
    )

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
    
    # Account status field
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=15)
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES)
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='Active',
        help_text="Account status - Active users can login, Inactive users cannot login"
    )
    
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


class AssessmentSeries(models.Model):
    name = models.CharField(max_length=200, unique=True, help_text="Name of the assessment series")
    start_date = models.DateField(help_text="Start date of the assessment series")
    end_date = models.DateField(help_text="End date of the assessment series")
    date_of_release = models.DateField(help_text="Date when results will be released")
    is_current = models.BooleanField(default=False, help_text="Mark as current running series")
    results_released = models.BooleanField(default=False, help_text="Toggle to release results to candidates and assessment centers")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({'Current' if self.is_current else 'Inactive'})"
    
    def save(self, *args, **kwargs):
        # Ensure only one series can be current at a time
        if self.is_current:
            AssessmentSeries.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Assessment Series"
        verbose_name_plural = "Assessment Series"
        ordering = ['-is_current', '-start_date']

class CenterSeriesPayment(models.Model):
    """
    Track payment status for each center-series combination
    This allows us to mark specific center-series combinations as paid
    without affecting other series for the same center
    """
    assessment_center = models.ForeignKey('AssessmentCenter', on_delete=models.CASCADE)
    assessment_series = models.ForeignKey('AssessmentSeries', on_delete=models.CASCADE, null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_date = models.DateTimeField(auto_now_add=True)
    paid_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        unique_together = ('assessment_center', 'assessment_series')
        verbose_name = 'Center Series Payment'
        verbose_name_plural = 'Center Series Payments'
    
    def __str__(self):
        series_name = self.assessment_series.name if self.assessment_series else 'No series'
        return f"{self.assessment_center.center_name} - {series_name}: {self.amount_paid}"
