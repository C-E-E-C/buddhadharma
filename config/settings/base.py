"""Configuração comum a todos os ambientes.

Referências §N apontam para docs/ARQUITETURA.md.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

from apps.core.csp import DIRETIVAS, DIRETIVAS_ADMIN, montar_politica

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Variável de ambiente obrigatória ausente: {name}")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(int(default))).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def parse_database_url(url: str) -> dict[str, object]:
    """Converte DATABASE_URL no dicionário que o Django espera.

    Escrito à mão em vez de usar dj-database-url: são vinte linhas e evita
    uma dependência num projeto que deve ser fácil de auditar.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError(f"Apenas PostgreSQL é suportado, recebido: {parsed.scheme!r}")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }


# --------------------------------------------------------------------------
# Núcleo
# --------------------------------------------------------------------------

SECRET_KEY = env("SECRET_KEY")
SECRET_KEY_FALLBACKS = env_list("SECRET_KEY_FALLBACKS")
DEBUG = False
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "apps.core",
    "apps.accounts",
    "apps.forum",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Logo após o SecurityMiddleware: assim a CSP acompanha toda resposta,
    # inclusive as de erro e as de redirecionamento, que também renderizam
    # HTML e também precisam da defesa.
    "apps.core.middleware.ContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# --------------------------------------------------------------------------
# Content-Security-Policy — §7.1
# --------------------------------------------------------------------------

# As diretivas moram em apps/core/csp.py; aqui só se resolve o que depende do
# ambiente. Ver aquele módulo para o porquê de hash em vez de nonce.

# Hashes dos scripts inline servidos pelos templates. Vazio hoje: a Fase 1 não
# tem nenhum JavaScript. O alternador de tema (BD-005) é o primeiro a entrar
# aqui, e apps/core/tests/test_csp.py garante que nenhum script inline chegue
# aos templates sem o hash correspondente nesta tupla.
CSP_SCRIPT_HASHES: tuple[str, ...] = ()

# Com CSP_REPORT_ONLY=1 o navegador relata as violações e não bloqueia nada.
# Serve para validar a política contra tráfego real antes de aplicá-la de
# fato. O padrão é aplicar — uma política que só relata não defende ninguém.
CSP_REPORT_ONLY = env_bool("CSP_REPORT_ONLY", False)

CSP_ADMIN_PREFIX = "/admin/"

CSP_POLICY = montar_politica(DIRETIVAS, CSP_SCRIPT_HASHES)
CSP_POLICY_ADMIN = montar_politica(DIRETIVAS_ADMIN, CSP_SCRIPT_HASHES)

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Banco de dados
# --------------------------------------------------------------------------

DATABASES = {
    "default": parse_database_url(
        env("DATABASE_URL", "postgres://buddhadharma@127.0.0.1:5432/buddhadharma")
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", "redis://127.0.0.1:6379/0"),
        "OPTIONS": {
            # Se o Redis cair, o cache vira no-op em vez de derrubar o site.
            # Disponibilidade acima de rigor — §7.2.
            "IGNORE_EXCEPTIONS": True,
        },
    }
}
DJANGO_REDIS_IGNORE_EXCEPTIONS = True

# --------------------------------------------------------------------------
# Autenticação
# --------------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

# Argon2id à frente — §7.2. Os demais ficam na lista apenas para permitir
# a verificação de hashes antigos durante migração.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# Recuperação de senha — §7.3
# --------------------------------------------------------------------------

# O padrão do Django é 3 dias. Um link de recuperação é credencial de acesso
# total à conta: quanto mais tempo vive numa caixa de email, mais tempo fica
# exposto a quem venha a ler aquela caixa. Duas horas cobre com folga o uso
# real — pedir, abrir o email, escolher a senha.
PASSWORD_RESET_TIMEOUT = 60 * 60 * 2

# Limite de pedidos por janela. Os dois contadores valem ao mesmo tempo: o de
# IP contém quem varre muitos endereços, o de email contém quem escolhe uma
# vítima e enche a caixa dela. Nenhum dos dois distingue email cadastrado de
# não cadastrado, então o limite não vira canal de enumeração.
PASSWORD_RESET_JANELA = 60 * 60
PASSWORD_RESET_LIMITE_POR_IP = 5
PASSWORD_RESET_LIMITE_POR_EMAIL = 3

# Remetente das mensagens automáticas. Em produção precisa ser um endereço do
# próprio domínio, ou o email cai em spam por falha de SPF/DKIM.
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Buddhadharma <nao-responda@localhost>")

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "forum:index"
LOGOUT_REDIRECT_URL = "forum:index"

# --------------------------------------------------------------------------
# Sessão
# --------------------------------------------------------------------------

# Cookie assinado em vez de Redis ou banco — §3.5. A sessão passa a ser válida
# em qualquer região sem replicar estado. Decisão tomada na Fase 0 mesmo
# rodando numa região só, porque trocar depois desloga todo mundo.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30

CSRF_COOKIE_SAMESITE = "Lax"

# --------------------------------------------------------------------------
# Idioma e fuso — §6.4
# --------------------------------------------------------------------------

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
LANGUAGES = [("pt-br", "Português (Brasil)")]
LOCALE_PATHS = [BASE_DIR / "locale"]

# --------------------------------------------------------------------------
# Arquivos estáticos e de mídia
# --------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
}

# --------------------------------------------------------------------------
# Fórum
# --------------------------------------------------------------------------

FORUM_POSTS_PER_PAGE = 20
FORUM_TOPICS_PER_PAGE = 30

# Versão do pipeline de renderização Markdown. Incrementar invalida todo o
# HTML em cache — §4.3. Depois de incrementar:
#   UPDATE forum_post SET body_html = '', html_version = 0 WHERE html_version < N;
FORUM_HTML_VERSION = 1

# --------------------------------------------------------------------------
# Log
# --------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{levelname} {name} {message}", "style": "{"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
