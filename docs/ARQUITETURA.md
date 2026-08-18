# Arquitetura — Fórum Buddhadharma

Documento de arquitetura para revisão. Versão 0.1 — anterior a qualquer código.

---

## 1. Objetivo e princípios

Fórum web sobre Budismo, em português, open source, espelhado em várias regiões geográficas.

**Prioridades declaradas, em ordem:**

1. **Disponibilidade** — o fórum continua no ar quando uma região cai.
2. **Armazenamento eficiente** — uma fonte de verdade por dado, texto compacto, derivados descartáveis.
3. **Velocidade e desempenho** — importante, mas cede às duas acima quando conflitarem.

**Ordem de execução é outra coisa.** O espelhamento multi-região é a **última prioridade de implementação** (§11, Fase 5). Constrói-se primeiro um fórum completo e bom em uma região.

Isso não é contradição com a prioridade 1. A distinção que organiza o projeto inteiro:

| | Quando | Por quê |
|---|---|---|
| **Decisões que preservam a opção** | agora, Fase 0 | custam quase nada hoje; retrofitar depois exige reescrever e reindexar a base |
| **Infraestrutura multi-região** | por último, Fase 5 | replicar um schema que ainda muda toda semana é sofrimento evitável |

Decisões da primeira linha, que entram já: collation ICU (§6.1), normalização NFC (§6.2), sessão em cookie assinado (§3.5), estado sempre fora do processo, agregação de escritas de alta frequência (§8), migrações retrocompatíveis (§9.3). Nenhuma delas exige uma segunda região para valer a pena — todas ficariam caras ou impossíveis de introduzir depois.

O desenho multi-região da §3 é **alvo documentado, não trabalho agendado**. Existe para que nada construído nas fases 1 a 4 o inviabilize.

**Princípios que decorrem disso:**

- **Uma fonte de verdade por dado.** Tudo que puder ser recalculado (HTML renderizado, contagens, índices de busca) é cache ou derivado, nunca dado primário.
- **Estado fora da aplicação.** Processos Django são descartáveis e intercambiáveis. Todo estado vive em Postgres, Redis ou no armazenamento de objetos.
- **Degradação em vez de queda.** Região secundária isolada do primário continua servindo leitura. Busca fora do ar não derruba o fórum.
- **Simplicidade operacional é uma feature.** Projeto open source é mantido por voluntários. Cada peça de infraestrutura adicionada é dívida operacional permanente.

**Escala alvo:** dezenas de milhares de usuários registrados, ordem de 10⁵–10⁶ posts. Isso é pequeno para PostgreSQL. A arquitetura é dimensionada para disponibilidade, não para volume.

---

## 2. Stack

| Camada | Escolha | Licença |
|---|---|---|
| Linguagem | Python 3.12+ | PSF |
| Framework | Django 5.x | BSD-3 |
| Banco | PostgreSQL 16+ | PostgreSQL |
| Cache / sessões / filas | Redis 7 (ou Valkey) | BSD / BSD |
| Tarefas assíncronas | Celery ou Django-Q2 | BSD |
| Frontend | HTMX + Alpine.js, templates Django | BSD / MIT |
| Editor | EasyMDE (Markdown) | MIT |
| Renderização Markdown | `markdown-it-py` | MIT |
| Sanitização HTML | `nh3` (Rust/ammonia) | MIT |
| Armazenamento de objetos | Garage | AGPL-3.0 |
| Alta disponibilidade Postgres | Patroni + etcd | MIT / Apache-2.0 |
| Proxy / TLS | Caddy ou nginx | Apache-2.0 / BSD |
| Métricas | Prometheus + Grafana | Apache-2.0 / AGPL-3.0 |
| Erros | GlitchTip | MIT |

**Licença do projeto: AGPL-3.0.** Fórum é software acessado pela rede. A GPL comum não obriga quem roda um fork modificado como serviço a publicar as mudanças; a AGPL obriga. Alinhado com o objetivo de replicação aberta.

### Por que Django

Um fórum é, em boa parte, software que o Django já traz:

- `django.contrib.auth` — usuários, sessões, hashing de senha, fluxo de recuperação. Não escrevemos autenticação, que é onde moram os piores bugs de segurança.
- **Django Admin** — painel de moderação funcional desde o primeiro dia.
- Grupos e permissões — papéis de moderador e administrador, nativo.
- Sistema de migrações — schema versionado e revisável, essencial em projeto colaborativo.
- `django.contrib.postgres` — `SearchVector`, `SearchQuery`, `TrigramSimilarity` e `unaccent` expostos no ORM. Busca full-text em português sem serviço externo.
- i18n com pt-BR completo, incluindo pluralização e formatação de datas.

Python tem base ampla de contribuidores e o Django tem convenções fortes — ambos importam num projeto que dependerá de gente entrando e saindo.

### Por que HTMX em vez de SPA

Fórum é hipertexto: navegação por links, formulários, atualizações parciais. HTMX cobre exatamente isso sem etapa de build, sem API duplicada e sem reimplementar roteamento e estado no cliente.

Consequências práticas que atendem os requisitos:

- HTML renderizado no servidor é cacheável em disco, em Redis e na CDN — vantagem direta na estratégia multi-região.
- Sem API pública separada, a superfície de ataque encolhe.
- Sem `node_modules`, a barreira para um contribuidor novo é `pip install` e rodar.

Alpine.js cobre o pouco de estado local necessário: menus, seletor de emoji, contadores otimistas.

---

## 3. Arquitetura de implantação

> **Estado desta seção: alvo, não trabalho agendado.** O multi-região é a última fase do roadmap (§11, Fase 5). Até lá o fórum roda em **uma região**: Caddy, Django, um Postgres, um Redis, um Garage. Esta seção existe para que nenhuma decisão das fases anteriores feche a porta.
>
> Do que está aqui, apenas três itens entram desde a Fase 0, porque são caros de introduzir depois: **collation ICU** (§6.1), **sessão em cookie assinado** (§3.5) e **agregação de escritas de alta frequência** (§8). O resto — roteador de banco, Patroni, réplicas, Garage distribuído — fica para a Fase 5.

### 3.1 Topologia

```
                        ┌───────────────┐
                        │  DNS geo/      │
                        │  anycast       │
                        └───┬────────┬───┘
              ┌─────────────┘        └─────────────┐
              ▼                                    ▼
   ╔═══════════════════════╗            ╔═══════════════════════╗
   ║  REGIÃO A (primária)  ║            ║  REGIÃO B (secundária)║
   ║                       ║            ║                       ║
   ║  Caddy                ║            ║  Caddy                ║
   ║  Django  ×N           ║            ║  Django  ×N           ║
   ║  Redis (local)        ║            ║  Redis (local)        ║
   ║  Postgres PRIMÁRIO ───╫──────────► ║  Postgres RÉPLICA     ║
   ║  Patroni + etcd       ║  streaming ║  Patroni + etcd       ║
   ║  Garage (nó)      ────╫──────────► ║  Garage (nó)          ║
   ╚═══════════════════════╝            ╚═══════════════════════╝
```

Regiões adicionais replicam o desenho da B. Mínimo viável: duas regiões. Recomendado: três, porque o etcd do Patroni precisa de quorum ímpar para eleger novo primário sem intervenção humana.

### 3.2 Escrita e leitura

Todas as escritas vão ao primário. Leituras vão à réplica local da região.

Justificativa: um fórum é dominado por leitura. Uma resposta postada com 150 ms adicionais de latência transcontinental é imperceptível; uma página de tópico servida da região local é perceptível.

Django suporta múltiplos bancos nativamente. Um roteador de banco (`DATABASE_ROUTERS`) direciona:

```python
class ReplicaRouter:
    def db_for_read(self, model, **hints):
        if getattr(_local, "force_primary", False):
            return "default"
        return "replica"

    def db_for_write(self, model, **hints):
        return "default"
```

### 3.3 Read-after-write — o problema que precisa ser resolvido de propósito

A replicação é assíncrona. O usuário publica uma resposta, é redirecionado para o tópico, a leitura vai à réplica que ainda não recebeu a linha — e a resposta "sumiu". É o defeito mais comum e mais irritante de arquiteturas com réplica de leitura.

**Solução adotada:** fixação temporária no primário, por usuário.

- Após qualquer escrita, grava-se na sessão um carimbo `primary_until = agora + 10s`.
- Um middleware lê esse carimbo e, se ainda válido, marca a requisição para ler do primário.
- Passados 10 segundos, o usuário volta a ler da réplica local.

Custo: uma fração pequena das leituras vai ao primário. Benefício: a inconsistência nunca é visível para quem escreveu.

**Alternativa mais precisa, se necessário depois:** comparar o LSN da réplica (`pg_last_wal_replay_lsn()`) com o LSN registrado no momento da escrita, e cair para o primário apenas se a réplica estiver atrasada em relação àquela escrita específica. Mais correto, mais complexo. Fase posterior.

### 3.4 Failover

**Patroni** com etcd gerencia o cluster Postgres. Se o primário fica indisponível, Patroni promove uma réplica e atualiza o endpoint que a aplicação consulta.

Consequências aceitas:

- Replicação assíncrona implica janela de perda de dados na promoção — tipicamente sub-segundo. Para um fórum, aceitável.
- Se a região primária inteira cai, as regiões secundárias operam **somente leitura** até a promoção concluir. O fórum permanece legível durante todo o incidente. Isso é o comportamento desejado: degradação, não queda.

A aplicação deve detectar `psycopg.errors.ReadOnlySqlTransaction` e exibir um aviso claro ("modo somente leitura, publicação temporariamente indisponível") em vez de um erro 500.

**Alternativa deliberadamente rejeitada:** banco distribuído multi-master (YugabyteDB, CockroachDB). Permitiria escrita local em qualquer região, mas exige no mínimo três nós de banco, faz cada escrita atravessar regiões para atingir quorum Raft, e multiplica a complexidade operacional. Injustificável na escala alvo. CockroachDB também está sob licença BSL, não open source. Se o volume de escrita algum dia justificar, migrar de PostgreSQL para YugabyteDB é viável — o protocolo de rede é o mesmo.

### 3.5 Redis

Um Redis por região, sem replicação entre regiões. Guarda apenas dados descartáveis: cache de HTML renderizado, contadores de rate limit, resultados intermediários. Perder um Redis inteiro causa lentidão momentânea, nunca perda de dados.

**Sessões ficam em cookie assinado** (`SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"`), não em Redis. Assim a sessão é válida em qualquer região sem replicação de estado — requisito direto do desenho multi-região.

### 3.6 Anexos

**Garage**: armazenamento S3-compatível escrito em Rust, projetado para clusters geo-distribuídos com latência entre nós. Não exige etcd nem consul; os nós se coordenam entre si.

- Um nó Garage por região, replicação factor 3.
- Django faz upload direto ao nó local via `django-storages`.
- Servido através do proxy da região, para permitir controle de acesso.
- Deduplicação por hash de conteúdo: o mesmo arquivo enviado duas vezes ocupa uma cópia. Contribuição direta ao requisito de armazenamento eficiente.

---

## 4. Modelo de dados

Notação: esboço de campos, não migração final. Chaves primárias `BIGINT` geradas por identidade.

### 4.1 Usuários

```
User                              (estende AbstractUser)
  id
  username           citext-like  identificador de login e URL, ver §6.3
  display_name       text         nome exibido, Unicode livre
  email              citext       único, case-insensitive
  bio                text         Markdown, limitado
  avatar             FileField    Garage
  trust_level        smallint     0..4, ver §7.4
  post_count         integer      materializado
  created_at         timestamptz
  last_seen_at       timestamptz  atualizado no máximo a cada 5 min
  is_active          boolean
```

`last_seen_at` atualizado com throttle: escrever a cada requisição transformaria toda leitura em escrita, enviando tráfego ao primário e inflando o WAL da replicação. Atualiza-se apenas se o valor tem mais de 5 minutos.

### 4.2 Categorias

```
Category
  id
  parent_id      FK self, nullable
  name           text
  slug           text  único
  description    text
  color          text
  position       integer        ordem manual
  is_locked      boolean        só moderadores publicam
  topic_count    integer        materializado
  post_count     integer        materializado
```

Hierarquia por chave estrangeira simples para o pai. Categorias de fórum são rasas (dois níveis na prática); nested sets ou `ltree` são complexidade sem retorno. A árvore inteira cabe em cache — é lida em toda página e muda raramente.

Gerenciadas em banco, editáveis pelo Django Admin, conforme requisito.

### 4.3 Tópicos e posts

```
Topic
  id
  category_id     FK
  author_id       FK
  title           text
  slug            text
  is_pinned       boolean
  is_locked       boolean
  post_count      integer      materializado
  view_count      integer      materializado, atualização em lote
  last_post_at    timestamptz  materializado, indexado — ordena a listagem
  created_at      timestamptz
  deleted_at      timestamptz  nullable, soft delete

Post
  id
  topic_id        FK
  author_id       FK
  position        integer      número sequencial dentro do tópico, começa em 1
  body_md         text         FONTE DE VERDADE
  body_html       text         nullable, cache de renderização
  html_version    smallint     versão do renderizador que gerou body_html
  reply_to_id     FK self, nullable
  created_at      timestamptz
  edited_at       timestamptz  nullable
  edit_count      smallint
  deleted_at      timestamptz  nullable, soft delete
  deleted_by_id   FK, nullable

  UNIQUE (topic_id, position)
```

**`body_md` é a fonte de verdade.** Markdown cru, comprimido automaticamente pelo TOAST do Postgres acima de ~2 KB. Portátil, diffável, independente do renderizador.

**`body_html` é cache persistido, não dado.** Guardado na linha em vez de só no Redis porque o custo de armazenamento é baixo e evita uma tempestade de re-renderização quando um Redis regional esvazia. `html_version` permite invalidar em massa quando o renderizador ou as regras de sanitização mudam: basta um `UPDATE post SET body_html = NULL WHERE html_version < N`.

**`position` sequencial por tópico** dá permalinks estáveis (`/t/o-caminho-do-meio/42`), paginação trivial e o número de post que fóruns exibem — sem depender de `id` global nem de `OFFSET`.

**Soft delete em todo conteúdo.** Moderação precisa ser reversível. Um `Manager` padrão filtra `deleted_at IS NULL`; um manager separado expõe tudo para moderadores.

### 4.4 Revisões

```
PostRevision
  id
  post_id         FK
  editor_id       FK
  body_md         text         snapshot completo
  edit_reason     text
  created_at      timestamptz
```

Snapshot completo em vez de diff: mais simples, mais robusto, e o TOAST comprime bem texto repetitivo. Transparência de edição é um requisito de moderação num fórum sobre um tema doutrinário — editar silenciosamente uma citação não pode ser possível.

Política de retenção: manter todas as revisões dos últimos 12 meses; acima disso, manter apenas primeira e última salvo se o post foi alvo de denúncia.

### 4.5 Reações

```
Emoji
  id
  shortcode      text  único, ex.: "lotus"
  character      text  ex.: "🪷"
  image          FileField  nullable, emoji customizado
  is_active      boolean
  position       integer

Reaction
  id
  post_id        FK
  user_id        FK
  emoji_id       FK
  created_at     timestamptz
  UNIQUE (post_id, user_id, emoji_id)

ReactionCount
  post_id        FK
  emoji_id       FK
  count          integer
  PRIMARY KEY (post_id, emoji_id)
```

`ReactionCount` é mantido por **trigger no Postgres**, não por código de aplicação:

```sql
CREATE FUNCTION bump_reaction_count() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO reactioncount (post_id, emoji_id, count)
    VALUES (NEW.post_id, NEW.emoji_id, 1)
    ON CONFLICT (post_id, emoji_id)
    DO UPDATE SET count = reactioncount.count + 1;
  ELSIF TG_OP = 'DELETE' THEN
    UPDATE reactioncount SET count = count - 1
    WHERE post_id = OLD.post_id AND emoji_id = OLD.emoji_id;
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
```

Trigger em vez de sinal Django porque a garantia vale mesmo em importação em massa, correção manual via `psql` ou script de migração — qualquer caminho que escreva na tabela.

**Nunca `COUNT(*)` em tempo real.** Uma página de tópico com 20 posts e 6 emojis faria 120 agregações por requisição.

Emojis vêm de tabela em banco, editável pelo Admin: adicionar um emoji não exige deploy.

### 4.6 Vínculos entre posts

```
PostLink
  id
  source_post_id  FK
  target_post_id  FK
  link_type       text   'quote' | 'reference' | 'mention' | 'crosspost'
  created_at      timestamptz
  UNIQUE (source_post_id, target_post_id, link_type)
```

Grafo em tabela relacional, não texto dentro do corpo do post. Extraído na renderização: quando o Markdown contém um link para uma URL interna de post, ou uma citação em bloco atribuída, cria-se a aresta.

Permite o recurso que fóruns bons têm e os ruins não: **backlinks**. Ao ler um post, ver quais posts posteriores o citaram. Consulta indexada por `target_post_id`, barata.

Para um fórum sobre Budismo isso tem valor específico: rastrear discussões que referenciam a mesma passagem de sutta ou o mesmo comentário ao longo de anos.

### 4.7 Notificações

```
Notification
  id
  user_id        FK
  actor_id       FK, nullable
  verb           text     'replied' | 'mentioned' | 'reacted' | 'quoted'
  target_post_id FK, nullable
  is_read        boolean
  created_at     timestamptz

  INDEX (user_id, is_read, created_at DESC)
```

Geradas de forma assíncrona pela fila de tarefas. Agrupadas na exibição ("3 pessoas reagiram") em vez de armazenadas agrupadas — mais simples e mais flexível.

### 4.8 Índices que importam

```sql
-- listagem de tópicos numa categoria, o acesso mais frequente do fórum
CREATE INDEX ON topic (category_id, is_pinned DESC, last_post_at DESC)
  WHERE deleted_at IS NULL;

-- posts de um tópico, em ordem; suporta paginação por keyset
CREATE INDEX ON post (topic_id, position) WHERE deleted_at IS NULL;

-- backlinks
CREATE INDEX ON postlink (target_post_id);

-- busca full-text, ver §5
CREATE INDEX ON post USING GIN (search_vector);

-- busca por trigrama, cobre escritas não-latinas
CREATE INDEX ON post USING GIN (body_md gin_trgm_ops);
```

**Paginação por keyset, nunca `OFFSET`.** `OFFSET 10000` obriga o Postgres a varrer e descartar dez mil linhas. Com `position` sequencial, a paginação é `WHERE topic_id = ? AND position > ? ORDER BY position LIMIT 20` — tempo constante em qualquer profundidade do tópico.

---

## 5. Busca

Full-text nativo do PostgreSQL. Nenhum serviço separado.

```
Post.search_vector    tsvector, coluna gerada ou mantida por trigger
```

Composição com pesos:

```sql
setweight(to_tsvector('portuguese', unaccent(coalesce(titulo_do_topico,''))), 'A') ||
setweight(to_tsvector('portuguese', unaccent(coalesce(body_md,''))), 'B')
```

- Configuração `portuguese` dá stemming: "meditação" e "meditações" casam; "praticar" e "prática" se aproximam.
- Extensão `unaccent` torna a busca insensível a acento — o usuário digita "budismo" ou "meditacao" e encontra assim mesmo.
- Índice GIN sobre `search_vector`.

**Escritas não-latinas.** Pāli, sânscrito em Devanágari, tibetano e CJK não têm stemmer no PostgreSQL. Degradam para correspondência de token exato, o que é aceitável — mas o índice `pg_trgm` sobre `body_md` cobre a lacuna, permitindo busca por substring e tolerância a erro de digitação nessas escritas. Termos em Pāli transliterado (`anicca`, `dukkha`, `anattā`) funcionam bem em ambos os índices.

**Diacríticos do Pāli.** `unaccent` remove mácrons e pontos subscritos: `anattā` indexa junto com `anatta`, `saṅgha` com `sangha`. É o comportamento certo — poucos digitam os diacríticos corretamente.

**Rota de escalada, se necessária depois:** `pg_search`/ParadeDB, que traz ranking BM25 escrito em Rust como extensão do próprio PostgreSQL — sem serviço adicional para operar, sem sincronização de índice, sem novo ponto de falha. Elasticsearch fica descartado: triplica o custo operacional para ganho nulo nesta escala.

Busca lê da réplica local. Se ficar indisponível, a busca falha isoladamente e o resto do fórum continua.

---

## 6. Idioma, Unicode e collation

Fórum em português, aceitando caracteres de outras línguas dentro do conteúdo. As decisões abaixo precisam estar corretas na **primeira migração** — mudar depois exige reescrever e reindexar toda a base.

### 6.1 Encoding e collation

- Cluster criado com `ENCODING 'UTF8'`.
- Collation padrão **ICU**: `pt-BR-x-icu`, com `LOCALE_PROVIDER = icu`.

ICU, não `libc`. A collation `libc` depende do locale instalado no sistema operacional; um primário e uma réplica com versões diferentes de glibc ordenam strings de forma diferente, o que corrompe índices silenciosamente durante failover. Num desenho multi-região com máquinas potencialmente heterogêneas, ICU não é preferência — é requisito.

Ordena corretamente: `Ávila` antes de `Azul`, `ç` entre `c` e `d`.

### 6.2 Normalização Unicode

`não` admite duas codificações válidas: `ã` pré-composto (U+00E3), ou `a` seguido de til combinante (U+0303). Aparência idêntica, bytes diferentes. macOS produz uma forma, Linux e Windows produzem outra. Sem normalização, isso quebra busca, quebra `UNIQUE` e quebra deduplicação — de forma invisível, porque na tela as duas strings são iguais.

Igualmente relevante aqui: `saṅgha` e nomes em Devanágari ou tibetano têm múltiplas formas normalizadas.

**Regra:** todo texto é normalizado para **NFC** na entrada da aplicação, antes de qualquer validação ou persistência. Implementado em um único ponto (form field base + `unicodedata.normalize`), com `CHECK (body_md = normalize(body_md, NFC))` no banco como rede de segurança.

### 6.3 Nomes de usuário — segurança

> **Aviso de segurança.** Aceitar Unicode irrestrito em nomes de usuário permite ataque de homóglifos. `Аdmin`, escrito com А cirílico (U+0410), é visualmente indistinguível de `Admin` latino, mas é uma string diferente e passa por qualquer verificação de unicidade ingênua. O resultado é personificação de moderadores e administradores.

**Mitigação — dois campos separados, com propósitos distintos:**

| Campo | Uso | Restrição |
|---|---|---|
| `username` | login, URL, menções, autorização | conjunto restrito |
| `display_name` | exibição apenas | Unicode livre, normalizado NFC |

Regras de `username`:

- Conjunto permitido: `a-z`, `0-9`, `.`, `_`, `-`, mais os acentuados do português (`á à â ã é ê í ó ô õ ú ü ç`). Sem cirílico, sem grego, sem escritas mistas.
- Normalizado NFC e comparado case-insensitively via collation ICU não-determinística.
- Unicidade verificada também sobre um **skeleton de confusáveis** (biblioteca `confusable_homoglyphs` ou tabela do Unicode TR39), garantindo que `rn` e `m`, `0` e `O`, `l` e `I` não gerem contas colidentes.
- Lista de reservados: `admin`, `moderador`, `sangha`, `sistema`, etc.

**Autorização nunca considera `display_name`.** Nenhuma verificação de permissão, menção ou rota usa esse campo.

### 6.4 Interface

- `LANGUAGE_CODE = "pt-br"`, `TIME_ZONE = "America/Sao_Paulo"`, `USE_TZ = True`.
- Timestamps armazenados em UTC (`timestamptz`), convertidos na exibição.
- Toda string da interface passa por `gettext` desde o início, mesmo com um único idioma. Retrofitar i18n num projeto maduro é trabalho penoso; fazer desde o começo custa quase nada e mantém aberta a porta para tradução por voluntários.

---

## 7. Segurança

### 7.1 Conteúdo gerado por usuário

Pipeline de renderização, em ordem fixa:

```
body_md  ──►  markdown-it-py  ──►  nh3.clean()  ──►  body_html
             (HTML bruto            (allowlist de
              desabilitado)          tags/atributos)
```

Duas defesas independentes:

1. `markdown-it-py` configurado com `html=False` — HTML embutido no Markdown é escapado, não interpretado.
2. Saída sanitizada por **`nh3`** com allowlist explícita de tags e atributos. `nh3` é binding Rust da biblioteca `ammonia`; `bleach`, a escolha histórica em Python, está descontinuado e não deve ser usado em projeto novo.

Nunca confiar apenas no renderizador de Markdown para segurança — vários permitem HTML bruto por padrão ou por descuido de configuração.

Regras adicionais:

- `<img>` permitido apenas com `src` apontando para o próprio Garage. Imagens externas são espelhadas (proxy de imagem) ou bloqueadas — evita vazamento de IP dos leitores e conteúdo que muda depois da moderação.
- Links externos recebem `rel="nofollow ugc noopener"` e `target="_blank"`.
- Content-Security-Policy restritiva, sem `unsafe-inline`.
- Blocos de código destacados no servidor (Pygments), nunca por script no cliente.

### 7.2 Autenticação

- Hashing **Argon2id** (`django[argon2]`), à frente da lista `PASSWORD_HASHERS`.
- 2FA via `django-otp` (TOTP), obrigatório para contas com papel de moderação.
- Rate limit em login, registro, recuperação de senha e publicação — `django-ratelimit`, contadores em Redis local, com fallback para permitir se o Redis cair (disponibilidade acima de rigor).
- Cookies `Secure`, `HttpOnly`, `SameSite=Lax`. HSTS ativado.
- Sessão em cookie assinado: rotação de `SECRET_KEY` invalida todas as sessões; usar `SECRET_KEY_FALLBACKS` para rotacionar sem deslogar todo mundo.

### 7.3 Enumeração e privacidade

- Recuperação de senha responde igual para email existente e inexistente.
- Email nunca exposto na interface pública nem em API.
- Endereços IP registrados apenas para moderação anti-spam, retidos por 90 dias, depois purgados por tarefa agendada.

### 7.4 Níveis de confiança (anti-spam)

Modelo escalonado, semelhante ao do Discourse:

| Nível | Como se obtém | O que libera |
|---|---|---|
| 0 — novo | registro | publicar com limite de taxa; sem links; sem anexos |
| 1 — básico | ler N tópicos, tempo mínimo de leitura | links, anexos, imagens |
| 2 — membro | participação sustentada | edição estendida, criação de enquete |
| 3 — regular | confiança da comunidade | renomear tópico, sinalizar com peso |
| 4 — moderador | designado | ações de moderação |

Isso resolve spam estruturalmente, sem CAPTCHA e sem serviço externo. Vale mais do que qualquer filtro: o custo de uma conta descartável passa a ser tempo real de leitura.

---

## 8. Cache e desempenho

Camadas, da mais externa para a mais interna:

1. **CDN / proxy** — assets estáticos com hash no nome, cache imutável de longa duração.
2. **Cache de página** — páginas de tópico para visitantes anônimos, em Redis local, chave incluindo `topic.last_post_at`. Uma resposta nova invalida naturalmente, sem lógica de expurgo.
3. **Cache de fragmento** — HTML do post, chave `post.id:post.edited_at:html_version`. Compartilhado entre usuários logados e anônimos.
4. **Cache de aplicação** — árvore de categorias, lista de emojis, configurações. TTL longo, invalidação em sinal de escrita.
5. **Banco** — índices da §4.8, réplica local, keyset pagination.

Regra transversal: **nada de N+1.** Toda listagem usa `select_related` e `prefetch_related` explícitos. Um teste de integração conta as queries por página e falha o CI se o número regredir — verificação barata que previne a classe de bug de desempenho mais comum em Django.

Contadores agregados (`post_count`, `topic_count`, `view_count`, `ReactionCount`) são materializados. `view_count` acumula em Redis e é descarregado no Postgres em lote a cada poucos minutos — escrever uma linha por visualização inundaria o WAL da replicação, que é o recurso mais escasso do desenho multi-região.

---

## 9. Operação

### 9.1 Backup

> Com o multi-região adiado para a Fase 5, **backup é a disponibilidade do projeto**. Da Fase 0 à 4 não existe segunda cópia viva dos dados — o backup é a única. Esta subseção deixa de ser rotina operacional e passa a ser o item de infraestrutura mais crítico do documento. Entra na Fase 0, não depois.

- **pgBackRest** — backup full semanal, incremental diário, WAL arquivado continuamente para o Garage. Permite PITR (recuperação a um instante arbitrário).
- Réplica **não é backup**. Um `DELETE` acidental replica em milissegundos.
- Restauração testada por rotina automática mensal, em ambiente descartável. Backup nunca testado deve ser considerado inexistente.
- Garage já replica os objetos entre regiões; ainda assim, uma cópia fria em provedor distinto.

### 9.2 Observabilidade

- `django-prometheus` expõe métricas; Prometheus e Grafana coletam e exibem.
- Métricas que efetivamente importam aqui: **atraso de replicação por região**, taxa de erro 5xx, latência p95 por rota, profundidade da fila de tarefas, taxa de acerto de cache.
- Alerta de atraso de replicação acima de 5 segundos — é o sinal precoce de quase todo problema neste desenho.
- **GlitchTip** para erros (compatível com SDK do Sentry, licença MIT).
- Logs estruturados em JSON, para stdout; agregação fica a critério de quem opera cada instância.

### 9.3 Implantação

- Imagens de container, Docker Compose para desenvolvimento e instâncias pequenas.
- Migrações aplicadas por passo explícito, nunca no start do container — em multi-região, N containers subindo aplicariam a mesma migração concorrentemente.
- **Migrações precisam ser retrocompatíveis**: durante o deploy, código antigo e novo rodam simultaneamente em regiões diferentes. Nada de renomear ou remover coluna numa migração só — usar o padrão expand/contract (adicionar, migrar dados, alternar código, remover numa release posterior).
- CI: lint (`ruff`), tipos (`mypy`), testes (`pytest-django`), teste de contagem de queries, verificação de migração faltante.

---

## 10. Decisões registradas

| # | Decisão | Alternativas rejeitadas | Motivo |
|---|---|---|---|
| 1 | Django | TypeScript full-stack, Rust, Elixir | Auth, admin e moderação prontos valem meses; Elixir cai fora por falta de familiaridade |
| 2 | PostgreSQL primário + réplicas | YugabyteDB, CockroachDB, CouchDB | Complexidade injustificada na escala; CockroachDB não é open source (BSL) |
| 3 | Espelhamento HA, não federação | ActivityPub | Requisito é o mesmo fórum em várias regiões, não instâncias independentes |
| 3b | **Multi-região por último (Fase 5)** | construir replicado desde o início | Schema instável torna cada migração cara; instância única com backup testado cobre a maioria dos incidentes reais |
| 3c | Decisões que preservam a opção entram na Fase 0 | decidir tudo depois | ICU e NFC exigiriam reescrever e reindexar a base; custam quase nada agora |
| 4 | HTMX + templates | React/Next.js, SPA | Sem etapa de build, HTML cacheável por região, menor barreira de contribuição |
| 5 | Markdown como fonte de verdade | HTML, JSON do ProseMirror | Compacto, portátil, diffável, independente do renderizador |
| 6 | Collation ICU | libc | Determinística entre máquinas; obrigatório com réplicas |
| 7 | Contadores materializados por trigger | `COUNT(*)`, sinais Django | Garantia independe do caminho de escrita |
| 8 | Busca nativa do Postgres | Elasticsearch, Meilisearch | Sem serviço extra para operar nem sincronizar |
| 9 | Sessão em cookie assinado | Sessão em Redis | Válida em qualquer região sem replicar estado |
| 10 | AGPL-3.0 | MIT, GPL-3.0 | Software de rede; impede fork fechado servido como serviço |

---

## 11. Roadmap

**Fase 0 — Fundação**
Projeto Django, Docker Compose (Postgres + Redis), CI, modelo `User` customizado desde o início (trocar depois é doloroso), configuração de collation e normalização, licença AGPL, `CONTRIBUTING.md`.

**Fase 1 — Fórum mínimo**
Categorias, tópicos, posts, registro e login, renderização Markdown com sanitização, paginação por keyset. Uma região só. Utilizável de ponta a ponta.

**Fase 2 — Riqueza de conteúdo**
Reações com emoji e contadores por trigger, editor EasyMDE, edição com histórico de revisões, `PostLink` e backlinks, citação, anexos no Garage, busca full-text.

**Fase 3 — Comunidade e moderação**
Notificações, menções, níveis de confiança, denúncias, fila de moderação, perfis, feed de atividade recente.

**Fase 4 — Maturidade open source**
Documentação de instalação, guia de contribuição, tradução via `gettext`, exportação e importação de dados, tema customizável, testes de carga.

**Fase 5 — Multi-região** *(última prioridade)*
Roteador de banco leitura/escrita, middleware de fixação no primário, Patroni + etcd, réplica na segunda região, Garage distribuído, ensaio de failover documentado, painel de atraso de replicação.

### Por que multi-região vem por último

Fases 1 a 4 entregam um fórum completo, público e mantível — em **uma região**.

- Replicação sobre um schema que ainda muda toda semana multiplica o custo de cada migração.
- A escala alvo (§1) cabe com folga num único Postgres. A segunda região resolve **falha de região**, não capacidade.
- Uma instância única bem operada — backup testado com PITR (§9.1), monitoramento, restauração ensaiada — já cobre a maioria esmagadora dos incidentes reais. Backup ruim derruba fóruns com muito mais frequência que região inteira caindo.
- Cada peça da Fase 5 (Patroni, etcd, réplicas, quorum) é dívida operacional permanente. Adiar é adiar custo real, não preguiça.

**Disponibilidade antes da Fase 5** vem de fundamentos, não de geografia: processos Django redundantes atrás do proxy, backup com PITR verificado mensalmente, monitoramento com alerta, migrações retrocompatíveis, deploy sem downtime.

**Gatilhos que promovem a Fase 5** — nenhum prazo, só condições:

- incidente real de indisponibilidade que uma segunda região teria evitado;
- comunidade concentrada numa geografia distante da instância, com latência reclamada;
- alguém disposto a operar o cluster de forma sustentada (é o gatilho decisivo).

---

## 12. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| **Instância única cair sem backup bom** | **Crítico — perda permanente de dados** | **Risco dominante até a Fase 5. pgBackRest com PITR, restauração testada mensalmente (§9.1)** |
| Complexidade multi-região cedo demais | Alto — trava o desenvolvimento | Adiada para a Fase 5, última prioridade, por decisão (§11) |
| Decisão barata hoje virar reescrita amanhã | Alto — ICU e NFC exigem reindexar a base | Entram já na Fase 0, mesmo sem segunda região (§1) |
| Read-after-write visível ao usuário | Alto — parece perda de dados | Só existe a partir da Fase 5; fixação no primário (§3.3) e teste de integração explícito |
| Divergência de collation entre nós | Alto — corrupção silenciosa de índice | ICU obrigatório desde a Fase 0; verificação de versão no CI |
| Atraso de replicação sob carga de escrita | Médio, só na Fase 5 | Agregar `view_count` e `last_seen_at` (§8) — já feito antes, por outro motivo |
| Projeto solo perdendo fôlego | Alto — realidade de projetos open source | Stack popular, sem peça exótica; documentação desde a Fase 0 |
| Moderação de conteúdo doutrinário | Médio — cismas em fórum religioso | Diretrizes explícitas da comunidade antes do lançamento; níveis de confiança |

---

## 13. Pontos ainda em aberto

1. **Hospedagem da instância única.** VPS auto-gerido (custo baixo, operação toda por conta) ou Postgres gerenciado (backup e failover deixam de ser problema, custo sobe, dependência de fornecedor). Decisão necessária já na Fase 0 — é o que define a qualidade da disponibilidade até a Fase 5.
2. **Regiões concretas.** Adiado para a Fase 5, não bloqueia nada agora. Quando chegar a hora: se o público for majoritariamente brasileiro, duas regiões no Brasil mais uma na Europa (comunidade lusófona) faz mais sentido que dispersão global. Não bloqueia nada agora.
3. **Anônimos podem ler tudo?** Assumido que sim. Se houver áreas restritas, o cache de página da §8 precisa de outro desenho.
4. **Idiomas do conteúdo além do português.** Assumido: interface e discussão em português, com termos e citações em Pāli, sânscrito, tibetano e chinês dentro do texto. Confirmar.
5. **Migração de conteúdo existente.** Há acervo a importar de algum fórum atual? Muda a prioridade de ferramentas de importação.
6. **Federação, no futuro.** Descartada agora. Se um dia entrar, ActivityPub sobre este schema é viável — mas seria uma decisão de arquitetura nova, não uma extensão.
