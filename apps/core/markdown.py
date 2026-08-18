"""Renderização de Markdown para HTML — §7.1 da arquitetura.

Pipeline, em ordem fixa:

    body_md  ──►  markdown-it-py  ──►  nh3.clean()  ──►  body_html
                  (html=False)         (allowlist)

Duas defesas independentes, de propósito:

1. markdown-it-py com ``html=False``: HTML embutido no Markdown é escapado,
   nunca interpretado.
2. Saída passada por ``nh3`` (binding Rust da ammonia) com allowlist explícita
   de tags e atributos.

Nunca confiar apenas no renderizador de Markdown para segurança: vários
permitem HTML bruto por padrão ou por descuido de configuração. A sanitização
é a linha que não pode falhar, e por isso é a última.

``bleach`` está descontinuado e não deve ser usado em código novo.
"""

from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlparse

import nh3
from django.conf import settings
from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from .text import normalize_nfc

# --------------------------------------------------------------------------
# Allowlist de sanitização
# --------------------------------------------------------------------------

ALLOWED_TAGS: set[str] = {
    "p",
    "br",
    "hr",
    "strong",
    "em",
    "del",
    "s",
    "sup",
    "sub",
    "blockquote",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "a",
    "img",
    "code",
    "pre",
    "span",
    "div",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}

ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "loading"},
    # `class` restrito a estes três porque é o que o Pygments emite. Não é
    # liberado em geral: classe arbitrária permite ao usuário reaproveitar
    # o CSS do site para forjar elementos de interface.
    "code": {"class"},
    "pre": {"class"},
    "span": {"class"},
    "div": {"class"},
    "th": {"align"},
    "td": {"align"},
}

ALLOWED_URL_SCHEMES: set[str] = {"http", "https", "mailto"}

# Aplicado a todo <a> na saída. `ugc` e `nofollow` evitam que o fórum vire
# alvo de spam de SEO; `noopener` impede que a página de destino manipule
# a janela de origem.
LINK_REL = "nofollow ugc noopener noreferrer"


# --------------------------------------------------------------------------
# Renderizador
# --------------------------------------------------------------------------


def _highlight_code(code: str, lang: str, _attrs: str) -> str:
    """Destaque de sintaxe no servidor, nunca por script no cliente."""
    if not lang:
        return ""
    try:
        lexer = get_lexer_by_name(lang, stripall=False)
    except ClassNotFound:
        return ""
    return str(highlight(code, lexer, HtmlFormatter(nowrap=False)))


def _is_local_url(url: str) -> bool:
    """Só URLs do próprio site — sem host e sem esquema."""
    parsed = urlparse(url)
    return not parsed.scheme and not parsed.netloc and url.startswith("/")


def _make_parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "linkify": True, "highlight": _highlight_code})
    md.enable(["table", "strikethrough", "linkify"])

    # md.renderer é declarado como RendererProtocol, que não expõe `rules`
    # nem `image`. Em `MarkdownIt("commonmark")` é sempre um RendererHTML.
    renderer = cast(RendererHTML, md.renderer)
    default_image = renderer.rules.get("image", renderer.image)

    def render_image(tokens: list[Token], idx: int, options: Any, env: Any) -> str:
        """Bloqueia imagem remota — §7.1.

        Imagem externa vaza o IP de todo leitor para um servidor de terceiros
        e pode trocar de conteúdo depois de a moderação ter aprovado o post.
        Só imagem servida pelo próprio site passa; o resto vira link comum.
        """
        token = tokens[idx]
        src = str(token.attrGet("src") or "")
        if _is_local_url(src):
            token.attrSet("loading", "lazy")
            return str(default_image(tokens, idx, options, env))
        alt = token.content or src
        return f'<a href="{escapeHtml(src)}">{escapeHtml(alt)}</a>'

    # Os stubs tipam `rules` como dict de MethodType, mas substituir uma regra
    # por função comum é a forma documentada de estender o markdown-it.
    renderer.rules["image"] = render_image  # type: ignore[assignment]
    return md


_PARSER = _make_parser()


def render_markdown(source: str) -> str:
    """Converte Markdown em HTML seguro, pronto para exibição."""
    if not source:
        return ""
    html = _PARSER.render(normalize_nfc(source))
    return nh3_clean(html)


def nh3_clean(html: str) -> str:
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes={tag: set(attrs) for tag, attrs in ALLOWED_ATTRIBUTES.items()},
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel=LINK_REL,
        strip_comments=True,
    )


def extract_internal_links(source: str) -> list[str]:
    """Devolve os caminhos internos citados no Markdown.

    Alimenta a tabela PostLink (§4.6), que sustenta os backlinks: ao ler um
    post, ver quais posts posteriores o citaram. Num fórum sobre Budismo isso
    permite rastrear, ao longo de anos, as discussões que referenciam a mesma
    passagem de sutta.
    """
    paths: list[str] = []
    for token in _PARSER.parse(normalize_nfc(source)):
        for child in token.children or []:
            if child.type == "link_open":
                href = str(child.attrGet("href") or "")
                if _is_local_url(href):
                    paths.append(href)
    return paths


def html_version() -> int:
    return int(settings.FORUM_HTML_VERSION)
