"""Montagem da Content-Security-Policy — §7.1 da arquitetura.

A CSP é a segunda linha de defesa sob a sanitização do Markdown: se algum dia
passar um ``<script>`` pelo ``nh3``, é ela que impede a execução no navegador
de quem lê.

**A política nasce aqui e em nenhum outro lugar.** Middleware, configurações e
testes leem estas constantes; nenhum deles monta cabeçalho à mão. Política
espalhada é política que diverge — e divergência em CSP se descobre em
produção, com o recurso quebrado ou com a defesa silenciosamente ausente.

Este módulo é de propósito só de biblioteca padrão: ``config/settings/base.py``
o importa enquanto o Django ainda está carregando, quando importar código de
aplicativo daria import circular.

Hash, nunca nonce
-----------------

Nonce precisa ser único por resposta. A §8 guarda páginas inteiras em cache, e
uma página servida do cache carregaria um nonce velho, que não bate com o
cabeçalho recalculado na requisição — a página quebra ou a proteção evapora.
Os scripts do projeto são estáticos, então o hash é estável e o cabeçalho não
varia com a resposta.
"""

from __future__ import annotations

import base64
import hashlib

# Cada diretiva aponta para as fontes que aceita. Tupla vazia não existe: o
# valor certo para "nada" é ``'none'``, explícito.
DIRETIVAS: dict[str, tuple[str, ...]] = {
    # Padrão fechado. Toda diretiva não listada abaixo herda daqui.
    "default-src": ("'self'",),
    # Sem 'unsafe-inline' e sem 'unsafe-eval'. Script inline entra por hash,
    # via CSP_SCRIPT_HASHES.
    "script-src": ("'self'",),
    "style-src": ("'self'",),
    # Imagem remota vira link na renderização do Markdown (apps/core/markdown.py),
    # então nenhuma página legítima carrega imagem de terceiro. Sem 'data:':
    # data: em img-src é vetor conhecido de exfiltração por SVG.
    "img-src": ("'self'",),
    "font-src": ("'self'",),
    "connect-src": ("'self'",),
    # Plugin e <object> não têm uso no projeto e são superfície de ataque pura.
    "object-src": ("'none'",),
    # Impede que uma injeção mude a base das URLs relativas e redirecione
    # todo carregamento da página para outro host.
    "base-uri": ("'self'",),
    # Clickjacking. Equivale a X-Frame-Options: DENY, que continua em prod.py
    # para navegador antigo que não conhece frame-ancestors.
    "frame-ancestors": ("'none'",),
    "form-action": ("'self'",),
    "frame-src": ("'none'",),
}

# O admin do Django serve o próprio JavaScript como arquivo estático, mas
# ainda emite atributos `style` e blocos de estilo inline em várias telas
# (calendário, seletor de relacionados). Sem esta frouxidão o admin fica
# visualmente quebrado. Ela vale **só** sob o prefixo do admin, e **só** para
# estilo: script-src continua estrito, que é o que impede execução.
DIRETIVAS_ADMIN: dict[str, tuple[str, ...]] = {
    **DIRETIVAS,
    "style-src": ("'self'", "'unsafe-inline'"),
}


def hash_de_script(conteudo: str) -> str:
    """Devolve a fonte ``'sha256-...'`` correspondente a um script inline.

    ``conteudo`` é o texto entre ``<script>`` e ``</script>``, sem as tags. O
    hash cobre o conteúdo exato: um espaço a mais e o navegador recusa o
    script. Por isso ``test_csp.py`` recalcula os hashes a partir dos próprios
    templates e compara com a configuração — assim a divergência aparece na
    suíte, não em produção.
    """
    digest = hashlib.sha256(conteudo.encode("utf-8")).digest()
    return f"'sha256-{base64.b64encode(digest).decode('ascii')}'"


def montar_politica(
    diretivas: dict[str, tuple[str, ...]],
    hashes_de_script: tuple[str, ...] = (),
) -> str:
    """Serializa as diretivas no valor do cabeçalho."""
    partes = []
    for nome, fontes in diretivas.items():
        if nome == "script-src":
            fontes = (*fontes, *hashes_de_script)
        partes.append(f"{nome} {' '.join(fontes)}")
    return "; ".join(partes)
