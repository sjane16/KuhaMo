from django.contrib import admin
from django.contrib.auth.models import User
from .models import Report
from .models import UserProfile

# Inline class - makes UserProfile appear inside the User page
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'

# Unregister the default User admin and re-register with our inline
admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(admin.ModelAdmin):
    inlines = [UserProfileInline]
    list_display = ('username', 'first_name', 'last_name', 'email')
    search_fields = ('username', 'first_name', 'last_name', 'email')

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'reporter_name', 'category', 'location', 'status', 'submitted_at')
    list_filter = ('status', 'category')
    raw_id_fields = ('user',)