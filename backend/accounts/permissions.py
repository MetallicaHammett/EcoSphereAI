from rest_framework.permissions import SAFE_METHODS, BasePermission


def _authed(request):
    return bool(request.user and request.user.is_authenticated)


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return _authed(request) and request.user.is_admin_role


class IsOperator(BasePermission):
    def has_permission(self, request, view):
        return _authed(request) and request.user.is_operator


class ReadOnlyOrAdmin(BasePermission):
    """Any signed-in user may read; only administrators may write."""

    def has_permission(self, request, view):
        if not _authed(request):
            return False
        return request.method in SAFE_METHODS or request.user.is_admin_role


class ReadOnlyOrOperator(BasePermission):
    """Any signed-in user may read; facility staff and administrators may write."""

    def has_permission(self, request, view):
        if not _authed(request):
            return False
        return request.method in SAFE_METHODS or request.user.is_operator
