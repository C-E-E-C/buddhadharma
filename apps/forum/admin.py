"""Painel de moderação — vem de graça com o Django, §2."""

from typing import TYPE_CHECKING

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import Category, Emoji, Post, PostLink, PostRevision, Reaction, Topic

if TYPE_CHECKING:
    # `ModelAdmin` desta versão do Django não define `__class_getitem__`, então
    # subscrever em tempo de execução levanta TypeError. Os aliases dão ao
    # verificador de tipos o parâmetro que ele precisa sem tocar no runtime.
    _CategoryAdminBase = admin.ModelAdmin[Category]
    _TopicAdminBase = admin.ModelAdmin[Topic]
    _PostAdminBase = admin.ModelAdmin[Post]
    _EmojiAdminBase = admin.ModelAdmin[Emoji]
else:
    _CategoryAdminBase = _TopicAdminBase = _PostAdminBase = _EmojiAdminBase = admin.ModelAdmin


@admin.register(Category)
class CategoryAdmin(_CategoryAdminBase):
    list_display = ["name", "parent", "position", "topic_count", "post_count", "is_locked"]
    list_editable = ["position"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "description"]


@admin.register(Topic)
class TopicAdmin(_TopicAdminBase):
    list_display = ["title", "category", "author", "post_count", "last_post_at", "deleted_at"]
    list_filter = ["category", "is_pinned", "is_locked"]
    search_fields = ["title"]
    raw_id_fields = ["author"]
    prepopulated_fields = {"slug": ("title",)}

    def get_queryset(self, request: HttpRequest) -> QuerySet[Topic]:
        # Moderação enxerga o que foi removido — §4.3.
        return Topic.all_objects.select_related("category", "author")


@admin.register(Post)
class PostAdmin(_PostAdminBase):
    list_display = ["__str__", "author", "created_at", "edited_at", "deleted_at"]
    list_filter = ["created_at"]
    search_fields = ["body_md"]
    raw_id_fields = ["topic", "author", "reply_to"]
    readonly_fields = ["position", "html_version", "edit_count"]
    exclude = ["body_html", "search_vector"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Post]:
        return Post.all_objects.select_related("topic", "author")


@admin.register(Emoji)
class EmojiAdmin(_EmojiAdminBase):
    list_display = ["shortcode", "character", "is_active", "position"]
    list_editable = ["is_active", "position"]


admin.site.register([PostRevision, Reaction, PostLink])

admin.site.site_header = "Buddhadharma — administração"
admin.site.site_title = "Buddhadharma"
admin.site.index_title = "Moderação e gestão"
