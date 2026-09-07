from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from apps.forum.models import Post

from .forms import RegistrationForm
from .models import User
from .ratelimit import excedeu


def register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("forum:index")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user = form.save()
        except IntegrityError:
            # O UNIQUE de username_skeleton disparou: outro registro chegou
            # primeiro entre a validação e a gravação. É o caminho esperado
            # numa corrida, não um erro do servidor.
            form.add_error("username", "Este nome de usuário acabou de ser tomado.")
        else:
            login(request, user)
            return redirect("forum:index")

    return render(request, "accounts/register.html", {"form": form})


def profile(request: HttpRequest, username: str) -> HttpResponse:
    user = get_object_or_404(User, username=username, is_active=True)
    recent = Post.objects.filter(author=user).select_related("topic").order_by("-created_at")[:20]
    return render(request, "accounts/profile.html", {"profile_user": user, "recent_posts": recent})


class PasswordResetView(auth_views.PasswordResetView):
    """Pedido de recuperação, com limite de taxa por IP e por email — §7.3.

    A view do Django já responde igual para email cadastrado e não cadastrado,
    que é a parte que costuma vazar quem tem conta. O que falta aqui é conter
    o abuso: sem limite, o formulário vira gerador de email para endereço
    alheio, e o custo é do fórum.

    **O limite não distingue email existente de inexistente.** Conta-se a
    tentativa antes de saber se há conta, então o atacante não aprende nada
    com o fato de ter sido limitado.

    Quando o limite estoura, a resposta diz isso claramente em vez de fingir
    que o email saiu. Fingir protegeria contra nada — o limite independe de
    existir conta — e deixaria quem esqueceu a senha esperando por um email
    que nunca vem.
    """

    def form_valid(self, form: Any) -> HttpResponse:
        email = form.cleaned_data["email"]
        # REMOTE_ADDR, não X-Forwarded-For: o cabeçalho é escrito pelo cliente
        # e só vale se um proxy conhecido o reescrever. Enquanto não houver
        # essa configuração, confiar nele seria dar ao atacante o poder de
        # trocar de identidade a cada pedido — e o limite por IP viraria enfeite.
        ip = self.request.META.get("REMOTE_ADDR", "")

        estourou = [
            excedeu(
                "senha-ip",
                ip,
                limite=settings.PASSWORD_RESET_LIMITE_POR_IP,
                janela=settings.PASSWORD_RESET_JANELA,
            ),
            excedeu(
                "senha-email",
                email,
                limite=settings.PASSWORD_RESET_LIMITE_POR_EMAIL,
                janela=settings.PASSWORD_RESET_JANELA,
            ),
        ]
        # Os dois contadores são consultados sempre, e não em curto-circuito:
        # parar no primeiro deixaria o segundo sem registrar a tentativa.
        if any(estourou):
            form.add_error(
                None,
                _("Pedidos demais em pouco tempo. Espere alguns minutos antes de tentar de novo."),
            )
            return self.form_invalid(form)

        return super().form_valid(form)
