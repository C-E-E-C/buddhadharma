from typing import TYPE_CHECKING

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User

if TYPE_CHECKING:
    # `ModelAdmin` define `__class_getitem__` e aceita subscrição em tempo de
    # execução; o `UserAdmin` do Django não. Parametrizar direto levanta
    # `TypeError: type 'UserAdmin' is not subscriptable` ao carregar o admin.
    _UserAdminBase = BaseUserAdmin[User]
else:
    _UserAdminBase = BaseUserAdmin


@admin.register(User)
class UserAdmin(_UserAdminBase):
    list_display = ["username", "display_name", "email", "trust_level", "post_count", "is_active"]
    list_filter = ["trust_level", "is_active", "is_staff"]
    search_fields = ["username", "display_name", "email"]
    ordering = ["username"]
    readonly_fields = ["username_skeleton", "post_count", "created_at", "last_seen_at"]

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Apresentação", {"fields": ("display_name", "email", "bio", "avatar")}),
        ("Estado", {"fields": ("trust_level", "post_count", "is_active")}),
        (
            "Permissões",
            {
                "classes": ("collapse",),
                "fields": ("is_staff", "is_superuser", "groups", "user_permissions"),
            },
        ),
        (
            "Diagnóstico",
            {
                "classes": ("collapse",),
                "fields": ("username_skeleton", "created_at", "last_seen_at"),
            },
        ),
    )
    add_fieldsets = (
        (None, {"fields": ("username", "email", "display_name", "password1", "password2")}),
    )
