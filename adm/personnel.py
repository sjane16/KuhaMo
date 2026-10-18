"""
The MED personnel roster: who can be assigned to a report and who appears in the
personnel ratings.

It comes from accounts with the "MED Personnel" role (set by the Head Admin in
User Management). The names that used to be written in the code are kept only
while existing reports still reference them, so past assignments and ratings
don't disappear.
"""
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import NotSupportedError

from user.models import Report

# The roster that used to be hard-coded in adm/views.py
LEGACY_PERSONNEL = [
    {"slug": "remigio", "name": "Mr. Remigio"},
    {"slug": "garboso", "name": "Mr. Garboso"},
    {"slug": "lacson", "name": "Mr. Lacson"},
    {"slug": "quibral", "name": "Ms. Quibral"},
]

CACHE_KEY = 'med_personnel_options'
CACHE_SECONDS = 60


def _display_name(user):
    return user.get_full_name() or user.email or user.username


def _legacy_name_in_use(name):
    try:
        return Report.objects.filter(assigned_personnel_data__contains=[{"name": name}]).exists()
    except NotSupportedError:
        # Databases without JSON "contains" (e.g. SQLite in tests): check in Python
        return any(item.get("name") == name
                   for data in Report.objects.exclude(assigned_personnel_data=[]).values_list('assigned_personnel_data', flat=True)
                   for item in (data or []))


def _build():
    options = [
        {"slug": f"med-{u.pk}", "name": _display_name(u)}
        for u in User.objects.filter(is_active=True, profile__role='med_personnel').order_by('first_name', 'last_name', 'email')
    ]
    taken = {o["name"] for o in options}
    options += [o for o in LEGACY_PERSONNEL if o["name"] not in taken and _legacy_name_in_use(o["name"])]
    return options


def personnel_options():
    """[{"slug": ..., "name": ...}, ...] - cached briefly, since several pages call it many times."""
    options = cache.get(CACHE_KEY)
    if options is None:
        options = _build()
        cache.set(CACHE_KEY, options, CACHE_SECONDS)
    return options


def clear_personnel_cache():
    """Call after anyone becomes or stops being MED personnel."""
    cache.delete(CACHE_KEY)
