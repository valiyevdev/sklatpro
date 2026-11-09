from django.utils.deprecation import MiddlewareMixin
from .translations import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from .lang import set_active_lang


class LanguageMiddleware(MiddlewareMixin):
    """Handle language selection via session, cookie, or query parameter."""

    def process_request(self, request):
        # Priority: query param > session > cookie > default
        lang = request.GET.get('lang')

        if lang and lang in SUPPORTED_LANGUAGES:
            request.session['language'] = lang
            request.LANGUAGE_CODE = lang
        elif 'language' in request.session and request.session['language'] in SUPPORTED_LANGUAGES:
            request.LANGUAGE_CODE = request.session['language']
        elif request.COOKIES.get('language') and request.COOKIES.get('language') in SUPPORTED_LANGUAGES:
            request.LANGUAGE_CODE = request.COOKIES.get('language')
            request.session['language'] = request.LANGUAGE_CODE
        else:
            request.LANGUAGE_CODE = DEFAULT_LANGUAGE
            request.session['language'] = DEFAULT_LANGUAGE

        set_active_lang(request.LANGUAGE_CODE)
        return None

    def process_response(self, request, response):
        if hasattr(request, 'LANGUAGE_CODE'):
            response.set_cookie('language', request.LANGUAGE_CODE, max_age=60 * 60 * 24 * 365)
        return response
