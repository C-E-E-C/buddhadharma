"""Verificações de autoridade.

Ponto único de decisão. Toda view que pergunta "esta pessoa pode moderar?"
chama daqui, e não `request.user.is_moderator` direto — porque `request.user`
pode ser `AnonymousUser`, que não tem esse atributo. O verificador de tipos
aponta isso; em produção seria um 500 na primeira visita de quem não está
autenticado.

Nenhuma destas funções olha `display_name` — §6.3.
"""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser

from apps.accounts.models import User


def is_moderator(user: User | AnonymousUser) -> bool:
    return bool(user.is_authenticated and isinstance(user, User) and user.is_moderator)


def require_user(user: User | AnonymousUser) -> User:
    """Estreita o tipo depois de `@login_required`.

    O decorador garante em tempo de execução que há usuário autenticado, mas
    essa garantia não chega ao verificador de tipos. Esta função transporta a
    garantia, e falha alto caso o decorador seja removido por engano.

    .. warning::
       O objeto devolvido continua sendo o ``request.user``, que é um
       ``SimpleLazyObject``. Ele delega ``__class__`` ao usuário embrulhado —
       daí o ``isinstance`` acima passar — mas **``type()`` devolve a classe do
       proxy**, sem ``.objects`` nem nada do modelo.

       Nunca escreva ``type(user).objects``; use ``get_user_model()``. Já
       causou um erro 500 ao publicar tópico.
    """
    if not isinstance(user, User):
        raise PermissionError("Esta operação exige usuário autenticado.")
    return user
