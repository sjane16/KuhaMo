from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from user.models import Report, SurveyResponse
from django.db.models import Count, Avg
from datetime import timedelta
import json

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Building, Floor, Room

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

    location_data = (
        filter_periods(Report.objects)
        .values('location')
        .annotate(count=Count('id'))
        .order_by('-count')[:6]
    )
    location = [l['location'] for l in location_data]
    location_counts = [l['count'] for l in location_data]

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
    return render(request, 'report_detail.html', {
        'report': report,
        'active_page': 'reports',
        'cba_items': report.cba_items,
    })


def report_save(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    if request.method == 'POST':
        priority = request.POST.get('priority', '').strip()
        assigned_personnel = request.POST.get('assigned_personnel', '').strip()
        report.priority = priority if priority else None
        report.assigned_personnel = assigned_personnel if assigned_personnel else None

        descriptions = request.POST.getlist('item_desc[]')
        quantities   = request.POST.getlist('item_qty[]')
        prices       = request.POST.getlist('item_price[]')

        items = []
        for desc, qty, price in zip(descriptions, quantities, prices):
            desc = (desc or '').strip()
            try:
                qty_val = float(qty) if qty else 0
            except ValueError:
                qty_val = 0
            try:
                price_val = float(price) if price else 0
            except ValueError:
                price_val = 0
            if desc or qty_val or price_val:
                items.append({
                    'description': desc,
                    'qty': qty_val,
                    'unit_price': price_val,
                    'subtotal': qty_val * price_val,
                })

        if items or report.cba_items:
            report.cba_items = items
            report.cba_total = sum(item['subtotal'] for item in items)

        forward_checked = request.POST.get('forward_procurement') == '1'
        if forward_checked:
            report.forwarded_to_procurement = True

        if forward_checked:
            report.status = 'closed'
            if not report.accomplished_at:
                report.accomplished_at = timezone.now()
        elif report.status == 'pending':
            report.status = 'in_progress'
            if not report.in_progress_at:
                report.in_progress_at = timezone.now()

        report.save()
    return redirect('adm_report_detail', report_id=report_id)


def report_status(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        report.status = new_status
        if new_status == 'in_progress' and not report.in_progress_at:
            report.in_progress_at = timezone.now()
        elif new_status == 'resolved':
            report.accomplished_at = timezone.now()
        report.save()
    return redirect('adm_report_detail', report_id=report_id)

def ProfileMenu(request):
    return render(request, 'menu-admin.html', {
        "active_page": "ProfileMenu"
})

def universitymap (request):
    return render(request, 'university-map.html', {
        "active_page": "universitymap"
})

CATEGORY_COLORS = {
    'electrical':        '#3B82F6',  # blue
    'plumbing':          '#22C55E',  # green
    'refrigeration_acu': '#06B6D4',  # cyan
    'carpentry_masonry': '#F97316',  # orange
    'painting':          '#A855F7',  # purple
    'vehicle_checkup':   '#EF4444',  # red
    'others':            '#6B7280',  # gray
}

def buildings_api(request):
    data = []
    for building in Building.objects.prefetch_related('floors').all():
        data.append({
            'id': building.id,
            'name': building.name,
            'code': building.code,
            'floors': [
                {
                    'id': f.id,
                    'floor_number': f.floor_number,
                    'label': f.label,
                }
                for f in building.floors.all()
            ]
        })
    return JsonResponse({'buildings': data})

def floor_map_api(request):
    floor_id = request.GET.get('floor_id')
    if not floor_id:
        return JsonResponse({'error': 'floor_id is required'}, status=400)

    floor = get_object_or_404(Floor, id=floor_id)
    rooms = floor.rooms.all()

    category_counts = {
        'electrical': 0,
        'plumbing': 0,
        'refrigeration_acu': 0,
        'carpentry_masonry': 0,
        'painting': 0,
        'vehicle_checkup': 0,
        'others': 0,
    }

    room_data = []
    for room in rooms:
        active_reports = room.get_active_reports()
        categories = room.get_categories()

        # Count per category across all rooms on this floor
        for cat in categories:
            if cat in category_counts:
                category_counts[cat] += 1

        # Build one entry per category for this room
        category_pins = []
        for cat in categories:
            cat_reports = active_reports.filter(category=cat)
            category_pins.append({
                'category': cat,
                'category_display': cat_reports.first().get_category_display(),
                'color': CATEGORY_COLORS.get(cat, '#6B7280'),
                'count': cat_reports.count(),
                'reports': [
                    {
                        'id': r.id,
                        'status': r.get_status_display(),
                        'submitted_at': r.submitted_at.strftime('%b %d, %Y'),
                    }
                    for r in cat_reports
                ]
            })

        room_data.append({
            'id': room.id,
            'name': room.name,
            'x': room.x,
            'y': room.y,
            'active_concerns': active_reports.count(),
            'category_pins': category_pins,  # ← list of pins per category
        })

    return JsonResponse({
        'floor_id': floor.id,
        'floor_label': floor.label,
        'image_url': request.build_absolute_uri(floor.map_image.url),
        'image_width': floor.image_width,
        'image_height': floor.image_height,
        'rooms': room_data,
        'category_counts': category_counts,
    })
