from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from user.models import Report, SurveyResponse
from django.db.models import Count, Avg
from datetime import timedelta
import json
from collections import defaultdict
from django.contrib import messages
from django.http import JsonResponse
from .models import Building, Floor, Room
from django.contrib.auth import update_session_auth_hash
from user.validators import validate_password_strength

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
    other = {"name": other_names[0] if other_names else ""}

    return rows, other


def format_hours(hours):
    if hours is None:
        return "-"
    if hours < 24:
        return f"{hours:g} hours"
    days = hours / 24
    if days.is_integer():
        return f"{int(days)} days"
    return f"{days:.1f} days"


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

    personnel_stats = defaultdict(lambda: {
        "name": "",
        "rating_total": 0,
        "survey_count": 0,
        "categories": set(),
        "met_expected": 0,
    })
    responses = []

    for survey in surveys:
        report = survey.report
        assignments = report.assigned_personnel_data or []
        if not assignments and report.assigned_personnel:
            assignments = [{"name": report.assigned_personnel, "qtt": 1}]

        expected_at = report.expected_resolution_at
        actual_at = report.accomplished_at
        met_expected = report.met_expected_resolution
        personnel_names = [item.get("name") for item in assignments if item.get("name")]

        responses.append({
            "personnel": ", ".join(personnel_names) if personnel_names else "Unassigned",
            "category": report.get_category_display(),
            "rating": survey.rating,
            "feedback": survey.feedback,
            "submitted_at": survey.submitted_at,
            "report": report,
            "expected_at": expected_at,
            "actual_at": actual_at,
            "met_expected": met_expected,
        })

        for item in assignments:
            name = item.get("name")
            if not name:
                continue
            stats = personnel_stats[name]
            stats["name"] = name
            stats["rating_total"] += survey.rating
            stats["survey_count"] += 1
            stats["categories"].add(report.get_category_display())
            if met_expected:
                stats["met_expected"] += 1

    personnel_rows = []
    for stats in personnel_stats.values():
        survey_count = stats["survey_count"]
        avg = stats["rating_total"] / survey_count if survey_count else 0
        quality = round((avg / 5) * 40, 1)
        quantity = min(30, survey_count * 10)
        timeliness = round((stats["met_expected"] / survey_count) * 30, 1) if survey_count else 0
        qtt_score = round(quality + quantity + timeliness, 1)
        personnel_rows.append({
            "name": stats["name"],
            "avg_rating": round(avg, 1),
            "total_surveys": survey_count,
            "categories_handled": len(stats["categories"]),
            "quality": quality,
            "quantity": round(quantity, 1),
            "timeliness": timeliness,
            "qtt_score": qtt_score,
        })

    personnel_rows.sort(key=lambda row: row["qtt_score"], reverse=True)

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
        return qs
    
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
    categories =[label_map.get(c['category'], c['category']) for c in categories_data]
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
            accomplished_at__range =(start, end)
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
        'satisfaction_labels': json.dumps(satisfaction_labels),
        'satisfaction_counts': json.dumps(satisfaction_counts),
        'categories': json.dumps(categories),
        'categories_counts': json.dumps(categories_counts),
        'location': json.dumps(location),
        'location_counts': json.dumps(location_counts),
        'resolution_weeks': json.dumps(resolution_weeks),
        'expected_hours': json.dumps(expected_hours),
        'actual_hours': json.dumps(actual_hours),
        'period': period, 
    }

    return render(request, 'dashboard.html', context)


def base(request):
    return render(request, 'layouts/base.html', {"active_page": "base"})


def reports(request):
    status_filter = request.GET.get('status', '')
    reports_qs = Report.objects.all().order_by('-submitted_at')
    if status_filter:
        reports_qs = reports_qs.filter(status=status_filter)
    return render(request, 'reports.html', {
        "active_page": "reports",
        "reports": reports_qs,
        "status_filter": status_filter,
        "total_count": Report.objects.count(),
        "filtered_count": reports_qs.count(),
    })


def report_detail(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    personnel_rows, other_personnel = build_personnel_rows(report)
    return render(request, 'report_detail.html', {
        'report': report,
        'active_page': 'reports',
        'personnel_rows': personnel_rows,
        'other_personnel': other_personnel,
    })


def report_save(request, report_id):
    report = get_object_or_404(Report, id=report_id)

    if request.method == 'POST':
        category = request.POST.get('category', '').strip()
        custom_category = request.POST.get('custom_category', '').strip()
        priority = request.POST.get('priority', '').strip()
        selected_personnel = request.POST.getlist('personnel_names')
        other_personnel = request.POST.get('other_personnel', '').strip()
        include_other_personnel = request.POST.get('include_other_personnel') == '1'

        awaiting_personnel = request.POST.get('pending_awaiting_personnel') == '1'
        awaiting_materials = request.POST.get('pending_awaiting_materials') == '1'
        awaiting_approval = request.POST.get('pending_awaiting_approval') == '1'
        now = timezone.now()

        valid_categories = dict(Report.CATEGORY_CHOICES)
        if category in valid_categories:
            report.category = category
            report.custom_category = custom_category if category == "others" else None

        report.priority = priority if priority else None
        assignments = []
        personnel_by_slug = {item["slug"]: item["name"] for item in PERSONNEL_OPTIONS}

        for slug in selected_personnel:
            name = personnel_by_slug.get(slug)
            if not name:
                continue
            assignments.append({"name": name})

        if include_other_personnel and other_personnel:
            assignments.append({"name": other_personnel})

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

        if (
            report.status == 'pending'
            and report.priority
            and assignments
        ):
            report.status = 'in_progress'

            if not report.in_progress_at:
                report.in_progress_at = now

        report.save()

    return redirect('adm_report_detail', report_id=report_id)


def report_status(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status == 'in_progress' and report.status == 'pending':
            report.status = new_status
            if not report.in_progress_at:
                report.in_progress_at = timezone.now()
        elif new_status == 'resolved':
            report.status = new_status
            report.accomplished_at = timezone.now()
        elif new_status == 'closed':
            return redirect('adm_report_detail', report_id=report_id)

        if new_status == 'in_progress' and not report.in_progress_at:
            report.in_progress_at = timezone.now()
        report.save()
    return redirect('adm_report_detail', report_id=report_id)

def ProfileMenu(request):
    if request.method == 'POST':
        if 'save_info' in request.POST:
            request.user.first_name = request.POST.get('first_name')
            request.user.last_name = request.POST.get('last_name')
            request.user.email = request.POST.get('email')
            request.user.save()
            messages.success(request, "Profile Updated Successfully")
            return redirect('ProfileMenu')

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
    return render(request, 'survey_analysis.html', build_survey_analysis_context())
