from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import Token

from .models import User


class KulyaTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds `role` (and `patient_id` for patient users) to the JWT claims and to the response body."""

    @classmethod
    def get_token(cls, user: User) -> Token:
        token = super().get_token(user)
        token["role"] = user.role
        token["patient_id"] = user.patient_id
        return token

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        data["role"] = self.user.role
        data["patient_id"] = self.user.patient_id
        return data
