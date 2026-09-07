"""Configuração de produção."""

from .base import *
from .base import env, env_bool, env_list

DEBUG = False
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")

# §7.2 — cabeçalhos e cookies. O proxy à frente termina o TLS.
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host and "*" not in host]

# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------
# Sem SMTP configurado, a recuperação de senha (§7.3) falha em silêncio: a
# página diz que o link foi enviado e nenhum email sai. As variáveis estão
# documentadas em .env.example.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 10
