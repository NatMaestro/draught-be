from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


def _user_by_email_or_username_as_email(username_field: str, email: str):
    """Resolve login string that looks like an email to a User (or None)."""
    u = User.objects.filter(email__iexact=email).first()
    if u is not None:
        return u
    return User.objects.filter(**{f"{username_field}__iexact": email}).first()


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Accept either Django username or email in the `username` field (SimpleJWT default).
    Users often type their email at login; map email -> username before authenticate().
    """

    def validate(self, attrs):
        username_field = User.USERNAME_FIELD
        original_raw = attrs.get(username_field)
        attrs = {**attrs}
        if original_raw and "@" in str(original_raw):
            email = str(original_raw).strip()
            user_obj = _user_by_email_or_username_as_email(username_field, email)
            if user_obj is not None:
                attrs[username_field] = getattr(user_obj, username_field)
        try:
            return super().validate(attrs)
        except AuthenticationFailed:
            # Wrong password vs inactive both yield no user from authenticate(); clarify inactive.
            pwd = attrs.get("password")
            if original_raw and "@" in str(original_raw) and pwd:
                email = str(original_raw).strip()
                u = _user_by_email_or_username_as_email(username_field, email)
                if (
                    u is not None
                    and u.check_password(pwd)
                    and not u.is_active
                ):
                    raise AuthenticationFailed(
                        "This account is inactive. Ask an admin to enable it "
                        "(User.is_active = True)."
                    ) from None
            raise


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "password_confirm"]

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "A user with this username already exists. Try logging in at /api/auth/login/ "
                "or choose a different username."
            )
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists. Try logging in at /api/auth/login/ "
                "or use a different email."
            )
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
