from rest_framework import generics, mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import User
from .permissions import IsAdminRole
from .serializers import MeSerializer, RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = RegisterSerializer


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MeSerializer

    def get_object(self):
        return self.request.user


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                  viewsets.GenericViewSet):
    """Administrators manage roles; accounts are created through registration."""

    permission_classes = [IsAdminRole]
    serializer_class = UserSerializer
    queryset = User.objects.order_by("username")

    def perform_update(self, serializer):
        user = serializer.instance
        data = serializer.validated_data
        if user == self.request.user and (data.get("is_active") is False or data.get("role", user.role) != user.role):
            raise ValidationError("You cannot change your own role or deactivate your own account.")
        serializer.save()
