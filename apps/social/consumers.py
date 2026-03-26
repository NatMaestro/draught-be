"""Per-user WebSocket for lightweight social UI refresh (friend requests, etc.)."""

import json

from channels.generic.websocket import AsyncWebsocketConsumer


class UserSocialConsumer(AsyncWebsocketConsumer):
    """Subscribe authenticated users to `user_social_{user_id}` for push fan-out."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self.close(code=4001)
            return
        self.group_name = f"user_social_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def social_notify(self, event):
        await self.send(text_data=json.dumps(event["data"]))
