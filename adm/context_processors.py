def admin_role(request):
    if request.user.is_authenticated and request.user.is_staff:
        return {"role": "Admin"}
    return {}