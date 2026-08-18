"""Normalização Unicode — §6.2 da arquitetura.

`não` admite duas codificações válidas em Unicode:

    "não"        ã pré-composto          (NFC)
    "não"       a + til combinante      (NFD)

Aparência idêntica, bytes diferentes. macOS produz NFD, Linux e Windows
produzem NFC. Sem normalizar, o mesmo texto visível gera chaves diferentes:
a busca não encontra, o UNIQUE não colide, a deduplicação falha — e nada
disso aparece na tela, porque as duas strings são visualmente iguais.

Vale igualmente para o conteúdo estrangeiro que o fórum aceita: `saṅgha`
em Pāli, Devanágari e tibetano têm todos múltiplas formas normalizadas.

Regra: todo texto é normalizado para NFC ao entrar, antes de qualquer
validação ou persistência. O ponto de aplicação são os campos de modelo
abaixo, e não os formulários, porque assim escritas feitas direto pelo ORM
(migrações de dados, comandos de gestão, shell) também passam pela regra.
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING, Any

from django.db import models

if TYPE_CHECKING:
    # django-stubs parametriza os campos por (tipo ao gravar, tipo ao ler).
    # Em tempo de execução esses índices não existem, daí o alias condicional.
    _CharBase = models.CharField[str, str]
    _TextBase = models.TextField[str, str]
else:
    _CharBase = models.CharField
    _TextBase = models.TextField


def normalize_nfc(value: str) -> str:
    """Normaliza para NFC. Idempotente."""
    return unicodedata.normalize("NFC", value)


def is_nfc(value: str) -> bool:
    return unicodedata.is_normalized("NFC", value)


class NFCFieldMixin:
    """Normaliza o valor para NFC no caminho de escrita do campo."""

    def get_prep_value(self, value: Any) -> Any:
        value = super().get_prep_value(value)  # type: ignore[misc]
        if isinstance(value, str):
            return normalize_nfc(value)
        return value

    def to_python(self, value: Any) -> Any:
        value = super().to_python(value)  # type: ignore[misc]
        if isinstance(value, str):
            return normalize_nfc(value)
        return value


class NFCCharField(NFCFieldMixin, _CharBase):
    """CharField que persiste sempre em NFC."""


class NFCTextField(NFCFieldMixin, _TextBase):
    """TextField que persiste sempre em NFC."""
