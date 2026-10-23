from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Notification, UserProfile
from .realtime import schedule_notification_update

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if not created:
        return

    if instance.is_staff or instance.is_superuser:
        UserProfile.objects.get_or_create(user=instance, defaults={'role': 'admin'})


@receiver(post_save, sender=Notification)
def broadcast_notification_change(sender, instance, created, update_fields=None, **kwargs):
    if created or update_fields is None or 'is_read' in update_fields:
        schedule_notification_update(instance.user_id)


@receiver(post_delete, sender=Notification)
def broadcast_notification_deletion(sender, instance, **kwargs):
    schedule_notification_update(instance.user_id)
