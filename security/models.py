from django.db import models

class HoneypotHit(models.Model):
    TRIGGER_TYPE = [
        ('form_field', 'Hidden Form Field'),
        ('decoy_admin', 'Decoy Admin Page'),
        ('probe_path', 'Known Attack Path'),
        ('honey_token', 'Fake API/Object Access'),
    ]

    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPE)
    path = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    time_stamp = models.DateTimeField(auto_now_add=True)
    extra_info = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.get_trigger_type_display()} from {self.ip_address} at {self.time_stamp}"
    
    class Meta:
        ordering=['-time_stamp']
