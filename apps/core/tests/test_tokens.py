"""Testes do sistema de design — docs/DESIGN.md §2 a §4 e §7.

Os contrastes da paleta estão calculados na documentação, mas documentação não
reprova ninguém. Estes testes recalculam os números **a partir do CSS que é
servido**, para que uma cor ajustada "só um tom" não derrube a legibilidade em
silêncio.
"""

from __future__ import annotations

import re

import pytest
from django.conf import settings

CSS = (settings.BASE_DIR / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
FORUM_CSS = (settings.BASE_DIR / "static" / "css" / "forum.css").read_text(encoding="utf-8")

# Limiares da WCAG 2.2.
AA_TEXTO = 4.5
AA_INTERFACE = 3.0


def _luminancia(hexa: str) -> float:
    hexa = hexa.lstrip("#")
    canais = [int(hexa[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contraste(a: str, b: str) -> float:
    """Razão de contraste da WCAG 2.2 entre duas cores."""
    la, lb = _luminancia(a), _luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _bloco(seletor: str) -> str:
    """Devolve o corpo da regra CSS de um seletor."""
    inicio = CSS.index(seletor)
    abre = CSS.index("{", inicio)
    return CSS[abre : CSS.index("\n}", abre)]


def _cru(token: str) -> str:
    """Resolve um token da rampa ou dos neutros até o hex literal."""
    achado = re.search(rf"^\s*{re.escape(token)}:\s*(#[0-9a-f]{{6}});", CSS, re.MULTILINE)
    assert achado, f"token sem valor cru: {token}"
    return achado.group(1)


def _semantico(bloco: str, token: str) -> str:
    """Resolve um token semântico, seguindo o var() até o valor cru."""
    achado = re.search(rf"^\s*{re.escape(token)}:\s*([^;]+);", bloco, re.MULTILINE)
    assert achado, f"token semântico ausente no bloco: {token}"
    valor = achado.group(1).strip()
    referencia = re.fullmatch(r"var\((--[a-z0-9-]+)\)", valor)
    return _cru(referencia.group(1)) if referencia else valor


CLARO = ":root {"
ESCURO = ':root[data-theme="dark"] {'


@pytest.mark.parametrize("raiz", [CLARO, ESCURO], ids=["claro", "escuro"])
@pytest.mark.parametrize(
    ("frente", "fundo", "limiar"),
    [
        ("--tinta", "--fundo", AA_TEXTO),
        ("--tinta", "--superficie", AA_TEXTO),
        # Texto secundário é texto: não pode virar decoração cinza.
        ("--tinta-suave", "--fundo", AA_TEXTO),
        ("--acento", "--fundo", AA_TEXTO),
        ("--acento", "--superficie", AA_TEXTO),
        ("--perigo", "--fundo", AA_TEXTO),
        ("--sucesso", "--fundo", AA_TEXTO),
        ("--info", "--fundo", AA_TEXTO),
        # O par preenchimento + rótulo do botão sólido.
        ("--acento-rotulo", "--acento-superficie", AA_TEXTO),
        # Contorno de foco e borda de aviso são componentes de interface.
        ("--foco", "--fundo", AA_INTERFACE),
        ("--aviso-borda", "--fundo", AA_INTERFACE),
    ],
)
def test_contraste_dos_pares_semanticos(raiz: str, frente: str, fundo: str, limiar: float) -> None:
    bloco = _bloco(raiz)
    if raiz is ESCURO:
        # O bloco escuro só redefine o que muda; o resto herda do :root.
        claro = _bloco(CLARO)
        obter = lambda t: (  # noqa: E731
            _semantico(bloco, t)
            if re.search(rf"^\s*{re.escape(t)}:", bloco, re.MULTILINE)
            else _semantico(claro, t)
        )
    else:
        obter = lambda t: _semantico(bloco, t)  # noqa: E731
    razao = contraste(obter(frente), obter(fundo))
    assert razao >= limiar, f"{frente} sobre {fundo} em {raiz}: {razao:.2f}:1 < {limiar}:1"


def test_amarelo_nunca_e_tinta() -> None:
    """§3 — o passo 400 dá 1.92:1 sobre fundo claro. É superfície, não texto."""
    assert contraste(_cru("--quente-400"), _cru("--neutro-claro-fundo")) < AA_INTERFACE
    assert _semantico(_bloco(CLARO), "--acento") != _cru("--quente-400")


def test_rampa_completa_de_100_a_900() -> None:
    passos = re.findall(r"--quente-(\d00):", CSS)
    assert passos == ["100", "200", "300", "400", "500", "600", "700", "800", "900"]


def test_a_guarda_do_tema_claro_explicito() -> None:
    """Sem `:not([data-theme="light"])`, quem pediu claro recebe escuro."""
    assert "@media (prefers-color-scheme: dark)" in CSS
    assert ':root:not([data-theme="light"])' in CSS


def test_color_scheme_declarado_nos_dois_temas() -> None:
    assert "color-scheme: light" in _bloco(CLARO)
    assert "color-scheme: dark" in _bloco(ESCURO)


def test_nenhuma_cor_existe_so_dentro_de_media_query_ou_data_theme() -> None:
    """No estado "sistema" o atributo não é estampado.

    Uma cor definida só no bloco escuro simplesmente some ali, e a página
    renderiza texto de um tema sobre o fundo do outro.
    """
    no_root = set(re.findall(r"^\s*(--[a-z0-9-]+):", _bloco(CLARO), re.MULTILINE))
    for seletor in (ESCURO, ':root:not([data-theme="light"])'):
        for token in re.findall(r"^\s*(--[a-z0-9-]+):", _bloco(seletor), re.MULTILINE):
            assert token in no_root, f"{token} só existe em {seletor}"


def test_os_dois_gatilhos_de_escuro_dao_o_mesmo_resultado() -> None:
    """Preferência do sistema e escolha explícita não podem divergir."""

    def tokens(seletor: str) -> dict[str, str]:
        bloco = _bloco(seletor)
        return dict(re.findall(r"^\s*(--[a-z0-9-]+):\s*([^;]+);", bloco, re.MULTILINE))

    assert tokens(ESCURO) == tokens(':root:not([data-theme="light"])')


def test_medida_de_leitura_entre_65_e_75_caracteres() -> None:
    achado = re.search(r"--medida:\s*(\d+)ch;", CSS)
    assert achado, "--medida não definida"
    assert 65 <= int(achado.group(1)) <= 75
    assert "max-width: var(--medida)" in FORUM_CSS, "a medida existe mas não é aplicada ao corpo"


def test_nenhum_componente_referencia_a_rampa_ou_cor_crua() -> None:
    """A rampa se inverte entre os temas; quem a referencia quebra no escuro."""
    assert not re.search(r"--quente-\d00", FORUM_CSS)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", FORUM_CSS)
