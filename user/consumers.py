import asyncio

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .realtime import notification_group_name


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated or not user.is_active:
            await self.close(code=4401)
            return

        self.group_name = notification_group_name(user.pk)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        session = self.scope.get('session')
        if session is not None:
            self.session_expiry_task = asyncio.create_task(self.close_when_session_expires(session))

    async def disconnect(self, close_code):
        expiry_task = getattr(self, 'session_expiry_task', None)
        if expiry_task is not None:
            expiry_task.cancel()
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def close_when_session_expires(self, session):
        await asyncio.sleep(max(0, session.get_expiry_age()))
        await self.close(code=4401)

    async def notifications_changed(self, event):
        # Send an invalidation only; the browser re-fetches its own authorized Django data.
        await self.send_json({'type': 'notifications.changed'})
