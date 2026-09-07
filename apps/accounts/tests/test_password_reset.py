"""Testes da recuperação de senha — §7.3.

O ponto sensível não é o fluxo funcionar, é ele não contar quem tem conta.
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from django.core import mail
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User

CADASTRADO = "ananda@exemplo.org"
NAO_CADASTRADO = "ninguem@exemplo.org"


@pytest.fixture(autouse=True)
def _cache_limpo():
    # O limite de taxa vive no cache e atravessaria os testes.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def usuario(db) -> User:
    return User.objects.create_user(
        username="ananda", email=CADASTRADO, display_name="Ānanda", password="senha-antiga-longa"
    )


def _pedir(client: Client, email: str):
    return client.post(reverse("accounts:password_reset"), {"email": email})


def _link_do_email() -> str:
    corpo = mail.outbox[-1].body
    achado = re.search(r"https?://[^/]+(/conta/senha/confirmar/[^\s]+)", corpo)
    assert achado, f"link ausente no email:\n{corpo}"
    return achado.group(1)


@pytest.mark.django_db
class TestNaoRevelaQuemTemConta:
    """A parte que costuma vazar."""

    def test_resposta_identica_para_email_cadastrado_e_inexistente(
        self, client: Client, usuario: User
    ) -> None:
        com_conta = _pedir(client, CADASTRADO)
        cache.clear()
        sem_conta = _pedir(client, NAO_CADASTRADO)

        assert com_conta.status_code == sem_conta.status_code
        assert com_conta["Location"] == sem_conta["Location"]

    def test_pagina_de_confirmacao_identica_nos_dois_casos(
        self, client: Client, usuario: User
    ) -> None:
        _pedir(client, CADASTRADO)
        com_conta = client.get(reverse("accounts:password_reset_done")).content
        cache.clear()
        _pedir(client, NAO_CADASTRADO)
        sem_conta = client.get(reverse("accounts:password_reset_done")).content

        assert com_conta == sem_conta

    def test_so_o_email_cadastrado_gera_mensagem(self, client: Client, usuario: User) -> None:
        _pedir(client, NAO_CADASTRADO)
        assert mail.outbox == []

        _pedir(client, CADASTRADO)
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [CADASTRADO]


@pytest.mark.django_db
class TestToken:
    def test_link_permite_trocar_a_senha(self, client: Client, usuario: User) -> None:
        _pedir(client, CADASTRADO)
        # A view do Django redireciona o token da URL para uma sessão interna
        # antes de mostrar o formulário; seguir o redirecionamento é o fluxo real.
        resposta = client.get(_link_do_email(), follow=True)
        assert resposta.context["validlink"] is True

        client.post(
            resposta.request["PATH_INFO"],
            {"new_password1": "senha-nova-bem-longa", "new_password2": "senha-nova-bem-longa"},
        )
        usuario.refresh_from_db()
        assert usuario.check_password("senha-nova-bem-longa")

    def test_link_serve_uma_vez_so(self, client: Client, usuario: User) -> None:
        _pedir(client, CADASTRADO)
        link = _link_do_email()
        primeira = client.get(link, follow=True)
        client.post(
            primeira.request["PATH_INFO"],
            {"new_password1": "senha-nova-bem-longa", "new_password2": "senha-nova-bem-longa"},
        )

        # O token deriva do hash da senha: trocá-la invalida o link usado.
        segunda = Client().get(link, follow=True)
        assert segunda.context["validlink"] is False

    def test_token_de_um_usuario_nao_serve_para_outro(self, client: Client, usuario: User) -> None:
        outro = User.objects.create_user(
            username="shantideva",
            email="shantideva@exemplo.org",
            display_name="Śāntideva",
            password="outra-senha-longa",
        )
        _pedir(client, CADASTRADO)
        link_de_ananda = _link_do_email()

        # Troca só o identificador do usuário, mantendo o token.
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid_do_outro = urlsafe_base64_encode(force_bytes(outro.pk))
        partes = link_de_ananda.strip("/").split("/")
        partes[-2] = uid_do_outro
        adulterado = "/" + "/".join(partes) + "/"

        assert Client().get(adulterado, follow=True).context["validlink"] is False

    def test_token_expirado_e_recusado(
        self, client: Client, usuario: User, settings, monkeypatch
    ) -> None:
        _pedir(client, CADASTRADO)
        link = _link_do_email()

        # Adiantar o relógio do gerador, em vez de zerar o prazo: com prazo
        # zero a comparação do Django é `0 > 0`, que é falsa, e o teste
        # passaria sem que nada expirasse.
        settings.PASSWORD_RESET_TIMEOUT = 60
        from django.contrib.auth.tokens import PasswordResetTokenGenerator

        agora = PasswordResetTokenGenerator()._now()
        monkeypatch.setattr(
            PasswordResetTokenGenerator,
            "_now",
            lambda self: agora + timedelta(seconds=120),
        )
        assert Client().get(link, follow=True).context["validlink"] is False

    def test_o_prazo_padrao_nao_e_o_do_django(self) -> None:
        """O padrão do Django são 3 dias; §7.3 quer bem menos."""
        from django.conf import settings as configuracao

        assert configuracao.PASSWORD_RESET_TIMEOUT <= 60 * 60 * 24


@pytest.mark.django_db
class TestLimiteDeTaxa:
    def test_limita_por_email(self, client: Client, usuario: User, settings) -> None:
        settings.PASSWORD_RESET_LIMITE_POR_EMAIL = 2
        settings.PASSWORD_RESET_LIMITE_POR_IP = 100

        for _ in range(2):
            assert _pedir(client, CADASTRADO).status_code == 302
        assert _pedir(client, CADASTRADO).status_code == 200  # reexibe o formulário
        assert len(mail.outbox) == 2

    def test_limita_por_ip_mesmo_trocando_de_email(self, client: Client, settings) -> None:
        settings.PASSWORD_RESET_LIMITE_POR_IP = 2
        settings.PASSWORD_RESET_LIMITE_POR_EMAIL = 100

        for i in range(2):
            assert _pedir(client, f"pessoa{i}@exemplo.org").status_code == 302
        assert _pedir(client, "pessoa9@exemplo.org").status_code == 200

    def test_o_limite_nao_distingue_email_cadastrado(
        self, client: Client, usuario: User, settings
    ) -> None:
        """Se limitasse só o que existe, o limite viraria canal de enumeração."""
        settings.PASSWORD_RESET_LIMITE_POR_IP = 1
        settings.PASSWORD_RESET_LIMITE_POR_EMAIL = 100

        _pedir(client, NAO_CADASTRADO)
        assert _pedir(client, NAO_CADASTRADO).status_code == 200

        cache.clear()
        _pedir(client, CADASTRADO)
        assert _pedir(client, CADASTRADO).status_code == 200


@pytest.mark.django_db
class TestEmail:
    def test_texto_puro_sem_html_e_sem_imagem_remota(self, client: Client, usuario: User) -> None:
        """HTML com imagem remota vazaria o IP de quem abre a mensagem."""
        _pedir(client, CADASTRADO)
        mensagem = mail.outbox[0]

        assert mensagem.alternatives == []
        assert mensagem.content_subtype == "plain"
        assert "<img" not in mensagem.body
        # Um único endereço no corpo, e é o link de recuperação. Qualquer
        # outro seria recurso remoto carregado ao abrir a mensagem.
        enderecos = re.findall(r"https?://\S+", mensagem.body)
        assert len(enderecos) == 1
        assert enderecos[0].endswith(_link_do_email())

    def test_assunto_em_uma_linha_e_em_portugues(self, client: Client, usuario: User) -> None:
        _pedir(client, CADASTRADO)
        assunto = mail.outbox[0].subject
        assert "\n" not in assunto
        assert "Buddhadharma" in assunto
