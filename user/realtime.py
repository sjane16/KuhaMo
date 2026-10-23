from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction


def notification_group_name(user_id):
    return f'notifications.{user_id}'


def send_notification_update(user_id):
    channel_layer = get_channel_layer()
    if channel_layer is not None:
        async_to_sync(channel_layer.group_send)(
            notification_group_name(user_id),
            {'type': 'notifications.changed'},
        )


def schedule_notification_update(user_id):
    transaction.on_commit(
        lambda: send_notification_update(user_id),
        robust=True,
    )
