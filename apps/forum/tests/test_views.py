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


class TestBusca:
    """A view da busca — §5 e BD-012.

    O motor já é coberto por ``test_models.py::TestBusca``. O que se prova
    aqui é o que só a view pode errar: sinalizar o resultado aproximado,
    paginar sem repetir e não quebrar com entrada adulterada.
    """

    def test_estado_inicial_sem_termo(self, client: Client, topico: Topic, usuario: User) -> None:
        """Sem termo, uma lista vazia seria uma porta fechada."""
        Post.create_in_topic(topico, usuario, "A prática da meditação sentada.")
        resposta = client.get(reverse("forum:search"))

        assert resposta.status_code == 200
        assert "categorias" in resposta.context
        assert list(resposta.context["recentes"])

    def test_encontra_por_radical(self, client: Client, topico: Topic, usuario: User) -> None:
        Post.create_in_topic(topico, usuario, "Sobre as meditações do Buda.")
        resposta = client.get(reverse("forum:search"), {"q": "meditação"})

        assert len(resposta.context["resultados"]) == 1
        assert resposta.context["aproximado"] is False

    def test_encontra_sem_acento(self, client: Client, topico: Topic, usuario: User) -> None:
        Post.create_in_topic(topico, usuario, "A prática da meditação sentada.")
        assert (
            len(client.get(reverse("forum:search"), {"q": "meditacao"}).context["resultados"]) == 1
        )

    def test_encontra_diacritico_do_pali(
        self, client: Client, topico: Topic, usuario: User
    ) -> None:
        Post.create_in_topic(topico, usuario, "Sobre anattā e a vida do saṅgha.")
        for termo in ("anatta", "anattā", "sangha"):
            resultados = client.get(reverse("forum:search"), {"q": termo}).context["resultados"]
            assert len(resultados) == 1, termo

    def test_recuo_por_trigrama_e_sinalizado(
        self, client: Client, topico: Topic, usuario: User
    ) -> None:
        """Sem acento e noutra flexão, só o trigrama alcança — e quem lê
        precisa saber que a ordem não é por relevância."""
        Post.create_in_topic(topico, usuario, "Sobre as meditações do Buda.")
        resposta = client.get(reverse("forum:search"), {"q": "meditacao"})

        assert len(resposta.context["resultados"]) == 1
        assert resposta.context["aproximado"] is True
        assert "aproximados" in resposta.content.decode()

    def test_sem_resultado_nenhum(self, client: Client, topico: Topic, usuario: User) -> None:
        Post.create_in_topic(topico, usuario, "A prática da meditação sentada.")
        resposta = client.get(reverse("forum:search"), {"q": "nagarjuna"})

        assert resposta.status_code == 200
        assert resposta.context["resultados"] == []
        assert resposta.context["aproximado"] is False

    @pytest.mark.parametrize("entrada", ["&&&", "( solto", "a & | b", "!!!", "'aspas"])
    def test_sintaxe_quebrada_responde_200(
        self, client: Client, topico: Topic, usuario: User, entrada: str
    ) -> None:
        Post.create_in_topic(topico, usuario, "A prática da meditação sentada.")
        assert client.get(reverse("forum:search"), {"q": entrada}).status_code == 200

    @pytest.mark.parametrize("cursor", ["", "lixo", "1.0", ":", "abc:def", "1.0:x", "9" * 400])
    def test_cursor_adulterado_nao_quebra(
        self, client: Client, topico: Topic, usuario: User, cursor: str
    ) -> None:
        Post.create_in_topic(topico, usuario, "A prática da meditação sentada.")
        resposta = client.get(reverse("forum:search"), {"q": "meditação", "apos": cursor})
        assert resposta.status_code == 200

    def test_paginacao_por_keyset_nao_repete_nem_perde(
        self, client: Client, topico: Topic, usuario: User, settings
    ) -> None:
        """Relevância empata com frequência; sem ordem total, um post
        apareceria em duas páginas e outro sumiria."""
        settings.FORUM_POSTS_PER_PAGE = 3
        for i in range(7):
            Post.create_in_topic(topico, usuario, f"A prática da meditação sentada, nota {i}.")

        vistos: list[int] = []
        parametros = {"q": "meditação"}
        for _ in range(4):
            resposta = client.get(reverse("forum:search"), parametros)
            vistos += [post.pk for post in resposta.context["resultados"]]
            cursor = resposta.context["next_cursor"]
            if not cursor:
                break
            parametros = {"q": "meditação", "apos": cursor}

        assert len(vistos) == 7
        assert len(set(vistos)) == 7

    def test_paginacao_do_trigrama_nao_troca_de_fonte(
        self, client: Client, topico: Topic, usuario: User, settings
    ) -> None:
        """Se a segunda página voltasse ao full-text, ela viria vazia e o
        resultado aproximado sumiria no meio da lista."""
        settings.FORUM_POSTS_PER_PAGE = 2
        for i in range(3):
            Post.create_in_topic(topico, usuario, f"Sobre as meditações do Buda, nota {i}.")

        primeira = client.get(reverse("forum:search"), {"q": "meditacao"})
        assert primeira.context["aproximado"] is True
        assert primeira.context["next_cursor"]

        segunda = client.get(
            reverse("forum:search"),
            {"q": "meditacao", "apos": primeira.context["next_cursor"], "aprox": "1"},
        )
        assert segunda.context["aproximado"] is True
        assert len(segunda.context["resultados"]) == 1

    def test_sem_n_mais_um(self, client: Client, topico: Topic, usuario: User) -> None:
        """Tópico e autor de cada resultado saem na mesma consulta."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        for i in range(10):
            Post.create_in_topic(topico, usuario, f"A prática da meditação sentada, nota {i}.")

        with CaptureQueriesContext(connection) as consultas:
            resposta = client.get(reverse("forum:search"), {"q": "meditação"})
            conteudo = resposta.content.decode()

        assert "Sobre anicca" in conteudo  # o título do tópico foi renderizado
        # Uma consulta para os resultados, mais o que a sessão e a autenticação
        # fazem. Sem select_related seriam vinte a mais, uma por post.
        assert len(consultas) <= 5, [c["sql"][:90] for c in consultas.captured_queries]
