import logging
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import NoReverseMatch, reverse

from .models import Notification

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    'in_progress': 'In Progress',
    'resolved': 'Resolved',
    'closed': 'Closed',
}


def _send_status_email(email, report, status, message):
    label = STATUS_LABELS.get(status, status)
    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    try:
        link = site_url + reverse('userNotifications')
    except NoReverseMatch:
        link = site_url
    body = (
        f"{message}\n\n"
        f"Job Order: {report.job_order_id}\n"
        f"Status: {label}\n\n"
        f"View your notifications: {link}\n\n"
        "This is an automated message from Fac-Check. Please do not reply."
    )
    try:
        send_mail(
            subject=f"[Fac-Check] Report {report.job_order_id} is now {label}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except (SMTPException, OSError):
        logger.exception("Failed to send status email for report %s", report.job_order_id)


def notify_status_change(report, status, message):
    notification = Notification.objects.create(
        user=report.user,
        report=report,
        message=message,
        status_snapshot=status,
    )
    email = (report.user.email or '').strip()
    if email:
        transaction.on_commit(lambda: _send_status_email(email, report, status, message))
    return notification
