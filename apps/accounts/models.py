"""Modelo de usuário — §4.1 da arquitetura.

``AbstractBaseUser`` em vez de ``AbstractUser``: o modelo padrão do Django traz
``first_name``/``last_name``, que não fazem sentido aqui, e um validador de
``username`` que aceita coisas que §6.3 proíbe. Definir o modelo por extenso
custa pouco e deixa explícito o que é identidade e o que é apresentação.

Modelo customizado desde a primeira migração. Trocar o modelo de usuário depois
que o projeto tem dados é uma das migrações mais dolorosas do Django — por isso
está na Fase 0, antes de existir qualquer usuário.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.text import NFCCharField, NFCTextField, normalize_nfc

from .validators import (
    USERNAME_MAX_LENGTH,
    username_skeleton,
    validate_display_name,
    validate_username,
)

# Intervalo mínimo entre gravações de `last_seen_at`. Atualizar a cada
# requisição transformaria toda leitura numa escrita — o que envia tráfego ao
# primário e infla o WAL, o recurso mais escasso quando houver replicação (§4.1).
LAST_SEEN_THROTTLE = timedelta(minutes=5)


class TrustLevel(models.IntegerChoices):
    """Níveis de confiança — §7.4.

    Resolve spam estruturalmente, sem CAPTCHA e sem serviço externo: o custo de
    uma conta descartável passa a ser tempo real de leitura.
    """

    NEW = 0, _("Novo")
    BASIC = 1, _("Básico")
    MEMBER = 2, _("Membro")
    REGULAR = 3, _("Regular")
    MODERATOR = 4, _("Moderador")


class UserManager(BaseUserManager["User"]):
    def create_user(
        self, username: str, email: str, password: str | None = None, **extra: Any
    ) -> User:
        if not username:
            raise ValueError("Nome de usuário é obrigatório.")
        if not email:
            raise ValueError("Email é obrigatório.")
        extra.setdefault("display_name", username)
        user = self.model(
            username=normalize_nfc(username), email=self.normalize_email(email), **extra
        )
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_superuser(
        self, username: str, email: str, password: str | None = None, **extra: Any
    ) -> User:
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("trust_level", TrustLevel.MODERATOR)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Superusuário exige is_staff e is_superuser.")
        return self.create_user(username, email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    # --- Identidade ------------------------------------------------------
    # Conjunto restrito de caracteres, usado em login, URL e menção.
    # Ver validators.py para o porquê de não aceitar Unicode livre.
    username = NFCCharField(
        _("nome de usuário"),
        max_length=USERNAME_MAX_LENGTH,
        unique=True,
        validators=[validate_username],
        help_text=_("Minúsculas, números, ponto, hífen e sublinhado. Acentos aceitos."),
    )

    # Forma visualmente canônica do username. É esta coluna que carrega a
    # garantia contra homóglifos, e a garantia vem do UNIQUE do banco — não de
    # uma consulta na aplicação, que perderia a corrida entre dois registros
    # simultâneos. Preenchida em save(), nunca editada à mão.
    username_skeleton = models.CharField(
        max_length=USERNAME_MAX_LENGTH, unique=True, editable=False
    )

    # --- Apresentação ----------------------------------------------------
    # Unicode livre. NUNCA usado em autenticação ou autorização.
    display_name = NFCCharField(
        _("nome exibido"), max_length=60, validators=[validate_display_name]
    )

    email = models.EmailField(_("email"), unique=True)

    bio = NFCTextField(_("apresentação"), blank=True, max_length=2000)
    avatar = models.ImageField(_("avatar"), upload_to="avatares/", blank=True, null=True)

    # --- Estado ----------------------------------------------------------
    trust_level = models.PositiveSmallIntegerField(
        _("nível de confiança"), choices=TrustLevel.choices, default=TrustLevel.NEW
    )
    post_count = models.PositiveIntegerField(_("posts"), default=0, editable=False)

    is_active = models.BooleanField(_("ativo"), default=True)
    is_staff = models.BooleanField(_("acessa o admin"), default=False)
    created_at = models.DateTimeField(_("criado em"), default=timezone.now, editable=False)
    last_seen_at = models.DateTimeField(_("visto por último"), null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = _("usuário")
        verbose_name_plural = _("usuários")
        ordering = ["username"]

    def __str__(self) -> str:
        return self.username

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.username = normalize_nfc(self.username)
        self.username_skeleton = username_skeleton(self.username)
        self.email = self.email.lower().strip()
        if not self.display_name:
            self.display_name = self.username
        super().save(*args, **kwargs)

    def get_full_name(self) -> str:
        return self.display_name

    def get_short_name(self) -> str:
        return self.display_name

    @property
    def is_moderator(self) -> bool:
        """Único ponto que decide autoridade de moderação.

        Note que olha `trust_level` e `is_staff` — nunca `display_name`.
        """
        return self.is_staff or self.trust_level >= TrustLevel.MODERATOR

    def touch_last_seen(self) -> None:
        """Atualiza `last_seen_at`, no máximo uma vez a cada LAST_SEEN_THROTTLE."""
        now = timezone.now()
        if self.last_seen_at and now - self.last_seen_at < LAST_SEEN_THROTTLE:
            return
        self.last_seen_at = now
        User.objects.filter(pk=self.pk).update(last_seen_at=now)
