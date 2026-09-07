"""Middleware do núcleo."""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse


class ContentSecurityPolicyMiddleware:
    """Aplica a CSP a toda resposta — §7.1.

    A política já vem pronta das configurações (``apps/core/csp.py`` a monta).
    Aqui só se decide **qual** das duas usar e sob que nome de cabeçalho.

    ``setdefault`` e não atribuição: uma view que precise de política própria
    pode definir o cabeçalho antes, e o middleware respeita.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        resposta = self.get_response(request)
        nome = (
            "Content-Security-Policy-Report-Only"
            if settings.CSP_REPORT_ONLY
            else "Content-Security-Policy"
        )
        politica = (
            settings.CSP_POLICY_ADMIN
            if request.path.startswith(settings.CSP_ADMIN_PREFIX)
            else settings.CSP_POLICY
        )
        resposta.setdefault(nome, politica)
        return resposta
