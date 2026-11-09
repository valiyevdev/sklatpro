from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.http import HttpResponse
from django.utils.http import url_has_allowed_host_and_scheme
from users.views import register
from core.translations import get_translation

User = get_user_model()

@csrf_protect
@require_http_methods(["GET", "POST"])
def custom_login(request):
    """
    Custom login view with detailed error handling and professional authentication flow.
    """
    lang = request.session.get('language', 'uz')
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('username', '').strip()  # Form field is still named 'username' for compatibility
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me') == 'on'
        
        # Check if fields are empty
        if not email and not password:
            messages.error(request, get_translation('login_fields_required', lang))
            return render(request, 'registration/login.html', {
                'error': get_translation('login_fields_required', lang),
                'username': email
            })
        
        if not email:
            messages.error(request, get_translation('login_email_required', lang))
            return render(request, 'registration/login.html', {
                'error': get_translation('login_email_required', lang),
                'username': email
            })
        
        if not password:
            messages.error(request, get_translation('login_password_required', lang))
            return render(request, 'registration/login.html', {
                'error': get_translation('login_password_required', lang),
                'username': email
            })
        
        # Authenticate user (AxesBackend + ModelBackend)
        authenticated_user = authenticate(request, username=email, password=password)

        if authenticated_user is not None:
            if not authenticated_user.is_active:
                messages.error(request, get_translation('account_deactivated', lang))
                return render(request, 'registration/login.html', {
                    'error': get_translation('account_deactivated', lang),
                    'username': email
                })

            login(request, authenticated_user)

            try:
                from saas_platform.models import AuditLog
                AuditLog.objects.create(
                    company=getattr(authenticated_user, 'company', None),
                    user=authenticated_user,
                    action='login',
                    resource_type='user',
                    resource_id=str(authenticated_user.pk),
                    resource_name=authenticated_user.email,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=str(request.META.get('HTTP_USER_AGENT', ''))[:500],
                    request_id=getattr(request, 'request_id', ''),
                )
            except Exception:
                pass

            if not remember_me:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(1209600)

            messages.success(request, get_translation('login_success', lang))
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                return redirect(next_url)
            return redirect('dashboard')
        else:
            messages.error(request, get_translation('incorrect_password', lang))
            return render(request, 'registration/login.html', {
                'error': get_translation('incorrect_password', lang),
                'username': email
            })
    
    return render(request, 'registration/login.html')


@never_cache
def custom_logout(request):
    lang = request.session.get('language', 'uz')
    if request.user.is_authenticated:
        messages.success(request, get_translation('logout_success', lang))
        logout(request)

    response = redirect('login')
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@never_cache
def welcome(request):
    """
    Fullscreen Telegram-style onboarding slider shown to all guests.
    Serves the primary root route ('/' and '/welcome/'):
      - NOT logged in -> ALWAYS render the onboarding slider (refresh-agnostic).
      - Logged in     -> redirect to the primary dashboard.
    `?next=login|register` shortcuts from Skip / "Tizimga kirish" / "Boshlash"
    land the user on the target page immediately.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    next_to = request.GET.get('next')
    if next_to in ('login', 'register'):
        return redirect(next_to)

    return render(request, 'welcome/onboarding.html')
