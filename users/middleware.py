from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib import messages
from core.translations import get_translation

class CompanyMiddleware(MiddlewareMixin):
    """
    Middleware to ensure users are associated with a company.
    Redirects users without a company to appropriate pages.
    """
    
    def process_request(self, request):
        # Only process authenticated users
        if not request.user.is_authenticated:
            return None
        
        # Allow superusers to access everything
        if request.user.is_superuser:
            return None
        
        # Check if user has a company
        if not request.user.company:
            # Allow access to certain URLs without company
            allowed_urls = [
                '/users/profile/',
                '/users/change-password/',
                '/logout/',
                '/admin/',
            ]
            
            if not any(request.path.startswith(url) for url in allowed_urls):
                lang = request.session.get('language', 'uz')
                messages.warning(request, get_translation('no_company_assigned', lang))
                return redirect('users:profile')
        
        return None
