"""Configuración local de demostración; mantiene separada la base habitual."""

from copy import deepcopy

from decouple import config

from .settings import *

DATABASES = deepcopy(DATABASES)
DATABASES['default']['NAME'] = config('DB_NAME_DEMO', default='restaurante_demo')
DEMO_MODE = True
DEBUG = True
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_NAME = 'restaurante_demo_session'
CSRF_COOKIE_NAME = 'restaurante_demo_csrf'
ALLOWED_HOSTS = ['localhost', '127.0.0.1']
