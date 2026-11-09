import threading
from .translations import get_translation, DEFAULT_LANGUAGE

_local = threading.local()


def set_active_lang(lang):
    _local.lang = lang


def active_lang():
    return getattr(_local, 'lang', None)


class PlaceholderRef:
    __slots__ = ('key',)

    def __init__(self, key):
        self.key = key

    def __str__(self):
        return get_translation(self.key, active_lang())


def ph(key):
    return PlaceholderRef(key)