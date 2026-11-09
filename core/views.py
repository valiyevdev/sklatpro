from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .translations import SUPPORTED_LANGUAGES


@require_POST
def set_language(request):
    """AJAX endpoint to switch language."""
    lang = request.POST.get('language') or request.GET.get('language')
    if lang and lang in SUPPORTED_LANGUAGES:
        request.session['language'] = lang
        return JsonResponse({'status': 'ok', 'language': lang})
    return JsonResponse({'status': 'error', 'message': 'Invalid language'}, status=400)
