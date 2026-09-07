"""Testes da Content-Security-Policy — §7.1."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client

from apps.core.csp import DIRETIVAS, hash_de_script, montar_politica


def _diretiva(politica: str, nome: str) -> str:
    """Extrai uma diretiva do cabeçalho, para não testar por substring solta."""
    for parte in politica.split(";"):
        parte = parte.strip()
        if parte.split(" ")[0] == nome:
            return parte
    raise AssertionError(f"diretiva ausente na política: {nome!r}\n{politica}")


@pytest.mark.django_db
class TestCabecalho:
    def test_presente_em_pagina_comum(self, client: Client) -> None:
        resposta = client.get("/")
        assert resposta["Content-Security-Policy"] == settings.CSP_POLICY

    def test_presente_tambem_em_redirecionamento(self, client: Client) -> None:
        # Resposta de erro e de redirecionamento também renderizam HTML.
        resposta = client.get("/nao-existe-esta-url/")
        assert resposta.status_code == 404
        assert "Content-Security-Policy" in resposta

    def test_sem_unsafe_inline_nem_unsafe_eval_em_script(self, client: Client) -> None:
        script_src = _diretiva(client.get("/")["Content-Security-Policy"], "script-src")
        assert "'unsafe-inline'" not in script_src
        assert "'unsafe-eval'" not in script_src


class TestPolitica:
    @pytest.mark.parametrize(
        ("nome", "esperado"),
        [
            ("default-src", "default-src 'self'"),
            ("object-src", "object-src 'none'"),
            ("base-uri", "base-uri 'self'"),
            ("frame-ancestors", "frame-ancestors 'none'"),
            ("img-src", "img-src 'self'"),
        ],
    )
    def test_diretivas_exigidas(self, nome: str, esperado: str) -> None:
        assert _diretiva(settings.CSP_POLICY, nome) == esperado

    def test_hashes_entram_em_script_src(self) -> None:
        politica = montar_politica(DIRETIVAS, ("'sha256-abc'", "'sha256-def'"))
        assert _diretiva(politica, "script-src") == "script-src 'self' 'sha256-abc' 'sha256-def'"

    def test_hash_confere_com_o_algoritmo_do_navegador(self) -> None:
        # Valor conhecido, conferido fora do Python:
        #     printf 'alert(1)' | openssl dgst -sha256 -binary | openssl base64
        # Se esta linha falhar, o hash publicado no cabeçalho não é o que o
        # navegador calcula, e todo script inline do projeto é recusado.
        assert hash_de_script("alert(1)") == "'sha256-bhHHL3z2vDgxUt0W3dWQOrprscmda2Y5pLsLg4GF+pI='"


@pytest.mark.django_db
class TestAdmin:
    def test_estilo_inline_liberado_sob_o_admin(self, client: Client) -> None:
        politica = client.get("/admin/login/")["Content-Security-Policy"]
        assert "'unsafe-inline'" in _diretiva(politica, "style-src")

    def test_script_continua_estrito_sob_o_admin(self, client: Client) -> None:
        politica = client.get("/admin/login/")["Content-Security-Policy"]
        assert _diretiva(politica, "script-src") == _diretiva(settings.CSP_POLICY, "script-src")


@pytest.mark.django_db
class TestModoRelato:
    def test_muda_o_nome_do_cabecalho_e_mantem_a_politica(
        self, client: Client, settings_relato: None
    ) -> None:
        resposta = client.get("/")
        assert "Content-Security-Policy" not in resposta
        assert resposta["Content-Security-Policy-Report-Only"] == settings.CSP_POLICY


@pytest.fixture
def settings_relato(settings):  # type: ignore[no-untyped-def]
    settings.CSP_REPORT_ONLY = True


SCRIPT_COM_CONTEUDO = re.compile(
    r"<script(?![^>]*\ssrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
)


def test_todo_script_inline_dos_templates_tem_hash_configurado() -> None:
    """Impede que um script inline entre sem o hash correspondente.

    Sem esta guarda, o script novo é recusado silenciosamente pelo navegador:
    a página carrega, o recurso não funciona, e nada aparece nos registros do
    servidor. O caso que ela cobre é justamente o do BD-005.
    """
    faltando: list[str] = []
    for template in (settings.BASE_DIR / "templates").rglob("*.html"):
        for conteudo in SCRIPT_COM_CONTEUDO.findall(template.read_text(encoding="utf-8")):
            if not conteudo.strip():
                continue
            if hash_de_script(conteudo) not in settings.CSP_SCRIPT_HASHES:
                faltando.append(f"{Path(template).relative_to(settings.BASE_DIR)}: {conteudo[:60]}")
    assert not faltando, "script inline sem hash em CSP_SCRIPT_HASHES:\n" + "\n".join(faltando)
