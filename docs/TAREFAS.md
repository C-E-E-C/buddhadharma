# Tarefas — Buddhadharma

Lote inicial, pronto para virar issue no GitHub. Formato neutro de propósito: título, contexto, critérios de aceite, arquivos e cuidados.

Cada tarefa é fechada — dá para pegar uma sem negociar com quem pegou outra.

- Estado geral e fases: [ROADMAP.md](ROADMAP.md)
- Decisões técnicas: [ARQUITETURA.md](ARQUITETURA.md)
- Paleta, temas e usabilidade: [DESIGN.md](DESIGN.md)
- Fluxo e padrões: [../CONTRIBUTING.md](../CONTRIBUTING.md)

---

## Como usar

**Tamanho** estima esforço, não dificuldade: `P` até meio dia, `M` um a dois dias, `G` mais que isso.

**Antes de começar:** comente na issue que vai pegar. Leia as [Armadilhas](ROADMAP.md#armadilhas) — várias tarefas encostam em decisões travadas.

**Para terminar:** `make check` precisa passar. Toda tarefa que muda comportamento leva teste junto.

### Rótulos sugeridos

`fase-1` `fase-2` · `área:segurança` `área:interface` `área:busca` `área:infra` `área:moderação` · `bom-primeiro-passo` · `precisa-decisão`

---

## Dependências

```
BD-001 (GitHub + CI) ─── independente, mas destrava a revisão de todo o resto

BD-002 (recuperação de senha) ─── independente
BD-003 (CSP) ──────┐
                   ├──► BD-005 (alternador de tema)
BD-004 (tokens) ───┤
                   ├──► BD-006 (componentes) ──► BD-007 (referência viva)
                   └──► BD-008 (Category.color)

BD-006 ──► BD-009 … BD-020   (toda a interface da Fase 2)

BD-018 (gravar PostLink) ──► BD-019 (backlinks)
BD-012 (view de busca) ──► BD-013, BD-014, BD-015
BD-016 (edição) ──► BD-017 (histórico)
```

**Livres agora:** BD-001, BD-002, BD-003, BD-004, BD-018.

Quem quiser começar sem esperar ninguém: **BD-002** ou **BD-018**.

---

## Infraestrutura

### BD-001 — Criar repositório no GitHub e fazer o CI rodar

| | |
|---|---|
| Fase | 0 | 
| Tamanho | P |
| Depende de | — |
| Rótulos | `área:infra` |

**Contexto.** O workflow de CI está escrito em `.github/workflows/ci.yml` e **nunca executou** — o repositório é local. A primeira execução costuma revelar ajustes, e enquanto isso não acontecer nenhuma revisão de pull request tem verificação automática.

**Critérios de aceite**
- [ ] Repositório público no GitHub, licença AGPL-3.0 reconhecida pelo GitHub
- [ ] `main` protegida: sem push direto, pull request obrigatório
- [ ] CI verde num pull request de teste
- [ ] Serviço PostgreSQL do CI sobe com collation ICU — confirmar no log que `datlocprovider` é `i`
- [ ] Descrição, tópicos e link para `docs/ROADMAP.md` no README do repositório

**Arquivos.** `.github/workflows/ci.yml`

**Cuidados.** O passo `check --deploy` usa `config.settings.prod` e exige `ALLOWED_HOSTS`; confirme que o valor de CI não vira um aviso silencioso. Se o CI ficar lento, a causa provável é o download da imagem do Postgres, não os testes — que rodam em segundos.

---

## Segurança

### BD-002 — Recuperação de senha

| | |
|---|---|
| Fase | 1 |
| Tamanho | P |
| Depende de | — |
| Rótulos | `fase-1` `área:segurança` `bom-primeiro-passo` |

**Contexto.** Lacuna da Fase 1. A [§7.3](ARQUITETURA.md#73-enumeração-e-privacidade) especifica o comportamento — resposta idêntica para email existente e inexistente, para não revelar quem tem conta —, mas as rotas não existem. Sem isso, quem esquece a senha perde a conta em definitivo.

**Critérios de aceite**
- [ ] Fluxo completo: pedir, email enviado, confirmar, concluído
- [ ] **Resposta idêntica** para email cadastrado e não cadastrado — mesma página, mesmo tempo de resposta aparente
- [ ] Link expira; expiração configurável por `PASSWORD_RESET_TIMEOUT`
- [ ] Link é de uso único — usar duas vezes falha
- [ ] Rate limit no pedido, por IP e por email
- [ ] Templates de email em português, texto puro e sem imagem remota
- [ ] Todo texto passa por `gettext`
- [ ] Testes: email inexistente devolve a mesma resposta que existente; token não reutilizável; token de um usuário não serve para outro

**Arquivos.** `apps/accounts/urls.py`, `apps/accounts/views.py`, `templates/accounts/`, `apps/accounts/tests/`

**Cuidados.** As views de `django.contrib.auth` já fazem quase tudo certo — não reimplemente. Confirme com teste que a resposta é indistinguível: é a parte que costuma vazar. Em produção falta configurar SMTP; deixe documentado em `.env.example` o que precisa ser preenchido.

---

### BD-003 — Content-Security-Policy

| | |
|---|---|
| Fase | 1 |
| Tamanho | M |
| Depende de | — |
| Rótulos | `fase-1` `área:segurança` |

**Contexto.** A [§7.1](ARQUITETURA.md#71-conteúdo-gerado-por-usuário) prevê CSP restritiva, e ela **não está implementada** — hoje só existem os cabeçalhos de `prod.py`. É a segunda linha de defesa sob a sanitização do Markdown: se algum dia passar um `<script>`, a CSP é o que impede a execução.

Pré-requisito do alternador de tema (BD-005), que precisa de um script inline.

**Critérios de aceite**
- [ ] CSP aplicada, sem `unsafe-inline` e sem `unsafe-eval` em `script-src`
- [ ] `default-src 'self'`; `object-src 'none'`; `base-uri 'self'`; `frame-ancestors 'none'`
- [ ] `img-src` restrito ao próprio site (imagem remota já vira link na renderização)
- [ ] Fonte da CSP num único lugar, não espalhada
- [ ] Suporte a **hash** para script inline — ver o cuidado abaixo
- [ ] Modo `report-only` disponível por configuração, para validar antes de aplicar
- [ ] Teste verificando que o cabeçalho existe e não contém `unsafe-inline`

**Arquivos.** `config/settings/`, middleware novo em `apps/core/`

**Cuidados.**
> **Não use `nonce`.** Nonce precisa ser único por resposta; a [§8](ARQUITETURA.md#8-cache-e-desempenho) guarda páginas inteiras em cache, e uma página servida do cache carregaria um nonce velho que não bate com o cabeçalho gerado na requisição. Use **hash** — os scripts do projeto são estáticos, então o hash é estável e o cabeçalho não varia.

O Django Admin usa estilo inline e pode quebrar; considere CSP mais frouxa apenas sob `/admin/`, documentando o porquê.

---

## Fase 2.0 — Sistema de design

> Vem **antes** de 2.1–2.6. Se chegar depois, toda a interface da Fase 2 é reestilizada.

### BD-004 — Tokens de cor e escala tipográfica

| | |
|---|---|
| Fase | 2.0 |
| Tamanho | M |
| Depende de | — |
| Rótulos | `fase-2` `área:interface` `bom-primeiro-passo` |

**Contexto.** A paleta e os contrastes já estão calculados em [DESIGN.md](DESIGN.md) — esta tarefa é transcrever aquilo para CSS, não redecidir. Base de tudo que vem depois.

**Critérios de aceite**
- [ ] Rampa quente 100–900 e neutros quentes, em custom properties
- [ ] Tokens **semânticos** (`--fundo`, `--tinta`, `--acento`, `--perigo`, `--sucesso`…) por cima da rampa
- [ ] Três estados de tema: `:root` claro; `@media (prefers-color-scheme: dark)` com a guarda `:root:not([data-theme="light"])`; `:root[data-theme="dark"]`
- [ ] `color-scheme` declarado, para controles nativos e barra de rolagem acompanharem
- [ ] Escala tipográfica e escala de espaçamento definidas como tokens
- [ ] Medida de leitura entre 65 e 75 caracteres no corpo do post
- [ ] Nenhuma cor definida apenas dentro de bloco de media query ou `[data-theme]`

**Arquivos.** `static/css/`

**Cuidados.**
> **Componente nenhum referencia o passo da rampa.** A rampa se inverte entre os temas: no claro só 600–900 são legíveis, no escuro só 100–500. Tudo passa por token semântico, e o tema troca o valor por baixo.

Amarelo (400) nunca é tinta sobre fundo claro — 1.92:1 reprova até como borda.

---

### BD-005 — Alternador de tema, três estados

| | |
|---|---|
| Fase | 2.0 |
| Tamanho | M |
| Depende de | BD-003, BD-004 |
| Rótulos | `fase-2` `área:interface` |

**Contexto.** Claro, escuro e **sistema**, com sistema como padrão. Quem muda o telemóvel para escuro à noite espera que o fórum acompanhe, salvo escolha explícita em contrário.

O artifact do roadmap tem uma implementação de referência funcionando — vale olhar antes de começar.

**Critérios de aceite**
- [ ] Três estados, com "sistema" como padrão
- [ ] Preferência em `localStorage`; **não** gravada no perfil do usuário
- [ ] Tema aplicado **antes da primeira pintura** — sem piscada de tema errado
- [ ] Script inline liberado por **hash** na CSP, nunca por `nonce`
- [ ] Sem JavaScript a página continua correta, seguindo `prefers-color-scheme`
- [ ] Controle acessível: grupo rotulado, estado anunciado, alvo de toque ≥ 44 px
- [ ] `localStorage` indisponível (modo privado) não quebra a página
- [ ] Teste verificando que o HTML servido **não varia** com o tema

**Arquivos.** `templates/base.html`, `static/js/`, configuração da CSP

**Cuidados.**
> **O HTML tem de ser neutro em relação ao tema.** Decidir no servidor triplica o cache de página da §8. As cores vêm de custom properties; só o atributo na raiz muda, e quem escreve é o cliente.

---

### BD-006 — Componentes base

| | |
|---|---|
| Fase | 2.0 |
| Tamanho | M |
| Depende de | BD-004 |
| Rótulos | `fase-2` `área:interface` |

**Contexto.** O vocabulário visual que todas as telas da Fase 2 vão usar. Escopo fechado de propósito — não invente componente que ninguém pediu.

**Critérios de aceite**
- [ ] Botão: primário (preenchido), secundário (contorno), **destrutivo** e desabilitado
- [ ] Etiqueta de estado, campo de formulário com erro e ajuda, linha de listagem, aviso (informação, sucesso, atenção, perigo)
- [ ] Foco visível em tudo que recebe teclado
- [ ] Alvos de toque ≥ 44 × 44 px
- [ ] `prefers-reduced-motion` respeitado
- [ ] Todos verificados nos dois temas

**Arquivos.** `static/css/`, `templates/componentes/`

**Cuidados.**
> **Ação destrutiva é contorno com ícone, nunca preenchimento sólido.** Vermelho de marca e vermelho de perigo têm razão de luminância de 1.04:1 — são idênticos em brilho, e quem tem protanopia ou está no sol vê dois botões iguais. A forma carrega a distinção; a cor só reforça.

Nenhuma informação pode ser transmitida só por cor. Vale para categoria, tópico fixado ou trancado, e nível de confiança.

---

### BD-007 — Página de referência viva

| | |
|---|---|
| Fase | 2.0 |
| Tamanho | P |
| Depende de | BD-005, BD-006 |
| Rótulos | `fase-2` `área:interface` |

**Contexto.** Uma página mostrando todos os tokens e componentes nos dois temas. É o que impede a deriva: sem um lugar onde os dois temas aparecem lado a lado, o tema escuro quebra e ninguém percebe até um usuário reclamar.

**Critérios de aceite**
- [ ] Rota acessível só em `DEBUG`, ou restrita a moderação
- [ ] Rampa completa com os contrastes anotados
- [ ] Todos os componentes de BD-006, em todos os estados
- [ ] Amostra de tipografia com português acentuado, Pāli (`anattā`, `saṅgha`), devanágari, tibetano e CJK
- [ ] Alternador de tema na própria página

**Arquivos.** `apps/core/views.py`, `templates/referencia.html`

---

### BD-008 — `Category.color`: de hex livre para tokens

| | |
|---|---|
| Fase | 2.0 |
| Tamanho | M |
| Depende de | BD-004 |
| Rótulos | `fase-2` `área:interface` `área:moderação` |

**Contexto.** Hoje é texto livre com padrão `#8B6F47` — que nem pertence à paleta nova. Quem modera pode escolher uma cor ilegível sem perceber, e um hex fixo não pode servir aos dois temas.

**Critérios de aceite**
- [ ] Conjunto curado de tokens de categoria, verificados nos dois temas
- [ ] Campo guarda o **nome do token**, não o hex
- [ ] Admin oferece escolha entre os tokens, não campo livre
- [ ] Migração de dados mapeia os valores existentes para o token mais próximo
- [ ] Categoria continua distinguível sem depender de cor — ícone ou rótulo

**Arquivos.** `apps/forum/models.py`, `apps/forum/admin.py`, migração nova

**Cuidados.** Mudança de schema: precisa ser retrocompatível. Use expand/contract — adiciona a coluna nova, migra os dados, troca o código, remove a antiga numa release posterior. Nunca as duas coisas na mesma migração.

---

## Fase 2.1 — Reações

### BD-009 — Caminho de escrita das reações

| | |
|---|---|
| Fase | 2.1 |
| Tamanho | M |
| Depende de | BD-006 |
| Rótulos | `fase-2` `área:interface` |

**Contexto.** Modelos, trigger de contagem e exibição estão prontos e testados; **não existe forma de reagir**. Primeira vez que o HTMX entra no projeto — o padrão criado aqui será copiado pelo resto da fase, então vale caprichar.

**Critérios de aceite**
- [ ] Alternar reação: clicar adiciona, clicar de novo remove
- [ ] Resposta devolve só o fragmento das reações daquele post
- [ ] Contagem lida de `ReactionCount`, nunca de `COUNT(*)`
- [ ] Estado "eu reagi" visível, e não apenas pela cor
- [ ] Exige autenticação; anônimo vê as contagens e é convidado a entrar
- [ ] Rate limit por usuário
- [ ] Reagir duas vezes em corrida não estoura erro 500 — o `UNIQUE` é tratado
- [ ] Funciona sem JavaScript, via formulário comum
- [ ] Testes: alternar incrementa e decrementa; contagem materializada bate; anônimo é barrado

**Arquivos.** `apps/forum/views.py`, `apps/forum/urls.py`, `templates/forum/`

**Cuidados.** O trigger cuida da contagem — não some nem subtraia no Python, sob risco de contar duas vezes. HTMX precisa do token CSRF em toda requisição de escrita.

---

### BD-010 — Seletor de emoji

| | |
|---|---|
| Fase | 2.1 |
| Tamanho | P |
| Depende de | BD-009 |
| Rótulos | `fase-2` `área:interface` |

**Critérios de aceite**
- [ ] Lista os emojis ativos, na ordem de `position`
- [ ] Navegável por teclado; fecha com `Esc`; foco volta ao botão de origem
- [ ] Lista vem do cache de aplicação, não do banco a cada abertura
- [ ] Cada emoji tem rótulo textual acessível
- [ ] Alvos ≥ 44 px

**Arquivos.** `templates/forum/`, `static/js/`

---

### BD-011 — Quem reagiu

| | |
|---|---|
| Fase | 2.1 |
| Tamanho | P |
| Depende de | BD-009 |
| Rótulos | `fase-2` `área:interface` |

**Critérios de aceite**
- [ ] Ver quem reagiu, agrupado por emoji
- [ ] Carregado sob demanda, não junto da página
- [ ] Limite com "ver mais" para posts muito reagidos
- [ ] Sem N+1 — teste de contagem de queries

**Arquivos.** `apps/forum/views.py`, `templates/forum/`

---

## Fase 2.2 — Busca

### BD-012 — View e página de resultados

| | |
|---|---|
| Fase | 2.2 |
| Tamanho | M |
| Depende de | BD-006 |
| Rótulos | `fase-2` `área:busca` |

**Contexto.** O motor está pronto e medido em `apps/forum/search.py`, com 9 testes em `apps/forum/tests/test_models.py`. Falta a interface.

**Critérios de aceite**
- [ ] Rota de busca com o termo na query string, para o resultado ser compartilhável
- [ ] Usa `search_posts()` — **não** monta `SearchQuery` à mão
- [ ] Resultado mostra tópico, autor, data e trecho
- [ ] Busca vazia mostra estado inicial útil, não lista vazia
- [ ] Sem resultado, oferece o recuo por trigrama (`fuzzy_fallback=True`) e diz que os resultados são aproximados
- [ ] Paginação por keyset
- [ ] Entrada com sintaxe quebrada (`&&&`, parêntese solto) não gera erro
- [ ] Sem N+1

**Arquivos.** `apps/forum/views.py`, `apps/forum/urls.py`, `templates/forum/busca.html`

**Cuidados.**
> **Consultar só uma das duas configurações perde metade dos resultados, em silêncio.** `search_posts()` já cuida disso. A tentação de "simplificar" a consulta é exatamente a armadilha registrada.

---

### BD-013 — Caixa de busca no cabeçalho

| | |
|---|---|
| Fase | 2.2 |
| Tamanho | P |
| Depende de | BD-012 |
| Rótulos | `fase-2` `área:busca` `bom-primeiro-passo` |

**Critérios de aceite**
- [ ] Presente em todas as páginas, `<form>` comum com `GET`
- [ ] Funciona sem JavaScript
- [ ] Rotulada para leitor de tela
- [ ] Não empurra o conteúdo no telemóvel

**Arquivos.** `templates/base.html`

---

### BD-014 — Destaque do trecho

| | |
|---|---|
| Fase | 2.2 |
| Tamanho | M |
| Depende de | BD-012 |
| Rótulos | `fase-2` `área:busca` |

**Critérios de aceite**
- [ ] Trecho ao redor do termo, com o termo destacado
- [ ] Destaque gerado no PostgreSQL (`ts_headline`), com as **duas** configurações de busca
- [ ] Saída escapada — o trecho vem do Markdown cru e não pode virar HTML
- [ ] Destaque não depende só de cor
- [ ] Texto sem correspondência exata (recuo por trigrama) degrada sem quebrar

**Arquivos.** `apps/forum/search.py`, `templates/forum/busca.html`

**Cuidados.** `ts_headline` é caro; aplique só aos resultados da página atual, nunca ao conjunto inteiro.

---

### BD-015 — Filtros por categoria e autor

| | |
|---|---|
| Fase | 2.2 |
| Tamanho | P |
| Depende de | BD-012 |
| Rótulos | `fase-2` `área:busca` |

**Critérios de aceite**
- [ ] Filtrar por categoria e por autor, combináveis com o termo
- [ ] Filtros refletidos na URL
- [ ] Filtro ativo visível e removível
- [ ] Consulta continua usando os índices — verificar com `EXPLAIN`

**Arquivos.** `apps/forum/search.py`, `apps/forum/views.py`, `templates/forum/busca.html`

---

## Fase 2.3 — Edição com histórico

### BD-016 — Editar post gravando revisão

| | |
|---|---|
| Fase | 2.3 |
| Tamanho | M |
| Depende de | BD-006 |
| Rótulos | `fase-2` `área:moderação` |

**Contexto.** `PostRevision` existe e nunca é gravado. A [§4.4](ARQUITETURA.md#44-revisões) trata transparência de edição como requisito: num fórum de tema doutrinário, editar em silêncio uma citação de sutta não pode ser possível.

**Critérios de aceite**
- [ ] Autor edita o próprio post; moderação edita qualquer um
- [ ] Cada edição grava `PostRevision` com o texto **anterior**, dentro da mesma transação
- [ ] `edited_at` e `edit_count` atualizados
- [ ] `body_html` regenerado e sanitizado
- [ ] Vetor de busca atualizado — o trigger cuida, mas confirme com teste
- [ ] Motivo da edição, opcional
- [ ] Marca "editado" visível no post
- [ ] Teste: editar duas vezes gera duas revisões, e a primeira guarda o texto original

**Arquivos.** `apps/forum/views.py`, `apps/forum/urls.py`, `apps/forum/forms.py`, `templates/forum/`

**Cuidados.** Gravar a revisão e atualizar o post têm de ser atômicos — se a revisão falhar, a edição não pode passar. O trigger de busca dispara em `UPDATE OF body_md`; se alterar a coluna por caminho diferente, confirme que ainda dispara.

---

### BD-017 — Histórico de revisões visível

| | |
|---|---|
| Fase | 2.3 |
| Tamanho | M |
| Depende de | BD-016 |
| Rótulos | `fase-2` `área:moderação` `precisa-decisão` |

**Critérios de aceite**
- [ ] Ver as revisões de um post, com autor e data
- [ ] Diferença entre versões, legível
- [ ] Diferença renderizada com escape — texto de usuário nunca vira HTML
- [ ] Quem pode ver: definir na issue (público, ou só moderação) — **precisa de decisão**
- [ ] Post removido não expõe conteúdo pelo histórico

**Arquivos.** `apps/forum/views.py`, `templates/forum/`

**Cuidados.** Marcar com `precisa-decisão`: histórico público é mais transparente, mas expõe texto que alguém apagou por vergonha ou por engano. Decidir antes de implementar.

---

## Fase 2.4 — Vínculos entre posts

### BD-018 — Gravar `PostLink` ao salvar

| | |
|---|---|
| Fase | 2.4 |
| Tamanho | M |
| Depende de | — |
| Rótulos | `fase-2` `bom-primeiro-passo` |

**Contexto.** `extract_internal_links()` está implementada e testada em `apps/core/markdown.py`, e **nunca é chamada**. A tabela `PostLink` existe, com índice por alvo. Falta ligar as duas pontas.

Livre agora — não depende do sistema de design.

**Critérios de aceite**
- [ ] Ao criar ou editar post, os links internos viram linhas em `PostLink`
- [ ] Resolver o caminho para um `Post` de verdade — ver o cuidado abaixo
- [ ] Link para tópico sem número de post aponta para o post 1
- [ ] Link que não resolve é ignorado em silêncio, sem erro
- [ ] Editar um post recalcula os vínculos: some o que saiu, entra o que foi acrescentado
- [ ] Post apagado não deixa vínculo pendurado
- [ ] Sem duplicata — o `UNIQUE` é respeitado, reeditar não estoura
- [ ] Testes: link resolve; link quebrado é ignorado; edição recalcula

**Arquivos.** `apps/forum/models.py`, `apps/core/markdown.py`, `apps/forum/tests/`

**Cuidados.**
> **O caminho carrega fragmento.** `Post.get_absolute_url()` devolve `/t/<pk>/<slug>/#post-<position>`, e `extract_internal_links()` entrega a string inteira. A resolução precisa separar o caminho do fragmento, achar o tópico pelo `pk` e o post pela `position` — não existe rota que resolva um post diretamente.

Resolver dentro do laço de salvamento é um N+1 esperando acontecer. Junte os identificadores e resolva em uma consulta.

---

### BD-019 — Backlinks: "citado em"

| | |
|---|---|
| Fase | 2.4 |
| Tamanho | P |
| Depende de | BD-018 |
| Rótulos | `fase-2` `área:interface` |

**Contexto.** O recurso que fóruns bons têm e os ruins não: ao ler um post, ver quais posts posteriores o citaram. Num fórum sobre Budismo, permite rastrear ao longo de anos as discussões que referenciam a mesma passagem.

**Critérios de aceite**
- [ ] Post mostra quem o citou, usando o índice por alvo
- [ ] Post removido não aparece como citação
- [ ] Lista limitada, com "ver mais"
- [ ] Sem N+1
- [ ] Post sem citação não mostra seção vazia

**Arquivos.** `apps/forum/views.py`, `templates/forum/topic.html`

---

### BD-020 — Botão de citar

| | |
|---|---|
| Fase | 2.4 |
| Tamanho | P |
| Depende de | BD-006, BD-018 |
| Rótulos | `fase-2` `área:interface` |

**Critérios de aceite**
- [ ] Citar um post insere a citação em Markdown no campo de resposta
- [ ] Citar uma seleção usa só o trecho selecionado
- [ ] A citação inclui link para o post de origem, o que alimenta o `PostLink`
- [ ] Atribuição visível na citação renderizada
- [ ] Sem JavaScript, o botão leva ao campo de resposta com a citação já preenchida

**Arquivos.** `templates/forum/topic.html`, `static/js/`

---

## Ainda não prontas

Precisam de decisão antes de virar tarefa.

**2.5 — Editor de Markdown.** Depende de BD-004 e BD-006, e da escolha do editor. EasyMDE é o candidato do roadmap, mas vale confirmar manutenção e tamanho antes de assumir a dependência.

**2.6 — Anexos.** O maior item da fase: traz Garage e armazenamento de objetos. Antes de abrir tarefa é preciso decidir limites por nível de confiança, política de retenção e o que fazer com anexo de post apagado.

**Fase 3 em diante.** Só depois que a Fase 2 fechar. Abrir agora produz issue que envelhece.
