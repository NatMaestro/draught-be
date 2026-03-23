from rest_framework import serializers


class JoinQueueSerializer(serializers.Serializer):
    ranked = serializers.BooleanField(default=False)
    use_clock = serializers.BooleanField(default=True)
    time_control_sec = serializers.IntegerField(required=False, default=600, min_value=0, max_value=7200)

    def validate(self, attrs):
        if attrs.get("use_clock", True):
            tc = attrs.get("time_control_sec", 600)
            if tc < 60:
                attrs["time_control_sec"] = 60
        return attrs

