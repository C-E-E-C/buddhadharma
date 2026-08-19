"""Busca full-text — §5 da arquitetura.

O vetor gravado em ``Post.search_vector`` combina duas configurações de busca
(a migração 0003 traz a medição que levou a isso):

* ``portuguese``   — stemmer com acentos. Faz `meditações` casar com `meditação`.
* ``pt_unaccent``  — mesma configuração com ``unaccent`` na cadeia de
  dicionários. Faz `meditacao` casar com `meditação`, e `anatta` com `anattā`.

**A consulta precisa usar as duas.** Consultar só uma delas perde metade dos
resultados, e perde em silêncio: a busca devolve menos, sem erro nenhum.

Sobra um caso que nenhuma das duas cobre — consulta **sem acento** numa
**flexão diferente** da que está no texto (`meditacao` contra um post que só
diz `meditações`). Para esse, há o recuo para trigrama em ``fuzzy_posts``.

Este módulo existe para que essas regras fiquem num lugar só. Nenhuma view
deve montar `SearchQuery` à mão.
"""

from __future__ import annotations

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import QuerySet

from .models import Post

CONFIG_COM_ACENTO = "portuguese"
CONFIG_SEM_ACENTO = "pt_unaccent"


def build_query(termo: str) -> SearchQuery:
    """Monta a consulta que casa com as duas metades do vetor."""
    termo = termo.strip()
    return SearchQuery(termo, config=CONFIG_COM_ACENTO, search_type="websearch") | SearchQuery(
        termo, config=CONFIG_SEM_ACENTO, search_type="websearch"
    )


def fulltext_posts(termo: str, *, limit: int = 50) -> QuerySet[Post]:
    """Só a parte full-text, ordenada por relevância."""
    if not termo.strip():
        return Post.objects.none()

    consulta = build_query(termo)
    return (
        Post.objects.filter(search_vector=consulta)
        .annotate(rank=SearchRank("search_vector", consulta))
        .select_related("topic", "author")
        .order_by("-rank", "-created_at")[:limit]
    )


def fuzzy_posts(termo: str, *, limit: int = 50) -> QuerySet[Post]:
    """Recuo por trigrama, para o que o full-text não alcança.

    Usa ``trigram_word_similar`` (operador ``%>``) e não ``trigram_similar``
    (``%``). A diferença importa: ``%`` compara as duas strings inteiras, então
    uma palavra contra um post de parágrafos dá similaridade baixíssima e nunca
    casa. Medido neste banco:

        similarity('Sobre as meditações do Buda.', 'meditacao')       = 0.19
        word_similarity('meditacao', 'Sobre as meditações do Buda.')  = 0.60

    Com o limiar padrão de 0.3, só a segunda passa. ``%>`` compara o termo com
    a melhor palavra do texto, que é o que se quer aqui.

    O índice GIN ``post_trigrama_idx`` atende este operador — verificado por
    EXPLAIN, é Bitmap Index Scan e não varredura sequencial.
    """
    termo = termo.strip()
    if not termo:
        return Post.objects.none()

    return (
        Post.objects.filter(body_md__trigram_word_similar=termo)
        .select_related("topic", "author")
        .order_by("-created_at")[:limit]
    )


def search_posts(termo: str, *, limit: int = 50, fuzzy_fallback: bool = False) -> QuerySet[Post]:
    """Busca posts, mais relevantes primeiro.

    `websearch` aceita a sintaxe que as pessoas já conhecem de buscadores:
    aspas para expressão exata, `-palavra` para excluir, `or` para alternativa.
    Ao contrário de `to_tsquery`, nunca levanta erro de sintaxe com entrada
    digitada por usuário — o que importa quando a entrada vem da web.

    Com ``fuzzy_fallback``, uma busca full-text sem resultado tenta o trigrama
    antes de desistir. Fica desligado por padrão: o trigrama não tem noção de
    relevância e, misturado ao resultado bom, só adiciona ruído. Como último
    recurso antes de "nada encontrado", vale a pena.
    """
    resultado = fulltext_posts(termo, limit=limit)
    if fuzzy_fallback and not resultado.exists():
        return fuzzy_posts(termo, limit=limit)
    return resultado
