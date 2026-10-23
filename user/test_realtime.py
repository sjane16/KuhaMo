from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser, User
from django.test import TransactionTestCase, override_settings

from .consumers import NotificationConsumer
from .models import Notification


@override_settings(CHANNEL_LAYERS={
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
})
class NotificationWebSocketTests(TransactionTestCase):
    async def test_notification_refresh_is_private_to_its_user(self):
        user = await sync_to_async(User.objects.create_user)(username='notif-user')
        other = await sync_to_async(User.objects.create_user)(username='other-user')

        user_socket = WebsocketCommunicator(NotificationConsumer.as_asgi(), '/ws/notifications/')
        user_socket.scope['user'] = user
        other_socket = WebsocketCommunicator(NotificationConsumer.as_asgi(), '/ws/notifications/')
        other_socket.scope['user'] = other

        self.assertTrue((await user_socket.connect())[0])
        self.assertTrue((await other_socket.connect())[0])

        await sync_to_async(Notification.objects.create)(
            user=user,
            account_event=Notification.ADMIN_ACCESS_GRANTED,
            message='Admin access granted',
        )

        self.assertEqual(
            await user_socket.receive_json_from(timeout=1),
            {'type': 'notifications.changed'},
        )
        self.assertTrue(await other_socket.receive_nothing(timeout=0.1))

        await user_socket.disconnect()
        await other_socket.disconnect()

    async def test_anonymous_socket_is_rejected(self):
        socket = WebsocketCommunicator(NotificationConsumer.as_asgi(), '/ws/notifications/')
        socket.scope['user'] = AnonymousUser()

        connected, _ = await socket.connect()

        self.assertFalse(connected)
