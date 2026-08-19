"""Testes das views do fórum.

Existem por causa de um erro 500 real ao publicar tópico: os testes de modelo
chamavam ``Post.create_in_topic()`` com uma instância de ``User`` de verdade,
enquanto a view passa ``request.user`` — um ``SimpleLazyObject``. O proxy delega
``__class__``, então ``isinstance`` passa, mas ``type()`` devolve a classe do
proxy, sem ``.objects``.

A lição é mais ampla que o defeito: **testar só o modelo não cobre a view.**
O que chega numa view não é o que se constrói num teste.
"""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.forum.models import Category, Post, Topic

pytestmark = pytest.mark.django_db

SENHA = "senha-de-teste-longa-123"


@pytest.fixture
def usuario() -> User:
    return User.objects.create_user("ananda", "ananda@exemplo.org", SENHA)


@pytest.fixture
def logado(client: Client, usuario: User) -> Client:
    client.force_login(usuario)
    return client


@pytest.fixture
def categoria() -> Category:
    return Category.objects.create(name="Primeiros passos", slug="primeiros-passos")


@pytest.fixture
def topico(categoria: Category, usuario: User) -> Topic:
    return Topic.objects.create(
        category=categoria, author=usuario, title="Sobre anicca", slug="sobre-anicca"
    )


class TestCriarTopico:
    def test_publica_pela_view(self, logado: Client, categoria: Category, usuario: User) -> None:
        """Regressão: este é o caminho que devolvia 500.

        `request.user` é um SimpleLazyObject; `type(author).objects` estourava
        AttributeError dentro de create_in_topic.
        """
        resposta = logado.post(
            reverse("forum:topic_create", kwargs={"slug": categoria.slug}),
            {"title": "O caminho do meio", "body_md": "Primeira mensagem."},
        )

        assert resposta.status_code == 302
        topico = Topic.objects.get(title="O caminho do meio")
        assert topico.posts.count() == 1
        assert topico.posts.get().position == 1

    def test_contadores_atualizados(
        self, logado: Client, categoria: Category, usuario: User
    ) -> None:
        logado.post(
            reverse("forum:topic_create", kwargs={"slug": categoria.slug}),
            {"title": "Sobre a impermanência", "body_md": "Texto."},
        )
        categoria.refresh_from_db()
        usuario.refresh_from_db()
        assert categoria.topic_count == 1
        assert categoria.post_count == 1
        assert usuario.post_count == 1

    def test_anonimo_e_redirecionado(self, client: Client, categoria: Category) -> None:
        resposta = client.post(
            reverse("forum:topic_create", kwargs={"slug": categoria.slug}),
            {"title": "Tentativa anônima", "body_md": "Texto."},
        )
        assert resposta.status_code == 302
        assert "entrar" in resposta["Location"]
        assert not Topic.objects.filter(title="Tentativa anônima").exists()

    def test_titulo_curto_rejeitado(self, logado: Client, categoria: Category) -> None:
        resposta = logado.post(
            reverse("forum:topic_create", kwargs={"slug": categoria.slug}),
            {"title": "abc", "body_md": "Texto."},
        )
        assert resposta.status_code == 200
        assert Topic.objects.count() == 0

    def test_categoria_trancada_barra_nao_moderador(
        self, logado: Client, categoria: Category
    ) -> None:
        categoria.is_locked = True
        categoria.save()
        resposta = logado.post(
            reverse("forum:topic_create", kwargs={"slug": categoria.slug}),
            {"title": "Deveria falhar", "body_md": "Texto."},
        )
        assert resposta.status_code == 404


class TestResponder:
    def test_responde_pela_view(self, logado: Client, topico: Topic) -> None:
        resposta = logado.post(
            reverse("forum:post_create", kwargs={"pk": topico.pk}),
            {"body_md": "Uma resposta."},
        )
        assert resposta.status_code == 302
        assert topico.posts.count() == 1

    def test_posicao_sequencial(self, logado: Client, topico: Topic) -> None:
        url = reverse("forum:post_create", kwargs={"pk": topico.pk})
        for _ in range(3):
            logado.post(url, {"body_md": "Mensagem."})
        assert list(topico.posts.values_list("position", flat=True)) == [1, 2, 3]

    def test_markdown_renderizado_e_sanitizado(self, logado: Client, topico: Topic) -> None:
        logado.post(
            reverse("forum:post_create", kwargs={"pk": topico.pk}),
            {"body_md": "**forte** <script>alert(1)</script>"},
        )
        post = topico.posts.get()
        assert "<strong>forte</strong>" in post.body_html
        assert "<script" not in post.body_html

    def test_topico_trancado_barra_nao_moderador(self, logado: Client, topico: Topic) -> None:
        topico.is_locked = True
        topico.save()
        resposta = logado.post(
            reverse("forum:post_create", kwargs={"pk": topico.pk}),
            {"body_md": "Deveria falhar."},
        )
        assert resposta.status_code == 404
        assert topico.posts.count() == 0

    def test_anonimo_nao_responde(self, client: Client, topico: Topic) -> None:
        resposta = client.post(
            reverse("forum:post_create", kwargs={"pk": topico.pk}),
            {"body_md": "Texto."},
        )
        assert resposta.status_code == 302
        assert topico.posts.count() == 0


class TestLeitura:
    def test_indice(self, client: Client, categoria: Category) -> None:
        assert client.get(reverse("forum:index")).status_code == 200

    def test_categoria(self, client: Client, categoria: Category) -> None:
        assert client.get(categoria.get_absolute_url()).status_code == 200

    def test_topico(self, client: Client, topico: Topic, usuario: User) -> None:
        Post.create_in_topic(topico, usuario, "Texto.")
        assert client.get(topico.get_absolute_url()).status_code == 200

    def test_slug_errado_redireciona(self, client: Client, topico: Topic) -> None:
        resposta = client.get(f"/t/{topico.pk}/slug-errado/")
        assert resposta.status_code == 301
        assert resposta["Location"] == topico.get_absolute_url()

    def test_visualizacao_incrementa(self, client: Client, topico: Topic, usuario: User) -> None:
        Post.create_in_topic(topico, usuario, "Texto.")
        client.get(topico.get_absolute_url())
        client.get(topico.get_absolute_url())
        topico.refresh_from_db()
        assert topico.view_count == 2

    def test_cursor_invalido_nao_estoura(self, client: Client, topico: Topic) -> None:
        resposta = client.get(topico.get_absolute_url() + "?depois=abc")
        assert resposta.status_code == 404
