import re


def validate_password_strength(password):
    """Returns a list of error messages. Empty list = valid password."""
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r'[0-9]', password):
        errors.append("Password must contain at least one number.")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=~`\[\]\\/;\']', password):
        errors.append("Password must contain at least one symbol.")
    return errors

