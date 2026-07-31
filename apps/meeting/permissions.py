from rest_framework.permissions import BasePermission, IsAdminUser


class IsAdminStaff(IsAdminUser):
    """Kept as an explicit alias so intent is obvious in view `permission_classes`."""


class IsMeetingStaffOrTokenOwner(BasePermission):
    """
    Grants object-level access to:
      * authenticated staff/admin users (full management), or
      * an unauthenticated visitor presenting the meeting's `public_token`
        as a `token` query parameter (mailed to them in their confirmation email).
    """

    message = "You do not have permission to access this meeting."

    def has_permission(self, request, view) -> bool:
        # Defer the actual decision to the per-object check.
        return True

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if user and user.is_authenticated and user.is_staff:
            return True
        token = request.query_params.get("token")
        return bool(token) and str(obj.public_token) == token
