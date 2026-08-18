from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.text import normalize_nfc

BODY_MAX_LENGTH = 60_000


class MarkdownBodyMixin(forms.Form):
    body_md = forms.CharField(
        label=_("Mensagem"),
        widget=forms.Textarea(attrs={"rows": 10, "placeholder": _("Escreva em Markdown…")}),
        max_length=BODY_MAX_LENGTH,
    )

    def clean_body_md(self) -> str:
        value = normalize_nfc(self.cleaned_data["body_md"]).strip()
        if not value:
            raise forms.ValidationError(_("A mensagem não pode ser vazia."))
        return value


class TopicForm(MarkdownBodyMixin):
    title = forms.CharField(label=_("Título"), max_length=200)

    field_order = ["title", "body_md"]

    def clean_title(self) -> str:
        value = normalize_nfc(self.cleaned_data["title"]).strip()
        if len(value) < 5:
            raise forms.ValidationError(_("O título precisa de pelo menos 5 caracteres."))
        return value


class PostForm(MarkdownBodyMixin):
    pass
