"""Modelos do fórum — §4 da arquitetura."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models, transaction
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core.markdown import render_markdown
from apps.core.models import SoftDeleteModel, TimeStampedModel
from apps.core.text import NFCCharField, NFCTextField


class Category(models.Model):
    """Categoria — §4.2.

    Hierarquia por chave estrangeira simples para o pai. Categorias de fórum são
    rasas (dois níveis na prática); nested sets ou ltree seriam complexidade sem
    retorno. A árvore inteira cabe em cache — é lida em toda página e muda raramente.

    Gerenciada em banco e editável pelo admin, conforme o requisito.
    """

    parent = models.ForeignKey(
        "self",
        verbose_name=_("categoria mãe"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    name = NFCCharField(_("nome"), max_length=100)
    slug = models.SlugField(_("slug"), max_length=120, unique=True)
    description = NFCTextField(_("descrição"), blank=True)
    color = models.CharField(_("cor"), max_length=7, default="#8B6F47")
    position = models.IntegerField(_("ordem"), default=0)
    is_locked = models.BooleanField(
        _("trancada"), default=False, help_text=_("Apenas moderadores publicam.")
    )

    topic_count = models.PositiveIntegerField(default=0, editable=False)
    post_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        verbose_name = _("categoria")
        verbose_name_plural = _("categorias")
        ordering = ["position", "name"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("forum:category", kwargs={"slug": self.slug})


class Topic(SoftDeleteModel, TimeStampedModel):
    """Tópico — §4.3."""

    category = models.ForeignKey(
        Category, verbose_name=_("categoria"), on_delete=models.PROTECT, related_name="topics"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("autor"),
        on_delete=models.PROTECT,
        related_name="topics",
    )
    title = NFCCharField(_("título"), max_length=200)
    slug = models.SlugField(_("slug"), max_length=220)

    is_pinned = models.BooleanField(_("fixado"), default=False)
    is_locked = models.BooleanField(_("trancado"), default=False)

    post_count = models.PositiveIntegerField(default=0, editable=False)
    view_count = models.PositiveIntegerField(default=0, editable=False)
    # Materializado porque é a chave de ordenação da listagem de categoria,
    # o acesso mais frequente do fórum. Calcular por subconsulta a cada
    # listagem seria o gargalo óbvio.
    last_post_at = models.DateTimeField(_("último post em"), null=True, db_index=True)

    class Meta:
        verbose_name = _("tópico")
        verbose_name_plural = _("tópicos")
        ordering = ["-is_pinned", "-last_post_at"]
        indexes = [
            models.Index(
                fields=["category", "-is_pinned", "-last_post_at"],
                condition=models.Q(deleted_at__isnull=True),
                name="topic_listagem_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("forum:topic", kwargs={"pk": self.pk, "slug": self.slug})


class Post(SoftDeleteModel, TimeStampedModel):
    """Post — §4.3."""

    topic = models.ForeignKey(
        Topic, verbose_name=_("tópico"), on_delete=models.CASCADE, related_name="posts"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("autor"),
        on_delete=models.PROTECT,
        related_name="posts",
    )

    # Número sequencial dentro do tópico, começando em 1. Dá permalink estável
    # (/t/42/o-caminho-do-meio#3), paginação por keyset e o "número do post"
    # que fóruns exibem — sem depender do id global nem de OFFSET.
    position = models.PositiveIntegerField(_("número no tópico"), editable=False)

    # FONTE DE VERDADE. Markdown cru, comprimido pelo TOAST acima de ~2 KB.
    # Portátil, diffável e independente do renderizador.
    body_md = NFCTextField(_("texto"))

    # Cache de renderização, não dado. Persistido na linha em vez de só no
    # Redis porque o custo de armazenamento é baixo e evita uma tempestade de
    # re-renderização quando um cache esvazia.
    body_html = models.TextField(editable=False, blank=True)

    # Versão do pipeline que gerou body_html. Permite invalidar em massa com
    # um UPDATE quando o renderizador ou as regras de sanitização mudarem.
    html_version = models.PositiveSmallIntegerField(default=0, editable=False)

    reply_to = models.ForeignKey(
        "self",
        verbose_name=_("em resposta a"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
    )

    edited_at = models.DateTimeField(_("editado em"), null=True, blank=True)
    edit_count = models.PositiveSmallIntegerField(default=0, editable=False)

    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        verbose_name = _("post")
        verbose_name_plural = _("posts")
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["topic", "position"], name="post_posicao_unica"),
        ]
        indexes = [
            models.Index(
                fields=["topic", "position"],
                condition=models.Q(deleted_at__isnull=True),
                name="post_topico_posicao_idx",
            ),
            GinIndex(fields=["search_vector"], name="post_busca_idx"),
            # Trigrama sobre o Markdown cru. Cobre as escritas que o PostgreSQL
            # não sabe radicalizar — tibetano, devanágari, CJK — e dá tolerância
            # a erro de digitação. Criado na migração 0002, junto da extensão
            # pg_trgm de que depende.
            GinIndex(fields=["body_md"], opclasses=["gin_trgm_ops"], name="post_trigrama_idx"),
        ]

    def __str__(self) -> str:
        return f"#{self.position} em {self.topic_id}"

    def get_absolute_url(self) -> str:
        return f"{self.topic.get_absolute_url()}#post-{self.position}"

    # -- renderização -----------------------------------------------------

    def render(self) -> None:
        """Regenera o HTML em cache a partir do Markdown."""
        self.body_html = render_markdown(self.body_md)
        self.html_version = settings.FORUM_HTML_VERSION

    @property
    def needs_render(self) -> bool:
        return self.html_version != settings.FORUM_HTML_VERSION

    def html(self) -> str:
        """HTML pronto para exibição, re-renderizando se o cache está velho."""
        if self.needs_render:
            self.render()
            if self.pk:
                Post.all_objects.filter(pk=self.pk).update(
                    body_html=self.body_html, html_version=self.html_version
                )
        return self.body_html

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.needs_render:
            self.render()
        super().save(*args, **kwargs)

    # -- criação ----------------------------------------------------------

    @classmethod
    @transaction.atomic
    def create_in_topic(
        cls,
        topic: Topic,
        author: Any,
        body_md: str,
        reply_to: Post | None = None,
    ) -> Post:
        """Cria um post atribuindo `position` sem corrida.

        O bloqueio é na linha do tópico, não numa agregação sobre os posts:
        `SELECT MAX(position)` não trava linha nenhuma, então dois posts
        simultâneos leriam o mesmo máximo e tentariam a mesma posição.
        Travando o tópico, a sequência é serializada por tópico — e o
        UNIQUE (topic, position) fica como rede de segurança, não como
        mecanismo principal.
        """
        locked = Topic.all_objects.select_for_update().get(pk=topic.pk)
        last = cls.all_objects.filter(topic=locked).aggregate(models.Max("position"))
        next_position = (last["position__max"] or 0) + 1

        post = cls(
            topic=locked,
            author=author,
            position=next_position,
            body_md=body_md,
            reply_to=reply_to,
        )
        post.save()

        Topic.all_objects.filter(pk=locked.pk).update(
            post_count=models.F("post_count") + 1, last_post_at=post.created_at
        )
        Category.objects.filter(pk=locked.category_id).update(post_count=models.F("post_count") + 1)

        # get_user_model() e não type(author): numa view, `author` é o
        # request.user, que é um SimpleLazyObject. Ele delega `__class__` ao
        # objeto embrulhado — por isso `isinstance(author, User)` passa —, mas
        # `type()` devolve a classe do proxy, que não tem `.objects`.
        get_user_model().objects.filter(pk=author.pk).update(post_count=models.F("post_count") + 1)
        return post


class PostRevision(TimeStampedModel):
    """Histórico de edição — §4.4.

    Snapshot completo em vez de diff: mais simples, mais robusto, e o TOAST
    comprime bem texto repetitivo.

    Transparência de edição é requisito de moderação num fórum de tema
    doutrinário. Editar em silêncio uma citação de sutta não pode ser possível.
    """

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="revisions")
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    body_md = NFCTextField(_("texto anterior"))
    edit_reason = NFCCharField(_("motivo"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("revisão")
        verbose_name_plural = _("revisões")
        ordering = ["-created_at"]


class Emoji(models.Model):
    """Emoji de reação — §4.5.

    Em tabela, não em enum no código: adicionar um emoji não exige deploy.
    """

    shortcode = models.SlugField(_("código"), max_length=50, unique=True)
    character = models.CharField(_("caractere"), max_length=8, blank=True)
    image = models.ImageField(_("imagem"), upload_to="emojis/", blank=True, null=True)
    is_active = models.BooleanField(_("ativo"), default=True)
    position = models.IntegerField(_("ordem"), default=0)

    class Meta:
        verbose_name = _("emoji")
        verbose_name_plural = _("emojis")
        ordering = ["position", "shortcode"]

    def __str__(self) -> str:
        return f":{self.shortcode}:"


class Reaction(TimeStampedModel):
    """Reação individual — §4.5."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reactions"
    )
    emoji = models.ForeignKey(Emoji, on_delete=models.CASCADE, related_name="reactions")

    class Meta:
        verbose_name = _("reação")
        verbose_name_plural = _("reações")
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user", "emoji"], name="reacao_unica_por_usuario"
            ),
        ]


class ReactionCount(models.Model):
    """Contagem materializada de reações — §4.5.

    Mantida por trigger no PostgreSQL, não por sinal do Django (ver a migração
    que cria a função). Trigger porque a garantia precisa valer também em
    importação em massa, correção manual via psql e migração de dados — todo
    caminho que escreva na tabela, e não apenas o que passa pelo ORM.

    Nunca COUNT(*) em tempo real: uma página com 20 posts e 6 emojis faria
    120 agregações por requisição.
    """

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="reaction_counts")
    emoji = models.ForeignKey(Emoji, on_delete=models.CASCADE, related_name="+")
    count = models.IntegerField(default=0)

    class Meta:
        verbose_name = _("contagem de reações")
        verbose_name_plural = _("contagens de reações")
        constraints = [
            models.UniqueConstraint(fields=["post", "emoji"], name="contagem_unica_post_emoji"),
        ]

    def __str__(self) -> str:
        return f"{self.emoji_id} x{self.count}"


class LinkType(models.TextChoices):
    QUOTE = "quote", _("Citação")
    REFERENCE = "reference", _("Referência")
    MENTION = "mention", _("Menção")
    CROSSPOST = "crosspost", _("Post cruzado")


class PostLink(TimeStampedModel):
    """Aresta entre posts — §4.6.

    Grafo em tabela relacional, não texto solto dentro do corpo. Extraída na
    renderização, quando o Markdown contém link para uma URL interna de post.

    Sustenta os backlinks — ao ler um post, ver quais posts posteriores o
    citaram. Num fórum sobre Budismo isso permite rastrear, ao longo de anos,
    as discussões que referenciam a mesma passagem.
    """

    source_post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="links_out")
    target_post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="links_in")
    link_type = models.CharField(
        max_length=20, choices=LinkType.choices, default=LinkType.REFERENCE
    )

    class Meta:
        verbose_name = _("vínculo entre posts")
        verbose_name_plural = _("vínculos entre posts")
        constraints = [
            models.UniqueConstraint(
                fields=["source_post", "target_post", "link_type"], name="vinculo_unico"
            ),
        ]
        indexes = [
            models.Index(fields=["target_post"], name="postlink_alvo_idx"),
        ]
