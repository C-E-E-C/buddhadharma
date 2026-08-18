"""Testes do pipeline de renderização — §7.1.

A sanitização é a linha que não pode falhar. Estes testes existem para que
uma mudança futura no renderizador não a atravesse sem ninguém perceber.
"""

import pytest

from apps.core.markdown import extract_internal_links, render_markdown


class TestSanitizacao:
    # As asserções olham a estrutura do HTML, não a presença da palavra: um
    # payload que sai escapado como texto (`&lt;script&gt;`) é o resultado
    # correto, e a palavra continua visível na saída.

    def test_script_embutido_nao_sobrevive(self) -> None:
        html = render_markdown("Olá <script>alert('xss')</script> mundo")
        assert "<script" not in html

    def test_html_bruto_e_escapado(self) -> None:
        html = render_markdown("<div onclick='roubar()'>clique</div>")
        assert "<div" not in html
        assert "&lt;div" in html

    def test_javascript_em_href_e_removido(self) -> None:
        html = render_markdown("[clique](javascript:alert(1))")
        assert 'href="javascript:' not in html
        assert "<a " not in html

    def test_atributo_de_evento_e_removido(self) -> None:
        html = render_markdown('<img src="/x.png" onerror="alert(1)">')
        assert "<img" not in html

    @pytest.mark.parametrize(
        "payload",
        [
            "<iframe src='https://exemplo.com'></iframe>",
            "<object data='x'></object>",
            "<style>body{display:none}</style>",
            "<svg onload=alert(1)>",
            "<form action='/roubar'><input name='senha'></form>",
        ],
    )
    def test_tags_perigosas_nao_passam(self, payload: str) -> None:
        html = render_markdown(payload)
        for tag in ("<iframe", "<object", "<style", "<svg", "<form", "<input"):
            assert tag not in html


class TestLinks:
    def test_link_externo_recebe_rel_de_seguranca(self) -> None:
        html = render_markdown("[site](https://exemplo.com)")
        assert "nofollow" in html
        assert "noopener" in html
        assert "ugc" in html


class TestImagens:
    def test_imagem_local_e_mantida(self) -> None:
        html = render_markdown("![lótus](/media/lotus.png)")
        assert "<img" in html
        assert "/media/lotus.png" in html

    def test_imagem_remota_vira_link(self) -> None:
        """Imagem externa vaza o IP de todo leitor e pode trocar de conteúdo
        depois da moderação. Vira link comum."""
        html = render_markdown("![externa](https://terceiro.example/rastreador.png)")
        assert "<img" not in html
        assert "<a href=" in html


class TestFormatacao:
    def test_markdown_basico(self) -> None:
        html = render_markdown("**forte** e *ênfase*")
        assert "<strong>forte</strong>" in html
        assert "<em>ênfase</em>" in html

    def test_citacao(self) -> None:
        assert "<blockquote>" in render_markdown("> palavra do Buda")

    def test_tabela(self) -> None:
        html = render_markdown("| a | b |\n|---|---|\n| 1 | 2 |")
        assert "<table>" in html

    def test_bloco_de_codigo_com_destaque(self) -> None:
        html = render_markdown("```python\nx = 1\n```")
        assert "<pre" in html

    def test_conteudo_estrangeiro_preservado(self) -> None:
        """Requisito do fórum: português na interface, citações em Pāli,
        sânscrito, tibetano e chinês dentro do texto."""
        fonte = "Sobre *anattā* (अनात्मन्, བདག་མེད་, 無我) no Saṃyutta Nikāya."
        html = render_markdown(fonte)
        for trecho in ("anattā", "अनात्मन्", "བདག་མེད་", "無我", "Saṃyutta"):
            assert trecho in html

    def test_vazio(self) -> None:
        assert render_markdown("") == ""


class TestVinculosInternos:
    def test_extrai_caminho_interno(self) -> None:
        fonte = "veja [este post](/t/12/anicca/) e [externo](https://exemplo.com)"
        assert extract_internal_links(fonte) == ["/t/12/anicca/"]

    def test_ignora_externos(self) -> None:
        assert extract_internal_links("[fora](https://exemplo.com)") == []
