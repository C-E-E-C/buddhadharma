# Roadmap — Buddhadharma

Fórum sobre Budismo, em português. Software livre sob AGPL-3.0.

Este documento diz **onde o projeto está** e **o que vem a seguir**. É o ponto de partida para quem quer contribuir.

- Decisões técnicas e o porquê de cada uma: [ARQUITETURA.md](ARQUITETURA.md)
- Como contribuir na prática: [../CONTRIBUTING.md](../CONTRIBUTING.md)

---

## Legenda

| | Significado |
|---|---|
| ✅ | Pronto e verificado |
| 🟡 | **Parcial** — existe no banco, falta a interface ou o caminho de escrita |
| ⬜ | Não começou |
| 🔒 | Decisão travada. Ver [Armadilhas](#armadilhas) antes de mexer |

O 🟡 é o estado mais importante deste documento. Várias coisas foram construídas **só na camada de dados**, de propósito: mudar schema depois que há conteúdo é caro, mudar interface não é. Quem pegar um item 🟡 encontra a fundação pronta e o trabalho concentrado na parte visível.

---

## Estado atual

**Fases 0 e 1 fechadas.** O fórum funciona de ponta a ponta numa região.

Verificado contra PostgreSQL 16 real, não só em teoria:

- 85 testes passando com banco recriado do zero
- `ruff`, `ruff format`, `mypy` em modo strict (41 arquivos), `manage.py check`, `manage.py check --deploy`, `makemigrations --check` — todos limpos
- Collation ICU confirmada no cluster (`datlocprovider = i`, locale `pt-BR`), com a ordenação do português conferida na prática
- Migrações 0001–0003 aplicadas, incluindo triggers e extensões
- Servidor sobe; índice, categoria, login, registro e admin respondem 200
- Fluxo real exercitado: tópico com Markdown e Pāli, dois posts, uma reação — numeração, renderização, trigger de contagem e busca todos corretos

**Stack:** Django 5.2 · PostgreSQL 16 · Redis · Markdown (`markdown-it-py` + `nh3`) · templates server-side. Sem etapa de build, sem `node_modules`.

**Hospedagem decidida:** PostgreSQL gerenciado ([§14](ARQUITETURA.md#14-hospedagem-postgresql-gerenciado)). Provedor ainda não escolhido — ver [Decisões pendentes](#decisões-pendentes).

---

## Fase 0 — Fundação ✅

Concluída. Aqui ficaram as decisões que custam pouco agora e ficariam caras ou impossíveis depois.

- [x] Projeto Django, configuração separada por ambiente (`base`/`dev`/`test`/`prod`)
- [x] Docker Compose com PostgreSQL 16 e Redis
- [x] 🔒 Collation **ICU** `pt-BR` no cluster — não `libc`
- [x] 🔒 Normalização **NFC** aplicada no campo de modelo
- [x] 🔒 Modelo `User` customizado desde a primeira migração
- [x] 🔒 Sessão em cookie assinado, não em Redis
- [x] Argon2id, cabeçalhos de segurança, CSP prevista
- [x] Workflow de CI (lint, formatação, tipos, migração faltante, testes com Postgres ICU)
- [x] Licença AGPL-3.0, `README.md`, `CONTRIBUTING.md`

> **Nota:** o CI está escrito mas **nunca rodou** — o repositório ainda não tem remote. Primeira execução vai revelar ajustes.

---

## Fase 1 — Fórum mínimo ✅

Concluída, com uma lacuna listada abaixo.

- [x] Categorias hierárquicas, gerenciadas em banco e editáveis pelo admin
- [x] Tópicos e posts, com numeração sequencial por tópico
- [x] 🔒 `body_md` como fonte de verdade; `body_html` como cache versionado
- [x] 🔒 Renderização Markdown em duas camadas de defesa (`markdown-it-py` com `html=False`, depois `nh3` com allowlist)
- [x] 🔒 Paginação por keyset, nunca `OFFSET`
- [x] 🔒 Remoção reversível (soft delete) com manager de moderação separado
- [x] Registro, login, logout, perfil
- [x] 🔒 `username` restrito com unicidade sobre skeleton de confusáveis; `display_name` livre
- [x] Painel de moderação via Django Admin
- [x] Comando `seed_forum` idempotente

### Lacuna conhecida

- [ ] **Recuperação de senha** — a [§7.3](ARQUITETURA.md#73-enumeração-e-privacidade) especifica o comportamento (resposta idêntica para email existente e inexistente, para não vazar quem tem conta), mas as rotas não existem. Um fórum sem "esqueci minha senha" perde usuário de forma permanente e silenciosa.

---

## Fase 2 — Riqueza de conteúdo 🟡

**É aqui que o trabalho está agora.** Metade já existe no banco.

### 2.1 Reações com emoji 🟡

- [x] Modelos `Emoji`, `Reaction`, `ReactionCount`
- [x] 🔒 Contagem mantida por **trigger no PostgreSQL**, não por sinal do Django
- [x] Exibição das contagens na página do tópico
- [x] Emojis em tabela, editáveis pelo admin sem deploy
- [ ] **Botão de reagir** — não existe caminho de escrita
- [ ] Seletor de emoji
- [ ] Lista de quem reagiu

> Primeiro lugar onde o **HTMX** entra no projeto. O padrão estabelecido aqui será reusado pelo resto da fase — vale fazer com cuidado.

### 2.2 Busca 🟡

- [x] 🔒 Vetor com duas configurações (`portuguese` + `pt_unaccent`), mantido por trigger
- [x] Índice trigrama para escritas sem stemmer e erro de digitação
- [x] `apps/forum/search.py` com a lógica de consulta e o recuo por trigrama
- [x] Coberto por 9 testes
- [ ] **View de busca**
- [ ] Caixa de busca no cabeçalho
- [ ] Página de resultados com destaque do trecho
- [ ] Filtros por categoria e autor

> O motor está pronto e medido. Falta só a interface.

### 2.3 Edição com histórico ⬜

- [x] Modelo `PostRevision`
- [ ] View de edição de post
- [ ] Registro da revisão ao salvar
- [ ] Exibição de "editado" e do histórico
- [ ] Janela de edição por nível de confiança

> A [§4.4](ARQUITETURA.md#44-revisões) trata transparência de edição como requisito, não recurso: num fórum de tema doutrinário, editar em silêncio uma citação de sutta não pode ser possível.

### 2.4 Vínculos entre posts e backlinks 🟡

- [x] Modelo `PostLink` com índice por alvo
- [x] `extract_internal_links()` implementada e testada
- [ ] **Chamar a extração ao salvar o post** — a função existe e nunca é invocada
- [ ] Exibir "citado em" no post de destino
- [ ] Botão de citar, gerando a citação em Markdown

### 2.5 Editor ⬜

- [ ] EasyMDE, ou outro editor de Markdown
- [ ] Pré-visualização
- [ ] Barra de ferramentas
- [ ] Atalhos de teclado

Hoje é um `<textarea>` puro. Funciona, mas afasta quem não conhece Markdown.

### 2.6 Anexos ⬜

- [ ] Garage (S3-compatível) no Docker Compose
- [ ] Upload de imagem com validação de tipo real, não da extensão
- [ ] Deduplicação por hash de conteúdo
- [ ] Limite por nível de confiança
- [ ] Avatares migrados para o mesmo armazenamento

> Maior item da fase: traz infraestrutura nova. Deixe por último.

---

## Fase 3 — Comunidade e moderação ⬜

- [ ] Notificações (modelo existe; sem geração nem interface)
- [ ] Menções com `@usuario`
- [ ] Níveis de confiança operando de fato — hoje o campo existe e ninguém promove ninguém
- [ ] Denúncias e fila de moderação
- [ ] Perfis com atividade
- [ ] Feed de discussões recentes
- [ ] Marcação de lido/não lido

> Os níveis de confiança ([§7.4](ARQUITETURA.md#74-níveis-de-confiança-anti-spam)) são a defesa anti-spam do projeto. Sem eles, o fórum depende de moderação manual desde o primeiro dia de tráfego público.

---

## Fase 4 — Maturidade open source ⬜

- [ ] Documentação de instalação em produção
- [ ] Traduções via `gettext` (o código já está preparado)
- [ ] Exportação e importação de dados
- [ ] Tema customizável
- [ ] Testes de carga
- [ ] Guia de moderação e diretrizes da comunidade
- [ ] Acessibilidade auditada

---

## Fase 5 — Multi-região ⬜ *(última prioridade)*

Adiada de propósito. O raciocínio está na [§11](ARQUITETURA.md#por-que-multi-região-vem-por-último).

- [ ] Roteador de banco leitura/escrita
- [ ] Middleware de fixação no primário (read-after-write)
- [ ] Réplica de leitura em segunda região
- [ ] Garage distribuído
- [ ] Ensaio de failover documentado
- [ ] Painel de atraso de replicação

**Não comece esta fase sem um destes gatilhos:**

1. incidente real de indisponibilidade que uma segunda região teria evitado;
2. comunidade concentrada longe da instância, com latência reclamada;
3. alguém disposto a operar o cluster de forma sustentada.

O terceiro é o decisivo.

---

## Fora do roadmap

Discutido e descartado. Reabrir exige argumento novo, não preferência.

| Item | Por quê |
|---|---|
| Federação / ActivityPub | O requisito é o mesmo fórum espelhado, não instâncias independentes |
| SPA em React ou Angular | Fórum é hipertexto; HTMX cobre sem etapa de build ([§2](ARQUITETURA.md#por-que-htmx-em-vez-de-spa)) |
| Banco distribuído (Yugabyte, Cockroach) | Complexidade injustificada na escala; Cockroach nem é open source |
| Elasticsearch | Triplica o custo operacional para ganho nulo aqui |
| App móvel nativo | Site responsivo primeiro |

---

## Armadilhas

Coisas que parecem melhorias e quebram o projeto. Tudo aqui está marcado 🔒 acima.

**Não troque a collation ICU por `libc`.** `libc` depende do locale do sistema operacional e diverge entre máquinas, corrompendo índices em silêncio. Definida na criação do cluster; mudar depois exige reindexar tudo.

**Não remova a normalização NFC.** `não` tem duas codificações Unicode válidas, visualmente idênticas. Sem normalizar, busca, `UNIQUE` e deduplicação quebram de forma invisível.

**Não libere Unicode no `username`.** `Аdmin` com А cirílico é indistinguível de `admin` e permite personificar moderadores. O nome livre é o `display_name`, que nunca decide autorização.

**Não troque o trigger de contagem por um sinal do Django.** O trigger vale para todo caminho de escrita — importação em massa, `psql`, migração de dados. O sinal só vale para o ORM.

**Não simplifique a busca para uma configuração só.** Já foi tentado e medido: `unaccent()` roda antes do stemmer e o desliga, fazendo singular e plural pararem de casar. Os números estão na [§5](ARQUITETURA.md#5-busca) e na migração `0003`. Pelo mesmo motivo, o recuo por trigrama usa `%>` e não `%`.

**Não use `OFFSET` para paginar.** `OFFSET 10000` varre e descarta dez mil linhas.

**Não conte reações com `COUNT(*)` em tempo real.** Uma página com 20 posts e 6 emojis faria 120 agregações por requisição.

**Não mova a sessão para o Redis.** O cookie assinado é o que a mantém válida em qualquer região sem replicar estado.

**Migrações precisam ser retrocompatíveis.** Durante o deploy, código antigo e novo rodam juntos. Use expand/contract.

---

## Decisões pendentes

Precisam de resposta humana, não de código.

1. **Provedor de PostgreSQL gerenciado.** Requisito eliminatório: permitir `CREATE DATABASE ... LOCALE_PROVIDER icu`, definível só na criação. Muito provedor não expõe isso. A consulta SQL de verificação está na [§14](ARQUITETURA.md#14-hospedagem-postgresql-gerenciado) — rode no período de avaliação antes de assinar.
2. **Onde o repositório vai morar.** Ainda não tem remote, e por isso o CI nunca rodou.
3. **Diretrizes da comunidade.** Fórum de tema religioso precisa delas *antes* do lançamento público, não depois do primeiro conflito.
4. **Domínio e identidade visual.**

---

## Por onde começar

Ambiente local:

```bash
make setup && make up && make migrate && make seed
uv run python manage.py createsuperuser
make run
```

`make check` roda tudo que o CI roda. Precisa passar antes de qualquer pull request.

### Boas primeiras contribuições

Ordem sugerida — cada uma é pequena, isolada e com a fundação já pronta:

| Tarefa | Onde | Por que é boa para começar |
|---|---|---|
| Recuperação de senha | Fase 1 | Django traz quase pronto; fecha uma lacuna real |
| Botão de reagir | 2.1 | Modelo e trigger prontos; estabelece o padrão de HTMX |
| View e caixa de busca | 2.2 | Motor pronto e testado; falta só a interface |
| Ligar `extract_internal_links` ao salvamento | 2.4 | Função pronta e testada, só não é chamada |
| Edição de post com revisão | 2.3 | Modelo pronto; requisito de moderação |

### Antes de abrir um pull request

- Leia a [§10](ARQUITETURA.md#10-decisões-registradas) (decisões registradas) e as [Armadilhas](#armadilhas) acima
- Discorda de uma decisão travada? Abra uma issue **antes** de escrever código
- Toda correção de bug começa por um teste que falha
- Teste de segurança que falha aponta defeito no código, nunca no teste
- Nenhuma listagem pode ter N+1
