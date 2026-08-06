from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    """Full admin OR employee (is_staff). Used as base gate."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_admin or request.user.is_staff)
        )


class IsFullAdmin(BasePermission):
    """Only full admins (is_admin=True). Employees are denied."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_admin
        )


def HasPagePermission(page_key):
    """Returns a permission class that allows full admins OR employees with the given page_key."""
    class _Permission(BasePermission):
        def has_permission(self, request, view):
            if not (request.user and request.user.is_authenticated):
                return False
            if request.user.is_admin:
                return True
            if request.user.is_staff:
                try:
                    perms = request.user.employee_profile.permissions
                    return page_key in perms
                except Exception:
                    return False
            return False
    _Permission.__name__ = f'HasPagePermission_{page_key}'
    return _Permission
