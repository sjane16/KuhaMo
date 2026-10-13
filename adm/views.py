from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from requests import request
from user.models import Report, SurveyResponse, Notification, invalidate_trusted_devices
from django.db.models import Count, Avg, Q
from datetime import timedelta, datetime
import calendar
import json
import re
from django.conf import settings
from collections import defaultdict
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from user.forms import UserForm  
from user.validators import validate_password_strength
from security.audit import log_event
from django.contrib.auth import update_session_auth_hash
from xhtml2pdf import pisa
from user.views import link_callback
from user.notifications import notify_status_change
from user.context_processors import get_unread_notifications_count
from .models import Building 


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


def _fmt_hours(h):
    """Format oras: N/A, minutes (<1h), hours (<=48h), o days (>48h)."""
    if h is None:
        return 'N/A'
    if h < 1:
        return f"{round(h * 60)} min"
    if h <= 48:
        return f"{h:.1f} h"
    return f"{h / 24:.1f} days"


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


def build_survey_responses_list():
    """Builds just the Individual Responses list — does NOT touch Personnel Performance
    stats (no looping over all Reports, no N+1 report.survey queries). Used both by the
    full-page context builder AND directly by the responses-pagination endpoint, so
    paginating this table alone never re-triggers the expensive personnel-stats computation."""
    surveys = SurveyResponse.objects.select_related('report').order_by('-submitted_at')

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
            "quality": survey.quality,
            "quantity": survey.quantity,
            "timeliness": survey.timeliness,
            "date_submitted": report.submitted_at,
            "expected_at": report.expected_resolution_at,
            "actual_at": report.accomplished_at,
            "expected_resolution_met": expected_resolution_met,
            "resolution_delay_days": resolution_delay_days,
            "closure_turnaround_met": closure_turnaround_met,
            "closure_delay_days": closure_delay_days,
        })

    return responses


def build_survey_analysis_context():
    surveys = SurveyResponse.objects.select_related('report').order_by('-submitted_at')
    total_surveys = surveys.count()
    score_values = []
    for survey in surveys:
        score_values.extend(
            value for value in (survey.quality, survey.quantity, survey.timeliness)
            if value is not None
        )
    avg_rating = round(sum(score_values) / len(score_values), 1) if score_values else 0
    rating_counts = {
        rating: sum(score == rating for score in score_values)
        for rating in range(1, 6)
    }
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
            "quality_total": 0,
            "quantity_total": 0,
            "timeliness_total": 0,
            "quality_count": 0,
            "quantity_count": 0,
            "timeliness_count": 0,
            "categories": set(),
            "timeliness_scores": [],
            "qqt_reports": 0,
            "qqt_surveyed": 0,
            "qqt_quality_sum": 0,
            "qqt_quantity_sum": 0,
            "qqt_timeliness_sum": 0,
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

            # QQT tally: bilang ng reports = resolved OR closed
            if report.status in ('resolved', 'closed'):
                stats["qqt_reports"] += 1
                qqt_survey = getattr(report, 'survey', None)
                if qqt_survey:
                    stats["qqt_surveyed"] += 1
                    stats["qqt_quality_sum"] += qqt_survey.quality or 0
                    stats["qqt_quantity_sum"] += qqt_survey.quantity or 0
                    stats["qqt_timeliness_sum"] += qqt_survey.timeliness or 0

            if report.status != 'closed':
                continue

            stats["closed_count"] += 1
            stats["categories"].add(report.get_category_display())

            survey = getattr(report, 'survey', None)
            if survey:
                for field in ('quality', 'quantity', 'timeliness'):
                    value = getattr(survey, field)
                    if value is not None:
                        stats[f"{field}_total"] += value
                        stats[f"{field}_count"] += 1

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
        quality = round(stats["quality_total"] / stats["quality_count"], 1) if stats["quality_count"] else 0
        quantity_survey = round(stats["quantity_total"] / stats["quantity_count"], 1) if stats["quantity_count"] else 0

        total_assigned = stats["total_assigned"]
        completion_pct = (stats["closed_count"] / total_assigned * 100) if total_assigned else 0
        quantity = quantity_survey or (_percent_to_score(completion_pct) if total_assigned else 0)

        timeliness_scores = stats["timeliness_scores"]
        timeliness_avg = (sum(timeliness_scores) / len(timeliness_scores)) if timeliness_scores else 0
        timeliness_survey = round(stats["timeliness_total"] / stats["timeliness_count"], 1) if stats["timeliness_count"] else 0
        timeliness = timeliness_survey or round(timeliness_avg, 1)

        scores = [score for score in (quality, quantity, timeliness) if score]
        personnel_avg_rating = round(sum(scores) / len(scores), 2) if scores else 0

        # QQT = Σ score / number of reports (resolved + closed); None -> "-" kapag walang survey
        qqt_reports = stats["qqt_reports"]
        if qqt_reports and stats["qqt_surveyed"]:
            qqt_quality = stats["qqt_quality_sum"] / qqt_reports
            qqt_quantity = stats["qqt_quantity_sum"] / qqt_reports
            qqt_timeliness = stats["qqt_timeliness_sum"] / qqt_reports
            qqt_avg = (qqt_quality + qqt_quantity + qqt_timeliness) / 3
        else:
            qqt_quality = qqt_quantity = qqt_timeliness = qqt_avg = None

        personnel_rows.append({
            "name": stats["name"],
            "avg_rating": qqt_avg,
            "total_score": round(personnel_avg_rating, 1),
            "total_surveys": max(stats["quality_count"], stats["quantity_count"], stats["timeliness_count"]),
            "complete_task": qqt_reports,
            "quality": qqt_quality,
            "quantity": qqt_quantity,
            "timeliness": qqt_timeliness,
        })

    personnel_rows.sort(
        key=lambda row: row["avg_rating"] if row["avg_rating"] is not None else -1,
        reverse=True,
    )
    # (uses the dict key "avg_rating", unaffected by the personnel_avg_rating rename above)

    # ---- Individual Responses — official personnel only (outsourced-only reports are hidden) ----
    responses = build_survey_responses_list()

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


def _build_resolution_buckets(period, now, start_date=None, end_date=None):
    """
    Return ordered resolution buckets as tuples: (label, bucket_start, bucket_end).
    """
    local_now = timezone.localtime(now)
    buckets = []

    # Month picker mode: split selected month into fixed week ranges.
    if period is None and start_date is not None and end_date is not None:
        local_start = timezone.localtime(start_date)
        year, month = local_start.year, local_start.month
        last_day = calendar.monthrange(year, month)[1]
        month_periods = _pdf_week_periods(
            datetime(year, month, 1).date(),
            datetime(year, month, last_day).date(),
        )
        for p in month_periods:
            buckets.append((_fmt_period_label_short(p['start'], p['end']), p['start'], p['end']))
        return buckets

    # Last 7 Days: daily buckets.
    if period == '7':
        start_day = (local_now - timedelta(days=6)).date()
        for day_offset in range(7):
            day = start_day + timedelta(days=day_offset)
            bucket_start = timezone.make_aware(datetime(day.year, day.month, day.day, 0, 0, 0))
            bucket_end = timezone.make_aware(datetime(day.year, day.month, day.day, 23, 59, 59))
            buckets.append((day.strftime('%b %d'), bucket_start, bucket_end))
        return buckets

    # Last 30 Days: 4 weekly buckets going backward from today.
    if period == '30':
        for week_index in range(4, 0, -1):
            start_delta = week_index * 7 - 1
            end_delta = (week_index - 1) * 7
            start_day = (local_now - timedelta(days=start_delta)).date()
            end_day = (local_now - timedelta(days=end_delta)).date()
            bucket_start = timezone.make_aware(datetime(start_day.year, start_day.month, start_day.day, 0, 0, 0))
            bucket_end = timezone.make_aware(datetime(end_day.year, end_day.month, end_day.day, 23, 59, 59))
            buckets.append((_fmt_period_label_short(bucket_start, bucket_end), bucket_start, bucket_end))
        return buckets

    # All Time: monthly buckets (last 12 months).
    if period == 'all':
        year = local_now.year
        month = local_now.month
        month_pairs = []

        for _ in range(12):
            month_pairs.append((year, month))
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        month_pairs.reverse()

        for bucket_year, bucket_month in month_pairs:
            last_day = calendar.monthrange(bucket_year, bucket_month)[1]
            bucket_start = timezone.make_aware(datetime(bucket_year, bucket_month, 1, 0, 0, 0))
            bucket_end = timezone.make_aware(datetime(bucket_year, bucket_month, last_day, 23, 59, 59))
            label = datetime(bucket_year, bucket_month, 1).strftime('%b %Y')
            buckets.append((label, bucket_start, bucket_end))
        return buckets

    # Fallback: one bucket covering the explicit range if present.
    if start_date is not None and end_date is not None:
        buckets.append(('Range', start_date, end_date))
    return buckets


def _build_dashboard_data(period, start_date=None, end_date=None):
    now = timezone.now()

    # If caller didn't provide explicit start/end dates, derive from period
    if start_date is None and end_date is None:
        if period == '7':
            start_date = now - timedelta(days=7)
            end_date = now
        elif period == '30':
            start_date = now - timedelta(days=30)
            end_date = now
        else:
            start_date = None
            end_date = None

    def filter_periods(qs):
        # Support both open-ended (>= start) and closed ranges (start..end)
        if start_date and end_date:
            return qs.filter(submitted_at__range=(start_date, end_date))
        if start_date:
            return qs.filter(submitted_at__gte=start_date)
        return qs.all()

    survey_scores = SurveyResponse.objects.values_list('quality', 'quantity', 'timeliness')
    survey_values = [value for scores in survey_scores for value in scores if value is not None]
    avg_satisfaction = round(sum(survey_values) / len(survey_values), 1) if survey_values else 0

    status_counts_qs = (
        filter_periods(Report.objects)
        .values('status')
        .annotate(count=Count('id'))
    )
    status_map = dict(Report.STATUS_CHOICES)
    status_counts = {status_map[s['status']]: s['count'] for s in status_counts_qs}

    status_labels = [status_map[code] for code, _ in Report.STATUS_CHOICES]
    status_data = [status_counts.get(label, 0) for label in status_labels]

    satisfaction_labels = [
        "5-Outstanding",
        "4-Very Satisfactory",
        "3-Satisfactory",
        "2-Fair",
        "1-Unsatisfactory"
    ]   
    # Per-score tally across Quality, Quantity, Timeliness (same pooling as avg_satisfaction)
    satisfaction_counts = [
        sum(1 for value in survey_values if value == i)
        for i in range(5, 0, -1)
    ]

    categories_data = (
        filter_periods(Report.objects)
        .values('category')
        .annotate(count=Count('id'))
        .order_by('-count')
        # [:6]
    )
    # label_map = dict(Report.CATEGORY_CHOICES)
    # categories = [label_map.get(c['category'], c['category']) for c in categories_data]
    # categories_counts = [c['count'] for c in categories_data]

    # Look up the report count for each category that has reports.
    category_count_map = {
        item['category']: item['count']
        for item in categories_data
    }

    # Include every category, then sort by report count.
    sorted_categories = sorted(
        Report.CATEGORY_CHOICES,
        key=lambda category: category_count_map.get(category[0], 0),
        reverse=True,
    )

    categories = [
        label for code, label in sorted_categories
    ]

    categories_counts = [
        category_count_map.get(code, 0)
        for code, label in sorted_categories
    ]

    building_status_counts = defaultdict(
        lambda: {code: 0 for code, _ in Report.STATUS_CHOICES}
    )

    # Include every building, even if it has no reports.
    for name in Building.objects.order_by('name').values_list('name', flat=True):
        building_status_counts[name.strip()] = {
            code: 0 for code, _ in Report.STATUS_CHOICES
        }

    for report in filter_periods(Report.objects):
        building = report.location.split(',')[0].strip() if report.location else None
        if building:
            building_status_counts[building][report.status] += 1

    sorted_buildings = sorted(
        building_status_counts.items(),
        key=lambda item: sum(item[1].values()),
        reverse=True,
    )
    # [:8]
    building_labels = [building for building, _ in sorted_buildings]
    building_status_data = {
        code: [counts[code] for _, counts in sorted_buildings]
        for code, _ in Report.STATUS_CHOICES
    }

    resolution_weeks = []
    resolution_by_priority = {
        code: {
            'label': label,
            'target': PRIORITY_SLA_HOURS[code],
            'expected': [],
            'actual': [],
            'counts': [],
        }
        for code, label in Report.PRIORITY_CHOICES
    }
    sla_total = 0
    sla_met = 0

    resolution_buckets = _build_resolution_buckets(
        period,
        now,
        start_date=start_date,
        end_date=end_date,
    )

    for bucket_label, bucket_start, bucket_end in resolution_buckets:
        finished = Report.objects.filter(
            status__in=['resolved', 'closed'],
            accomplished_at__range=(bucket_start, bucket_end),
            submitted_at__isnull=False,
        )
        resolution_weeks.append(bucket_label)
        priority_actuals = {code: [] for code in resolution_by_priority}
        for r in finished:
            diff = (r.accomplished_at - r.submitted_at).total_seconds() / 3600
            if diff < 0:
                continue  # invalid: natapos bago ma-submit
            target = PRIORITY_SLA_HOURS.get(r.priority, 72)
            sla_total += 1
            if diff <= target:
                sla_met += 1
            if r.priority in priority_actuals:
                priority_actuals[r.priority].append(diff)

        for code, series in resolution_by_priority.items():
            values = priority_actuals[code]
            series['expected'].append(series['target'])
            series['actual'].append(
                round(sum(values) / len(values), 2) if values else None
            )
            series['counts'].append(len(values))

    sla_within_pct = round(sla_met / sla_total * 100, 1) if sla_total else None

    return {
        'avg_satisfaction': avg_satisfaction,
        'satisfaction_labels': satisfaction_labels,
        'satisfaction_counts': satisfaction_counts,
        'categories': categories,
        'categories_counts': categories_counts,
        'building_labels': building_labels,
        'building_status_data': building_status_data,
        'resolution_weeks': resolution_weeks,
        'resolution_by_priority': resolution_by_priority,
        'sla_total': sla_total,
        'sla_met': sla_met,
        'sla_within_pct': sla_within_pct,
        'status_labels': status_labels,
        'status_data': status_data,
    }


def adm_dashboard_ajax(request):
    period = request.GET.get('period', '30')
    report_month = (request.GET.get('report_month') or '').strip()

    if report_month:
        try:
            start_dt, end_dt = _parse_report_month(report_month)
        except ValueError:
            return JsonResponse({'error': 'Invalid report_month format. Expected YYYY-MM.'}, status=400)
        data = _build_dashboard_data(None, start_date=start_dt, end_date=end_dt)
    else:
        data = _build_dashboard_data(period)

    html = render_to_string(
        'partials/_dashboard_content.html',
        {
            'avg_satisfaction': data['avg_satisfaction'],
            'period': period,
            'sla_within_pct': data['sla_within_pct'],
            'sla_met': data['sla_met'],
            'sla_total': data['sla_total'],
        },
        request=request,
    )

    today = timezone.localtime(timezone.now()).date()
    last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])

    return JsonResponse({
        'html': html,
        'can_generate_report': settings.DEBUG or _is_last_day_of_month(today) or bool(report_month),
        'report_available_on': last_day.strftime('%b %d, %Y'),
        **data,
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
    })

    desktop_html = render_to_string('partials/_reports_desktop_rows.html', {
        'reports': page_obj,
    })

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
    report = get_object_or_404(
        Report.objects.select_related('user', 'survey'),
        id=report_id,
    )
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
    report = get_object_or_404(
        Report.objects.select_related('user__profile', 'survey'),
        id=report_id,
    )

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


def export_personnel_performance_pdf(request):
    context = build_survey_analysis_context()
    context.pop("responses", None)

    html = render_to_string('personnel_performance_pdf.html', context)

    response = HttpResponse(content_type='application/pdf')
    filename = f"Personnel_Performance_QQT_{timezone.now().strftime('%Y-%m-%d')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
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
        return HttpResponse("Something went wrong generating the Personnel Performance PDF.", status=500)

    return response


DASHBOARD_CHART_PATTERN = re.compile(r'^data:image/png;base64,[A-Za-z0-9+/=]+$')
DASHBOARD_CHART_MAX_LEN = 1_500_000
DASHBOARD_SUMMARY_MAX_LEN = 3000


def _is_last_day_of_month(day):
    return day.day == calendar.monthrange(day.year, day.month)[1]


def _clean_chart_image(value):
    """Accept only a small PNG data URI, so pisa never fetches arbitrary paths/URLs."""
    if not value or len(value) > DASHBOARD_CHART_MAX_LEN:
        return None
    return value if DASHBOARD_CHART_PATTERN.match(value) else None


def _join_and(items):
    items = list(items)
    if len(items) <= 1:
        return ''.join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _build_report_summary(data, period_start, period_end, priority_tables=None):
    """Plain-text summary paragraph (system-suggested; admin can edit before PDF)."""
    fmt = lambda d: f"{d:%B} {d.day}, {d:%Y}"
    parts = [
        "This report summarizes the corrective maintenance reports received by the "
        "Maintenance and Engineering Division of Universidad de Manila from "
        f"{fmt(period_start)} to {fmt(period_end)}, based on the analytics of the Admin Dashboard."
    ]

    total = sum(data['status_data'])
    if total:
        status_bits = [
            f"{count} ({count / total * 100:.1f}%) {label.lower()}"
            for label, count in zip(data['status_labels'], data['status_data'])
        ]
        parts.append(
            f"During this period, a total of {total} report{'' if total == 1 else 's'} "
            f"{'was' if total == 1 else 'were'} received. The reports are distributed by "
            f"status as follows: {_join_and(status_bits)}, as shown in Figure 1."
        )
    else:
        parts.append("No reports were received during this period.")

    category_total = sum(data['categories_counts'])
    active_categories = [
        (label, count) for label, count in zip(data['categories'], data['categories_counts'])
        if count > 0
    ]
    if active_categories:
        pct = lambda c: f"{c / category_total * 100:.1f}"
        top_label, top_count = active_categories[0]
        text = (
            f"By category, the {top_label} category accounted for the largest share of "
            f"reports with {top_count} ({pct(top_count)}%)"
        )
        rest = active_categories[1:3]
        if rest:
            text += ", followed by " + _join_and(
                f"the {label} category with {count} ({pct(count)}%)" for label, count in rest
            )
        text += "."
        others = active_categories[3:]
        if others:
            text += " The remaining reports were classified under " + _join_and(
                f"{label} ({count})" for label, count in others
            ) + "."
        text += " The distribution of reports by category is shown in Figure 2."
        parts.append(text)

    building_totals = []
    for index, name in enumerate(data['building_labels']):
        b_total = sum(
            data['building_status_data'][code][index]
            for code, _ in Report.STATUS_CHOICES
        )
        if b_total > 0:
            building_totals.append((name, b_total))
    if building_totals:
        text = (
            f"By location, {building_totals[0][0]} recorded the highest number of reports "
            f"with {building_totals[0][1]}"
        )
        rest = building_totals[1:3]
        if rest:
            text += ", followed by " + _join_and(f"{n} with {t}" for n, t in rest)
        text += ". The breakdown of reports per building by status is presented in Table 1."
        parts.append(text)

    if priority_tables is None:
        priority_tables = _build_pdf_priority_tables(period_start, period_end)

    text = (
        "With respect to resolution time, the Division's target turnaround depends on the "
        "priority of the report: 3 hours for Critical/Urgent, 24 hours for High Priority, "
        "and 72 hours for Standard."
    )
    completed_tables = [t for t in priority_tables if t['completed']]
    if completed_tables:
        bits = [
            f"{t['label']} reports averaged {_fmt_hours(t['avg_actual'])} against the "
            f"{t['target_hours']}-hour target, with {t['met']} of {t['completed']} "
            f"meeting the target time"
            for t in completed_tables
        ]
        text += " During the reporting period, " + _join_and(bits) + "."
        text += (
            " The comparison of expected and actual resolution time per priority level "
            "and per period is shown in Tables 2 to 4."
        )
    else:
        text += (
            " No reports were completed during the reporting period; hence, there is no actual "
            "resolution time available for comparison, as shown in Tables 2 to 4."
        )
    parts.append(text)

    return "\n\n".join(parts)


def _parse_report_month(report_month):
    parsed = datetime.strptime(report_month, '%Y-%m')
    first_day = datetime(parsed.year, parsed.month, 1)
    last_day = calendar.monthrange(parsed.year, parsed.month)[1]
    last_dt = datetime(parsed.year, parsed.month, last_day, 23, 59, 59)
    return timezone.make_aware(first_day), timezone.make_aware(last_dt)


def _fmt_period_label(start, end):
    if start == end:
        return f"{start.strftime('%B')} {start.day}"
    if start.month == end.month:
        return f"{start.strftime('%B')} {start.day} - {end.day}"
    return f"{start.strftime('%B')} {start.day} - {end.strftime('%B')} {end.day}"


def _fmt_period_label_short(start, end):
    """Maikling label para sa web charts: 'Sep 10-16' o 'Sep 28 - Oct 4'."""
    if start.date() == end.date() if hasattr(start, 'date') else start == end:
        return f"{start.strftime('%b')} {start.day}"
    if start.month == end.month:
        return f"{start.strftime('%b')} {start.day}-{end.day}"
    return f"{start.strftime('%b')} {start.day} - {end.strftime('%b')} {end.day}"


def _pdf_week_periods(period_start, period_end):
    """Calendar weeks (Sunday-Saturday) na naka-clip sa period_start..period_end."""
    periods = []
    cursor = period_start
    while cursor <= period_end:
        days_to_sat = (5 - cursor.weekday()) % 7
        end_day = min(cursor + timedelta(days=days_to_sat), period_end)
        periods.append({
            'label': _fmt_period_label(cursor, end_day),
            'start': timezone.make_aware(datetime(cursor.year, cursor.month, cursor.day, 0, 0, 0)),
            'end': timezone.make_aware(datetime(end_day.year, end_day.month, end_day.day, 23, 59, 59)),
        })
        cursor = end_day + timedelta(days=1)
    return periods


PDF_PRIORITY_STYLES = [
    # (code, header color, row tint)
    ('critical', '#dc2626', '#fee2e2'),
    ('high', '#ea580c', '#ffedd5'),
    ('standard', '#2563eb', '#dbeafe'),
]


def _build_pdf_priority_tables(period_start, period_end):
    """Isang table kada priority: rows = periods, may Expected (target) at Actual (average)."""
    periods = _pdf_week_periods(period_start, period_end)
    priority_labels = dict(Report.PRIORITY_CHOICES)
    tables = []
    for code, color, tint in PDF_PRIORITY_STYLES:
        target = PRIORITY_SLA_HOURS[code]
        rows = []
        all_actual = []
        for p in periods:
            actual_list = []
            finished = Report.objects.filter(
                priority=code,
                status__in=['resolved', 'closed'],
                accomplished_at__range=(p['start'], p['end']),
                submitted_at__isnull=False,
            )
            for r in finished:
                diff = (r.accomplished_at - r.submitted_at).total_seconds() / 3600
                if diff < 0:
                    continue
                actual_list.append(diff)
            all_actual.extend(actual_list)
            avg = sum(actual_list) / len(actual_list) if actual_list else None
            rows.append({
                'period': p['label'],
                'expected_label': _fmt_hours(target),
                'actual_label': _fmt_hours(avg),
            })
        tables.append({
            'code': code,
            'label': priority_labels.get(code, code),
            'color': color,
            'tint': tint,
            'target_hours': target,
            'target_label': _fmt_hours(target),
            'rows': rows,
            'completed': len(all_actual),
            'met': sum(1 for h in all_actual if h <= target),
            'avg_actual': sum(all_actual) / len(all_actual) if all_actual else None,
        })
    return tables


def export_dashboard_report_pdf(request):
    if request.method != 'POST':
        return HttpResponse("Invalid request.", status=405)

    now = timezone.localtime(timezone.now())
    today = now.date()

    # Allow admins to explicitly request any month via the "report_month" POST field (format: YYYY-MM).
    # If no month is specified, keep the original restriction: only allow generation on the last day
    # of the current month (unless DEBUG).
    report_month = (request.POST.get('report_month') or '').strip()
    start_dt = None
    end_dt = None
    if report_month:
        try:
            start_dt, end_dt = _parse_report_month(report_month)
        except ValueError:
            return HttpResponse("Invalid report_month format. Expected YYYY-MM.", status=400)

    if not settings.DEBUG and not report_month and not _is_last_day_of_month(today):
        return HttpResponse(
            "The monthly report can only be generated on the last day of the month.",
            status=403,
        )

    if report_month:
        data = _build_dashboard_data(None, start_date=start_dt, end_date=end_dt)
        period_start = start_dt.date()
        period_end = end_dt.date()
    else:
        data = _build_dashboard_data('30')
        period_end = today
        period_start = today - timedelta(days=30)

    priority_tables = _build_pdf_priority_tables(period_start, period_end)

    # Admin's edited text wins (even if blank -> no SUMMARY section).
    # If the field wasn't sent at all, fall back to the system-generated summary.
    if 'summary_text' in request.POST:
        summary_text = request.POST.get('summary_text', '').strip()[:DASHBOARD_SUMMARY_MAX_LEN]
    else:
        summary_text = _build_report_summary(data, period_start, period_end, priority_tables)

    total = sum(data['status_data'])
    status_colors = ['#f59e0b', '#6366f1', '#10b981', '#64748b']
    category_colors = [
        '#3b82f6', '#8b5cf6', '#14b8a6', '#f59e0b',
        '#f43f5e', '#64748b', '#06b6d4',
    ]

    status_rows = [
        {
            'label': label,
            'count': count,
            'pct': round(count / total * 100, 1) if total else 0,
            'color': status_colors[index % len(status_colors)],
        }
        for index, (label, count) in enumerate(
            zip(data['status_labels'], data['status_data'])
        )
    ]

    category_total = sum(data['categories_counts'])
    category_rows = [
        {
            'label': label,
            'count': count,
            'pct': round(count / category_total * 100, 1) if category_total else 0,
            'color': category_colors[index % len(category_colors)],
        }
        for index, (label, count) in enumerate(
            zip(data['categories'], data['categories_counts'])
        )
    ]

    status_tints = ['#fef3c7', '#e0e7ff', '#d1fae5', '#e2e8f0']
    status_columns = [
        {
            'label': label,
            'color': status_colors[index % len(status_colors)],
        }
        for index, label in enumerate(data['status_labels'])
    ]

    building_rows = []
    for index, name in enumerate(data['building_labels']):
        counts = [
            data['building_status_data'][code][index]
            for code, _ in Report.STATUS_CHOICES
        ]
        cells = [
            {'value': count, 'tint': status_tints[i % len(status_tints)]}
            for i, count in enumerate(counts)
        ]
        building_rows.append({
            'name': name,
            'counts': counts,
            'cells': cells,
            'total': sum(counts),
        })

    active_categories = [row for row in category_rows if row['count'] > 0]
    top_categories = active_categories[:3]
    other_categories = active_categories[3:]
    top_buildings = [row for row in building_rows if row['total'] > 0][:3]

    html = render_to_string('dashboard_report_pdf.html', {
        'period_start': period_start,
        'period_end': period_end,
        'generated_at': now,
        'generated_by': request.user.get_full_name() or request.user.get_username(),
        'total_reports': total,
        'category_active_count': len(active_categories),
        'top_categories': top_categories,
        'other_categories': other_categories,
        'top_buildings': top_buildings,
        'summary_text': summary_text,
        'summary_paragraphs': [
            p.strip()
            for p in re.split(r'\n\s*\n', summary_text.replace('\r\n', '\n'))
            if p.strip()
        ],
        'status_labels': data['status_labels'],
        'status_columns': status_columns,
        'status_rows': status_rows,
        'category_rows': category_rows,
        'building_rows': building_rows,
        'priority_tables': priority_tables,
        'chart_status': _clean_chart_image(request.POST.get('chart_status')),
        'chart_categories': _clean_chart_image(request.POST.get('chart_categories')),
        'footer_text': f"Report Period: {period_start.strftime('%b %d, %Y')} to {period_end.strftime('%b %d, %Y')}  |  Generated: {now.strftime('%b %d, %Y %I:%M %p')}",
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f"Dashboard_Report_{period_end.strftime('%Y-%m')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
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
        return HttpResponse("Something went wrong generating the Dashboard Report PDF.", status=500)

    return response


def dashboard_report_summary(request):
    """Returns the system-suggested summary paragraph to prefill the editable textarea."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request.'}, status=405)

    now = timezone.localtime(timezone.now())
    today = now.date()

    report_month = (request.GET.get('report_month') or '').strip()
    start_dt = None
    end_dt = None
    if report_month:
        try:
            start_dt, end_dt = _parse_report_month(report_month)
        except ValueError:
            return JsonResponse({'error': 'Invalid report_month format. Expected YYYY-MM.'}, status=400)

    if not settings.DEBUG and not report_month and not _is_last_day_of_month(today):
        return JsonResponse(
            {'error': 'The monthly report can only be generated on the last day of the month.'},
            status=403,
        )

    if report_month:
        data = _build_dashboard_data(None, start_date=start_dt, end_date=end_dt)
        period_start = start_dt.date()
        period_end = end_dt.date()
    else:
        data = _build_dashboard_data('30')
        period_end = today
        period_start = today - timedelta(days=30)

    return JsonResponse({'summary': _build_report_summary(data, period_start, period_end)})


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

        # ── MATERIALS REQUIREMENT (Phase 3: Phase 1 save logic) ─────────────────
        mat_qtys = request.POST.getlist('mat_qty')
        mat_units = request.POST.getlist('mat_unit')
        mat_descs = request.POST.getlist('mat_desc')

        materials_rows = []
        for qty, unit, desc in zip(mat_qtys, mat_units, mat_descs):
            qty = qty.strip()
            unit = unit.strip()
            desc = desc.strip()

            # Skip fully blank rows, and cap to 4 items.
            if not qty and not unit and not desc:
                continue

            if len(materials_rows) >= 4:
                break

            # Row with qty/unit but no description is NOT saved.
            if (qty or unit) and not desc:
                messages.warning(
                    request,
                    f"Report {report.job_order_id}: a materials row was skipped because it has no Item Description."
                )
                continue

            materials_rows.append({
                'qty': qty,
                'unit': unit,
                'description': desc,
            })

        report.materials_required = materials_rows

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
            notify_status_change(report, 'in_progress', f"Your report {report.job_order_id} is now In Progress.")
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

            if report.in_progress_at and accomplished_at < report.in_progress_at.replace(second=0, microsecond=0):
                messages.error(request, "Date and Time Completed cannot be earlier than the Date In Progress.")
                return redirect('adm_report_detail', report_id=report_id)

            if accomplished_at > timezone.now():
                messages.error(request, "Date and Time Completed cannot be a future date/time.")
                return redirect('adm_report_detail', report_id=report_id)

            report.status = new_status
            report.accomplished_at = accomplished_at
            report.completion_photo = completion_photo
        elif new_status == 'closed':
            return redirect('adm_report_detail', report_id=report_id)

        if new_status == 'in_progress' and not report.in_progress_at:
            report.in_progress_at = timezone.now()
        report.save()

        if new_status == 'resolved':
            notify_status_change(report, 'resolved', f"Your report {report.job_order_id} has been Resolved. Please take the Client Satisfaction Survey.")
            messages.success(request, f"Report {report.job_order_id} has been marked Resolved.")
    return redirect('adm_report_detail', report_id=report_id)

def ProfileMenu(request):
    is_post_render = request.method == 'POST'

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
                    invalidate_trusted_devices(request.user)
                    log_event(request, 'password_changed', user=request.user, where='Edit Profile')
                    update_session_auth_hash(request, request.user)
                    messages.success(request, "Password changed successfully.")
                    return redirect('ProfileMenu')

    return render(request, 'menu-admin.html', {
        "active_page": "ProfileMenu",
        "role": "Admin",
        "is_post_render": is_post_render,
    })

def adm_menu_ajax(request):
    html = render_to_string('partials/_menu_content.html', {
        "role": "Admin",
    }, request = request)

    return JsonResponse({"html": html})

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
    all_responses = build_survey_responses_list()
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
    notifications = Notification.objects.filter(user=request.user).select_related('report')

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

    unread_count = get_unread_notifications_count(request)

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
