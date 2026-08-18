"""Testes de segurança de nome de usuário — §6.3.

Estes testes protegem uma propriedade de segurança, não uma conveniência:
se caírem, o fórum voltou a permitir personificação de moderadores.
"""

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.validators import (
    username_skeleton,
    validate_display_name,
    validate_username,
)


class TestHomoglifos:
    def test_cirilico_e_rejeitado(self) -> None:
        """`Аdmin` com А cirílico (U+0410) parece `admin` latino."""
        with pytest.raises(ValidationError):
            validate_username("аdmin")  # а cirílico

    def test_grego_e_rejeitado(self) -> None:
        with pytest.raises(ValidationError):
            validate_username("οmega")  # ο grego

    def test_rn_colide_com_m(self) -> None:
        assert username_skeleton("rnoderador") == username_skeleton("moderador")

    def test_zero_colide_com_o(self) -> None:
        assert username_skeleton("m0derad0r") == username_skeleton("moderador")

    def test_um_e_l_e_i_colidem(self) -> None:
        assert username_skeleton("s1lva") == username_skeleton("silva")
        assert username_skeleton("sllva") == username_skeleton("silva")

    def test_reservado_com_troca_de_homoglifo_e_bloqueado(self) -> None:
        """`admin` tem skeleton `admln` (i → l). Comparar contra a lista crua
        deixaria o próprio `admin` passar."""
        for variante in ("admin", "admln", "adm1n", "rnoderador", "m0derador"):
            with pytest.raises(ValidationError):
                validate_username(variante)

    def test_separadores_sao_decorativos(self) -> None:
        base = username_skeleton("mariasilva")
        assert username_skeleton("maria.silva") == base
        assert username_skeleton("maria_silva") == base
        assert username_skeleton("maria-silva") == base

    def test_acento_nao_cria_conta_distinta(self) -> None:
        assert username_skeleton("joão") == username_skeleton("joao")

    def test_nomes_realmente_distintos_nao_colidem(self) -> None:
        assert username_skeleton("ananda") != username_skeleton("nagarjuna")


class TestUsernameValido:
    @pytest.mark.parametrize(
        "nome", ["ananda", "maria.silva", "joão", "nagarjuna-2", "praticante_01", "açucena"]
    )
    def test_aceitos(self, nome: str) -> None:
        validate_username(nome)

    @pytest.mark.parametrize(
        "nome",
        [
            "ab",  # curto demais
            "a" * 31,  # longo demais
            "Maiuscula",  # maiúscula
            ".comeca_com_ponto",
            "termina_com_ponto.",
            "com espaco",
            "emoji🪷",
            "admin",  # reservado
            "rnoderador",  # skeleton bate em reservado
        ],
    )
    def test_rejeitados(self, nome: str) -> None:
        with pytest.raises(ValidationError):
            validate_username(nome)


class TestDisplayName:
    @pytest.mark.parametrize(
        "nome", ["Maria Silva", "मैत्रेय", "ཀུན་དགའ་", "慧能", "Ānanda Thera", "Zé 🪷"]
    )
    def test_unicode_livre_e_aceito(self, nome: str) -> None:
        """A liberdade aqui é intencional: escrever o próprio nome em tibetano
        ou devanágari precisa funcionar."""
        validate_display_name(nome)

    def test_vazio_rejeitado(self) -> None:
        with pytest.raises(ValidationError):
            validate_display_name("   ")

    def test_caractere_invisivel_rejeitado(self) -> None:
        """U+200B é largura zero: permitiria dois perfis visualmente iguais."""
        with pytest.raises(ValidationError):
            validate_display_name("Maria​Silva")

    def test_marcador_de_direcao_rejeitado(self) -> None:
        """U+202E inverte a ordem do texto na tela e serve para disfarçar."""
        with pytest.raises(ValidationError):
            validate_display_name("Maria‮Silva")

    def test_longo_demais_rejeitado(self) -> None:
        with pytest.raises(ValidationError):
            validate_display_name("a" * 61)
