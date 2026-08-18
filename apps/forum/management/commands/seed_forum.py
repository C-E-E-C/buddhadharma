"""Popula categorias e emojis iniciais.

Idempotente: rodar duas vezes não duplica nada.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.forum.models import Category, Emoji

CATEGORIAS: list[dict[str, Any]] = [
    {
        "slug": "primeiros-passos",
        "name": "Primeiros passos",
        "description": "Para quem está começando. Nenhuma pergunta é básica demais.",
        "color": "#8B6F47",
    },
    {
        "slug": "sutras-e-suttas",
        "name": "Sutras e suttas",
        "description": "Leitura, tradução e discussão dos textos.",
        "color": "#A6862F",
    },
    {
        "slug": "pratica",
        "name": "Prática",
        "description": "Meditação, ética e vida cotidiana.",
        "color": "#6E7F5C",
    },
    {
        "slug": "tradicoes",
        "name": "Tradições",
        "description": "Theravāda, Mahāyāna, Vajrayāna, Zen e outras escolas.",
        "color": "#7A5C7E",
    },
    {
        "slug": "sangha",
        "name": "Comunidade",
        "description": "Grupos, retiros e encontros de língua portuguesa.",
        "color": "#4F7A8A",
    },
    {
        "slug": "meta",
        "name": "Sobre o fórum",
        "description": "Sugestões, regras e funcionamento.",
        "color": "#6F665C",
    },
]

EMOJIS: list[tuple[str, str]] = [
    ("lotus", "🪷"),
    ("anjali", "🙏"),
    ("coracao", "❤️"),
    ("iluminado", "💡"),
    ("obrigado", "🙇"),
    ("interessante", "🤔"),
]


class Command(BaseCommand):
    help = "Cria categorias e emojis iniciais. Idempotente."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        for position, dados in enumerate(CATEGORIAS):
            _, criada = Category.objects.update_or_create(
                slug=dados["slug"],
                defaults={**dados, "position": position},
            )
            if criada:
                self.stdout.write(f"  categoria: {dados['name']}")

        for position, (shortcode, character) in enumerate(EMOJIS):
            _, criado = Emoji.objects.update_or_create(
                shortcode=shortcode,
                defaults={"character": character, "position": position, "is_active": True},
            )
            if criado:
                self.stdout.write(f"  emoji: {character} :{shortcode}:")

        self.stdout.write(self.style.SUCCESS("Conteúdo inicial pronto."))
