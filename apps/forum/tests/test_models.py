"""Testes dos modelos do fórum.

Exigem PostgreSQL: dependem de triggers, de extensões e do comportamento real
de UNIQUE e SELECT FOR UPDATE. Rodar com `make up && make test`.
"""

import pytest
from django.db import IntegrityError, connection

from apps.accounts.models import User
from apps.forum.models import Category, Emoji, Post, Reaction, ReactionCount, Topic
from apps.forum.search import fuzzy_posts, search_posts

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
    """Busca full-text — §5, com a correção medida na migração 0003.

    O vetor combina duas configurações porque radical e acento são propriedades
    conflitantes numa configuração só: `unaccent` roda antes do stemmer e o
    desliga na prática. Ver a docstring da migração para os números.
    """

    def test_vetor_e_preenchido_por_trigger(self, topico: Topic, autor: User) -> None:
        post = Post.create_in_topic(topico, autor, "A prática da meditação sentada.")
        post.refresh_from_db()
        assert post.search_vector is not None

    def test_acento_ignorado(self, topico: Topic, autor: User) -> None:
        """Quem digita `meditacao` no celular precisa encontrar `meditação`."""
        Post.create_in_topic(topico, autor, "A prática da meditação sentada.")
        assert search_posts("meditacao").count() == 1

    def test_radical_com_acento(self, topico: Topic, autor: User) -> None:
        """Consulta acentuada casa singular e plural — o stemmer funcionando.

        Este é o teste que pegou o defeito da 0002: com `unaccent()` antes do
        `to_tsvector`, `meditações` virava 'meditaco' e `meditação` virava
        'meditaca', e os dois deixavam de casar.
        """
        Post.create_in_topic(topico, autor, "Sobre as meditações do Buda.")
        assert search_posts("meditação").count() == 1
        assert search_posts("meditações").count() == 1

    def test_diacritico_do_pali(self, topico: Topic, autor: User) -> None:
        """Poucos digitam os diacríticos do Pāli. Os dois lados precisam achar."""
        Post.create_in_topic(topico, autor, "Sobre anattā e a vida do saṅgha.")
        assert search_posts("anatta").count() == 1
        assert search_posts("anattā").count() == 1
        assert search_posts("sangha").count() == 1
        assert search_posts("saṅgha").count() == 1

    def test_termo_ausente_nao_casa(self, topico: Topic, autor: User) -> None:
        Post.create_in_topic(topico, autor, "A prática da meditação sentada.")
        assert search_posts("nagarjuna").count() == 0

    def test_entrada_com_sintaxe_quebrada_nao_levanta_erro(
        self, topico: Topic, autor: User
    ) -> None:
        """`websearch` em vez de `to_tsquery`: entrada da web nunca é confiável
        e `to_tsquery` levanta erro de sintaxe com caractere solto."""
        Post.create_in_topic(topico, autor, "A prática da meditação sentada.")
        for entrada in ["&&&", "( unbalanced", "a & | b", "!!!", ""]:
            assert search_posts(entrada).count() >= 0

    def test_limitacao_do_fulltext_sem_acento_e_outra_flexao(
        self, topico: Topic, autor: User
    ) -> None:
        """Documenta o que o full-text NÃO faz, e quem cobre.

        Consulta sem acento numa flexão diferente da do texto não casa por
        full-text — é o resíduo do conflito entre acento e radical. O trigrama
        cobre, e é para isso que existe o recuo em `search_posts`.

        Se o primeiro assert algum dia começar a falhar, a limitação foi
        resolvida e o teste deve ser reescrito, não apagado.
        """
        Post.create_in_topic(topico, autor, "Sobre as meditações do Buda.")

        assert search_posts("meditacao").count() == 0
        assert fuzzy_posts("meditacao").count() == 1
        assert search_posts("meditacao", fuzzy_fallback=True).count() == 1

    def test_trigrama_usa_operador_de_palavra_nao_de_frase(
        self, topico: Topic, autor: User
    ) -> None:
        """`%` compara strings inteiras; `%>` compara com a melhor palavra.

        Uma palavra contra um post de parágrafos dá similaridade baixíssima
        pelo `%` e nunca casaria. Este teste trava a escolha do operador —
        trocar `trigram_word_similar` por `trigram_similar` o derruba.
        """
        texto = "Sobre as meditações do Buda e o caminho que delas decorre."
        Post.create_in_topic(topico, autor, texto)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT similarity(%s, %s), word_similarity(%s, %s)",
                [texto, "meditacao", "meditacao", texto],
            )
            frase, palavra = cursor.fetchone()

        assert frase < 0.3, "premissa: similaridade de frase inteira fica sob o limiar"
        assert palavra >= 0.3, "premissa: similaridade de palavra passa o limiar"
        assert fuzzy_posts("meditacao").count() == 1

    def test_trigrama_nao_casa_palavra_sem_relacao(self, topico: Topic, autor: User) -> None:
        Post.create_in_topic(topico, autor, "Sobre as meditações do Buda.")
        assert fuzzy_posts("nagarjuna").count() == 0
