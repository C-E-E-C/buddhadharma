"""Testes de normalização Unicode — §6.2."""

import unicodedata

from apps.core.text import is_nfc, normalize_nfc

# Mesma palavra visível, duas codificações. Sem normalizar, são chaves
# diferentes no banco — e a diferença é invisível na tela.
NAO_NFC = "não"  # ã pré-composto
NAO_NFD = "não"  # a + til combinante


class TestNormalizacao:
    def test_as_duas_formas_sao_bytes_diferentes(self) -> None:
        """Confirma a premissa do problema antes de testar a solução."""
        assert NAO_NFC != NAO_NFD
        assert len(NAO_NFC) == 3
        assert len(NAO_NFD) == 4

    def test_normalizacao_torna_iguais(self) -> None:
        assert normalize_nfc(NAO_NFC) == normalize_nfc(NAO_NFD)

    def test_idempotente(self) -> None:
        uma_vez = normalize_nfc(NAO_NFD)
        assert normalize_nfc(uma_vez) == uma_vez

    def test_is_nfc(self) -> None:
        assert is_nfc(NAO_NFC)
        assert not is_nfc(NAO_NFD)

    def test_pali_normalizado(self) -> None:
        """`saṅgha` também tem múltiplas formas — vale a mesma regra."""
        composto = "saṅgha"  # ṅ pré-composto
        decomposto = "saṅgha"  # n + ponto sobrescrito
        assert normalize_nfc(composto) == normalize_nfc(decomposto)

    def test_devanagari_preservado(self) -> None:
        texto = "अनात्मन्"
        assert normalize_nfc(texto) == unicodedata.normalize("NFC", texto)

    def test_texto_sem_acento_inalterado(self) -> None:
        assert normalize_nfc("dukkha") == "dukkha"
