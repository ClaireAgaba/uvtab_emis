from django.db import models
from django.contrib.auth.models import User

def format_title_case(text):
    """
    Convert text to title case, keeping small words lowercase except at the beginning.
    Example: "horticulture in agriculture" -> "Horticulture in Agriculture"
    """
    if not text:
        return text
    
    small_words = {'in', 'of', 'and', 'or', 'the', 'a', 'an', 'at', 'by', 'for', 'with', 'to', 'on'}
    words = text.strip().split()
    formatted_words = []
    
    for i, word in enumerate(words):
        # Always capitalize first word, otherwise check if it's a small word
        if i == 0 or word.lower() not in small_words:
            formatted_words.append(word.capitalize())
        else:
            formatted_words.append(word.lower())
    
    return ' '.join(formatted_words)
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

def validate_complaint_attachment(value):
    """Validate complaint attachment types (images, PDF, Word) up to 20MB"""
    if value:
        ext = os.path.splitext(value.name)[1].lower()
        valid_extensions = ['.png', '.jpg', '.jpeg', '.pdf', '.doc', '.docx']
        if ext not in valid_extensions:
            raise ValidationError(
                f'Unsupported file type {ext}. Allowed: PNG, JPG, JPEG, PDF, DOC, DOCX.'
            )
        if value.size > 20 * 1024 * 1024:
            raise ValidationError('File size must be less than 20MB')


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
    contact = models.CharField(max_length=20, blank=True, null=True, help_text="Phone number or contact information")
    has_branches = models.BooleanField(default=False, help_text="Check if this center has branches")

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


class AssessmentCenterBranch(models.Model):
    """Model for assessment center branches"""
    assessment_center = models.ForeignKey('AssessmentCenter', on_delete=models.CASCADE, related_name='branches')
    branch_code = models.CharField(max_length=100, unique=True, help_text="Unique branch code (e.g., UBT001-Leju)")
    district = models.ForeignKey('District', on_delete=models.CASCADE, help_text="District where the branch is located")
    village = models.ForeignKey('Village', on_delete=models.CASCADE, help_text="Village where the branch is located (must be unique)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.branch_code} - {self.assessment_center.center_name}"
    
    def get_full_name(self):
        """Get full branch name with center name"""
        return f"{self.assessment_center.center_name} - {self.branch_code}"
    
    class Meta:
        ordering = ['branch_code']
        verbose_name = "Assessment Center Branch"
        verbose_name_plural = "Assessment Center Branches"
        unique_together = [['assessment_center', 'village']]  # Each center can have only one branch per village


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

    def save(self, *args, **kwargs):
        """Override save to enforce title case formatting for name"""
        if self.name:
            self.name = format_title_case(self.name)
        super().save(*args, **kwargs)

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

    def save(self, *args, **kwargs):
        """Override save to enforce title case formatting for name"""
        if self.name:
            self.name = format_title_case(self.name)
        super().save(*args, **kwargs)

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

    def save(self, *args, **kwargs):
        """Override save to enforce formatting and ensure persistence"""
        # Normalize fields
        if self.name:
            self.name = format_title_case(self.name)
        if self.code:
            self.code = self.code.strip().upper()
        # For Worker's PAS/Informal categories, a module is typically required via forms,
        # but we do not enforce here to allow admin data corrections.
        super().save(*args, **kwargs)

    def __str__(self):
        parts = [self.code or "", self.name or ""]
        display = " - ".join([p for p in parts if p])
        # Add occupation/level context for clarity in admin dropdowns
        context = []
        if hasattr(self, 'occupation') and self.occupation_id:
            context.append(self.occupation.code)
        if hasattr(self, 'level') and self.level_id:
            context.append(self.level.name)
        if context:
            display += f" ({' / '.join(context)})"
        return display or f"Paper #{self.pk}"


class Sector(models.Model):
    name = models.CharField(max_length=255, unique=True, help_text="Name of the sector")
    description = models.TextField(blank=True, help_text="Description of the sector")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='created_sectors', null=True, blank=True, on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):
        """Override save to enforce title case formatting for name"""
        if self.name:
            self.name = format_title_case(self.name)
        super().save(*args, **kwargs)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, related_name='updated_sectors', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# =========================
# Complaints Module Models
# =========================
class HelpdeskTeam(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ComplaintCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Complaint Category'
        verbose_name_plural = 'Complaint Categories'

    def __str__(self):
        return self.name


def generate_ticket_no():
    """Generate next ticket number in format TKTyy#### e.g. TKT250001

    yy = current two-digit year
    #### = zero-padded sequential unique id (based on last complaint id + 1)
    """
    from django.utils import timezone
    yy = timezone.now().strftime('%y')
    last = Complaint.objects.order_by('-id').first()
    next_num = 1 if not last else last.id + 1
    return f"TKT{yy}{next_num:04d}"


class Complaint(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ]

    ticket_no = models.CharField(max_length=16, unique=True, editable=False, default='')
    category = models.ForeignKey('ComplaintCategory', on_delete=models.SET_NULL, null=True, blank=True)
    assessment_center = models.ForeignKey('AssessmentCenter', on_delete=models.SET_NULL, null=True, blank=True)
    registration_category = models.ForeignKey('RegistrationCategory', on_delete=models.SET_NULL, null=True, blank=True)
    occupation = models.ForeignKey('Occupation', on_delete=models.SET_NULL, null=True, blank=True)
    assessment_series = models.ForeignKey('AssessmentSeries', on_delete=models.SET_NULL, null=True, blank=True)
    helpdesk_team = models.ForeignKey('HelpdeskTeam', on_delete=models.SET_NULL, null=True, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    issue_description = models.TextField()
    team_response = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, related_name='created_complaints', on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, null=True, blank=True, related_name='updated_complaints', on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):
        if not self.ticket_no:
            # Assign on first save
            self.ticket_no = generate_ticket_no()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.ticket_no


def complaint_attachment_upload_path(instance, filename):
    return f"complaints/{instance.complaint.ticket_no}/{filename}"


class ComplaintAttachment(models.Model):
    complaint = models.ForeignKey('Complaint', related_name='attachments', on_delete=models.CASCADE)
    file = models.FileField(upload_to=complaint_attachment_upload_path, validators=[validate_complaint_attachment])
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def filename(self):
        return os.path.basename(self.file.name)

    def __str__(self):
        return f"{self.complaint.ticket_no} - {self.filename()}"


# Lightweight draft storage to allow users to save candidate creation progress
class CandidateDraft(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='candidate_drafts')
    assessment_center = models.ForeignKey('AssessmentCenter', on_delete=models.SET_NULL, null=True, blank=True)
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Draft #{self.pk} by {self.user}" 

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
    assessment_series = models.ForeignKey('AssessmentSeries', on_delete=models.SET_NULL, null=True, blank=True, help_text="Assessment series for this result")
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
        # Auto-set assessment series from candidate if not already set
        if not self.assessment_series and self.candidate and self.candidate.assessment_series:
            self.assessment_series = self.candidate.assessment_series
        
        # Handle grade and comment calculation
        if self.mark == -1:
            self.grade = 'Ms'
            self.comment = 'Missing'
        else:
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
        
        # Determine status (Normal, Retake, or Missing Paper)
        self._determine_status()
        
        # For modular results, ensure level is blank/null
        if self.result_type == 'modular':
            self.level = None
        super().save(*args, **kwargs)
    
    def _determine_status(self):
        """
        Determine status based on sitting history:
        - Normal: First sitting (always, regardless of mark)
        - Updated: Mark correction within same assessment series
        - Missing Paper: Subsequent sitting where candidate didn't sit (mark = -1)
        - Retake: Subsequent sitting in different assessment series where candidate sat (mark >= 0)
        """
        # Check if there are previous results for the same candidate, paper/module, and assessment type
        previous_results = Result.objects.filter(
            candidate=self.candidate,
            assessment_type=self.assessment_type
        )
        
        # Filter by paper or module depending on what this result has
        if self.paper:
            previous_results = previous_results.filter(paper=self.paper)
        elif self.module:
            previous_results = previous_results.filter(module=self.module)
        elif self.level:
            # For formal results without specific paper/module, filter by level
            previous_results = previous_results.filter(level=self.level)
        
        # Exclude the current result if it already exists (for updates)
        if self.pk:
            previous_results = previous_results.exclude(pk=self.pk)
        
        # Check if there are any previous results
        if previous_results.exists():
            # This is NOT the first sitting - check if same or different assessment date
            same_date_results = previous_results.filter(assessment_date=self.assessment_date)
            
            if same_date_results.exists():
                # Same assessment date = mark correction/update
                if self.mark == -1:
                    self.status = 'Missing Paper'
                else:
                    self.status = 'Updated'  # Mark correction within same assessment series
            else:
                # Different assessment date = actual retake
                if self.mark == -1:
                    self.status = 'Missing Paper'
                else:
                    self.status = 'Retake'  # Actual retake in different assessment series
        else:
            # No previous results found, this is the first sitting
            # Always "Normal" regardless of mark (even if -1)
            self.status = 'Normal'



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
    
    # Refugee status fields (only relevant for non-Ugandan nationals)
    is_refugee = models.BooleanField(default=False, help_text="Is this candidate a refugee?")
    refugee_number = models.CharField(max_length=50, blank=True, null=True, help_text="Refugee identification number (optional)")

    # Section 2 - Contact and Location
    contact = models.CharField(max_length=20, blank=True)
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True)
    village = models.ForeignKey(Village, on_delete=models.SET_NULL, null=True)

    # Section 3 - Assessment Info (without modules or levels yet)
    assessment_center = models.ForeignKey(AssessmentCenter, on_delete=models.SET_NULL, null=True)
    assessment_center_branch = models.ForeignKey('AssessmentCenterBranch', on_delete=models.SET_NULL, null=True, blank=True, help_text="Branch of the assessment center (if applicable)")
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
    start_date = models.DateField(null=True, blank=True, help_text="Training start date (optional for Worker's PAS/Informal)")
    finish_date = models.DateField(null=True, blank=True, help_text="Training finish date (optional for Worker's PAS/Informal)")
    assessment_date = models.DateField(help_text="Assessment date (mandatory for all registration categories)")

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
    # Candidate portal results visibility control
    block_portal_results = models.BooleanField(
        default=False,
        help_text="If true, this candidate will be blocked from viewing results in the candidate portal"
    )
    
    # Fees balance field
    fees_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Outstanding fees balance for this candidate"
    )
    # Modular enrollment choices and billing cache
    modular_module_count = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(1, '1 module'), (2, '2 modules')],
        help_text="For Modular candidates: center-chosen number of modules to bill (1 or 2)."
    )
    modular_billing_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cached modular billing amount at time of center selection; preserves billing when enrollments are cleared."
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
            # Decoupled modular billing: use stored center choice instead of live enrollments
            selected_count = self.modular_module_count or 0
            if selected_count in (1, 2):
                # If we have a cached amount, prefer it to preserve historical billing
                if self.modular_billing_amount is not None:
                    total_fees = self.modular_billing_amount
                else:
                    # Determine appropriate level for fee lookup
                    level = None
                    # 1) If any enrolled module exists, use its level
                    first_module = self.candidatemodule_set.first()
                    if first_module and first_module.module:
                        level = first_module.module.level
                    # 2) Else, try to fetch Level 1 (or first configured level) for the occupation
                    if level is None and self.occupation_id:
                        try:
                            from .models import OccupationLevel
                            occ_levels = OccupationLevel.objects.filter(occupation=self.occupation).select_related('level')
                            # Prefer a level whose name contains '1'
                            level1 = next((ol.level for ol in occ_levels if '1' in str(ol.level.name)), None)
                            level = level1 or (occ_levels.first().level if occ_levels.exists() else None)
                        except Exception:
                            level = None
                    if level is not None:
                        total_fees = level.get_fee_for_registration('Modular', selected_count)
                    # Cache the computed amount to modular_billing_amount so it persists
                    try:
                        from decimal import Decimal
                        self.modular_billing_amount = Decimal(total_fees)
                        # Avoid recursive save during calculate; caller update_fees_balance will save
                    except Exception:
                        pass
                    
        elif self.registration_category == 'Formal':
            # For formal candidates: calculate based on level enrolled
            enrolled_levels = self.candidatelevel_set.all()
            for candidate_level in enrolled_levels:
                level = candidate_level.level
                fee = level.get_fee_for_registration('Formal', 1)
                total_fees += fee
                
        elif self.registration_category in ['Informal', "Worker's PAS", 'Workers PAS', 'informal', "worker's pas"]:
            # For Worker's PAS candidates: calculate based on actual assessment attempts (results + enrollments)
            # This accounts for retakes where the same module may be attempted multiple times
            
            # Count unique assessment attempts (results) per assessment series
            from django.db.models import Count
            results_count = self.result_set.values('assessment_series', 'level', 'module').distinct().count()
            
            # Count enrolled modules that don't have results yet
            enrolled_modules = self.candidatemodule_set.count()
            
            # Total billable attempts = results + pending enrollments
            total_attempts = max(results_count, enrolled_modules)
            
            if total_attempts > 0:
                # Get fee per attempt from any enrolled module's level
                first_module = self.candidatemodule_set.first()
                if first_module and first_module.module:
                    level = first_module.module.level
                    total_fees = level.get_fee_for_registration('Informal', total_attempts)
                elif results_count > 0:
                    # If no enrollments but have results, use results to get level
                    first_result = self.result_set.first()
                    if first_result and first_result.level:
                        level = first_result.level
                        total_fees = level.get_fee_for_registration('Informal', total_attempts)
        
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
        CENTER_NO/N/YY/I/OC_CODE/REG_TYPE/SERIAL
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
                    # New format: CENTER_NO/N/YY/I/OC_CODE/REG_TYPE/SERIAL
                    # Old format: N/YY/I/OC_CODE/REG_TYPE/SERIAL-CENTER_NO
                    # Alternative old format: N/YY/I/OC_CODE/LEVEL/SERIAL-CENTER_NO
                    parts = c.reg_number.split('/')
                    if len(parts) >= 7:
                        # New format - serial is the last part
                        serial_int = int(parts[-1])
                    elif len(parts) >= 6 and '-' in parts[-1]:
                        # Old format (6 parts) - serial is before the dash in the last part
                        last_part = parts[-1]
                        serial_part = last_part.split('-')[0]
                        serial_int = int(serial_part)
                    elif len(parts) == 5 and '-' in parts[-1]:
                        # Alternative old format (5 parts) - serial is before the dash in the last part
                        last_part = parts[-1]
                        serial_part = last_part.split('-')[0]
                        serial_int = int(serial_part)
                    else:
                        continue
                    if serial_int > max_serial:
                        max_serial = serial_int
                except (ValueError, IndexError, AttributeError):
                    continue
            next_serial = max_serial + 1
            serial_str = str(next_serial).zfill(3)

        self.reg_number = f"{center_code}/{nat}/{year}/{intake}/{occ_code}/{reg_type}/{serial_str}"

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
    # Optional: when set, this representative is scoped to a specific branch of the center
    assessment_center_branch = models.ForeignKey('AssessmentCenterBranch', null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=15)

    # Audit trail fields
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(get_user_model(), related_name='created_centerreps', null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(get_user_model(), related_name='updated_centerreps', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.name} ({self.center.center_number})"

    def clean(self):
        # Ensure branch (if any) belongs to the same center
        if self.assessment_center_branch and self.assessment_center_branch.assessment_center_id != self.center_id:
            from django.core.exceptions import ValidationError
            raise ValidationError("Selected branch does not belong to the chosen assessment center.")


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
        ('IT', 'IT'),
        ('Admin', 'Admin'),
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


class PracticalAssessor(models.Model):
    """Practical Assessors for conducting practical assessments"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='practical_assessor_profile', null=True, blank=True)
    fullname = models.CharField(max_length=100, default="Unknown", help_text="Full name of the practical assessor")
    contact = models.CharField(max_length=15, null=True, blank=True, help_text="Phone number or contact information")
    email = models.EmailField(default="unknown@example.com", help_text="Email address")
    district = models.ForeignKey(District, on_delete=models.CASCADE, default=1, help_text="District where assessor is based")
    village = models.ForeignKey(Village, on_delete=models.CASCADE, default=1, help_text="Village where assessor is based")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['fullname']
        verbose_name = "Practical Assessor"
        verbose_name_plural = "Practical Assessors"
    
    def __str__(self):
        return f"{self.fullname} - {self.district.name}"


class PracticalAssessorAssignment(models.Model):
    """Assignment of Practical Assessors to Assessment Centers and Series"""
    
    assessor = models.ForeignKey(PracticalAssessor, on_delete=models.CASCADE, related_name='assignments')
    assessment_center = models.ForeignKey(AssessmentCenter, on_delete=models.CASCADE)
    assessment_series = models.ForeignKey('AssessmentSeries', on_delete=models.CASCADE)
    registration_category = models.ForeignKey('RegistrationCategory', on_delete=models.CASCADE, null=True, blank=True)
    occupation = models.ForeignKey('Occupation', on_delete=models.CASCADE, null=True, blank=True)
    level = models.ForeignKey('Level', on_delete=models.CASCADE, null=True, blank=True)
    module = models.ForeignKey('Module', on_delete=models.CASCADE, null=True, blank=True)
    assigned_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='practical_assessor_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['assessor', 'assessment_center', 'assessment_series', 'registration_category', 'occupation', 'level', 'module']
        ordering = ['-assigned_at']
        verbose_name = "Practical Assessor Assignment"
        verbose_name_plural = "Practical Assessor Assignments"

    def __str__(self):
        level_module = ""
        if self.level:
            level_module = f" - {self.level.name}"
        elif self.module:
            level_module = f" - {self.module.name}"
        
        occupation_name = self.occupation.name if self.occupation else "All Occupations"
        return f"{self.assessor.fullname} - {self.assessment_center.center_name} - {occupation_name}{level_module}"
    
    def get_marksheet_status(self):
        """Check if marksheet exists and its status"""
        if not self.occupation or not self.registration_category:
            return 'not_configured'
            
        try:
            marksheet = PracticalMarksheet.objects.get(
                assessment_center=self.assessment_center,
                assessment_series=self.assessment_series,
                registration_category=self.registration_category,
                occupation=self.occupation,
                assessor=self.assessor.user
            )
            return marksheet.status
        except PracticalMarksheet.DoesNotExist:
            return 'not_generated'
    
    def get_marksheet_id(self):
        """Get the marksheet ID for this assignment if it exists"""
        if not self.occupation or not self.registration_category:
            return None
            
        try:
            marksheet = PracticalMarksheet.objects.get(
                assessment_center=self.assessment_center,
                assessment_series=self.assessment_series,
                registration_category=self.registration_category,
                occupation=self.occupation,
                assessor=self.assessor.user
            )
            return marksheet.id
        except PracticalMarksheet.DoesNotExist:
            return None


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


# =========================
# Practical Assessment Module Models
# =========================

def practical_marksheet_upload_path(instance, filename):
    """Generate upload path for practical marksheet documents"""
    return f'practical_marksheets/{instance.assessment_series.name}/{instance.assessment_center.center_number}/{filename}'


class PracticalMarksheet(models.Model):
    """
    Model for storing practical assessment marksheets
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    # Basic Information
    assessment_center = models.ForeignKey('AssessmentCenter', on_delete=models.CASCADE, help_text="Assessment center where practical assessment was conducted")
    assessment_series = models.ForeignKey('AssessmentSeries', on_delete=models.CASCADE, help_text="Assessment series for this marksheet")
    registration_category = models.ForeignKey('RegistrationCategory', on_delete=models.CASCADE, help_text="Registration category (Formal, Modular, Worker's PAS)")
    occupation = models.ForeignKey('Occupation', on_delete=models.CASCADE, help_text="Occupation being assessed")
    
    # Assessor Information
    assessor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='practical_marksheets', help_text="Staff member who created this marksheet")
    
    # Document and Status
    marksheet_document = models.FileField(
        upload_to=practical_marksheet_upload_path, 
        blank=True, 
        null=True,
        help_text="Generated marksheet document (PDF)"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Audit Trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True, help_text="When the marksheet was submitted")
    
    class Meta:
        verbose_name = 'Practical Marksheet'
        verbose_name_plural = 'Practical Marksheets'
        ordering = ['-created_at']
        unique_together = ['assessment_center', 'assessment_series', 'registration_category', 'occupation', 'assessor']
    
    def __str__(self):
        return f"{self.assessment_center.center_name} - {self.occupation.name} ({self.registration_category.name}) - {self.assessment_series.name}"
    
    def get_candidate_count(self):
        """Get the number of candidates in this marksheet"""
        return self.practical_marks.count()
    
    def save(self, *args, **kwargs):
        # Set submitted_at when status changes to submitted
        if self.status == 'submitted' and not self.submitted_at:
            self.submitted_at = timezone.now()
        super().save(*args, **kwargs)


class PracticalMark(models.Model):
    """
    Model for storing individual candidate marks in practical assessments
    """
    marksheet = models.ForeignKey('PracticalMarksheet', on_delete=models.CASCADE, related_name='practical_marks')
    candidate = models.ForeignKey('Candidate', on_delete=models.CASCADE, help_text="Candidate being assessed")
    
    # Marks (using DecimalField to allow for decimal marks like 85.5)
    mark = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Practical assessment mark (0-100)"
    )
    
    # Additional fields for tracking
    grade = models.CharField(max_length=5, blank=True, help_text="Calculated grade based on mark")
    comments = models.TextField(blank=True, help_text="Optional comments about the candidate's performance")
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Practical Mark'
        verbose_name_plural = 'Practical Marks'
        unique_together = ['marksheet', 'candidate']
        ordering = ['candidate__full_name']
    
    def __str__(self):
        mark_display = f"{self.mark}" if self.mark is not None else "No Mark"
        return f"{self.candidate.full_name} - {mark_display}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate grade based on mark
        if self.mark is not None:
            self.grade = self.calculate_grade()
        super().save(*args, **kwargs)
    
    def calculate_grade(self):
        """Calculate grade based on the mark using the Grade model"""
        if self.mark is None:
            return ""
        
        try:
            # Get the appropriate grade for practical assessments
            grade_obj = Grade.objects.filter(
                type='practical',
                min_score__lte=self.mark,
                max_score__gte=self.mark
            ).first()
            
            if grade_obj:
                return grade_obj.grade
            else:
                # Fallback grading system if no Grade objects exist
                if self.mark >= 80:
                    return "A"
                elif self.mark >= 70:
                    return "B"
                elif self.mark >= 60:
                    return "C"
                elif self.mark >= 50:
                    return "D"
                else:
                    return "F"
        except:
            return ""


class CandidateChangeLog(models.Model):
    """Audit trail of candidate-related actions."""
    ACTION_CHOICES = [
        ('create', 'Create Candidate'),
        ('edit_bio', 'Edit Bio Data'),
        ('enroll', 'Enroll'),
        ('clear_enrollment', 'Clear Enrollment'),
        ('clear_enrollment_results', 'Clear Enrollment and Results'),
        ('add_result', 'Add Result'),
        ('edit_result', 'Edit Result'),
        ('change_center', 'Change Center'),
        ('change_occupation', 'Change Occupation'),
        ('change_reg_category', 'Change Registration Category'),
        ('regenerate_regno', 'Regenerate Reg Number'),
        ('portal_block_results', 'Portal: Block Results View'),
        ('portal_unblock_results', 'Portal: Unblock Results View'),
        ('other', 'Other'),
    ]

    candidate = models.ForeignKey('Candidate', on_delete=models.CASCADE, related_name='change_logs')
    action = models.CharField(max_length=64, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    request_path = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Candidate Change Log'
        verbose_name_plural = 'Candidate Change Logs'

    def __str__(self):
        user = self.performed_by.username if self.performed_by else 'system'
        return f"{self.candidate.reg_number or self.candidate.id} - {self.get_action_display()} by {user} @ {self.created_at:%Y-%m-%d %H:%M}"
