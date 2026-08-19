# Buddhadharma

Fórum web sobre Budismo, em português. Software livre sob [AGPL-3.0](LICENSE).

Categorias gerenciadas em banco, posts em Markdown, reações com emoji, vínculos
entre posts com backlinks, histórico de edição e busca full-text em português —
aceitando Pāli, sânscrito, tibetano e chinês dentro do texto.

**Estado: Fases 0 e 1 concluídas.** Um fórum funcional em uma região.
O que vem a seguir e como pegar uma tarefa: **[docs/ROADMAP.md](docs/ROADMAP.md)**.

---

## Rodando

Precisa de [uv](https://docs.astral.sh/uv/) e Docker.

```bash
make setup     # dependências e .env
make up        # PostgreSQL e Redis
make migrate
make seed      # categorias e emojis iniciais
uv run python manage.py createsuperuser
make run       # http://localhost:8000
```

O painel de moderação fica em `/admin/`.

### Sem Docker

Precisa de um PostgreSQL 16+ **criado com collation ICU**. Não é detalhe de
preferência: a collation padrão `libc` depende do locale do sistema operacional
e diverge entre máquinas, o que corrompe índices em silêncio quando houver
réplica. Trocar depois exige reindexar a base inteira.

```sql
CREATE DATABASE buddhadharma
  ENCODING 'UTF8'
  LOCALE_PROVIDER icu
  ICU_LOCALE 'pt-BR'
  LOCALE 'C'
  TEMPLATE template0;
```

Depois aponte `DATABASE_URL` no `.env` para esse banco.

---

## Comandos

| Comando | O que faz |
|---|---|
| `make check` | Tudo que o CI roda |
| `make test` | Suíte completa (precisa do PostgreSQL) |
| `make lint` | Ruff |
| `make typecheck` | mypy |
| `make fmt` | Formata e corrige o que dá |

---

## Stack

Django 5.2 · PostgreSQL 16 · Redis · Markdown (`markdown-it-py` + `nh3`) ·
templates server-side. Sem etapa de build e sem `node_modules`.

Detalhe e justificativa de cada escolha em **[docs/ARQUITETURA.md](docs/ARQUITETURA.md)**.

---

## Decisões que parecem estranhas até você ler o porquê

Estão todas documentadas, mas vale o aviso antes de alguém "consertar":

- **`username` não aceita Unicode livre.** `Аdmin` com А cirílico é
  indistinguível de `admin` e permite personificar moderadores. O nome livre
  fica em `display_name`, que nunca é usado em autorização. ([§6.3](docs/ARQUITETURA.md#63-nomes-de-usuário--segurança))
- **Contagem de reações é mantida por trigger no PostgreSQL**, não por sinal do
  Django — para valer também em importação em massa e correção via `psql`. ([§4.5](docs/ARQUITETURA.md#45-reações))
- **Paginação por cursor, nunca `OFFSET`.** ([§4.8](docs/ARQUITETURA.md#48-índices-que-importam))
- **Sessão em cookie assinado**, não em Redis. ([§3.5](docs/ARQUITETURA.md#35-redis))
- **Imagem externa vira link.** Vaza o IP de quem lê e pode trocar de conteúdo
  depois da moderação. ([§7.1](docs/ARQUITETURA.md#71-conteúdo-gerado-por-usuário))
- **`body_md` é a fonte de verdade; `body_html` é cache descartável.** ([§4.3](docs/ARQUITETURA.md#43-tópicos-e-posts))

---

## Contribuir

Projeto comunitário. Comece por:

1. **[docs/ROADMAP.md](docs/ROADMAP.md)** — o que está pronto, o que falta, boas primeiras tarefas
2. **[docs/ARQUITETURA.md](docs/ARQUITETURA.md)** — decisões técnicas e o porquê de cada uma
3. **[CONTRIBUTING.md](CONTRIBUTING.md)** — fluxo, padrões e regras de migração

O roadmap tem uma seção de **Armadilhas**: mudanças que parecem melhorias e quebram o projeto em silêncio. Vale a leitura antes do primeiro pull request.

## Licença

AGPL-3.0-or-later. Fórum é software acessado pela rede: a AGPL garante que quem
rodar uma versão modificada como serviço publique as mudanças.
