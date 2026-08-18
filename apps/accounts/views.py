from __future__ import annotations

from django.contrib.auth import login
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.forum.models import Post

from .forms import RegistrationForm
from .models import User


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
