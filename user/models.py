from django.db import models, transaction
from django.db.models import F
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from cloudinary.models import CloudinaryField
from .validators import phone_validator
from simple_history.models import HistoricalRecords
from .constants import PRIORITY_SLA_HOURS


REPORT_PREFIX = "MED-JO"


class ReportSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.year} - {self.last_number}"


class Report(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    CATEGORY_CHOICES = [
        ('electrical', 'Electrical'),
        ('plumbing', 'Plumbing'),
        ('refrigeration_acu', 'Refrigeration / ACUs'),
        ('carpentry_masonry', 'Carpentry / Masonry'),
        ('painting', 'Painting'),
        ('vehicle_checkup', 'Vehicle Check-up'),
        ('others', 'Others'),
    ]

    PRIORITY_CHOICES = [
    ('critical', 'Critical / Urgent'),
    ('high', 'High Priority'),
    ('standard', 'Standard'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    job_order_id = models.CharField(max_length=30, unique=True, blank=True, null=True)
    photo = CloudinaryField('Photo', folder='reports/', null=True, blank=True)
    completion_photo = CloudinaryField('Completion Photo', folder='reports/completion/', null=True, blank=True)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    custom_category = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    priority = models.CharField(max_length=30, choices=PRIORITY_CHOICES, blank=True, null=True)
    assigned_personnel = models.CharField(max_length=255, blank=True, null=True)
    assigned_personnel_data = models.JSONField(default=list, blank=True)
    accomplished_at = models.DateTimeField(null=True, blank=True)
    in_progress_at = models.DateTimeField(null=True, blank=True)
    pending_awaiting_personnel = models.BooleanField(default=False)
    pending_awaiting_personnel_at = models.DateTimeField(null=True, blank=True)
    pending_awaiting_materials = models.BooleanField(default=False)
    pending_awaiting_materials_at = models.DateTimeField(null=True, blank=True)
    pending_awaiting_approval = models.BooleanField(default=False)
    pending_awaiting_approval_at = models.DateTimeField(null=True, blank=True)
    cnn_raw_prediction = models.CharField(max_length=100, blank=True, null=True)
    cnn_confidence = models.FloatField(blank=True, null=True)
    cnn_margin = models.FloatField(blank=True, null=True)
    flagged_for_review = models.BooleanField(default=False)
    findings = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    materials_required = models.JSONField(default=list, blank=True)

    @property
    def materials_rows(self):
        """Laging 4 na row (qty/unit/description) para sa Job Order PDF."""
        rows = []
        for item in (self.materials_required or [])[:4]:
            rows.append({
                'qty': (item.get('qty') or '').strip(),
                'unit': (item.get('unit') or '').strip(),
                'description': (item.get('description') or '').strip(),
            })
        while len(rows) < 4:
            rows.append({'qty': '', 'unit': '', 'description': ''})
        return rows

    @property
    def room_location(self):
        return self.location.split(",")[-1].strip()

    @property
    def reporter_name(self):
        if self.user:
            full_name = self.user.get_full_name()
            return full_name if full_name else self.user.username
        return '—'

    @property
    def assigned_personnel_summary(self):
        if self.assigned_personnel_data:
            return ", ".join(
                item.get('name')
                for item in self.assigned_personnel_data
                if item.get('name')
            )

        if self.assigned_personnel:
            import re
            return re.sub(
                r'\s*\(QTT\s+\d+\)',
                '',
                self.assigned_personnel
            )

        return None

    @property
    def expected_resolution_hours(self):
        """
        Expected resolution time based on Maintenance & Engineering Division policy.

        Critical / Urgent:
            2–3 hours(system uses 3 hours)

        High Priority:
            Within the same day

        Standard:
            Typically resolved within 2–3 days(system uses 72 hours)
        """

        return PRIORITY_SLA_HOURS.get(self.priority)

    @property
    def expected_resolution_at(self):
        if not self.in_progress_at:
            return None
        return self.in_progress_at + timedelta(hours=self.expected_resolution_hours)

    @property
    def actual_resolution_hours(self):
        if not self.in_progress_at or not self.accomplished_at:
            return None
        seconds = (self.accomplished_at - self.in_progress_at).total_seconds()
        return round(seconds / 3600, 1)

    @property
    def met_expected_resolution(self):
        expected_at = self.expected_resolution_at
        if not expected_at or not self.accomplished_at:
            return False
        return self.accomplished_at <= expected_at

    @property
    def closed_at(self):
        try:
            return self.survey.submitted_at
        except SurveyResponse.DoesNotExist:
            return self.accomplished_at

    def save(self, *args, **kwargs):
        if self.job_order_id:
            return super().save(*args, **kwargs)

        with transaction.atomic():
            sequence, _ = ReportSequence.objects.select_for_update().get_or_create(
                year=timezone.localtime(self.submitted_at).year,
                defaults={'last_number': 0},
            )
            ReportSequence.objects.filter(pk=sequence.pk).update(
                last_number=F('last_number') + 1
            )
            sequence.refresh_from_db()

            report_date = timezone.localtime(self.submitted_at)
            self.job_order_id = (
                f"{REPORT_PREFIX}-{report_date.year}-"
                f"{report_date.month:02d}-{sequence.last_number:06d}"
            )
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.job_order_id or f'#{self.id:04d}'} - {self.get_category_display()} ({self.location})"

    history = HistoricalRecords()


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('faculty', 'Faculty'),
        ('staff', 'Staff'),
        ('admin', 'Admin'),
    ]

    DEPARTMENT_CHOICES = [
        ('CCS', 'College of Computing Studies'),
        ('CHS', 'College of Health Sciences'),
        ('CCJ', 'College of Criminal Justice'),
        ('CED', 'College of Education'),
        ('NSTP', 'National Service Training Program'),
        ('GenED', 'General Education'),
        ('CBPM', 'College of Business and Public Management'),
        ('COL', 'College of Law'),
        ('CAS', 'College of Arts and Sciences'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    department = models.CharField(max_length=100, choices=DEPARTMENT_CHOICES, blank=True)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)

    otp = models.CharField(max_length=6, blank=True, default='')
    otp_created_at = models.DateTimeField(null=True, blank=True)
    otp_attempts = models.PositiveSmallIntegerField(default=0, db_default=0)
    # Bumped on every real password change; trusted-device cookies carry it,
    # so a password change logs out every trusted device (see accounts/views.py)
    credentials_version = models.PositiveIntegerField(default=0, db_default=0)

    def __str__(self):
        return f"{self.user.username} - Profile"

    history = HistoricalRecords()


class SurveyResponse(models.Model):
    report = models.OneToOneField(Report, on_delete=models.CASCADE, related_name='survey')
    quality = models.IntegerField(null=True, blank=True)
    quantity = models.IntegerField(null=True, blank=True)
    timeliness = models.IntegerField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Survey for Report {self.report.job_order_id or f'#{self.report.id:04d}'}"

    history = HistoricalRecords()


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    status_snapshot = models.CharField(max_length=20, choices=Report.STATUS_CHOICES, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.message[:40]}"

    @property
    def time_ago(self):
        diff = timezone.now() - self.created_at
        seconds = diff.total_seconds()

        if seconds < 60:
            return "Just now"

        minutes = seconds // 60
        if minutes < 60:
            return f"{int(minutes)}m"

        hours = minutes // 60
        if hours < 24:
            return f"{int(hours)}h"

        days = hours // 24
        return f"{int(days)}d"

    @property
    def is_recent(self):
        """True if this notification was created less than 24 hours ago."""
        return (timezone.now() - self.created_at) < timedelta(hours=24)

def invalidate_trusted_devices(user):
    """Call after a real password change so every trusted device needs MFA again."""
    UserProfile.objects.filter(user=user).update(credentials_version=models.F('credentials_version') + 1)


class Passkey(models.Model):
    """A WebAuthn passkey a user can sign in with (fingerprint, face or screen lock)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='passkeys')
    name = models.CharField(max_length=60)
    # base64url-encoded credential ID, as sent by the browser
    credential_id = models.CharField(max_length=512, unique=True)
    public_key = models.BinaryField()
    sign_count = models.PositiveBigIntegerField(default=0)
    transports = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.name}"
