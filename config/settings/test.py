"""Configuração usada pela suíte de testes."""

from .dev import *

DEBUG = False

# Argon2 é lento de propósito. Numa suíte que cria centenas de usuários isso
# domina o tempo total sem testar nada. Só aqui — este módulo nunca serve tráfego.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
