from .models import Notification


def get_unread_notifications_count(request):
    if not request.user.is_authenticated:
        return 0
    if not hasattr(request, "unread_notifications_count"):
        request.unread_notifications_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
    return request.unread_notifications_count


def notifications_context(request):
    return {"unread_notifications_count": get_unread_notifications_count(request)}
