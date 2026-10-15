def admin_role(request):
    if request.user.is_authenticated and request.user.is_staff:
        # Badge on the "Users" sidebar / bottom-nav link
        from .user_management import pending_staff_count
        return {"role": "Admin", "pending_staff_count": pending_staff_count()}
    return {}
