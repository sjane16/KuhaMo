from django.db import models
from django.contrib.auth.models import User


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
    photo = models.ImageField(upload_to='reports/')
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
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

    @property
    def reporter_name(self):
        if self.user:
            full_name = self.user.get_full_name()
            return full_name if full_name else self.user.username
        return '—'

    def __str__(self):
        return f"#{self.id:04d} - {self.get_category_display()} ({self.location})"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('faculty', 'Faculty'),
        ('staff', 'Staff'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    department = models.CharField(max_length=100, blank=True)
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
        return f"Survey for Report #{self.report.id:04d}"