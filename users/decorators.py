from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from core.translations import get_translation


def company_admin_required(view_func):
    """
    Decorator to restrict access to Company Admin only
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if not request.user.is_company_admin():
            lang = request.session.get('language', 'uz')
            messages.error(request, get_translation('no_permission_admin', lang))
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def manager_required(view_func):
    """
    Decorator to restrict access to Managers and above
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if not (request.user.is_company_admin() or request.user.is_manager()):
            lang = request.session.get('language', 'uz')
            messages.error(request, get_translation('no_permission_manager', lang))
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def staff_required(view_func):
    """
    Decorator to restrict access to Staff and above
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if not (request.user.is_company_admin() or request.user.is_manager() or request.user.is_staff_user()):
            lang = request.session.get('language', 'uz')
            messages.error(request, get_translation('no_permission', lang))
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def company_required(view_func):
    """
    Decorator to ensure user belongs to a company
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if not request.user.company and not request.user.is_superuser:
            lang = request.session.get('language', 'uz')
            messages.error(request, get_translation('no_company_assigned', lang))
            return redirect('login')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def active_user_required(view_func):
    """
    Decorator to ensure user account is active
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if not request.user.is_active:
            lang = request.session.get('language', 'uz')
            messages.error(request, get_translation('account_deactivated', lang))
            return redirect('login')
        
        return view_func(request, *args, **kwargs)
    return wrapper
