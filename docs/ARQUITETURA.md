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
| Alta disponibilidade Postgres | responsabilidade do provedor gerenciado (§14) | — |
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
> Do que está aqui, apenas três itens entram desde a Fase 0, porque são caros de introduzir depois: **collation ICU** (§6.1), **sessão em cookie assinado** (§3.5) e **agregação de escritas de alta frequência** (§8). O resto — roteador de banco, réplicas, Garage distribuído — fica para a Fase 5, e o failover do banco é do provedor (§14).

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
   ║  (failover: provedor) ║  streaming ║  (failover: provedor) ║
   ║  Garage (nó)      ────╫──────────► ║  Garage (nó)          ║
   ╚═══════════════════════╝            ╚═══════════════════════╝
```

Regiões adicionais replicam o desenho da B. Mínimo viável: duas regiões.

O PostgreSQL do diagrama é **gerenciado** (§14): a promoção de réplica e o quorum de eleição são do provedor. O que continua sendo nosso é tudo acima da linha do banco — as regiões de aplicação, o roteamento de leitura e a fixação no primário.

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

O failover do banco é **do provedor gerenciado** (§14). Se o primário fica indisponível, o provedor promove uma réplica e mantém o endpoint estável — a aplicação reconecta sozinha, sem cluster nosso para operar.

O que precisamos garantir do nosso lado é o comportamento durante a janela de promoção, descrito a seguir.

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

### O que a versão 0.1 deste documento prescrevia — e por que estava errado

A primeira versão desta seção mandava compor o vetor assim:

```sql
-- ERRADO. Mantido aqui como registro.
setweight(to_tsvector('portuguese', unaccent(coalesce(body_md,''))), 'B')
```

Parece razoável: stemming do português mais insensibilidade a acento. Está errado, e o erro é silencioso — a busca funciona, só devolve menos.

`unaccent()` roda **antes** do stemmer, e o stemmer snowball do português reconhece os sufixos pelos acentos. Sem eles, cai em regras genéricas. Medido no banco do projeto:

| Entrada | `to_tsvector('portuguese', unaccent(x))` | `to_tsvector('portuguese', x)` |
|---|---|---|
| `meditações` | `meditaco` | `medit` |
| `meditação` | `meditaca` | `medit` |

Com `unaccent` na frente, **singular e plural param de casar**. O stemming, que era a razão de escolher a configuração `portuguese`, ficava desligado na prática.

Trocar a chamada inline pela receita canônica — `unaccent` como dicionário na cadeia de uma configuração customizada — **não resolve**: a ordem continua sendo unaccent, depois stem. Também foi medido.

### O que o projeto faz

As duas propriedades são genuinamente conflitantes numa configuração só, e as duas importam. Então indexamos e consultamos **duas**:

```sql
to_tsvector('portuguese',  txt)  ||  to_tsvector('pt_unaccent', txt)
```

- `portuguese` — stemmer com acentos preservados. Faz `meditações` casar com `meditação`.
- `pt_unaccent` — cópia da anterior com `unaccent` na cadeia de dicionários. Faz `meditacao` casar com `meditação`, e `anatta` com `anattā`.

Criadas na migração `0003`, com o trigger que mantém o vetor. Índice GIN sobre `search_vector`.

Comportamento medido:

| Consulta | Encontra |
|---|---|
| `meditação` | `meditação` e `meditações` |
| `meditações` | `meditação` e `meditações` |
| `meditacao` | `meditação` |
| `anatta` / `anattā` | `anattā` |
| `sangha` / `saṅgha` | `saṅgha` |

Custo: o vetor guarda os lexemas das duas configurações e fica maior. Troca aceita — espaço de índice é barato, busca que não encontra é cara.

### O caso que sobra, e quem cobre

Consulta **sem acento** numa **flexão diferente** da que está no texto — `meditacao` contra um post que só diz `meditações` — continua sem casar por full-text. É o resíduo do conflito.

Cobre esse caso o índice trigrama sobre `body_md`, exposto em `apps/forum/search.py` como recuo explícito.

> **Detalhe que inverte o resultado:** o operador precisa ser `%>` (`trigram_word_similar`), não `%` (`trigram_similar`). `%` compara as **strings inteiras**, então uma palavra contra um post de parágrafos dá similaridade baixíssima e nunca casa. Medido:
>
> ```
> similarity('Sobre as meditações do Buda.', 'meditacao')       = 0.19   ← sob o limiar de 0.3
> word_similarity('meditacao', 'Sobre as meditações do Buda.')  = 0.60   ← passa
> ```
>
> `%>` compara o termo com a melhor palavra do texto. O índice GIN atende esse operador — verificado por `EXPLAIN`: Bitmap Index Scan, não varredura sequencial.

O recuo fica **desligado por padrão**. Trigrama não tem noção de relevância; misturado ao resultado bom, adiciona ruído. Como último recurso antes de "nada encontrado", vale.

### Escritas não-latinas

Pāli, sânscrito em Devanágari, tibetano e CJK não têm stemmer no PostgreSQL. Degradam para correspondência de token exato, o que é aceitável — e o índice trigrama cobre a lacuna com busca aproximada.

Para o Pāli, a configuração `pt_unaccent` remove mácrons e pontos subscritos: `anattā` indexa junto com `anatta`, `saṅgha` com `sangha`. É o comportamento certo, porque poucos digitam os diacríticos.

### Entrada do usuário

`websearch_to_tsquery`, nunca `to_tsquery`. Aceita a sintaxe que as pessoas conhecem de buscadores (aspas, `-palavra`, `or`) e **nunca levanta erro de sintaxe** com entrada digitada — `to_tsquery` levanta com um `&` solto, o que vira erro 500 vindo de uma caixa de busca pública.

### Rota de escalada, se necessária depois

`pg_search`/ParadeDB, que traz ranking BM25 escrito em Rust como extensão do próprio PostgreSQL — sem serviço adicional para operar, sem sincronização de índice, sem novo ponto de falha. Elasticsearch fica descartado: triplica o custo operacional para ganho nulo nesta escala.

Busca lê da réplica local quando houver réplica. Se ficar indisponível, falha isoladamente e o resto do fórum continua.
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

- **PITR é do provedor gerenciado** (§14): backup contínuo e recuperação a um instante arbitrário fazem parte do serviço. Confirme a janela de retenção do WAL — precisa cobrir o intervalo entre o erro acontecer e alguém perceber, que num fórum é medido em dias.
- **Cópia fria fora do provedor**, nossa: `pg_dump` periódico para o Garage ou outro S3. Conta suspensa ou projeto excluído por engano levam junto os backups que moram lá dentro.
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
| 11 | **PostgreSQL gerenciado** | VPS auto-gerido com Patroni | Backup, PITR e failover deixam de ser trabalho de voluntário — o risco dominante (§12) vira responsabilidade contratada. Ver §14 |

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
Roteador de banco leitura/escrita, middleware de fixação no primário, réplica de leitura em segunda região (configuração do provedor), Garage distribuído, ensaio de failover documentado, painel de atraso de replicação.

### Por que multi-região vem por último

Fases 1 a 4 entregam um fórum completo, público e mantível — em **uma região**.

- Replicação sobre um schema que ainda muda toda semana multiplica o custo de cada migração.
- A escala alvo (§1) cabe com folga num único Postgres. A segunda região resolve **falha de região**, não capacidade.
- Uma instância única bem operada — backup testado com PITR (§9.1), monitoramento, restauração ensaiada — já cobre a maioria esmagadora dos incidentes reais. Backup ruim derruba fóruns com muito mais frequência que região inteira caindo.
- Cada peça da Fase 5 (réplicas, roteamento, fixação no primário) é dívida operacional e de código permanente. Adiar é adiar custo real, não preguiça.

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

1. ~~**Hospedagem da instância única.**~~ **Resolvido: PostgreSQL gerenciado.** Ver §14.
2. **Regiões concretas.** Adiado para a Fase 5, não bloqueia nada agora. Quando chegar a hora: se o público for majoritariamente brasileiro, duas regiões no Brasil mais uma na Europa (comunidade lusófona) faz mais sentido que dispersão global. Não bloqueia nada agora.
3. **Anônimos podem ler tudo?** Assumido que sim. Se houver áreas restritas, o cache de página da §8 precisa de outro desenho.
4. **Idiomas do conteúdo além do português.** Assumido: interface e discussão em português, com termos e citações em Pāli, sânscrito, tibetano e chinês dentro do texto. Confirmar.
5. **Migração de conteúdo existente.** Há acervo a importar de algum fórum atual? Muda a prioridade de ferramentas de importação.
6. **Federação, no futuro.** Descartada agora. Se um dia entrar, ActivityPub sobre este schema é viável — mas seria uma decisão de arquitetura nova, não uma extensão.

---

## 14. Hospedagem: PostgreSQL gerenciado

**Decisão tomada.** O banco roda em serviço gerenciado, não em VPS auto-gerido.

### Por quê

A §12 identifica o risco dominante do projeto até a Fase 5: **instância única cair sem backup bom**. Enquanto não houver segunda região, o backup é a única cópia dos dados.

Esse risco é operacional, não técnico — e projeto open source mantido por voluntários é justamente onde trabalho operacional recorrente falha. Backup exige atenção contínua: verificar que rodou, verificar que restaura, verificar depois de cada mudança de schema. É o tipo de tarefa que ninguém percebe estar abandonada até o dia em que importa.

Gerenciado transfere PITR, failover e retenção para quem tem plantão. O custo é dinheiro, que dá para orçar; a alternativa custa vigilância, que não dá.

**Consequência direta:** **Patroni e etcd saem do escopo.** As menções na §3.4 e na §11 (Fase 5) passam a descrever o que o provedor faz, não o que operamos.

### O que isto NÃO resolve

> **A responsabilidade pelo backup não desaparece — muda de forma.** O provedor garante que o backup existe; ninguém além de nós garante que ele **restaura o nosso schema**. Um backup nunca restaurado deve ser tratado como inexistente, seja ele gerenciado ou não.

Continuam sendo nossos:

- **Ensaio de restauração mensal**, em instância descartável, com verificação de que os triggers da migração 0002 e as extensões voltaram funcionando. Automatizado, não manual.
- **Cópia fria em provedor distinto.** Conta suspensa, erro de faturamento ou exclusão acidental do projeto levam junto os backups que moram lá dentro. `pg_dump` periódico para o Garage (ou qualquer S3 fora do provedor do banco).
- **Retenção do WAL** suficiente para PITR cobrir o intervalo entre a hora em que um erro acontece e a hora em que alguém percebe. Num fórum, isso pode ser dias, não horas.

### Requisitos que o provedor precisa atender

O primeiro item é eliminatório e é o menos comum de ser oferecido.

#### 1. Collation ICU na criação do banco — eliminatório

A §6.1 exige `LOCALE_PROVIDER icu` com `ICU_LOCALE 'pt-BR'`. Isso só pode ser definido **na criação** do banco. Provedor que não permita passar esses parâmetros nos entrega um banco com collation `libc`, e a decisão fica travada para sempre — mudar depois exige recriar e reindexar tudo.

Muito provedor gerenciado expõe apenas "crie um banco com este nome", sem controle sobre `CREATE DATABASE`. Verifique antes de assinar, num período de avaliação:

```sql
-- Precisa executar sem erro:
CREATE DATABASE teste_icu
  ENCODING 'UTF8'
  LOCALE_PROVIDER icu
  ICU_LOCALE 'pt-BR'
  LOCALE 'C'
  TEMPLATE template0;

-- E depois, conectado a teste_icu, precisa devolver 'icu' e 'pt-BR':
SELECT datlocprovider, daticulocale FROM pg_database WHERE datname = 'teste_icu';

-- Prova prática de que a ordenação é a do português:
SELECT * FROM (VALUES ('Azul'),('Ávila'),('Amora')) t(x) ORDER BY x;
-- Correto:   Amora, Ávila, Azul
-- Com libc:  Amora, Azul, Ávila   ← rejeite o provedor
```

#### 2. Extensões `unaccent` e `pg_trgm`

Necessárias para a busca (§5). Ambas são **trusted** no PostgreSQL 13+, então o dono do banco pode instalá-las sem superusuário — o que normalmente resolve, já que serviço gerenciado nunca dá superusuário. Confirme mesmo assim: alguns provedores mantêm uma allowlist própria, mais restritiva que a do PostgreSQL.

```sql
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

A migração `0003` também cria uma **configuração de busca** própria. Não exige privilégio especial — qualquer dono de banco cria a sua —, mas confirme junto com as extensões:

```sql
CREATE TEXT SEARCH CONFIGURATION pt_unaccent (COPY = portuguese);
ALTER TEXT SEARCH CONFIGURATION pt_unaccent
    ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem;
```

#### 3. PostgreSQL 16 ou superior

Por causa da maturidade do suporte a ICU. A migração 0001 não usa recurso exclusivo de versão nova, mas não vale economizar aqui.

#### 4. Triggers e funções PL/pgSQL

A migração 0002 cria duas funções e dois triggers. Não exigem privilégio especial e funcionam em qualquer PostgreSQL gerenciado — mas serviços "PostgreSQL-compatível" que não são PostgreSQL de verdade podem falhar. Rode `make migrate` contra a avaliação antes de decidir.

#### 5. Pooler de conexões

Serviço gerenciado costuma ter limite de conexões bem menor que um Postgres próprio. Se o provedor oferecer pooler (PgBouncer ou equivalente):

> **Cuidado.** Pooler em modo *transaction* quebra cursores do lado do servidor e prepared statements. Com PgBouncer nesse modo é obrigatório configurar no Django:
> ```python
> DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
> ```
> Sem isso, consultas grandes falham de forma intermitente e difícil de diagnosticar — o erro aparece longe da causa.

Com pooler externo, `CONN_MAX_AGE` deve ir para `0`; o pool passa a ser dele, não do Django.

#### 6. Saída sem sequestro

Projeto AGPL precisa ser instalável por qualquer pessoa. Nada de extensão proprietária, nada de recurso exclusivo do provedor no schema. O que roda em gerenciado tem que rodar igual no `docker compose` do repositório — que continua sendo o ambiente de desenvolvimento e a referência de portabilidade.

Um `pg_dump` restaurável em PostgreSQL padrão é o teste: se não restaura, há dependência de fornecedor escondida.

### Efeito no roadmap

- **Fase 0–4:** banco gerenciado, uma região. Nada de Patroni.
- **Fase 5:** o multi-região passa a ser configuração do provedor (réplica de leitura em outra região) em vez de cluster próprio. Continua sendo necessário o roteador de leitura/escrita do Django e o middleware de fixação no primário (§3.2, §3.3) — esses são da aplicação, e nenhum provedor resolve por nós.

### Desenvolvimento continua em Docker

Nada disto muda o ambiente local. O `docker-compose.yml` do repositório sobe PostgreSQL 16 com a mesma collation ICU e é onde os testes rodam, inclusive no CI. Gerenciado é decisão de produção; a paridade de collation entre local, CI e produção é o que impede que um bug de ordenação apareça só depois do deploy.
