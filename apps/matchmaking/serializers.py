from rest_framework import serializers


class JoinQueueSerializer(serializers.Serializer):
    ranked = serializers.BooleanField(default=False)

