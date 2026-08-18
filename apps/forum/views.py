"""Views do fórum.

Duas regras atravessam este módulo:

* **Paginação por keyset, nunca OFFSET** (§4.8). `OFFSET 10000` obriga o
  PostgreSQL a varrer e descartar dez mil linhas. Com `position` sequencial,
  paginar é `WHERE topic_id = ? AND position > ?` — tempo constante em
  qualquer profundidade do tópico.

* **Nada de N+1** (§8). Toda listagem declara `select_related` e
  `prefetch_related` explicitamente.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from apps.core.permissions import is_moderator, require_user

from .forms import PostForm, TopicForm
from .models import Category, Post, ReactionCount, Topic


def index(request: HttpRequest) -> HttpResponse:
    categories = (
        Category.objects.filter(parent__isnull=True)
        .prefetch_related("children")
        .order_by("position", "name")
    )
    recent = (
        Topic.objects.select_related("category", "author")
        .exclude(last_post_at__isnull=True)
        .order_by("-last_post_at")[:10]
    )
    return render(request, "forum/index.html", {"categories": categories, "recent_topics": recent})


def category(request: HttpRequest, slug: str) -> HttpResponse:
    cat = get_object_or_404(Category, slug=slug)

    topics = (
        Topic.objects.filter(category=cat)
        .select_related("author", "category")
        .order_by("-is_pinned", "-last_post_at")
    )

    # Keyset por last_post_at. O cursor é o timestamp do último item da página
    # anterior, não um número de página.
    cursor = request.GET.get("antes")
    if cursor:
        topics = topics.filter(is_pinned=False, last_post_at__lt=cursor)

    page = list(topics[: settings.FORUM_TOPICS_PER_PAGE + 1])
    has_more = len(page) > settings.FORUM_TOPICS_PER_PAGE
    page = page[: settings.FORUM_TOPICS_PER_PAGE]
    # last_post_at é nulo em tópico sem post. Sem esta guarda, a primeira
    # página com um tópico assim quebraria a paginação com AttributeError.
    ultimo = page[-1].last_post_at if has_more and page else None
    next_cursor = ultimo.isoformat() if ultimo else None

    return render(
        request,
        "forum/category.html",
        {"category": cat, "topics": page, "next_cursor": next_cursor},
    )


def topic(request: HttpRequest, pk: int, slug: str) -> HttpResponse:
    obj = get_object_or_404(Topic.objects.select_related("category", "author"), pk=pk)
    if obj.slug != slug:
        return redirect(obj.get_absolute_url(), permanent=True)

    after = request.GET.get("depois")
    posts_qs = (
        Post.objects.filter(topic=obj)
        .select_related("author", "reply_to", "reply_to__author")
        .prefetch_related(
            Prefetch(
                "reaction_counts",
                queryset=ReactionCount.objects.select_related("emoji").filter(count__gt=0),
            )
        )
        .order_by("position")
    )
    if after:
        try:
            posts_qs = posts_qs.filter(position__gt=int(after))
        except ValueError as exc:
            raise Http404("Cursor inválido.") from exc

    posts = list(posts_qs[: settings.FORUM_POSTS_PER_PAGE + 1])
    has_more = len(posts) > settings.FORUM_POSTS_PER_PAGE
    posts = posts[: settings.FORUM_POSTS_PER_PAGE]

    # Acumulado em cache e descarregado em lote — escrever uma linha por
    # visualização inundaria o WAL (§8). Por ora, incremento direto; a
    # agregação entra junto com o Redis de contadores.
    Topic.all_objects.filter(pk=obj.pk).update(view_count=obj.view_count + 1)

    return render(
        request,
        "forum/topic.html",
        {
            "topic": obj,
            "posts": posts,
            "next_cursor": posts[-1].position if has_more and posts else None,
            "form": PostForm() if request.user.is_authenticated else None,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def topic_create(request: HttpRequest, slug: str) -> HttpResponse:
    cat = get_object_or_404(Category, slug=slug)
    if cat.is_locked and not is_moderator(request.user):
        raise Http404("Categoria trancada.")

    autor = require_user(request.user)

    form = TopicForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        new_topic = Topic.objects.create(
            category=cat,
            author=autor,
            title=form.cleaned_data["title"],
            slug=slugify(form.cleaned_data["title"])[:220] or "topico",
        )
        Post.create_in_topic(new_topic, autor, form.cleaned_data["body_md"])
        Category.objects.filter(pk=cat.pk).update(topic_count=cat.topic_count + 1)
        return redirect(new_topic.get_absolute_url())

    return render(request, "forum/topic_form.html", {"category": cat, "form": form})


@login_required
@require_http_methods(["POST"])
def post_create(request: HttpRequest, pk: int) -> HttpResponse:
    obj = get_object_or_404(Topic, pk=pk)
    if obj.is_locked and not is_moderator(request.user):
        raise Http404("Tópico trancado.")

    form = PostForm(request.POST)
    if not form.is_valid():
        return render(request, "forum/topic.html", {"topic": obj, "form": form}, status=400)

    post = Post.create_in_topic(obj, require_user(request.user), form.cleaned_data["body_md"])
    return redirect(post.get_absolute_url())
