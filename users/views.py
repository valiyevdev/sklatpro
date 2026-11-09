from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from .models import User, Company
from .forms import (
    CompanyRegistrationForm, UserRegistrationForm, CustomPasswordChangeForm,
    CustomPasswordResetForm, CustomSetPasswordForm, UserUpdateForm,
    EmployeeCreateForm, EmployeeUpdateForm
)
from django.core.paginator import Paginator
from core.translations import get_translation


@csrf_protect
@require_http_methods(["GET", "POST"])
def register(request):
    """
    Company registration view - creates Company and Company Owner Account
    """
    lang = request.session.get('language', 'uz')
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        company_form = CompanyRegistrationForm(request.POST, language=lang)
        user_form = UserRegistrationForm(request.POST, language=lang)

        if company_form.is_valid() and user_form.is_valid():
            try:
                with transaction.atomic():
                    # Create company
                    company = company_form.save(commit=False)
                    company.is_active = True
                    company.is_verified = False
                    company.subscription_plan = 'free'
                    company.save()

                    # Create company owner
                    user = user_form.save(commit=False)
                    user.company = company
                    user.role = 'COMPANY_ADMIN'
                    user.is_active = True
                    user.save()
            except IntegrityError:
                messages.error(request, get_translation('registration_failed', lang))
                return render(request, 'registration/register.html', {
                    'company_form': company_form,
                    'user_form': user_form
                })

            # Log the user in
            authenticated_user = authenticate(request, username=user.email, password=user_form.cleaned_data['password1'])
            if authenticated_user:
                login(request, authenticated_user)
                messages.success(request, get_translation('registration_success', lang))
                return redirect('dashboard')
    else:
        company_form = CompanyRegistrationForm(language=lang)
        user_form = UserRegistrationForm(language=lang)
    
    return render(request, 'registration/register.html', {
        'company_form': company_form,
        'user_form': user_form
    })


@login_required
@never_cache
def profile(request):
    """
    User profile view
    """
    lang = request.session.get('language', 'uz')
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, get_translation('profile_updated', lang))
            return redirect('users:profile')
    else:
        form = UserUpdateForm(instance=request.user)
    
    return render(request, 'users/profile.html', {
        'form': form,
        'user': request.user
    })


@login_required
@never_cache
def change_password(request):
    """
    Change password view
    """
    lang = request.session.get('language', 'uz')
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, get_translation('password_changed', lang))
            return redirect('users:change_password')
    else:
        form = CustomPasswordChangeForm(request.user)
    
    return render(request, 'users/change_password.html', {
        'form': form
    })


def password_reset_request(request):
    """
    Password reset request view
    """
    lang = request.session.get('language', 'uz')
    if request.method == 'POST':
        form = CustomPasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                reset_url = f"{request.scheme}://{request.get_host()}/reset/{uid}/{token}/"
                try:
                    send_mail(
                        get_translation('password_reset_subject', lang),
                        get_translation('password_reset_body', lang).format(reset_url=reset_url),
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=False,
                    )
                    messages.success(request, get_translation('password_reset_link_sent', lang))
                except Exception:
                    messages.warning(request, get_translation('password_reset_link_sent', lang))
                return render(request, 'registration/password_reset_done.html')
            except User.DoesNotExist:
                messages.error(request, get_translation('user_not_found', lang))
    else:
        form = CustomPasswordResetForm()
    
    return render(request, 'registration/password_reset.html', {
        'form': form
    })


def password_reset_confirm(request, uidb64, token):
    """
    Password reset confirm view
    """
    lang = request.session.get('language', 'uz')
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = CustomSetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, get_translation('password_reset_success', lang))
                return render(request, 'registration/password_reset_complete.html')
        else:
            form = CustomSetPasswordForm(user)
        
        return render(request, 'registration/password_reset_confirm.html', {
            'form': form
        })
    else:
        messages.error(request, get_translation('password_reset_invalid', lang))
        return redirect('users:password_reset')


@login_required
@never_cache
def employee_list(request):
    """
    Employee list view - only for Company Admin
    """
    lang = request.session.get('language', 'uz')
    if not request.user.is_superuser and not request.user.is_company_admin():
        messages.error(request, get_translation('no_permission', lang))
        return redirect('dashboard')
    
    company = request.user.company
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('dashboard')
    
    employees = User.objects.filter(company=company, is_deleted=False).exclude(id=request.user.id) if company else User.objects.filter(is_deleted=False, is_superuser=False).exclude(id=request.user.id)
    
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')
    
    if search_query:
        employees = employees.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    if role_filter:
        employees = employees.filter(role=role_filter)
    
    paginator = Paginator(employees, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'users/employee_list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
    })


@login_required
@never_cache
def employee_create(request):
    """
    Employee create view - only for Company Admin
    """
    lang = request.session.get('language', 'uz')
    if not request.user.is_superuser and not request.user.is_company_admin():
        messages.error(request, get_translation('no_permission', lang))
        return redirect('dashboard')
    
    company = request.user.company
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = EmployeeCreateForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.company = company
            employee.is_active = True
            employee.save()
            messages.success(request, f'{employee.get_full_name()} muvaffaqiyatli qo\'shildi!')
            return redirect('users:employee_list')
    else:
        form = EmployeeCreateForm()
    
    return render(request, 'users/employee_form.html', {
        'form': form,
        'title': 'Xodim qo\'shish'
    })


@login_required
@never_cache
def employee_update(request, pk):
    lang = request.session.get('language', 'uz')
    if not request.user.is_superuser and not request.user.is_company_admin():
        messages.error(request, get_translation('no_permission', lang))
        return redirect('dashboard')
    
    company = request.user.company
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('dashboard')
    
    employee = get_object_or_404(User, pk=pk) if request.user.is_superuser else get_object_or_404(User, pk=pk, company=company)
    
    if request.method == 'POST':
        form = EmployeeUpdateForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, f'{employee.get_full_name()} muvaffaqiyatli yangilandi!')
            return redirect('users:employee_list')
    else:
        form = EmployeeUpdateForm(instance=employee)
    
    return render(request, 'users/employee_form.html', {
        'form': form,
        'employee': employee,
        'title': 'Xodimni tahrirlash'
    })


@login_required
@never_cache
def employee_delete(request, pk):
    lang = request.session.get('language', 'uz')
    if not request.user.is_superuser and not request.user.is_company_admin():
        messages.error(request, get_translation('no_permission', lang))
        return redirect('dashboard')
    
    company = request.user.company
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('dashboard')
    
    employee = get_object_or_404(User, pk=pk) if request.user.is_superuser else get_object_or_404(User, pk=pk, company=company)
    
    if request.method == 'POST':
        employee.soft_delete()
        messages.success(request, f'{employee.get_full_name()} muvaffaqiyatli o\'chirildi!')
        return redirect('users:employee_list')
    
    return render(request, 'users/employee_confirm_delete.html', {
        'employee': employee
    })


@login_required
@never_cache
def employee_reset_password(request, pk):
    lang = request.session.get('language', 'uz')
    if not request.user.is_superuser and not request.user.is_company_admin():
        messages.error(request, get_translation('no_permission', lang))
        return redirect('dashboard')
    
    company = request.user.company
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('dashboard')
    
    employee = get_object_or_404(User, pk=pk) if request.user.is_superuser else get_object_or_404(User, pk=pk, company=company)
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        if new_password:
            employee.set_password(new_password)
            employee.save()
            messages.success(request, f'{employee.get_full_name()} paroli muvaffaqiyatli tiklandi!')
            return redirect('users:employee_list')
    
    return render(request, 'users/employee_reset_password.html', {
        'employee': employee
    })
