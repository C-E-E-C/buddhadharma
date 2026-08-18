"""Testes dos modelos do fórum.

Exigem PostgreSQL: dependem de triggers, de extensões e do comportamento real
de UNIQUE e SELECT FOR UPDATE. Rodar com `make up && make test`.
"""

import pytest
from django.db import IntegrityError, connection

from apps.accounts.models import User
from apps.forum.models import Category, Emoji, Post, Reaction, ReactionCount, Topic

pytestmark = pytest.mark.django_db


@pytest.fixture
def autor() -> User:
    return User.objects.create_user("ananda", "ananda@exemplo.org", "senha-de-teste-123")


@pytest.fixture
def categoria() -> Category:
    return Category.objects.create(name="Prática", slug="pratica")


@pytest.fixture
def topico(categoria: Category, autor: User) -> Topic:
    return Topic.objects.create(
        category=categoria, author=autor, title="Sobre anicca", slug="sobre-anicca"
    )


class TestPosicaoDoPost:
    def test_comeca_em_um(self, topico: Topic, autor: User) -> None:
        post = Post.create_in_topic(topico, autor, "primeiro")
        assert post.position == 1

    def test_incrementa_por_topico(self, topico: Topic, autor: User) -> None:
        for esperado in (1, 2, 3):
            assert Post.create_in_topic(topico, autor, "texto").position == esperado

    def test_numeracao_independente_entre_topicos(self, categoria: Category, autor: User) -> None:
        a = Topic.objects.create(category=categoria, author=autor, title="Tópico A", slug="a")
        b = Topic.objects.create(category=categoria, author=autor, title="Tópico B", slug="b")
        Post.create_in_topic(a, autor, "x")
        Post.create_in_topic(a, autor, "y")
        assert Post.create_in_topic(b, autor, "z").position == 1

    def test_posicao_duplicada_e_rejeitada_pelo_banco(self, topico: Topic, autor: User) -> None:
        """O UNIQUE é a rede de segurança sob o SELECT FOR UPDATE."""
        Post.create_in_topic(topico, autor, "primeiro")
        with pytest.raises(IntegrityError):
            Post.objects.create(topic=topico, author=autor, position=1, body_md="colidente")

    def test_contadores_sao_atualizados(self, topico: Topic, autor: User) -> None:
        Post.create_in_topic(topico, autor, "texto")
        topico.refresh_from_db()
        autor.refresh_from_db()
        assert topico.post_count == 1
        assert topico.last_post_at is not None
        assert autor.post_count == 1


class TestRenderizacao:
    def test_html_e_gerado_ao_salvar(self, topico: Topic, autor: User) -> None:
        post = Post.create_in_topic(topico, autor, "**forte**")
        assert "<strong>forte</strong>" in post.body_html

    def test_markdown_e_a_fonte_de_verdade(self, topico: Topic, autor: User) -> None:
        post = Post.create_in_topic(topico, autor, "**forte**")
        post.refresh_from_db()
        assert post.body_md == "**forte**"

    def test_cache_velho_e_regenerado(self, topico: Topic, autor: User) -> None:
        """Incrementar FORUM_HTML_VERSION invalida todo o HTML gravado."""
        post = Post.create_in_topic(topico, autor, "*texto*")
        Post.all_objects.filter(pk=post.pk).update(body_html="<p>obsoleto</p>", html_version=0)
        recarregado = Post.objects.get(pk=post.pk)
        assert "<em>texto</em>" in recarregado.html()

    def test_script_nao_sobrevive_ate_o_banco(self, topico: Topic, autor: User) -> None:
        post = Post.create_in_topic(topico, autor, "<script>alert(1)</script>")
        assert "<script" not in post.body_html


class TestRemocaoReversivel:
    def test_manager_padrao_esconde_removido(self, topico: Topic, autor: User) -> None:
        post = Post.create_in_topic(topico, autor, "texto")
        post.soft_delete(by=autor)
        assert not Post.objects.filter(pk=post.pk).exists()
        assert Post.all_objects.filter(pk=post.pk).exists()

    def test_restaurar(self, topico: Topic, autor: User) -> None:
        post = Post.create_in_topic(topico, autor, "texto")
        post.soft_delete(by=autor)
        post.restore()
        assert Post.objects.filter(pk=post.pk).exists()


class TestTriggerDeReacoes:
    """A contagem é mantida por trigger no PostgreSQL, não pelo ORM (§4.5).

    Estes testes escrevem pelo ORM, mas o que verificam é o trigger — por isso
    conferem também a escrita em SQL cru, que não passa pelo Django.
    """

    @pytest.fixture
    def emoji(self) -> Emoji:
        return Emoji.objects.create(shortcode="lotus", character="🪷")

    def test_inserir_incrementa(self, topico: Topic, autor: User, emoji: Emoji) -> None:
        post = Post.create_in_topic(topico, autor, "texto")
        Reaction.objects.create(post=post, user=autor, emoji=emoji)
        assert ReactionCount.objects.get(post=post, emoji=emoji).count == 1

    def test_remover_decrementa(self, topico: Topic, autor: User, emoji: Emoji) -> None:
        post = Post.create_in_topic(topico, autor, "texto")
        reacao = Reaction.objects.create(post=post, user=autor, emoji=emoji)
        reacao.delete()
        assert ReactionCount.objects.get(post=post, emoji=emoji).count == 0

    def test_reacao_repetida_e_rejeitada(self, topico: Topic, autor: User, emoji: Emoji) -> None:
        post = Post.create_in_topic(topico, autor, "texto")
        Reaction.objects.create(post=post, user=autor, emoji=emoji)
        with pytest.raises(IntegrityError):
            Reaction.objects.create(post=post, user=autor, emoji=emoji)

    def test_trigger_vale_para_sql_cru(self, topico: Topic, autor: User, emoji: Emoji) -> None:
        """A razão de ser trigger e não sinal do Django: vale para todo
        caminho de escrita, inclusive psql e importação em massa."""
        post = Post.create_in_topic(topico, autor, "texto")
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO forum_reaction (post_id, user_id, emoji_id, created_at) "
                "VALUES (%s, %s, %s, NOW())",
                [post.pk, autor.pk, emoji.pk],
            )
        assert ReactionCount.objects.get(post=post, emoji=emoji).count == 1


class TestBusca:
    def test_vetor_e_preenchido_por_trigger(self, topico: Topic, autor: User) -> None:
        post = Post.create_in_topic(topico, autor, "A prática da meditação sentada.")
        post.refresh_from_db()
        assert post.search_vector is not None

    def test_busca_ignora_acento(self, topico: Topic, autor: User) -> None:
        """unaccent: quem digita `meditacao` precisa encontrar `meditação`."""
        Post.create_in_topic(topico, autor, "A prática da meditação sentada.")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM forum_post "
                "WHERE search_vector @@ to_tsquery('portuguese', unaccent(%s))",
                ["meditacao"],
            )
            assert cursor.fetchone()[0] == 1

    def test_busca_encontra_radical(self, topico: Topic, autor: User) -> None:
        """Stemmer português: `meditações` casa com `meditação`."""
        Post.create_in_topic(topico, autor, "Sobre as meditações do Buda.")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM forum_post "
                "WHERE search_vector @@ to_tsquery('portuguese', unaccent(%s))",
                ["meditacao"],
            )
            assert cursor.fetchone()[0] == 1
