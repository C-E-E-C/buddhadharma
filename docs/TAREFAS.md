# Tarefas — Buddhadharma

Lote inicial, pronto para virar issue no GitHub. Formato neutro de propósito: título, contexto, critérios de aceite, arquivos e cuidados.

Cada tarefa é fechada — dá para pegar uma sem negociar com quem pegou outra.

- Estado geral e fases: [ROADMAP.md](ROADMAP.md)
- Decisões técnicas: [ARQUITETURA.md](ARQUITETURA.md)
- Paleta, temas e usabilidade: [DESIGN.md](DESIGN.md)
- Fluxo e padrões: [../CONTRIBUTING.md](../CONTRIBUTING.md)

---

## Como usar

Cada tarefa segue a mesma estrutura, na mesma ordem:

| Seção | O que responde |
|---|---|
| **Objetivo** | O que estará verdadeiro quando terminar |
| **Contexto** | Por que existe, e o que já está pronto |
| **Critérios de aceite** | Como saber que terminou — verificável, não opinião |
| **Como implementar** | Abordagem sugerida, com esboço de código onde a forma importa |
| **Pontos de partida** | Arquivos e símbolos que já existem no código |
| **Método de teste** | O que verificar e onde escrever o teste |
| **Cuidados** | O que costuma dar errado nesta tarefa — só quando há algo |

As issues no GitHub são geradas deste documento e trazem todas as seções **menos "Como implementar"**: a issue enuncia o problema e os critérios, e a abordagem fica a cargo de quem implementa. A sugestão continua aqui, para quem quiser um ponto de partida.

**Tamanho** estima esforço, não dificuldade: `P` até meio dia, `M` um a dois dias, `G` mais que isso.

**Antes de começar:** comente na issue que vai pegar. Leia a seção **Cuidados** da tarefa e as [decisões registradas](ARQUITETURA.md#10-decisões-registradas) — várias tarefas encostam em escolhas já fechadas.

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

#### Objetivo

O repositório impede merge sem CI verde, e quem chega entende o projeto sem abrir o código.

#### Contexto

O workflow de CI está escrito em `.github/workflows/ci.yml` e **nunca executou** — o repositório é local. A primeira execução costuma revelar ajustes, e enquanto isso não acontecer nenhuma revisão de pull request tem verificação automática.

#### Critérios de aceite

- [ ] Repositório público no GitHub, licença AGPL-3.0 reconhecida pelo GitHub
- [ ] `main` protegida: sem push direto, pull request obrigatório
- [ ] CI verde num pull request de teste
- [ ] Serviço PostgreSQL do CI sobe com collation ICU — confirmar no log que `datlocprovider` é `i`
- [ ] Descrição, tópicos e link para `docs/ROADMAP.md` no README do repositório

#### Como implementar

O repositório e o CI já existem e a primeira execução passou. Resta o que exige decisão de configuração:

1. Proteger `main` em *Settings → Branches*: exigir pull request, exigir que o job `test` passe, bloquear push direto. Comece sem exigir revisão aprovada — com um mantenedor só, isso trava o trabalho.
2. Preencher descrição, tópicos (`django`, `forum`, `buddhism`, `portuguese`, `agpl`) e o link para `docs/ROADMAP.md`.
3. Subir as ações depreciadas: `actions/checkout@v4` → `v5`, `astral-sh/setup-uv@v5` → `v6`. O CI avisa que Node 20 foi descontinuado.

#### Pontos de partida

- `.github/workflows/ci.yml` — o workflow; o serviço `postgres` traz `POSTGRES_INITDB_ARGS` com ICU
- `docs/ROADMAP.md` — o que colocar na descrição

#### Método de teste

Abrir um pull request de teste e confirmar que o merge fica bloqueado enquanto o CI não termina.

---

#### Cuidados

O passo `check --deploy` usa `config.settings.prod` e exige `ALLOWED_HOSTS`; confirme que o valor de CI não vira um aviso silencioso. Se o CI ficar lento, a causa provável é o download da imagem do Postgres, não os testes — que rodam em segundos.

---

## Segurança

### BD-002 — Recuperação de senha

| | |
|---|---|
| Fase | 1 |
| Tamanho | P |
| Depende de | — |
| Rótulos | `fase-1` `área:segurança` `bom-primeiro-passo` |

#### Objetivo

Quem esquece a senha recupera o acesso sozinho, sem que o fórum revele quais emails têm conta.

#### Contexto

Lacuna da Fase 1. A [§7.3](ARQUITETURA.md#73-enumeração-e-privacidade) especifica o comportamento — resposta idêntica para email existente e inexistente, para não revelar quem tem conta —, mas as rotas não existem. Sem isso, quem esquece a senha perde a conta em definitivo.

#### Critérios de aceite

- [ ] Fluxo completo: pedir, email enviado, confirmar, concluído
- [ ] **Resposta idêntica** para email cadastrado e não cadastrado — mesma página, mesmo tempo de resposta aparente
- [ ] Link expira; expiração configurável por `PASSWORD_RESET_TIMEOUT`
- [ ] Link é de uso único — usar duas vezes falha
- [ ] Rate limit no pedido, por IP e por email
- [ ] Templates de email em português, texto puro e sem imagem remota
- [ ] Todo texto passa por `gettext`
- [ ] Testes: email inexistente devolve a mesma resposta que existente; token não reutilizável; token de um usuário não serve para outro

#### Como implementar

Use as views prontas de `django.contrib.auth`; elas já respondem igual para email existente e inexistente. O trabalho é ligar rotas, escrever templates e provar o comportamento com teste.

```python
# apps/accounts/urls.py
from django.contrib.auth import views as auth_views

path("senha/", auth_views.PasswordResetView.as_view(
        template_name="accounts/senha_pedir.html",
        email_template_name="accounts/email_senha.txt",
        subject_template_name="accounts/email_senha_assunto.txt",
        success_url=reverse_lazy("accounts:password_reset_done"),
     ), name="password_reset"),
# ... done / confirm / complete
```

Cinco templates: pedir, enviado, confirmar, concluído e o corpo do email. Email em texto puro — HTML com imagem remota vazaria o IP de quem abre.

Rate limit por IP e por email no `PasswordResetView`. Não há dependência de rate limit no projeto ainda; um contador no cache (`django.core.cache`) resolve, e o Redis já está configurado com `IGNORE_EXCEPTIONS`, então cair não derruba o fluxo.

#### Pontos de partida

- `apps/accounts/urls.py` — hoje só login, logout, registro e perfil
- `config/settings/base.py` — `PASSWORD_RESET_TIMEOUT` ainda não está definido; o padrão do Django é 3 dias
- `.env.example` — precisa ganhar as variáveis de SMTP
- `templates/accounts/login.html` — modelo de estrutura para os novos templates

#### Método de teste

Em `apps/accounts/tests/test_password_reset.py`:

- email cadastrado e não cadastrado produzem **a mesma resposta** — compare status e corpo renderizado
- email cadastrado gera uma mensagem em `django.core.mail.outbox`; o não cadastrado não gera
- o token do usuário A não serve para o usuário B
- usar o link duas vezes falha na segunda
- token expirado é recusado (ajuste `PASSWORD_RESET_TIMEOUT` no teste)

---

#### Cuidados

As views de `django.contrib.auth` já fazem quase tudo certo — não reimplemente. Confirme com teste que a resposta é indistinguível: é a parte que costuma vazar. Em produção falta configurar SMTP; deixe documentado em `.env.example` o que precisa ser preenchido.

---

### BD-003 — Content-Security-Policy

| | |
|---|---|
| Fase | 1 |
| Tamanho | M |
| Depende de | — |
| Rótulos | `fase-1` `área:segurança` |

#### Objetivo

Um script que escape da sanitização do Markdown não chega a executar no navegador de quem lê.

#### Contexto

A [§7.1](ARQUITETURA.md#71-conteúdo-gerado-por-usuário) prevê CSP restritiva, e ela **não está implementada** — hoje só existem os cabeçalhos de `prod.py`. É a segunda linha de defesa sob a sanitização do Markdown: se algum dia passar um `<script>`, a CSP é o que impede a execução.

Pré-requisito do alternador de tema (BD-005), que precisa de um script inline.

#### Critérios de aceite

- [ ] CSP aplicada, sem `unsafe-inline` e sem `unsafe-eval` em `script-src`
- [ ] `default-src 'self'`; `object-src 'none'`; `base-uri 'self'`; `frame-ancestors 'none'`
- [ ] `img-src` restrito ao próprio site (imagem remota já vira link na renderização)
- [ ] Fonte da CSP num único lugar, não espalhada
- [ ] Suporte a **hash** para script inline — ver o cuidado abaixo
- [ ] Modo `report-only` disponível por configuração, para validar antes de aplicar
- [ ] Teste verificando que o cabeçalho existe e não contém `unsafe-inline`

#### Como implementar

Middleware próprio em `apps/core/`, com a política montada a partir de uma constante nas configurações. Sem dependência nova — `django-csp` traria suporte a nonce, que é justamente o que não podemos usar.

```python
# apps/core/middleware.py
class ContentSecurityPolicyMiddleware:
    def __call__(self, request):
        resposta = self.get_response(request)
        cabecalho = ("Content-Security-Policy-Report-Only"
                     if settings.CSP_REPORT_ONLY else "Content-Security-Policy")
        resposta.setdefault(cabecalho, settings.CSP_POLICY)
        return resposta
```

Os hashes dos scripts inline entram em `CSP_SCRIPT_HASHES`, calculados no build ou fixados à mão:

```python
import base64, hashlib
hash_ = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
# script-src 'self' 'sha256-{hash_}'
```

O hash cobre o conteúdo do `<script>` **sem** as tags. Um espaço a mais quebra — vale um teste que recalcula o hash a partir do template e compara com a configuração, para não descobrir isso em produção.

O admin do Django usa estilo inline; deixe `style-src` mais frouxo sob `/admin/` e documente o porquê no código.

#### Pontos de partida

- `config/settings/prod.py` — onde vivem os demais cabeçalhos de segurança
- `config/settings/base.py` — `MIDDLEWARE`, onde o novo entra logo após `SecurityMiddleware`
- `apps/core/markdown.py` — a allowlist do `nh3` define o que a CSP precisa permitir

#### Método de teste

- o cabeçalho está presente e não contém `unsafe-inline` nem `unsafe-eval`
- o hash configurado bate com o script realmente servido no template
- em `report-only`, o cabeçalho muda de nome e a política continua igual

---

#### Cuidados

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

#### Objetivo

Toda cor do fórum vem de um token semântico que troca com o tema, sem nenhuma referência direta à rampa.

#### Contexto

A paleta e os contrastes já estão calculados em [DESIGN.md](DESIGN.md) — esta tarefa é transcrever aquilo para CSS, não redecidir. Base de tudo que vem depois.

#### Critérios de aceite

- [ ] Rampa quente 100–900 e neutros quentes, em custom properties
- [ ] Tokens **semânticos** (`--fundo`, `--tinta`, `--acento`, `--perigo`, `--sucesso`…) por cima da rampa
- [ ] Três estados de tema: `:root` claro; `@media (prefers-color-scheme: dark)` com a guarda `:root:not([data-theme="light"])`; `:root[data-theme="dark"]`
- [ ] `color-scheme` declarado, para controles nativos e barra de rolagem acompanharem
- [ ] Escala tipográfica e escala de espaçamento definidas como tokens
- [ ] Medida de leitura entre 65 e 75 caracteres no corpo do post
- [ ] Nenhuma cor definida apenas dentro de bloco de media query ou `[data-theme]`

#### Como implementar

Transcrever a paleta de `docs/DESIGN.md`, que já traz os contrastes medidos. Duas camadas:

```css
:root {
  /* rampa — valores crus, nunca usados direto por componente */
  --quente-100: #FDF3E0;  --quente-400: #EFA92B;  --quente-700: #A6321E;
  /* ... 100 a 900 ... */

  /* semânticos — é isto que os componentes usam */
  --fundo: #FAF9F7;  --superficie: #FFFFFF;
  --tinta: #1C1714;  --tinta-suave: #6B605A;
  --acento: var(--quente-700);
  --perigo: #B3261E;  --sucesso: #2F6B4F;  --info: #1F5F8B;
}
```

Os três estados de tema, nesta ordem — a guarda `:not([data-theme="light"])` faz uma escolha explícita por claro vencer um sistema escuro:

```css
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* só os semânticos mudam */ }
}
:root[data-theme="dark"] { /* idem */ }
```

Nenhuma cor pode existir **apenas** dentro de um bloco de media query: no estado "sistema" o atributo não é estampado, e a página renderiza texto de um tema sobre o fundo do outro.

O artifact do roadmap tem essa estrutura funcionando e serve de referência.

#### Pontos de partida

- `docs/DESIGN.md` §2 e §4 — rampa, neutros e contrastes já calculados
- `static/css/forum.css` — o CSS provisório atual, que esta tarefa substitui
- `templates/base.html` — onde a folha é carregada

#### Método de teste

Verificação manual, com a página de referência da BD-007 como destino. Enquanto ela não existe, confira nas telas atuais que nenhuma cor sumiu ao alternar o tema do sistema operacional.

---

#### Cuidados

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

#### Objetivo

O leitor escolhe claro, escuro ou seguir o sistema — sem piscada na carga e sem multiplicar o cache de página.

#### Contexto

Claro, escuro e **sistema**, com sistema como padrão. Quem muda o telemóvel para escuro à noite espera que o fórum acompanhe, salvo escolha explícita em contrário.

O artifact do roadmap tem uma implementação de referência funcionando — vale olhar antes de começar.

#### Critérios de aceite

- [ ] Três estados, com "sistema" como padrão
- [ ] Preferência em `localStorage`; **não** gravada no perfil do usuário
- [ ] Tema aplicado **antes da primeira pintura** — sem piscada de tema errado
- [ ] Script inline liberado por **hash** na CSP, nunca por `nonce`
- [ ] Sem JavaScript a página continua correta, seguindo `prefers-color-scheme`
- [ ] Controle acessível: grupo rotulado, estado anunciado, alvo de toque ≥ 44 px
- [ ] `localStorage` indisponível (modo privado) não quebra a página
- [ ] Teste verificando que o HTML servido **não varia** com o tema

#### Como implementar

Script inline mínimo, antes da folha de estilo, para o tema valer já na primeira pintura:

```html
<script>
(function(){var t;try{t=localStorage.getItem("bd-tema")}catch(e){}
if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)})();
</script>
```

Precisa ser inline e síncrono: um arquivo externo chega depois da primeira pintura e produz a piscada. Calcule o hash SHA-256 desse conteúdo e registre em `CSP_SCRIPT_HASHES` (BD-003).

O controle é um grupo de três botões com `aria-pressed`, não um interruptor de dois estados — "sistema" precisa ser alcançável.

Sem JavaScript, nada é estampado e o `@media (prefers-color-scheme)` assume. É o comportamento correto, não uma degradação.

#### Pontos de partida

- `templates/base.html` — o `<head>`, antes do `<link>` do CSS
- `apps/core/middleware.py` (de BD-003) — onde o hash é declarado
- `config/settings/base.py` — `CACHES`, para entender o cache que não pode variar

#### Método de teste

- o HTML da mesma página é **byte a byte igual** com e sem preferência de tema — é o teste que protege o cache
- o hash configurado bate com o script servido
- sem cookie e sem `localStorage`, a página responde 200 e não estampa atributo

---

#### Cuidados

> **O HTML tem de ser neutro em relação ao tema.** Decidir no servidor triplica o cache de página da §8. As cores vêm de custom properties; só o atributo na raiz muda, e quem escreve é o cliente.

---

### BD-006 — Componentes base

| | |
|---|---|
| Fase | 2.0 |
| Tamanho | M |
| Depende de | BD-004 |
| Rótulos | `fase-2` `área:interface` |

#### Objetivo

Toda tela da Fase 2 nasce do mesmo conjunto de componentes, e ação destrutiva se distingue da primária sem depender de cor.

#### Contexto

O vocabulário visual que todas as telas da Fase 2 vão usar. Escopo fechado de propósito — não invente componente que ninguém pediu.

#### Critérios de aceite

- [ ] Botão: primário (preenchido), secundário (contorno), **destrutivo** e desabilitado
- [ ] Etiqueta de estado, campo de formulário com erro e ajuda, linha de listagem, aviso (informação, sucesso, atenção, perigo)
- [ ] Foco visível em tudo que recebe teclado
- [ ] Alvos de toque ≥ 44 × 44 px
- [ ] `prefers-reduced-motion` respeitado
- [ ] Todos verificados nos dois temas

#### Como implementar

Componentes como parciais de template mais classes CSS, sem biblioteca. Escopo fechado:

| Componente | Estados |
|---|---|
| Botão | primário, secundário, destrutivo, desabilitado |
| Etiqueta | neutra, sucesso, atenção, perigo |
| Campo | normal, com erro, com texto de ajuda, desabilitado |
| Linha de listagem | normal, visitada, destacada |
| Aviso | informação, sucesso, atenção, perigo |

O botão destrutivo **não** é o primário com outra cor:

```html
<button class="botao botao--destrutivo">
  <svg aria-hidden="true">…</svg> Apagar
</button>
```

Contorno mais ícone, nunca preenchimento sólido. Vermelho de marca e de perigo têm razão de luminância de 1.04:1 — quem tem protanopia vê dois botões idênticos, e a forma é o que resta.

Foco visível em tudo que recebe teclado; `:focus-visible`, não `:focus`, para não marcar clique de rato.

#### Pontos de partida

- `docs/DESIGN.md` §3 e §7 — regra da forma e critérios de usabilidade
- `templates/forum/topic.html` — o formulário de resposta, primeiro consumidor
- `static/css/forum.css` — estilos provisórios a substituir

#### Método de teste

Manual, contra a página de referência da BD-007. Verificar navegação por teclado em toda a página e alvos de toque de 44 px no telemóvel.

---

#### Cuidados

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

#### Objetivo

Existe uma página onde os dois temas e todos os componentes aparecem juntos, de modo que regressão visual seja vista antes de chegar ao usuário.

#### Contexto

Uma página mostrando todos os tokens e componentes nos dois temas. É o que impede a deriva: sem um lugar onde os dois temas aparecem lado a lado, o tema escuro quebra e ninguém percebe até um usuário reclamar.

#### Critérios de aceite

- [ ] Rota acessível só em `DEBUG`, ou restrita a moderação
- [ ] Rampa completa com os contrastes anotados
- [ ] Todos os componentes de BD-006, em todos os estados
- [ ] Amostra de tipografia com português acentuado, Pāli (`anattā`, `saṅgha`), devanágari, tibetano e CJK
- [ ] Alternador de tema na própria página

#### Como implementar

Uma view simples e um template longo. A rota só existe em `DEBUG`, ou exige moderação:

```python
# apps/core/views.py
def referencia(request):
    if not settings.DEBUG and not is_moderator(request.user):
        raise Http404
    return render(request, "referencia.html")
```

A amostra tipográfica precisa exercitar a cobertura real de fonte do projeto:

> português com acentuação — ação, coração, também
> Pāli — anattā, saṅgha, Saṃyutta Nikāya, dukkha
> devanágari — अनात्मन्, धर्म
> tibetano — བདག་མེད་, ཆོས་
> chinês — 無我, 法

Se algum desses sair como retângulo vazio, a fonte escolhida não serve — e é melhor descobrir aqui do que num post de usuário.

#### Pontos de partida

- `apps/core/views.py` — hoje não existe; criar
- `config/urls.py` — onde a rota entra
- `apps/core/permissions.py` — `is_moderator`

#### Método de teste

- a rota responde 404 fora de `DEBUG` para quem não modera
- responde 200 em `DEBUG`

---

---

### BD-008 — `Category.color`: de hex livre para tokens

| | |
|---|---|
| Fase | 2.0 |
| Tamanho | M |
| Depende de | BD-004 |
| Rótulos | `fase-2` `área:interface` `área:moderação` |

#### Objetivo

Cor de categoria é legível nos dois temas, e moderação não consegue escolher uma combinação ilegível.

#### Contexto

Hoje é texto livre com padrão `#8B6F47` — que nem pertence à paleta nova. Quem modera pode escolher uma cor ilegível sem perceber, e um hex fixo não pode servir aos dois temas.

#### Critérios de aceite

- [ ] Conjunto curado de tokens de categoria, verificados nos dois temas
- [ ] Campo guarda o **nome do token**, não o hex
- [ ] Admin oferece escolha entre os tokens, não campo livre
- [ ] Migração de dados mapeia os valores existentes para o token mais próximo
- [ ] Categoria continua distinguível sem depender de cor — ícone ou rótulo

#### Como implementar

Expand/contract, em três releases — nunca tudo numa migração:

1. **Expandir** — adicionar `color_token` com escolhas, mantendo `color` intacto
2. **Migrar** — `RunPython` mapeando cada hex para o token de menor distância; use distância em espaço perceptual (Lab), não Euclidiana em RGB, que erra feio com cores quentes
3. **Contrair** — numa release posterior, remover `color`

```python
class CorCategoria(models.TextChoices):
    ACAFRAO = "acafrao", _("Açafrão")
    AMBAR = "ambar", _("Âmbar")
    # ... 6 a 8 opções, verificadas nos dois temas
```

O template resolve o token para custom property, e não para hex: `class="cat--{{ category.color_token }}"`. É o que permite a mesma categoria ser legível nos dois temas.

#### Pontos de partida

- `apps/forum/models.py` — `Category.color`, hoje `CharField` com padrão `#8B6F47`
- `apps/forum/admin.py` — `CategoryAdmin`
- `templates/forum/index.html` — usa `style="border-left-color: {{ category.color }}"`, que precisa virar classe

#### Método de teste

- a migração de dados mapeia os hex existentes sem deixar nulo
- cada token tem contraste suficiente nos dois temas
- categoria continua identificável sem cor — ícone ou texto

---

#### Cuidados

Mudança de schema: precisa ser retrocompatível. Use expand/contract — adiciona a coluna nova, migra os dados, troca o código, remove a antiga numa release posterior. Nunca as duas coisas na mesma migração.

---

## Fase 2.1 — Reações

### BD-009 — Caminho de escrita das reações

| | |
|---|---|
| Fase | 2.1 |
| Tamanho | M |
| Depende de | BD-006 |
| Rótulos | `fase-2` `área:interface` |

#### Objetivo

Quem lê um post consegue reagir a ele.

#### Contexto

Modelos, trigger de contagem e exibição estão prontos e testados; **não existe forma de reagir**. Primeira vez que o HTMX entra no projeto — o padrão criado aqui será copiado pelo resto da fase, então vale caprichar.

#### Critérios de aceite

- [ ] Alternar reação: clicar adiciona, clicar de novo remove
- [ ] Resposta devolve só o fragmento das reações daquele post
- [ ] Contagem lida de `ReactionCount`, nunca de `COUNT(*)`
- [ ] Estado "eu reagi" visível, e não apenas pela cor
- [ ] Exige autenticação; anônimo vê as contagens e é convidado a entrar
- [ ] Rate limit por usuário
- [ ] Reagir duas vezes em corrida não estoura erro 500 — o `UNIQUE` é tratado
- [ ] Funciona sem JavaScript, via formulário comum
- [ ] Testes: alternar incrementa e decrementa; contagem materializada bate; anônimo é barrado

#### Como implementar

Uma view que alterna e devolve só o fragmento das reações:

```python
@login_required
@require_POST
def reaction_toggle(request, pk, emoji_id):
    post = get_object_or_404(Post, pk=pk)
    reacao = Reaction.objects.filter(post=post, user=request.user, emoji_id=emoji_id).first()
    if reacao:
        reacao.delete()
    else:
        try:
            Reaction.objects.create(post=post, user=request.user, emoji_id=emoji_id)
        except IntegrityError:
            pass  # corrida: outra requisição chegou primeiro, e tudo bem
    return render(request, "forum/_reacoes.html", {"post": post})
```

O `try/except IntegrityError` não é zelo excessivo: dois cliques rápidos disparam duas requisições, e o `UNIQUE` é justamente o que impede a duplicata. Sem isso, o segundo clique vira erro 500.

Nunca some nem subtraia contagem em Python — o trigger da migração `0002` cuida disso, e mexer aqui contaria duas vezes.

No template, com HTMX:

```html
<button hx-post="{% url 'forum:reaction_toggle' post.pk emoji.pk %}"
        hx-target="#reacoes-{{ post.pk }}" hx-swap="outerHTML"
        aria-pressed="{{ eu_reagi|yesno:'true,false' }}">
```

O token CSRF precisa ir junto; configure `hx-headers` uma vez no `<body>`.

Sem JavaScript o mesmo endpoint responde a um `<form method="post">` comum, redirecionando de volta ao post.

#### Pontos de partida

- `apps/forum/models.py` — `Reaction`, `ReactionCount`, `Emoji`
- `apps/forum/migrations/0002_extensoes_e_triggers.py` — o trigger que mantém a contagem
- `templates/forum/topic.html` — o bloco `.reacoes`, hoje só exibição
- `apps/forum/views.py` — `post_create` como modelo de view de escrita

#### Método de teste

Em `apps/forum/tests/test_views.py`:

- alternar duas vezes volta ao estado inicial, e `ReactionCount` acompanha
- reagir duas vezes em sequência não gera 500
- anônimo recebe redirecionamento e nenhuma reação é criada
- a página do tópico continua sem N+1 com vários emojis

---

#### Cuidados

O trigger cuida da contagem — não some nem subtraia no Python, sob risco de contar duas vezes. HTMX precisa do token CSRF em toda requisição de escrita.

---

### BD-010 — Seletor de emoji

| | |
|---|---|
| Fase | 2.1 |
| Tamanho | P |
| Depende de | BD-009 |
| Rótulos | `fase-2` `área:interface` |

#### Objetivo

Reagir permite escolher entre os emojis ativos, também pelo teclado.

#### Contexto

Depois da BD-009 dá para reagir, mas com um emoji fixo. A tabela `Emoji` já existe, é editável pelo admin sem deploy e tem ordenação própria — falta a interface que expõe as opções.

#### Critérios de aceite

- [ ] Lista os emojis ativos, na ordem de `position`
- [ ] Navegável por teclado; fecha com `Esc`; foco volta ao botão de origem
- [ ] Lista vem do cache de aplicação, não do banco a cada abertura
- [ ] Cada emoji tem rótulo textual acessível
- [ ] Alvos ≥ 44 px

#### Como implementar

Lista de emojis ativos, ordenada por `position`, vinda do cache de aplicação:

```python
def emojis_ativos():
    emojis = cache.get("emojis_ativos")
    if emojis is None:
        emojis = list(Emoji.objects.filter(is_active=True).order_by("position"))
        cache.set("emojis_ativos", emojis, 3600)
    return emojis
```

Invalidar em `post_save`/`post_delete` de `Emoji`, senão adicionar um emoji pelo admin leva até uma hora para aparecer.

Acessibilidade é o ponto delicado: `role="menu"`, foco preso enquanto aberto, `Esc` fecha e devolve o foco ao botão de origem. Cada emoji precisa de nome textual — o `shortcode` serve.

#### Pontos de partida

- `apps/forum/models.py` — `Emoji`, já ordenado por `position`
- `config/settings/base.py` — `CACHES`, Redis com `IGNORE_EXCEPTIONS`
- `templates/forum/topic.html`

#### Método de teste

- só emojis com `is_active` aparecem, na ordem de `position`
- salvar um `Emoji` invalida o cache

---

---

### BD-011 — Quem reagiu

| | |
|---|---|
| Fase | 2.1 |
| Tamanho | P |
| Depende de | BD-009 |
| Rótulos | `fase-2` `área:interface` |

#### Objetivo

Dá para ver quem reagiu a um post, sem custo para quem só está lendo o tópico.

#### Contexto

A contagem diz quantos reagiram, não quem. Num fórum, saber quem concordou é parte da conversa — e é informação que já está na tabela `Reaction`, sem precisar de estrutura nova.

#### Critérios de aceite

- [ ] Ver quem reagiu, agrupado por emoji
- [ ] Carregado sob demanda, não junto da página
- [ ] Limite com "ver mais" para posts muito reagidos
- [ ] Sem N+1 — teste de contagem de queries

#### Como implementar

Endpoint separado, carregado sob demanda — a página do tópico não deve pagar por isto:

```python
def reaction_users(request, pk, emoji_id):
    reacoes = (Reaction.objects
               .filter(post_id=pk, emoji_id=emoji_id)
               .select_related("user")
               .order_by("-created_at")[:50])
```

`select_related("user")` não é opcional: sem ele são cinquenta consultas.

Exibir `display_name`, com link para o perfil por `username`.

#### Pontos de partida

- `apps/forum/models.py` — `Reaction`
- `templates/forum/topic.html` — as etiquetas de contagem viram gatilho

#### Método de teste

- agrupa corretamente por emoji
- teste de contagem de consultas: número fixo, independente de quantas reações existem

---

---

## Fase 2.2 — Busca

### BD-012 — View e página de resultados

| | |
|---|---|
| Fase | 2.2 |
| Tamanho | M |
| Depende de | BD-006 |
| Rótulos | `fase-2` `área:busca` |

#### Objetivo

O motor de busca, já pronto e medido, fica alcançável pela interface.

#### Contexto

O motor está pronto e medido em `apps/forum/search.py`, com 9 testes em `apps/forum/tests/test_models.py`. Falta a interface.

#### Critérios de aceite

- [ ] Rota de busca com o termo na query string, para o resultado ser compartilhável
- [ ] Usa `search_posts()` — **não** monta `SearchQuery` à mão
- [ ] Resultado mostra tópico, autor, data e trecho
- [ ] Busca vazia mostra estado inicial útil, não lista vazia
- [ ] Sem resultado, oferece o recuo por trigrama (`fuzzy_fallback=True`) e diz que os resultados são aproximados
- [ ] Paginação por keyset
- [ ] Entrada com sintaxe quebrada (`&&&`, parêntese solto) não gera erro
- [ ] Sem N+1

#### Como implementar

A lógica de consulta já está pronta e medida. A view chama e pagina:

```python
def search(request):
    termo = request.GET.get("q", "").strip()
    resultados = search_posts(termo, limit=settings.FORUM_POSTS_PER_PAGE + 1)
    aproximado = False
    if termo and not resultados:
        resultados = fuzzy_posts(termo, limit=settings.FORUM_POSTS_PER_PAGE)
        aproximado = bool(resultados)
```

O sinalizador `aproximado` importa para a interface: resultado de trigrama não tem noção de relevância, e o usuário precisa saber que está vendo aproximação.

Termo vazio mostra estado inicial — categorias mais ativas, discussões recentes — e não uma lista vazia.

#### Pontos de partida

- `apps/forum/search.py` — `search_posts`, `fuzzy_posts`, `build_query`
- `apps/forum/tests/test_models.py::TestBusca` — nove testes que fixam o comportamento
- `apps/forum/views.py` — `category` como modelo de paginação por keyset

#### Método de teste

Em `apps/forum/tests/test_views.py`:

- `?q=meditação` encontra post com `meditações` — o stemmer funcionando
- `?q=meditacao` encontra `meditação` — o acento ignorado
- `?q=anatta` encontra `anattā`
- entrada com sintaxe quebrada (`&&&`, `( solto`) responde 200
- busca sem resultado oferece o recuo e sinaliza que é aproximado

---

#### Cuidados

> **Consultar só uma das duas configurações perde metade dos resultados, em silêncio.** `search_posts()` já cuida disso. A tentação de "simplificar" a consulta é exatamente o que a migração `0003` documenta ter falhado.

---

### BD-013 — Caixa de busca no cabeçalho

| | |
|---|---|
| Fase | 2.2 |
| Tamanho | P |
| Depende de | BD-012 |
| Rótulos | `fase-2` `área:busca` `bom-primeiro-passo` |

#### Objetivo

Buscar está a um campo de distância em qualquer página, com ou sem JavaScript.

#### Contexto

A busca da BD-012 só é alcançável digitando a URL. Sem campo no cabeçalho, o recurso existe e ninguém usa.

#### Critérios de aceite

- [ ] Presente em todas as páginas, `<form>` comum com `GET`
- [ ] Funciona sem JavaScript
- [ ] Rotulada para leitor de tela
- [ ] Não empurra o conteúdo no telemóvel

#### Como implementar

Formulário `GET` no cabeçalho, sem JavaScript:

```html
<form class="busca" action="{% url 'forum:search' %}" method="get" role="search">
  <label for="busca-q" class="oculto-visualmente">{% translate "Buscar no fórum" %}</label>
  <input type="search" id="busca-q" name="q" value="{{ request.GET.q|default:'' }}"
         placeholder="{% translate 'Buscar…' %}">
</form>
```

`role="search"` e rótulo associado — `placeholder` não é rótulo e desaparece ao digitar, deixando quem usa leitor de tela sem contexto.

O `value` preenchido faz o termo persistir na página de resultados, que é o que se espera ao refinar uma busca.

No telemóvel, o campo não pode empurrar a navegação; considere recolher para um ícone que expande.

#### Pontos de partida

- `templates/base.html` — o `<header class="topo">`
- `static/css/forum.css` — precisa de uma classe `.oculto-visualmente` acessível (não `display:none`, que esconde do leitor de tela)

#### Método de teste

- a caixa aparece em índice, categoria e tópico
- enviar leva à rota de busca com o termo na query string

---

---

### BD-014 — Destaque do trecho

| | |
|---|---|
| Fase | 2.2 |
| Tamanho | M |
| Depende de | BD-012 |
| Rótulos | `fase-2` `área:busca` |

#### Objetivo

O resultado de busca mostra onde o termo aparece, não apenas que aparece.

#### Contexto

Lista de resultados sem trecho obriga a abrir cada post para saber se serve. O PostgreSQL gera o trecho destacado, e é ele que transforma a lista em algo utilizável.

#### Critérios de aceite

- [ ] Trecho ao redor do termo, com o termo destacado
- [ ] Destaque gerado no PostgreSQL (`ts_headline`), com as **duas** configurações de busca
- [ ] Saída escapada — o trecho vem do Markdown cru e não pode virar HTML
- [ ] Destaque não depende só de cor
- [ ] Texto sem correspondência exata (recuo por trigrama) degrada sem quebrar

#### Como implementar

`ts_headline` no PostgreSQL, com as **duas** configurações — usar só uma perde o destaque em metade dos casos:

```sql
ts_headline('portuguese', body_md, websearch_to_tsquery('portuguese', %s),
            'StartSel=<mark>, StopSel=</mark>, MaxFragments=2, FragmentDelimiter= … ')
```

O destaque roda **só sobre os resultados da página atual**, nunca sobre o conjunto todo — `ts_headline` lê o texto inteiro de cada linha e é caro.

Segurança: a entrada é `body_md`, texto cru de usuário. Escape o resultado e reintroduza apenas `<mark>`, ou passe pelo `nh3` com allowlist de uma tag só. Marcar como seguro o que veio do banco sem tratar é como se cria XSS.

`<mark>` já tem semântica própria — o destaque não fica dependendo só de cor.

#### Pontos de partida

- `apps/forum/search.py`
- `apps/core/markdown.py` — `nh3_clean` e a allowlist, como referência de sanitização

#### Método de teste

- o termo aparece envolto em `<mark>` no trecho
- `<script>` no corpo do post não sobrevive ao trecho destacado
- resultado vindo do trigrama, sem correspondência exata, não quebra

---

#### Cuidados

`ts_headline` é caro; aplique só aos resultados da página atual, nunca ao conjunto inteiro.

---

### BD-015 — Filtros por categoria e autor

| | |
|---|---|
| Fase | 2.2 |
| Tamanho | P |
| Depende de | BD-012 |
| Rótulos | `fase-2` `área:busca` |

#### Objetivo

Dá para estreitar uma busca por categoria e autor, e compartilhar o resultado filtrado por URL.

#### Contexto

Busca por termo comum num fórum maduro devolve resultado demais. Filtrar por categoria e autor é o que separa “encontrei” de “encontrei o que eu procurava”.

#### Critérios de aceite

- [ ] Filtrar por categoria e por autor, combináveis com o termo
- [ ] Filtros refletidos na URL
- [ ] Filtro ativo visível e removível
- [ ] Consulta continua usando os índices — verificar com `EXPLAIN`

#### Como implementar

Filtros aplicados sobre o queryset já filtrado por texto, com os valores refletidos na URL para o resultado ser compartilhável:

```python
if categoria := request.GET.get("categoria"):
    resultados = resultados.filter(topic__category__slug=categoria)
if autor := request.GET.get("autor"):
    resultados = resultados.filter(author__username=autor)
```

Filtrar por `slug` e `username`, não por id — a URL fica legível e não expõe contagem de registros.

Confirme com `EXPLAIN` que o índice GIN continua sendo usado depois dos filtros; um `JOIN` mal posicionado pode levar o planejador a varrer tudo.

#### Pontos de partida

- `apps/forum/search.py`
- `apps/forum/views.py`

#### Método de teste

- filtro por categoria restringe corretamente
- filtro combinado com termo devolve a interseção
- filtro com valor inexistente devolve vazio, sem erro

---

---

## Fase 2.3 — Edição com histórico

### BD-016 — Editar post gravando revisão

| | |
|---|---|
| Fase | 2.3 |
| Tamanho | M |
| Depende de | BD-006 |
| Rótulos | `fase-2` `área:moderação` |

#### Objetivo

Post pode ser corrigido, e nenhuma edição apaga o que foi dito antes.

#### Contexto

`PostRevision` existe e nunca é gravado. A [§4.4](ARQUITETURA.md#44-revisões) trata transparência de edição como requisito: num fórum de tema doutrinário, editar em silêncio uma citação de sutta não pode ser possível.

#### Critérios de aceite

- [ ] Autor edita o próprio post; moderação edita qualquer um
- [ ] Cada edição grava `PostRevision` com o texto **anterior**, dentro da mesma transação
- [ ] `edited_at` e `edit_count` atualizados
- [ ] `body_html` regenerado e sanitizado
- [ ] Vetor de busca atualizado — o trigger cuida, mas confirme com teste
- [ ] Motivo da edição, opcional
- [ ] Marca "editado" visível no post
- [ ] Teste: editar duas vezes gera duas revisões, e a primeira guarda o texto original

#### Como implementar

A gravação da revisão e a atualização do post têm de ser atômicas:

```python
@transaction.atomic
def edit(self, editor, novo_md, motivo=""):
    PostRevision.objects.create(
        post=self, editor=editor, body_md=self.body_md, edit_reason=motivo
    )
    self.body_md = novo_md
    self.html_version = 0          # força re-renderização em save()
    self.edited_at = timezone.now()
    self.edit_count = F("edit_count") + 1
    self.save()
```

A revisão guarda o texto **anterior**, não o novo — é isso que permite reconstruir o que foi dito antes.

Zerar `html_version` faz `save()` re-renderizar e re-sanitizar, aproveitando o mecanismo que já existe.

Autorização: autor edita o próprio post, moderação edita qualquer um. Use `is_moderator()` de `apps/core/permissions.py`; nunca compare `display_name`.

O trigger de busca dispara em `UPDATE OF body_md` — atualizar por `save()` cobre. Se algum caminho novo alterar a coluna por fora, confirme com teste que o vetor acompanhou.

#### Pontos de partida

- `apps/forum/models.py` — `PostRevision`, `Post.render()`, `Post.needs_render`
- `apps/forum/migrations/0003_busca_acento_e_radical.py` — o trigger e sua condição de disparo
- `apps/forum/forms.py` — `MarkdownBodyMixin`, reaproveitável no formulário de edição
- `apps/core/permissions.py`

#### Método de teste

- editar duas vezes gera duas revisões, e a primeira guarda o texto original
- `edited_at` e `edit_count` acompanham
- o HTML é re-renderizado e re-sanitizado
- o vetor de busca reflete o texto novo
- quem não é autor nem moderador recebe 403 ou 404
- falha ao gravar a revisão impede a edição — transação de verdade

---

#### Cuidados

Gravar a revisão e atualizar o post têm de ser atômicos — se a revisão falhar, a edição não pode passar. O trigger de busca dispara em `UPDATE OF body_md`; se alterar a coluna por caminho diferente, confirme que ainda dispara.

---

### BD-017 — Histórico de revisões visível

| | |
|---|---|
| Fase | 2.3 |
| Tamanho | M |
| Depende de | BD-016 |
| Rótulos | `fase-2` `área:moderação` `precisa-decisão` |

#### Objetivo

O que mudou entre versões de um post fica visível para quem tem direito de ver.

#### Contexto

A BD-016 passa a gravar as revisões, mas nada as exibe. Registro que ninguém consegue ler não cumpre o requisito de transparência da §4.4 da arquitetura.

#### Critérios de aceite

- [ ] Ver as revisões de um post, com autor e data
- [ ] Diferença entre versões, legível
- [ ] Diferença renderizada com escape — texto de usuário nunca vira HTML
- [ ] Quem pode ver: definir na issue (público, ou só moderação) — **precisa de decisão**
- [ ] Post removido não expõe conteúdo pelo histórico

#### Como implementar

Listar as revisões e mostrar a diferença entre versões consecutivas. `difflib` da biblioteca padrão basta — não vale dependência nova:

```python
import difflib
diff = difflib.unified_diff(
    anterior.body_md.splitlines(), atual.body_md.splitlines(), lineterm=""
)
```

Compare o **Markdown**, não o HTML: o Markdown é a fonte de verdade e produz diferença legível; o HTML produz ruído de tags.

Segurança: cada linha da diferença é texto de usuário. Escape tudo e aplique estilo por classe CSS, nunca inserindo HTML vindo do conteúdo. Post removido não pode expor texto pelo histórico — filtre por `deleted_at`.

#### Pontos de partida

- `apps/forum/models.py` — `PostRevision`, já ordenado por `-created_at`
- `apps/core/permissions.py` — `is_moderator`

#### Método de teste

- as revisões aparecem em ordem, com autor e data
- a diferença renderizada escapa HTML do conteúdo
- histórico de post removido não vaza texto
- a regra de acesso escolhida é respeitada

---

#### Cuidados

Marcar com `precisa-decisão`: histórico público é mais transparente, mas expõe texto que alguém apagou por vergonha ou por engano. Decidir antes de implementar.

---

## Fase 2.4 — Vínculos entre posts

### BD-018 — Gravar `PostLink` ao salvar

| | |
|---|---|
| Fase | 2.4 |
| Tamanho | M |
| Depende de | — |
| Rótulos | `fase-2` `bom-primeiro-passo` |

#### Objetivo

Citar um post passa a criar um vínculo consultável entre os dois.

#### Contexto

`extract_internal_links()` está implementada e testada em `apps/core/markdown.py`, e **nunca é chamada**. A tabela `PostLink` existe, com índice por alvo. Falta ligar as duas pontas.

Livre agora — não depende do sistema de design.

#### Critérios de aceite

- [ ] Ao criar ou editar post, os links internos viram linhas em `PostLink`
- [ ] Resolver o caminho para um `Post` de verdade — ver o cuidado abaixo
- [ ] Link para tópico sem número de post aponta para o post 1
- [ ] Link que não resolve é ignorado em silêncio, sem erro
- [ ] Editar um post recalcula os vínculos: some o que saiu, entra o que foi acrescentado
- [ ] Post apagado não deixa vínculo pendurado
- [ ] Sem duplicata — o `UNIQUE` é respeitado, reeditar não estoura
- [ ] Testes: link resolve; link quebrado é ignorado; edição recalcula

#### Como implementar

O caminho vem com fragmento, e é aí que a tarefa engana. `Post.get_absolute_url()` devolve `/t/<pk>/<slug>/#post-<position>`, e `extract_internal_links()` entrega a string inteira:

```python
from urllib.parse import urlparse
import re

def resolver(caminhos: list[str]) -> list[int]:
    alvos = []
    for bruto in caminhos:
        partes = urlparse(bruto)
        m = re.match(r"^/t/(\d+)/", partes.path)
        if not m:
            continue
        posicao = int(partes.fragment[5:]) if partes.fragment.startswith("post-") else 1
        alvos.append((int(m.group(1)), posicao))
    # uma consulta só, nunca uma por link
    return Post.objects.filter(
        reduce(or_, (Q(topic_id=t, position=p) for t, p in alvos))
    ).values_list("id", flat=True)
```

Link para tópico sem fragmento aponta para o post 1.

Ao editar, recalcule o conjunto: apague os vínculos que saíram e crie os que entraram. Reeditar sem mudar links não pode estourar o `UNIQUE` — use `get_or_create` ou `ignore_conflicts=True`.

Link que não resolve é ignorado em silêncio. Post apagado, post inexistente e URL de outro site são todos casos normais, não erro.

#### Pontos de partida

- `apps/core/markdown.py` — `extract_internal_links()`, testada e nunca chamada
- `apps/forum/models.py` — `PostLink`, `LinkType`, `Post.create_in_topic`
- `apps/core/tests/test_markdown.py::TestVinculosInternos` — o que a extração já garante

#### Método de teste

- link para post específico resolve para o post certo
- link para tópico sem fragmento resolve para o post 1
- link para post inexistente é ignorado, sem erro
- editar removendo um link apaga o vínculo
- reeditar sem mudança não duplica nem estoura
- teste de contagem de consultas: resolver dez links não faz dez consultas

---

#### Cuidados

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

#### Objetivo

Ao ler um post, dá para ver quais posts posteriores o citaram.

#### Contexto

O recurso que fóruns bons têm e os ruins não: ao ler um post, ver quais posts posteriores o citaram. Num fórum sobre Budismo, permite rastrear ao longo de anos as discussões que referenciam a mesma passagem.

#### Critérios de aceite

- [ ] Post mostra quem o citou, usando o índice por alvo
- [ ] Post removido não aparece como citação
- [ ] Lista limitada, com "ver mais"
- [ ] Sem N+1
- [ ] Post sem citação não mostra seção vazia

#### Como implementar

O índice `postlink_alvo_idx` existe justamente para isto:

```python
citacoes = (PostLink.objects
            .filter(target_post=post, source_post__deleted_at__isnull=True)
            .select_related("source_post", "source_post__author", "source_post__topic")
            .order_by("source_post__created_at")[:5])
```

`select_related` completo — sem ele, cada citação vira três consultas.

Filtrar `source_post__deleted_at__isnull=True` na consulta, e não no template: um post removido não pode aparecer como citação, e filtrar em Python já teria trazido as linhas.

Post sem citação não mostra seção vazia.

#### Pontos de partida

- `apps/forum/models.py` — `PostLink`, `indexes` com `postlink_alvo_idx`
- `templates/forum/topic.html`
- `apps/forum/views.py` — a view `topic`, onde o `Prefetch` das reações mostra o padrão

#### Método de teste

- post citado mostra quem o citou
- citação vinda de post removido não aparece
- teste de contagem de consultas na página do tópico

---

---

### BD-020 — Botão de citar

| | |
|---|---|
| Fase | 2.4 |
| Tamanho | P |
| Depende de | BD-006, BD-018 |
| Rótulos | `fase-2` `área:interface` |

#### Objetivo

Citar um post é um clique, e a citação já registra o vínculo sozinha.

#### Contexto

Citar hoje é manual: copiar, colar e prefixar cada linha com `>`. Quase ninguém faz. Sem botão, o grafo de vínculos da BD-018 fica vazio na prática.

#### Critérios de aceite

- [ ] Citar um post insere a citação em Markdown no campo de resposta
- [ ] Citar uma seleção usa só o trecho selecionado
- [ ] A citação inclui link para o post de origem, o que alimenta o `PostLink`
- [ ] Atribuição visível na citação renderizada
- [ ] Sem JavaScript, o botão leva ao campo de resposta com a citação já preenchida

#### Como implementar

Sem JavaScript, o botão é um link que leva ao formulário de resposta com a citação já preenchida:

```html
<a href="{% url 'forum:post_create_form' topic.pk %}?citar={{ post.position }}">Citar</a>
```

A view monta o Markdown:

```python
def citacao_markdown(post):
    corpo = "\n".join(f"> {linha}" for linha in post.body_md.splitlines())
    return f"[@{post.author.username} disse]({post.get_absolute_url()}):\n{corpo}\n\n"
```

O link interno na atribuição é o que alimenta o `PostLink` da BD-018 — a citação se registra sozinha no grafo.

Com JavaScript, o mesmo botão insere no `<textarea>` sem recarregar, e citar uma seleção usa `window.getSelection()` em vez do post inteiro.

Cuidado com citação aninhada: citar um post que já cita outro empilha `>` indefinidamente. Limite a um nível ao gerar.

#### Pontos de partida

- `apps/forum/models.py` — `Post.get_absolute_url()`
- `templates/forum/topic.html`
- `apps/forum/forms.py` — `PostForm`

#### Método de teste

- a citação gerada preserva o texto e inclui link para a origem
- o post resultante gera o `PostLink` correspondente
- citar post com múltiplas linhas prefixa todas

---

---

## Ainda não prontas

Precisam de decisão antes de virar tarefa.

**2.5 — Editor de Markdown.** Depende de BD-004 e BD-006, e da escolha do editor. EasyMDE é o candidato do roadmap, mas vale confirmar manutenção e tamanho antes de assumir a dependência.

**2.6 — Anexos.** O maior item da fase: traz Garage e armazenamento de objetos. Antes de abrir tarefa é preciso decidir limites por nível de confiança, política de retenção e o que fazer com anexo de post apagado.

**Fase 3 em diante.** Só depois que a Fase 2 fechar. Abrir agora produz issue que envelhece.
