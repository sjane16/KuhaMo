from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from requests import request
from user.models import Report, SurveyResponse, Notification
from django.db.models import Count, Avg, Q
from datetime import timedelta
import json
from collections import defaultdict
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from user.forms import UserForm  
from user.validators import validate_password_strength
from django.contrib.auth import update_session_auth_hash
from xhtml2pdf import pisa
from user.views import link_callback


REPORTS_PAGE_SIZE = 5

PERSONNEL_OPTIONS = [
    {"slug": "remigio", "name": "Mr. Remigio"},
    {"slug": "garboso", "name": "Mr. Garboso"},
    {"slug": "lacson", "name": "Mr. Lacson"},
    {"slug": "quibral", "name": "Ms. Quibral"},
]


def build_personnel_rows(report):
    saved = report.assigned_personnel_data or []
    saved_names = {
        item.get("name")
        for item in saved
        if item.get("name")
    }

    if not saved and report.assigned_personnel:
        saved_names = {
            name.strip()
            for name in report.assigned_personnel.split(",")
            if name.strip()
        }

    rows = []
    known_names = {item["name"] for item in PERSONNEL_OPTIONS}

    for option in PERSONNEL_OPTIONS:
        rows.append({
            **option,
            "checked": option["name"] in saved_names,
        })

    other_names = [
        name
        for name in saved_names
        if name not in known_names
    ]
    others = [{"name": name} for name in other_names]

    return rows, others


def format_hours(hours):
    if hours is None:
        return "-"
    if hours < 24:
        return f"{hours:g} hours"
    days = hours / 24
    if days.is_integer():
        return f"{int(days)} days"
    return f"{days:.1f} days"


RESPONSES_PAGE_SIZE = 5

PRIORITY_SLA_HOURS = {
    'standard': 72,
    'high': 24,
    'critical': 3,
}


def _delay_score(delay_hours):
    """Convert an elapsed-delay (in hours, already clamped to >= 0) into a 1-5 score."""
    if delay_hours is None:
        return None
    if delay_hours <= 0:
        return 5
    delay_days = delay_hours / 24
    if delay_days <= 2:
        return 4
    if delay_days <= 5:
        return 3
    if delay_days <= 7:
        return 2
    return 1


def _percent_to_score(pct):
    """Convert a completion percentage into a 1-5 score."""
    if pct >= 100:
        return 5
    if pct >= 90:
        return 4
    if pct >= 80:
        return 3
    if pct >= 70:
        return 2
    return 1


def _known_personnel_names(assignments):
    """Filter assignment dicts down to names that match the official PERSONNEL_OPTIONS roster
    (excludes outsourced/typed-in "other personnel")."""
    known = {option["name"] for option in PERSONNEL_OPTIONS}
    return [item.get("name") for item in assignments if item.get("name") in known]


def build_survey_analysis_context():
    surveys = SurveyResponse.objects.select_related('report').order_by('-submitted_at')
    total_surveys = surveys.count()
    avg_rating = round(surveys.aggregate(avg=Avg('rating'))['avg'] or 0, 1)
    rating_counts = {rating: surveys.filter(rating=rating).count() for rating in range(1, 6)}
    max_rating_count = max(rating_counts.values()) if rating_counts else 0
    rating_rows = []
    for rating in range(5, 0, -1):
        count = rating_counts.get(rating, 0)
        percent = round((count / max_rating_count) * 100) if max_rating_count else 0
        rating_rows.append({"rating": rating, "count": count, "percent": percent})

    # ---- Personnel Performance (QQT) — official personnel only, based on ALL assigned reports ----
    personnel_stats = {
        option["name"]: {
            "name": option["name"],
            "total_assigned": 0,
            "closed_count": 0,
            "rating_total": 0,
            "rating_count": 0,
            "categories": set(),
            "timeliness_scores": [],
        }
        for option in PERSONNEL_OPTIONS
    }

    for report in Report.objects.all():
        assignments = report.assigned_personnel_data or []
        if not assignments and report.assigned_personnel:
            assignments = [{"name": report.assigned_personnel}]

        names = _known_personnel_names(assignments)
        if not names:
            continue

        for name in names:
            stats = personnel_stats[name]
            stats["total_assigned"] += 1

            if report.status != 'closed':
                continue

            stats["closed_count"] += 1
            stats["categories"].add(report.get_category_display())

            survey = getattr(report, 'survey', None)
            if survey:
                stats["rating_total"] += survey.rating
                stats["rating_count"] += 1

            threshold = PRIORITY_SLA_HOURS.get(report.priority, 72)

            sla_score = None
            if report.in_progress_at and report.accomplished_at:
                sla_hours = (report.accomplished_at - report.in_progress_at).total_seconds() / 3600
                sla_score = _delay_score(max(0, sla_hours - threshold))

            close_score = None
            if report.accomplished_at and report.closed_at:
                close_hours = (report.closed_at - report.accomplished_at).total_seconds() / 3600
                close_score = _delay_score(max(0, close_hours))

            report_scores = [s for s in (sla_score, close_score) if s is not None]
            if report_scores:
                stats["timeliness_scores"].append(sum(report_scores) / len(report_scores))

    personnel_rows = []
    for stats in personnel_stats.values():
        rating_count = stats["rating_count"]
        quality_avg = (stats["rating_total"] / rating_count) if rating_count else 0
        quality = round(quality_avg, 1)

        total_assigned = stats["total_assigned"]
        completion_pct = (stats["closed_count"] / total_assigned * 100) if total_assigned else 0
        quantity = _percent_to_score(completion_pct) if total_assigned else 0

        timeliness_scores = stats["timeliness_scores"]
        timeliness_avg = (sum(timeliness_scores) / len(timeliness_scores)) if timeliness_scores else 0
        timeliness = round(timeliness_avg, 1)

        personnel_avg_rating = round((quality + quantity + timeliness) / 3, 2)

        personnel_rows.append({
            "name": stats["name"],
            "avg_rating": personnel_avg_rating,
            "total_score": stats["rating_total"],
            "total_surveys": rating_count,
            "complete_task": f"{stats['closed_count']}/{total_assigned}",
            "quality": quality,
            "quantity": quantity,
            "timeliness": timeliness,
        })

    personnel_rows.sort(key=lambda row: row["avg_rating"], reverse=True)
    # (uses the dict key "avg_rating", unaffected by the personnel_avg_rating rename above)

    # ---- Individual Responses — official personnel only (outsourced-only reports are hidden) ----
    responses = []
    for survey in surveys:
        report = survey.report
        assignments = report.assigned_personnel_data or []
        if not assignments and report.assigned_personnel:
            assignments = [{"name": report.assigned_personnel}]

        personnel_names = _known_personnel_names(assignments)
        if not personnel_names:
            continue

        threshold = PRIORITY_SLA_HOURS.get(report.priority, 72)

        expected_resolution_met = None
        resolution_delay_days = None
        if report.in_progress_at and report.accomplished_at:
            sla_hours = (report.accomplished_at - report.in_progress_at).total_seconds() / 3600
            delay_hours = max(0, sla_hours - threshold)
            expected_resolution_met = _delay_score(delay_hours) >= 4
            resolution_delay_days = round(delay_hours / 24) if delay_hours > 0 else 0

        closure_turnaround_met = None
        closure_delay_days = None
        if report.accomplished_at and report.closed_at:
            close_hours = (report.closed_at - report.accomplished_at).total_seconds() / 3600
            delay_hours = max(0, close_hours)
            closure_turnaround_met = _delay_score(delay_hours) >= 4
            closure_delay_days = round(delay_hours / 24) if delay_hours > 0 else 0

        responses.append({
            "personnel": ", ".join(personnel_names),
            "category": report.get_category_display(),
            "rating": survey.rating,
            "feedback": survey.feedback,
            "date_submitted": report.submitted_at,
            "expected_at": report.expected_resolution_at,
            "actual_at": report.accomplished_at,
            "expected_resolution_met": expected_resolution_met,
            "resolution_delay_days": resolution_delay_days,
            "closure_turnaround_met": closure_turnaround_met,
            "closure_delay_days": closure_delay_days,
        })

    return {
        "active_page": "survey_analysis",
        "avg_rating": avg_rating,
        "total_surveys": total_surveys,
        "rating_counts": rating_counts,
        "rating_rows": rating_rows,
        "max_rating_count": max_rating_count,
        "personnel_rows": personnel_rows,
        "responses": responses,
    }

def dashboard(request):
    period = request.GET.get('period', '30')

    return render(request, 'dashboard.html', {
        'period': period,
    })


def adm_dashboard_ajax(request):
    now = timezone.now()
    period = request.GET.get('period', '30')

    if period == '7':
        start_date = now - timedelta(days=7)
    elif period == '30':
        start_date = now - timedelta(days=30)
    else:
        start_date = None

    def filter_periods(qs):
        if start_date:
            return qs.filter(submitted_at__gte=start_date)
        return qs.all()

    pending = filter_periods(Report.objects.filter(status='pending')).count()
    in_progress = filter_periods(Report.objects.filter(status='in_progress')).count()
    resolved_thisweek = filter_periods(Report.objects.filter(status='resolved')).count()
    avg_satisfaction = SurveyResponse.objects.aggregate(avg=Avg('rating'))['avg'] or 0
    avg_satisfaction = round(avg_satisfaction, 1)

    satisfaction_labels = [
        "5-Outstanding",
        "4-Very Satisfactory",
        "3-Satisfactory",
        "2-Fair",
        "1-Unsatisfactory"
    ]
    satisfaction_counts = [
        SurveyResponse.objects.filter(rating=i).count()
        for i in range(5, 0, -1)
    ]

    categories_data = (
        filter_periods(Report.objects)
        .values('category')
        .annotate(count=Count('id'))
        .order_by('-count')[:6]
    )
    label_map = dict(Report.CATEGORY_CHOICES)
    categories = [label_map.get(c['category'], c['category']) for c in categories_data]
    categories_counts = [c['count'] for c in categories_data]

    room_counts = {}

    for report in filter_periods(Report.objects):
        room = report.room_location

        if room:
            room_counts[room] = room_counts.get(room, 0) + 1

    top_rooms = sorted(
        room_counts.items(),
        key=lambda item: item[1],
        reverse=True
    )[:6]

    location = [room for room, count in top_rooms]
    location_counts = [count for room, count in top_rooms]

    resolution_weeks = []
    expected_hours = []
    actual_hours = []

    for i in range(1, 5):
        start = now - timedelta(weeks=(5 - i))
        end = now - timedelta(weeks=(4 - i))
        resolved = Report.objects.filter(
            status='resolved',
            accomplished_at__range=(start, end)
        )
        resolution_weeks.append(f'Week {i}')
        expected_hours.append(24)
        total_hours = 0
        count = resolved.count()
        for r in resolved:
            if r.accomplished_at and r.submitted_at:
                diff = (r.accomplished_at - r.submitted_at).total_seconds() / 3600
                total_hours += diff
        actual_hours.append(round(total_hours / count, 1) if count else 0)

    context = {
        'pending': pending,
        'in_progress': in_progress,
        'resolved_thisweek': resolved_thisweek,
        'avg_satisfaction': avg_satisfaction,
        'period': period,
    }

    html = render_to_string('partials/_dashboard_content.html', context, request=request)

    return JsonResponse({
        'html': html,
        'satisfaction_labels': satisfaction_labels,
        'satisfaction_counts': satisfaction_counts,
        'categories': categories,
        'categories_counts': categories_counts,
        'location': location,
        'location_counts': location_counts,
        'resolution_weeks': resolution_weeks,
        'expected_hours': expected_hours,
        'actual_hours': actual_hours,
    })


def base(request):
    return render(request, 'layouts/base.html', {"active_page": "base"})


def _filter_admin_reports(status_filter, search_query):
    reports_qs = Report.objects.all().order_by('-submitted_at')

    if status_filter:
        reports_qs = reports_qs.filter(status=status_filter)

    if search_query:
        query = search_query.strip()

        q_filter = (
            Q(job_order_id__icontains=query)
            | Q(location__icontains=query)
            | Q(category__icontains=query)
            | Q(custom_category__icontains=query)
            | Q(assigned_personnel__icontains=query)
        )

        matching_statuses = [
            code for code, label in Report.STATUS_CHOICES
            if query.lower() in label.lower()
        ]
        if matching_statuses:
            q_filter |= Q(status__in=matching_statuses)

        matching_priorities = [
            code for code, label in Report.PRIORITY_CHOICES
            if query.lower() in label.lower()
        ]
        if matching_priorities:
            q_filter |= Q(priority__in=matching_priorities)

        matching_categories = [
            code for code, label in Report.CATEGORY_CHOICES
            if query.lower() in label.lower()
        ]
        if matching_categories:
            q_filter |= Q(category__in=matching_categories)

        reports_qs = reports_qs.filter(q_filter)

    return reports_qs


def reports(request):
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '').strip()

    reports_qs = _filter_admin_reports(status_filter, search_query)

    paginator = Paginator(reports_qs, REPORTS_PAGE_SIZE)
    page_obj = paginator.get_page(1)

    return render(request, 'reports.html', {
        "active_page": "reports",
        "reports": page_obj,
        "status_filter": status_filter,
        "search_query": search_query,
        "total_count": Report.objects.count(),
        "filtered_count": paginator.count,
    })


def adm_reports_ajax(request):
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '').strip()
    page_number = request.GET.get('page', 1)

    reports_qs = _filter_admin_reports(status_filter, search_query)

    paginator = Paginator(reports_qs, REPORTS_PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    mobile_html = render_to_string('partials/_reports_mobile_rows.html', {
        'reports': page_obj,
    }, request=request)

    desktop_html = render_to_string('partials/_reports_desktop_rows.html', {
        'reports': page_obj,
    }, request=request)

    return JsonResponse({
        'mobile_html': mobile_html,
        'desktop_html': desktop_html,
        'current_page': page_obj.number,
        'total_pages': paginator.num_pages,
        'has_previous': page_obj.has_previous(),
        'has_next': page_obj.has_next(),
        'total_count': paginator.count,
    })


def report_detail(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    personnel_rows, other_personnel = build_personnel_rows(report)
    is_locked = report.status in ('resolved', 'closed')

    if report.status == 'closed':
        session_key = f'closed_seen_{report.id}'
        if not request.session.get(session_key):
            messages.success(request, f"Report {report.job_order_id} has been Closed.")
            request.session[session_key] = True

    return render(request, 'report_detail.html', {
        'report': report,
        'active_page': 'reports',
        'personnel_rows': personnel_rows,
        'other_personnel': other_personnel,
        'is_locked': is_locked,
    })


def export_job_order_pdf_admin(request, report_id):
    report = get_object_or_404(Report, id=report_id)

    category_checks = {
        'vehicle_checkup': report.category == 'vehicle_checkup',
        'electrical': report.category == 'electrical',
        'refrigeration_acu': report.category == 'refrigeration_acu',
        'painting': report.category == 'painting',
        'carpentry_masonry': report.category == 'carpentry_masonry',
        'plumbing': report.category == 'plumbing',
        'others': report.category == 'others',
    }

    html = render_to_string('user/job_order_pdf.html', {
        "report": report,
        "category_checks": category_checks,
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Job_Order_{report.job_order_id or report.id}.pdf"'
    response['X-Frame-Options'] = 'SAMEORIGIN'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    pisa_status = pisa.CreatePDF(
        html,
        dest=response,
        link_callback=link_callback
    )

    if pisa_status.err:
        return HttpResponse("Something went wrong generating the Job Order PDF.", status=500)

    return response


def report_save(request, report_id):
    report = get_object_or_404(Report, id=report_id)

    if request.method == 'POST':
        if report.status in ('resolved', 'closed'):
            messages.error(request, "This report can no longer be edited.")
            return redirect('adm_report_detail', report_id=report_id)

        category = request.POST.get('category', '').strip()
        custom_category = request.POST.get('custom_category', '').strip()
        priority = request.POST.get('priority', '').strip()
        selected_personnel = request.POST.getlist('personnel_names')
        other_personnel_list = request.POST.getlist('other_personnel')
        include_other_personnel = request.POST.get('include_other_personnel') == '1'

        awaiting_personnel = request.POST.get('pending_awaiting_personnel') == '1'
        awaiting_materials = request.POST.get('pending_awaiting_materials') == '1'
        awaiting_approval = request.POST.get('pending_awaiting_approval') == '1'
        now = timezone.now()

        valid_categories = dict(Report.CATEGORY_CHOICES)
        if category in valid_categories:
            report.category = category
            report.custom_category = custom_category if category == "others" else None

        report.findings = request.POST.get('findings', '').strip()
        report.recommendation = request.POST.get('recommendation', '').strip()

        report.priority = priority if priority else None
        assignments = []
        personnel_by_slug = {item["slug"]: item["name"] for item in PERSONNEL_OPTIONS}

        for slug in selected_personnel:
            name = personnel_by_slug.get(slug)
            if not name:
                continue
            assignments.append({"name": name})

        if include_other_personnel:
            for name in other_personnel_list:
                name = name.strip()
                if name:
                    assignments.append({"name": name})

        report.assigned_personnel_data = assignments
        report.assigned_personnel = ", ".join(
            item["name"]
            for item in assignments
        ) if assignments else None

        if awaiting_personnel and not report.pending_awaiting_personnel_at:
            report.pending_awaiting_personnel_at = now
        if awaiting_materials and not report.pending_awaiting_materials_at:
            report.pending_awaiting_materials_at = now
        if awaiting_approval and not report.pending_awaiting_approval_at:
            report.pending_awaiting_approval_at = now

        report.pending_awaiting_personnel = awaiting_personnel
        report.pending_awaiting_materials = awaiting_materials
        report.pending_awaiting_approval = awaiting_approval

        if not awaiting_personnel:
            report.pending_awaiting_personnel_at = None
        if not awaiting_materials:
            report.pending_awaiting_materials_at = None
        if not awaiting_approval:
            report.pending_awaiting_approval_at = None

        became_in_progress = False

        if (
            report.status == 'pending'
            and report.priority
            and assignments
            and awaiting_personnel
            and awaiting_materials
        ):
            report.status = 'in_progress'
            became_in_progress = True

            if not report.in_progress_at:
                report.in_progress_at = now

        report.save()

        if became_in_progress:
            Notification.objects.create(
                user=report.user,
                report=report,
                message=f"Your report {report.job_order_id} is now In Progress.",
                status_snapshot=report.status,
            )
            messages.success(request, f"Report {report.job_order_id} is now In Progress.")
        elif report.status == 'pending':
            missing = []
            if not report.priority:
                missing.append("Priority Level")
            if not assignments:
                missing.append("Assign Personnel (at least one)")
            if not awaiting_personnel:
                missing.append('"With Assigned Personnel"')
            if not awaiting_materials:
                missing.append('"Materials Available"')

            if missing:
                messages.warning(
                    request,
                    f"Report {report.job_order_id} is still Pending — missing: {', '.join(missing)}."
                )

    return redirect('adm_report_detail', report_id=report_id)



def report_status(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status == 'resolved':
            completion_photo = request.FILES.get('completion_photo')
            if not completion_photo:
                messages.error(request, "Please upload a photo proof of the completed repair.")
                return redirect('adm_report_detail', report_id=report_id)

            accomplished_at_raw = request.POST.get('accomplished_at')
            accomplished_at = parse_datetime(accomplished_at_raw) if accomplished_at_raw else None

            if accomplished_at is None:
                messages.error(request, "Please enter the Date and Time Completed.")
                return redirect('adm_report_detail', report_id=report_id)

            if timezone.is_naive(accomplished_at):
                accomplished_at = timezone.make_aware(accomplished_at)

            if accomplished_at < report.submitted_at:
                messages.error(request, "Date and Time Completed cannot be earlier than the Date Submitted.")
                return redirect('adm_report_detail', report_id=report_id)

            if accomplished_at > timezone.now():
                messages.error(request, "Date and Time Completed cannot be a future date/time.")
                return redirect('adm_report_detail', report_id=report_id)

            report.status = new_status
            report.accomplished_at = accomplished_at
            report.completion_photo = completion_photo

            Notification.objects.create(
                user=report.user,
                report=report,
                message=f"Your report {report.job_order_id} has been Resolved. Please take the Client Satisfaction Survey.",
                status_snapshot=report.status,
            )
            messages.success(request, f"Report {report.job_order_id} has been marked Resolved.")
        elif new_status == 'closed':
            return redirect('adm_report_detail', report_id=report_id)

        if new_status == 'in_progress' and not report.in_progress_at:
            report.in_progress_at = timezone.now()
        report.save()
    return redirect('adm_report_detail', report_id=report_id)

def ProfileMenu(request):
    if request.method == 'POST':
        # Now uses UserForm to sanitize first_name/last_name
        if 'save_info' in request.POST:
            user_form = UserForm(request.POST, instance=request.user)
            if user_form.is_valid():
                user_form.save()
                messages.success(request, "Profile Updated Successfully")
                return redirect('ProfileMenu')
            else:
                # Plain-text error message (avoids raw HTML from form.errors)
                error_list = [
                    error
                    for field, errors in user_form.errors.items()
                    for error in errors
                ]
                messages.error(request, " ".join(error_list))

        elif 'change_password' in request.POST:
            old_password = request.POST.get('old_password', '').strip()
            new_password1 = request.POST.get('new_password1', '').strip()
            new_password2 = request.POST.get('new_password2', '').strip()

            if not old_password and not new_password1 and not new_password2:
                messages.error(request, "Please fill in the required fields.")
            elif not old_password:
                messages.error(request, "Please enter your current password.")
            elif not new_password1 or not new_password2:
                messages.error(request, "Please fill in both new password fields.")
            elif not request.user.check_password(old_password):
                messages.error(request, "Old password is incorrect.")
            elif new_password1 != new_password2:
                messages.error(request, "New passwords do not match.")
            elif new_password1 == old_password:
                messages.error(request, "New Password must be different from your current password.")
            else:
                password_errors = validate_password_strength(new_password1)
                if password_errors:
                    for err in password_errors:
                        messages.error(request, err)
                else:
                    request.user.set_password(new_password1)
                    request.user.save()
                    update_session_auth_hash(request, request.user)
                    messages.success(request, "Password changed successfully.")
                    return redirect('ProfileMenu')

    return render(request, 'menu-admin.html', {
        "active_page": "ProfileMenu",
        "role": "Admin",
    })

def universitymap (request):
    return render(request, 'university-map.html', {
        "active_page": "universitymap"
})

def calendar_view(request):
    return render(request, 'calendar.html', {
        "active_page": "calendar"
    })


def survey_analysis(request):
    return render(request, 'survey_analysis.html', {
        "active_page": "survey_analysis",
    })


def adm_survey_analysis_ajax(request):
    context = build_survey_analysis_context()

    all_responses = context.pop("responses")
    paginator = Paginator(all_responses, RESPONSES_PAGE_SIZE)
    page_obj = paginator.get_page(1)
    context["responses"] = page_obj
    context["responses_total_pages"] = paginator.num_pages
    context["responses_has_previous"] = page_obj.has_previous()
    context["responses_has_next"] = page_obj.has_next()
    context["responses_total_count"] = paginator.count

    html = render_to_string('partials/_survey_analysis_content.html', context, request=request)

    return JsonResponse({
        'html': html,
    })


def adm_survey_responses_ajax(request):
    context = build_survey_analysis_context()
    all_responses = context["responses"]
    page_number = request.GET.get('page', 1)

    paginator = Paginator(all_responses, RESPONSES_PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    html = render_to_string('partials/_survey_responses_rows.html', {
        'responses': page_obj,
    }, request=request)

    return JsonResponse({
        'html': html,
        'current_page': page_obj.number,
        'total_pages': paginator.num_pages,
        'has_previous': page_obj.has_previous(),
        'has_next': page_obj.has_next(),
        'total_count': paginator.count,
    })


def _filter_admin_notifications(request, notif_filter):
    notifications = Notification.objects.filter(user=request.user)

    if notif_filter == 'unread':
        notifications = notifications.filter(is_read=False)

    return notifications


def adminNotifications(request):
    notif_filter = request.GET.get('filter', 'all')

    return render(request, 'notifications.html', {
        "active_page": "adminNotifications",
        "notif_filter": notif_filter,
    })


def get_notifications_page_ajax_admin(request):
    notif_filter = request.GET.get('filter', 'all')
    notifications = _filter_admin_notifications(request, notif_filter)

    html = render_to_string('partials/_notifications_rows.html', {
        "notifications": notifications,
    }, request=request)

    return JsonResponse({
        "html": html,
    })


def get_notifications_ajax_admin(request):
    notif_filter = request.GET.get('filter', 'all')
    notifications = _filter_admin_notifications(request, notif_filter)[:10]

    data = [
        {
            "id": n.id,
            "message": n.message,
            "is_read": n.is_read,
            "is_recent": n.is_recent,
            "time_ago": n.time_ago,
            "report_id": n.report.id,
            "status": n.status_snapshot or n.report.status,
        }
        for n in notifications
    ]

    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

    return JsonResponse({
        "notifications": data,
        "unread_count": unread_count,
    })


def view_notification_admin(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)

    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])

    return redirect('adm_report_detail', report_id=notification.report.id)


def mark_all_notifications_read_admin(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)

    return JsonResponse({'success': True})