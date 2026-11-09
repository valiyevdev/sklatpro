from django.shortcuts import render, redirect

from django.contrib.auth.decorators import login_required

from django.contrib import messages

from django.core.paginator import Paginator

from django.views.decorators.cache import never_cache

from core.translations import get_translation

from .models import Activity



@login_required

@never_cache

def activity_timeline(request):

    # Get company

    company = request.user.company

    lang = request.session.get('language', 'uz')

    if not company and not request.user.is_superuser:

        messages.error(request, get_translation('no_company_assigned', lang))

        return redirect('login')

    

    # Filter by company

    if company:

        activities = Activity.objects.filter(company=company).select_related('user')

    else:

        # Superuser sees all

        activities = Activity.objects.select_related('user').all()

    

    # Filter by user role

    if not request.user.is_superuser and not request.user.is_company_admin():

        # Staff and viewers see only their own activities

        if request.user.is_staff_user() or request.user.is_viewer():

            activities = activities.filter(user=request.user)

        # Managers see all activities in their company (already filtered above)

    

    # Filter by activity type

    activity_type = request.GET.get('type', '')

    if activity_type:

        activities = activities.filter(activity_type=activity_type)

    

    paginator = Paginator(activities, 50)

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)

    

    context = {

        'page_obj': page_obj,

        'activity_type': activity_type,

        'company': company,

    }

    return render(request, 'activity/activity_timeline.html', context)



