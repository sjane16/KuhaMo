import re
from django.core.validators import RegexValidator 
from django.core.exceptions import ValidationError

def validate_no_gibberish(value):
    """Returns a list of error messages. Empty list = looks like real text.
    Flags runs of 5+ consecutive consonants with no vowel in between,
    which is characteristic of random keyboard-mashing (e.g. "dhasjdjasdja")."""
    errors = []
    if re.search(r'[b-df-hj-np-tv-z]{5,}', value, re.IGNORECASE):
        errors.append("Please enter a valid, descriptive input — random or nonsensical text is not allowed.")
    return errors


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

phone_validator = RegexValidator (
    regex=r'^\d{11}$',
    message="Phone number must be exactly 11 digits, numbers only"
)

# Sanitizes first/last name input
NAME_MAX_LENGTH = 50
NAME_PATTERN = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿÑñ.'\- ]+$")

def validate_name(value, field_label = "Name"):
    """Tutulungan tayo magsanitize nito, guys <3"""

    value = (value or '').strip()

    if not value:
        raise ValidationError(f"{field_label} is required.")
    
    if len(value) > NAME_MAX_LENGTH:
        raise ValidationError(f"{field_label} must not exceed {NAME_MAX_LENGTH} characters.")

    # Blocks numbers/symbols
    if not NAME_PATTERN.match(value):     
        raise ValidationError(
            f"{field_label} can only contain letters, spaces, hyphens ( - ), apostrophes ( ' ), and periods ( . )."
        )
    
    return value
