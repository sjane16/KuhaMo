from django.db import models

class Report(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
    ]

    CATEGORY_CHOICES = [
        ('av_it_equipment_failures', 'AV/IT Equipment Failures'),
        ('broken_furniture', 'Broken Furniture'),
        ('electrical_hazards', 'Electrical Hazards'),
        ('heating_or_cooling_system_problems', 'Heating or Cooling System Problems'),
        ('non_functional_fixtures', 'Non-functional Fixtures'),
    ]

    photo = models.ImageField(upload_to='reports/')
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    location = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"#{self.id:04d} - {self.get_category_display()} ({self.location})"