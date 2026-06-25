from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from user.models import Report


def dashboard(request):
    pending = Report.objects.filter(status='pending').count()
    in_progress = Report.objects.filter(status='in_progress').count()
    resolved_thisweek = Report.objects.filter(status='resolved').count()
    avg_satisfaction = 4.5

    satisfaction_labels = ["5-Outstanding", "4-Very Satisfactory", "3-Satisfactory", "2-Fair", "1-Unsatisfactory"]
    satisfaction_counts = [40, 30, 20, 7, 3]
    categories = ["Vehicle Check-up", "Electrical", "Refrigeration / ACU's", "Painting", "Carpentry/Masonry", "Plumbing"]
    categories_counts = [12, 9, 7, 5, 4, 3]
    location = ["Room 101", "Room 202", "Room 303", "Room 404", "Room 302", "Library"]
    location_counts = [8, 6, 5, 4, 3, 2]
    resolution_weeks = ["Week 1", "Week 2", "Week 3", "Week 4"]
    expected_hours = [24, 22, 20, 18]
    actual_hours = [20, 15, 14, 8]

    return render(request, 'dashboard.html', {
        'pending': pending,
        'in_progress': in_progress,
        'resolved_thisweek': resolved_thisweek,
        'avg_satisfaction': avg_satisfaction,
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