def admin_role(request):
    if request.user.is_authenticated and request.user.is_staff:
        from user.decorators import is_head_admin
        head = is_head_admin(request.user)
        context = {"role": "Head Admin" if head else "Admin", "is_head_admin": head}
        if head:
            # Badge on the "Users" sidebar / bottom-nav link (only the Head Admin sees it)
            from .user_management import pending_staff_count
            context["pending_staff_count"] = pending_staff_count()
        return context
    return {}
