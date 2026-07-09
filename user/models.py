from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone


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
        ('awaiting_materials', 'Awaiting Materials'),
        ('awaiting_approval', 'Awaiting Approval'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    report_number = models.CharField(max_length=30, unique=True, blank=True, null=True)
    photo = models.ImageField(upload_to='reports/')
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    custom_category = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    priority = models.CharField(max_length=30, choices=PRIORITY_CHOICES, blank=True, null=True)
    assigned_personnel = models.CharField(max_length=100, blank=True, null=True)
    accomplished_at = models.DateTimeField(null=True, blank=True)
    in_progress_at = models.DateTimeField(null=True, blank=True)
    forwarded_to_procurement = models.BooleanField(default=False)
    cba_items = models.JSONField(null=True, blank=True)
    cba_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cnn_raw_prediction = models.CharField(max_length=100, blank=True, null=True)
    cnn_confidence = models.FloatField(blank=True, null=True)
    cnn_margin = models.FloatField(blank=True, null=True)
    flagged_for_review = models.BooleanField(default=False)

    @property
    def room_location(self):
        return self.location.split(",")[-1].strip()

    @property
    def reporter_name(self):
        if self.user:
            full_name = self.user.get_full_name()
            return full_name if full_name else self.user.username
        return '—'

    def save(self, *args, **kwargs):
        if self.report_number:
            return super().save(*args, **kwargs)

        with transaction.atomic():
            super().save(*args, **kwargs)

            report_date = timezone.localtime(self.submitted_at)
            sequence, _ = ReportSequence.objects.select_for_update().get_or_create(
                year=report_date.year,
                defaults={'last_number': 0},
            )
            sequence.last_number += 1
            sequence.save(update_fields=['last_number'])

            self.report_number = (
                f"{REPORT_PREFIX}-{report_date.year}-"
                f"{report_date.month:02d}-{sequence.last_number:06d}"
            )
            super().save(update_fields=['report_number'])

    def __str__(self):
        return f"{self.report_number or f'#{self.id:04d}'} - {self.get_category_display()} ({self.location})"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('faculty', 'Faculty'),
        ('staff', 'Staff'),
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
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    department = models.CharField(max_length=100, choices=DEPARTMENT_CHOICES, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - Profile"


class SurveyResponse(models.Model):
    report = models.OneToOneField(Report, on_delete=models.CASCADE, related_name='survey')
    rating = models.IntegerField()
    feedback = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Survey for Report {self.report.report_number or f'#{self.report.id:04d}'}"
