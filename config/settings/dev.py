"""Configuração de desenvolvimento. Nunca use em produção."""

from .base import *
from .base import env_bool

DEBUG = env_bool("DEBUG", True)

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Argon2 continua ativo aqui, herdado de base.py. Enfraquecer o hashing só
# para acelerar acontece em config/settings/test.py, que nunca serve tráfego.
