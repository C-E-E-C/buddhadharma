from typing import TYPE_CHECKING

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import User
from .validators import username_skeleton

if TYPE_CHECKING:
    _RegistrationBase = UserCreationForm[User]
else:
    _RegistrationBase = UserCreationForm


class RegistrationForm(_RegistrationBase):
    class Meta:
        model = User
        fields = ["username", "display_name", "email"]

    def clean_username(self) -> str:
        username = str(self.cleaned_data["username"])
        # Checagem antecipada só para dar mensagem decente. A garantia real é
        # o UNIQUE em username_skeleton — esta consulta perderia a corrida
        # entre dois registros simultâneos (§6.3).
        if User.objects.filter(username_skeleton=username_skeleton(username)).exists():
            raise forms.ValidationError(
                _("Já existe um nome de usuário parecido demais com este."),
                code="username_confusavel",
            )
        return username

    def clean_email(self) -> str:
        email = str(self.cleaned_data["email"]).lower().strip()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_("Este email já está em uso."), code="email_duplicado")
        return email
