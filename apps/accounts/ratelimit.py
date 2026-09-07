"""Contador de tentativas no cache — §7.3.

Um contador por chave, com janela deslizante grosseira: a primeira tentativa
cria a chave com validade da janela, e as seguintes só incrementam. A janela
não desliza de verdade, ela expira inteira — o que basta para o uso aqui, que
é conter abuso, não medir tráfego.

Sem dependência nova. O Redis já está configurado com ``IGNORE_EXCEPTIONS``
(§7.2), então **se o cache cair, o limite deixa de valer e o fluxo continua**.
É a escolha certa para recuperação de senha: um limite que derruba o único
caminho de volta para a conta troca abuso por porta trancada.
"""

from __future__ import annotations

import hashlib

from django.core.cache import cache


def _chave(escopo: str, identificador: str) -> str:
    # O identificador é picado antes de virar chave: email em texto puro no
    # Redis é dado pessoal guardado sem necessidade, e o hash serve igual para
    # contar. Também evita os limites de tamanho e de caracteres da chave.
    digest = hashlib.sha256(identificador.strip().lower().encode("utf-8")).hexdigest()[:32]
    return f"limite:{escopo}:{digest}"


def excedeu(escopo: str, identificador: str, *, limite: int, janela: int) -> bool:
    """Registra uma tentativa e diz se ela passou do limite na janela."""
    chave = _chave(escopo, identificador)
    # add() só cria se não existir; é o que evita a corrida entre dois
    # pedidos simultâneos criarem a chave duas vezes e zerarem a contagem.
    if cache.add(chave, 1, timeout=janela):
        return False
    try:
        atual = cache.incr(chave)
    except ValueError:
        # A chave expirou entre o add() e o incr(). Tentativa nova, janela nova.
        cache.set(chave, 1, timeout=janela)
        return False
    return atual > limite
