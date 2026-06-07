from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from .forms import ReportForm, get_location_choices, UserForm, UserProfileForm, ProfilePhotoForm
from .models import Report


@login_required
def menu(request):
    profile = request.user.profile

    user_form = UserForm(instance=request.user)
    profile_form = UserProfileForm(instance=profile)
    photo_form = ProfilePhotoForm(instance=profile)

    if request.method == 'POST':
        if 'save_info' in request.POST:
            user_form = UserForm(request.POST, instance=request.user)
            profile_form = UserProfileForm(request.POST, instance=profile)

            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, "Profile Updated Successfully")
                return redirect('menu')
            else:
                messages.error(request, f"Errors: {user_form.errors}| {profile_form.errors}")
        
        elif 'save_photo' in request.POST:
            photo_form = ProfilePhotoForm(request.POST, request.FILES, instance=profile)

            if photo_form.is_valid():
                photo_form.save()
                messages.success(request, "Profile Photo Updated Successfully")
                return redirect('menu')
            else:
                messages.error(request, "Please upload a valid photo.")

        elif 'remove_photo' in request.POST:
            profile.profile_photo.delete(save=True)
            messages.success(request, "Profile Photo Removed Successfully")
            return redirect('menu')

        elif 'change_password' in request.POST:
            old_password = request.POST.get('old_password')
            new_password1 = request.POST.get('new_password1')
            new_password2 = request.POST.get('new_password2')

            if not request.user.check_password(old_password):
                messages.error(request, "Old password is incorrect.")
            elif new_password1 != new_password2:
                messages.error(request, "New passwords do not match.")
            elif len(new_password1) < 8:
                messages.error(request, "New password must be at least 8 characters long.")
            else:
                request.user.set_password(new_password1)
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, "New password saved successfully!", extra_tags='password_changed')
                return redirect('menu')
            
    return render(request, 'user/menu.html', {
        "active_page": "menu",
        "user_form": user_form,
        "profile_form": profile_form,
        "photo_form": photo_form,
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