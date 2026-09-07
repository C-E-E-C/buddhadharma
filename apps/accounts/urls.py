from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "accounts"

urlpatterns = [
    path(
        "entrar/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("registrar/", views.register, name="register"),
    # Recuperação de senha — §7.3. Quatro passos: pedir, avisar que saiu,
    # confirmar pelo link e concluir. As views do Django já respondem igual
    # para email cadastrado e não cadastrado; apps/accounts/tests/
    # test_password_reset.py prova que continua assim.
    path(
        "senha/",
        views.PasswordResetView.as_view(
            template_name="accounts/senha_pedir.html",
            email_template_name="accounts/email_senha.txt",
            subject_template_name="accounts/email_senha_assunto.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "senha/enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/senha_enviado.html",
        ),
        name="password_reset_done",
    ),
    path(
        "senha/confirmar/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/senha_confirmar.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "senha/concluida/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/senha_concluido.html",
        ),
        name="password_reset_complete",
    ),
    path("u/<str:username>/", views.profile, name="profile"),
]
