from django.shortcuts import render

def base(request):
    return render(request, 'layouts/base.html', {
        "active_page": "base"
    })

def dashboard(request):

    pending = 3
    in_progress = 2
    resolved_thisweek = 2
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

    context = {
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
    }

    return render(request, 'dashboard.html', context)