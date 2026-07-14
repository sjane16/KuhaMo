from django.contrib import admin
from .models import HoneypotHit

@admin.register(HoneypotHit)
class HoneypotHitAdmin(admin.ModelAdmin):
    list_display = ('trigger_type', 'ip_address', 'path', 'time_stamp')
    list_filter = ('trigger_type',)
    search_fields = ('ip_address', 'path', 'user_agent')
    ordering = ('-time_stamp',)
    readonly_fields = ('trigger_type', 'path', 'ip_address', 'user_agent', 'time_stamp', 'extra_info')

    def has_add_permission(self, request):
        return False 
