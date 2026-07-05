from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from .forms import ReportForm, UserForm, UserProfileForm, ProfilePhotoForm
import os
from django.http import JsonResponse
from django.conf import settings
from google import genai
from .models import Report, SurveyResponse, UserProfile
from adm.models import Floor, Room
from .validators import validate_password_strength


@login_required
def menu(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

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
                if 'profile_photo' in photo_form.errors:
                    messages.error(request, photo_form.errors['profile_photo'][0])
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
            else:
                password_errors = validate_password_strength(new_password1)
                if password_errors:
                    for err in password_errors:
                        messages.error(request, err)
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
    return render(request, 'user/layouts/base.html', {"active_page": "base"})


@login_required
def userDashboard(request):
    total_reports = Report.objects.filter(user=request.user).count()
    resolved_reports = Report.objects.filter(user=request.user, status='resolved').count()
    recent_reports = Report.objects.filter(user=request.user).order_by('-submitted_at')[:3]
    return render(request, 'user/user_dashboard.html', {
        "active_page": "userDashboard",
        "total_reports": total_reports,
        "resolved_reports": resolved_reports,
        "recent_reports": recent_reports,
    })


@login_required
def reportForm(request):
    if request.method == 'POST':
        form = ReportForm(request.POST, request.FILES)

        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user

            selected_room = form.cleaned_data['location']
            report.location = f"{selected_room.floor.building.name}, {selected_room.floor.label}, {selected_room.name}"

            try:
                from ml.predictor import predict_image

                prediction = predict_image(request.FILES['photo'])

                report.category = prediction['category']
                report.cnn_raw_prediction = prediction['raw_label']
                report.cnn_confidence = prediction['confidence']
                report.cnn_margin = prediction['margin']
                report.flagged_for_review = prediction['flagged_for_review']

            except Exception as error:
                print(f"CNN Prediction Error: {error}")
                messages.error(request, "Unable to analyze the uploaded photo. Please try again.")
                return render(request, 'user/report_form.html', {
                    "active_page": "reportForm",
                    "form": form,
                })

            report.save()

            messages.success(
                request,
                "Your concern has been submitted successfully."
            )

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

@login_required
def userReports(request):
    status_filter = request.GET.get('status', 'all')
    reports = Report.objects.filter(user=request.user).order_by('-submitted_at')
    if status_filter != 'all':
        reports = reports.filter(status=status_filter)
    return render(request, 'user/user_reports.html', {
        "active_page": "userReports",
        "reports": reports,
        "status_filter": status_filter,
    })


@login_required
def reportedIssue(request, report_id):
    report = get_object_or_404(
        Report,
        id=report_id,
        user=request.user
    )

    already_surveyed = SurveyResponse.objects.filter(
        report=report
    ).exists()

    show_survey = (
        report.status == 'resolved'
        and not already_surveyed
    )

    emojis = [
        ('😤', 'Frustrated', 1),
        ('😞', 'Disappointed', 2),
        ('😐', 'Neutral', 3),
        ('😊', 'Pleased', 4),
        ('😄', 'Delighted', 5),
    ]

    return render(request, 'user/reported_issue.html', {
        "active_page": "reportedIssue",
        "report": report,
        "already_surveyed": already_surveyed,
        "show_survey": show_survey,
        "emojis": emojis,
    })


@login_required
def userSurvey(request):
    submitted_surveys = SurveyResponse.objects.filter(
        report__user=request.user
    ).select_related('report').order_by('-submitted_at')

    return render(request, 'user/user_survey.html', {
        "active_page": "userSurvey",
        "submitted_surveys": submitted_surveys,
    })


@login_required
def submitSurvey(request, report_id):
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Invalid request.'
        }, status=400)

    report = get_object_or_404(
        Report,
        id=report_id,
        user=request.user
    )

    rating = request.POST.get('rating')
    feedback = request.POST.get('feedback', '').strip()

    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return JsonResponse({
            'success': False,
            'error': 'Please select a valid rating.'
        }, status=400)

    if rating not in [1, 2, 3, 4, 5]:
        return JsonResponse({
            'success': False,
            'error': 'Rating must be between 1 and 5.'
        }, status=400)

    if SurveyResponse.objects.filter(report=report).exists():
        return JsonResponse({
            'success': False,
            'error': 'You have already submitted a survey for this report.'
        }, status=400)

    SurveyResponse.objects.create(
        report=report,
        rating=rating,
        feedback=feedback,
    )

    return JsonResponse({
        'success': True
    })


def chatbot(request):
    return render(request, 'user/components/chatbot.html')


UDM_FAQ_DATA = """
OFFICIAL FAQ KNOWLEDGE BASE FOR KUHAMO SYSTEM (UDM):
1. What is KuhaMo?
- KuhaMo is an automated facility concern reporting system for Universidad de Manila (UDM). It allows students, faculty, and staff to report campus defects
using AI-powered image classification to streamline university maintenance.
2. Who can use this system?
- All official UDM stakeholders, including active students, professors, and university administrative staff can log in and submit facility reports.
3. How do I report a broken facility or equipment?
- First, log in to your KuhaMo account then go to the report submission page. After that, upload a clear photo of the defect and select the room location. Lastly, submit the report.
4. Why did my report get rejected?
- The system requires a clear image of the actual defect for the CNN Classification Engine to analyze it properly. Ensure your photo is not blurry, dark,
or unrelated to a facility concern. The file size must also be within the allowed system limit.
5. Can I edit or delete my report after submission?
- No. Once a report is submitted, it is locked to preserve data integrity and immediately routed to the Supply and Equipment Office. If you made
a critical mistake, please contact the administrator to cancel the report.
6. How do I check the status of my report?
- You can monitor your submitted concerns in real-time through your Dashboard page. Each report will display its current stage in the maintenance workflow.
7. What do the different report statuses mean?
- "Pending" means your report has been successfully submitted and is waiting for administrator validation. "In Progress" indicates that the maintenance team has acknowledged the issue and is actively
working on repair. "Resolved" means the defect has been fixed or addressed. "Closed" means the item has been forwarded to procurement.
8. What should I do if my account gets locked?
- For security reasons, our system utilizes security throttling that temporarily locks an account after multiple failed login attempts
to prevent unauthorized access. Please wait a few minutes before trying again, or contact IT support to reset your credentials.
9. Is my personal information safe in the system?
- Yes. The system employs HTTPS data encryption and secure Role-Based Access Controls to ensure that your personal profile and submitted data are strictly protected
and only accessible to authorized university personnel.
"""


def chatbot_response(request):
    if request.method == 'POST':
        user_message = request.POST.get('message', '').strip()
        if not user_message:
            return JsonResponse({'reply': "Please enter a message."})
        try:
            api_key = getattr(settings, "GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
            client = genai.Client(api_key=api_key)
            system_instruction = (
                "You are KM Bot, the official automated chat assistant for the KuhaMo system at Universidad de Manila (UDM). \n\n"
                "STRICT RULES: \n"
                "1. Answer the query strictly using the facts stated inside the OFFICIAL FAQ KNOWLEDGE BASE FOR KUHAMO SYSTEM (UDM) provided below. \n"
                "2. Do NOT use outside knowledge. If the answer cannot be found in the text document below, "
                "you are strictly prohibited from guessing or fabricating details. Instead, reply word-for-word: "
                "'Sorry, I don't have the information you're looking for.' \n\n"
                "3. Keep responses concise, helpful, and match the language used by the user (Tagalog, English, or a mix of both). \n\n"
                f"OFFICIAL FAQ KNOWLEDGE BASE FOR KUHAMO SYSTEM (UDM): \n{UDM_FAQ_DATA}"
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_message,
                config={
                    'system_instruction': system_instruction,
                    'temperature': 0.1,
                }
            )
            return JsonResponse({'reply': response.text})
        except Exception as e:
            print(f"Error encountered: {e}")
            return JsonResponse({'reply': "Sorry, I'm having trouble processing your request right now."})
    return JsonResponse({'error': 'Invalid request'}, status=400)

#AJAX VIEWS FOR THE DROPDOWN
def load_floors(request):
    building_id = request.GET.get('building')
    floors = Floor.objects.filter(building_id=building_id).order_by('floor_number')
    return JsonResponse(list(floors.values('id', 'label')), safe=False)

def load_rooms(request):
    floor_id = request.GET.get('floor')
    rooms = Room.objects.filter(floor_id=floor_id).order_by('name')
    return JsonResponse(list(rooms.values('id','name', 'code')), safe=False)