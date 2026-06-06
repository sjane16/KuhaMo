from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .forms import ReportForm, get_location_choices
from .models import Report


def menu(request):
    return render(request, 'user/menu.html', {
        "active_page": "menu"
    })


def base(request):
    return render(request, 'user/layouts/base.html', {
        "active_page": "base"
    })


def userDashboard(request):
    total_reports = Report.objects.count()
    resolved_reports = Report.objects.filter(status='resolved').count()
    recent_reports = Report.objects.all().order_by('-submitted_at')[:3]

    return render(request, 'user/user_dashboard.html', {
        "active_page": "userDashboard",
        "total_reports": total_reports,
        "resolved_reports": resolved_reports,
        "recent_reports": recent_reports,
    })


def reportForm(request):
    if request.method == 'POST':
        form = ReportForm(request.POST, request.FILES)

        if form.is_valid():
            report = form.save(commit=False)

            selected_value = form.cleaned_data['location']
            location_map = dict(get_location_choices())
            report.location = location_map.get(selected_value, selected_value)

            report.save()

            messages.success(request, "Your concern has been submitted successfully.")
            return redirect('userReports')

        if 'photo' in form.errors:
            messages.error(request, "Please upload a photo of the concern.")
        else:
            messages.error(request, "Please complete all required fields.")

    else:
        form = ReportForm()

    return render(request, 'user/report_form.html', {
        "active_page": "reportForm",
        "form": form,
    })


def userReports(request):
    status_filter = request.GET.get('status', 'all')
    reports = Report.objects.all().order_by('-submitted_at')

    if status_filter != 'all':
        reports = reports.filter(status=status_filter)

    return render(request, 'user/user_reports.html', {
        "active_page": "userReports",
        "reports": reports,
        "status_filter": status_filter,
    })


def reportedIssue(request, report_id):
    report = get_object_or_404(Report, id=report_id)

    return render(request, 'user/reported_issue.html', {
        "active_page": "reportedIssue",
        "report": report,
    })