"""Validação e desambiguação de nome de usuário — §6.3 da arquitetura.

O problema
----------

Aceitar Unicode irrestrito em nome de usuário permite ataque de homóglifos.
``Аdmin``, escrito com А cirílico (U+0410), é visualmente indistinguível de
``Admin`` latino, mas é outra string e passa por qualquer verificação de
unicidade ingênua. O resultado é personificação de moderadores — grave num
fórum, onde a autoridade de uma mensagem depende de quem a assina.

A defesa tem duas camadas
-------------------------

1. **Conjunto restrito de caracteres.** ``username`` aceita apenas minúsculas
   latinas, dígitos, ``. _ -`` e os acentuados do português. Isso já elimina
   toda a classe de ataque entre alfabetos (cirílico, grego, armênio), porque
   esses caracteres simplesmente não entram.

2. **Skeleton de confusáveis.** Sobra a confusão dentro do próprio alfabeto
   latino: ``rn`` parece ``m``, ``0`` parece ``o``, ``l`` parece ``1``. O
   skeleton reduz o nome à sua forma visualmente canônica, e é ele que carrega
   a restrição UNIQUE no banco. Assim ``rnoderador`` e ``moderador`` colidem.

A unicidade é imposta por constraint no banco, e não por consulta prévia na
aplicação: duas requisições simultâneas passariam pelas duas consultas antes
de qualquer uma gravar.

E o nome que a pessoa escolheu?
-------------------------------

Fica em ``display_name``, Unicode livre, exibido em toda a interface. É a
separação que resolve o dilema: liberdade na apresentação, rigor na
identidade. **Nenhuma decisão de autorização olha para ``display_name``.**
"""

from __future__ import annotations

import re
import unicodedata

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.core.text import normalize_nfc

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30

# Minúsculas latinas, dígitos, separadores e os acentuados do português.
# Deliberadamente sem outros alfabetos — ver camada 1 acima.
_PORTUGUESE_LETTERS = "áàâãéêíóôõúüç"
_USERNAME_RE = re.compile(
    rf"\A[a-z0-9{_PORTUGUESE_LETTERS}]([a-z0-9{_PORTUGUESE_LETTERS}._-]*"
    rf"[a-z0-9{_PORTUGUESE_LETTERS}])?\Z"
)

# Grupos que se confundem à vista dentro do alfabeto latino.
# A ordem importa: as sequências de dois caracteres são aplicadas antes.
_CONFUSABLE_SEQUENCES = (
    ("rn", "m"),
    ("vv", "w"),
    ("cl", "d"),
)
_CONFUSABLE_CHARS = str.maketrans(
    {
        "0": "o",
        "1": "l",
        "i": "l",
        "5": "s",
        "2": "z",
        "8": "b",
    }
)

RESERVED_USERNAMES = frozenset(
    {
        "admin",
        "administrador",
        "administracao",
        "root",
        "sistema",
        "system",
        "moderador",
        "moderacao",
        "mod",
        "staff",
        "equipe",
        "suporte",
        "ajuda",
        "buddhadharma",
        "sangha",
        "oficial",
        "anonimo",
        "deletado",
        "removido",
        "api",
        "static",
        "media",
        "conta",
        "login",
        "logout",
        "registro",
        "senha",
        "null",
        "none",
        "undefined",
        "me",
        "eu",
    }
)

# A comparação precisa ser entre skeletons, não entre os nomes literais.
# `admin` tem skeleton `admln` (i → l), então comparar o skeleton do candidato
# com a lista crua deixaria `admin` passar — e foi exatamente o que o teste
# pegou. A lista existe para bloquear tudo que *parece* reservado.
# RESERVED_SKELETONS é derivada logo após a definição de username_skeleton().


def username_skeleton(username: str) -> str:
    """Reduz o nome à forma visualmente canônica.

    Dois nomes com o mesmo skeleton são indistinguíveis a olho nu e não podem
    coexistir. É este valor que leva o UNIQUE no banco, não o ``username``.

    >>> username_skeleton("Moderador")
    'moderador'
    >>> username_skeleton("rnoderad0r") == username_skeleton("moderador")
    True
    >>> username_skeleton("ma.ri-a") == username_skeleton("maria")
    True
    """
    value = normalize_nfc(username).casefold()

    # Remove acento: `joão` e `joao` não podem ser contas diferentes.
    decomposed = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in decomposed if not unicodedata.combining(ch))

    for sequence, replacement in _CONFUSABLE_SEQUENCES:
        value = value.replace(sequence, replacement)
    value = value.translate(_CONFUSABLE_CHARS)

    # Separadores são decorativos: `maria.silva`, `maria_silva` e `mariasilva`
    # são o mesmo nome aos olhos de quem lê com pressa.
    return re.sub(r"[._-]", "", value)


RESERVED_SKELETONS = frozenset(username_skeleton(name) for name in RESERVED_USERNAMES)


def validate_username(value: str) -> None:
    """Valida ``username`` contra as regras da camada 1."""
    value = normalize_nfc(value)

    if len(value) < USERNAME_MIN_LENGTH:
        raise ValidationError(
            _("O nome de usuário precisa de pelo menos %(n)d caracteres."),
            params={"n": USERNAME_MIN_LENGTH},
            code="username_curto",
        )
    if len(value) > USERNAME_MAX_LENGTH:
        raise ValidationError(
            _("O nome de usuário pode ter no máximo %(n)d caracteres."),
            params={"n": USERNAME_MAX_LENGTH},
            code="username_longo",
        )
    if value != value.lower():
        raise ValidationError(
            _("Use apenas letras minúsculas no nome de usuário."),
            code="username_maiuscula",
        )
    if not _USERNAME_RE.match(value):
        raise ValidationError(
            _(
                "Use apenas letras minúsculas, números, ponto, hífen e sublinhado. "
                "Acentos do português são aceitos. O nome não pode começar nem "
                "terminar com separador."
            ),
            code="username_invalido",
        )
    if username_skeleton(value) in RESERVED_SKELETONS:
        raise ValidationError(
            _("Este nome de usuário é reservado."),
            code="username_reservado",
        )


def validate_display_name(value: str) -> None:
    """Valida o nome exibido — Unicode livre, com poucas restrições.

    Aqui a liberdade é intencional: escrever o próprio nome em tibetano,
    devanágari ou japonês precisa funcionar. O que se bloqueia é apenas o que
    quebra a apresentação ou forja elementos de interface.
    """
    value = normalize_nfc(value)

    if not value.strip():
        raise ValidationError(_("O nome exibido não pode ser vazio."), code="display_vazio")
    if len(value) > 60:
        raise ValidationError(
            _("O nome exibido pode ter no máximo 60 caracteres."), code="display_longo"
        )

    for ch in value:
        category = unicodedata.category(ch)
        # Cc: controle. Cf: formatação invisível, inclui os marcadores de
        # direção que reordenam texto na tela. Co: uso privado. Cs: surrogate.
        # Zl/Zp: quebra de linha e de parágrafo.
        if category in {"Cc", "Cf", "Co", "Cs", "Zl", "Zp"}:
            raise ValidationError(
                _("O nome exibido contém caracteres invisíveis ou de controle."),
                code="display_invisivel",
            )
