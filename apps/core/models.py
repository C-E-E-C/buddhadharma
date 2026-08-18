"""Modelos base reaproveitados pelas demais apps."""

from __future__ import annotations

from typing import TypeVar

from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("criado em", auto_now_add=True, db_index=True)

    class Meta:
        abstract = True


# Genéricos de propósito. Fixar o parâmetro em SoftDeleteModel faria
# `Post.objects.filter(...)` ser tipado como SoftDeleteModel, e o verificador
# passaria a rejeitar todo campo que não existe na base abstrata.
_M = TypeVar("_M", bound=models.Model)


class SoftDeleteQuerySet(models.QuerySet[_M]):
    def alive(self) -> SoftDeleteQuerySet[_M]:
        return self.filter(deleted_at__isnull=True)

    def dead(self) -> SoftDeleteQuerySet[_M]:
        return self.filter(deleted_at__isnull=False)


class AliveManager(models.Manager[_M]):
    """Manager padrão: esconde o que foi removido."""

    def get_queryset(self) -> SoftDeleteQuerySet[_M]:
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class AllObjectsManager(models.Manager[_M]):
    """Manager de moderação: enxerga tudo, inclusive o removido."""

    def get_queryset(self) -> SoftDeleteQuerySet[_M]:
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """Remoção reversível — §4.3.

    Moderação precisa poder desfazer. Um post apagado de verdade não volta,
    e a decisão de apagar costuma ser tomada com pressa e informação parcial.

    O manager padrão ``objects`` já filtra o que foi removido; ``all_objects``
    expõe tudo e existe para as telas de moderação.
    """

    deleted_at = models.DateTimeField("removido em", null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        "accounts.User",
        verbose_name="removido por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    objects = AliveManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self, by: object | None = None) -> None:
        self.deleted_at = timezone.now()
        self.deleted_by = by  # type: ignore[assignment]
        self.save(update_fields=["deleted_at", "deleted_by"])

    def restore(self) -> None:
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["deleted_at", "deleted_by"])
