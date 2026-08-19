# Design — Buddhadharma

Direção visual e critérios de interface. **Planejamento** — nenhuma decisão daqui está implementada ainda.

Complementa [ARQUITETURA.md](ARQUITETURA.md) (decisões técnicas) e [ROADMAP.md](ROADMAP.md) (estado e sequência).

---

## 1. Direção

Paleta quente: **amarelo, laranja e vermelho**, com tema claro e escuro alternáveis pelo usuário. Interface moderna, com alta usabilidade.

A origem da paleta não é decorativa. Têxteis monásticos budistas percorrem exatamente essa faixa — o ocre e o açafrão da tradição Theravāda, o vermelho profundo das escolas tibetanas. Isso dá à rampa uma progressão com significado próprio, em vez de "cores quentes porque são acolhedoras".

Duas coisas que essa escolha cobra, e que este documento resolve antes de virar código:

1. **Amarelo tem contraste péssimo sobre fundo claro.** Não é opinião, é medida — os números estão abaixo.
2. **Vermelho é a cor da marca e também a cor de perigo.** Num fórum, "Publicar" e "Apagar" não podem parecer a mesma coisa.

---

## 2. A rampa

Nove passos, do açafrão ao vermelho profundo.

| Passo | Hex | Sobre claro `#FAF9F7` | Sobre escuro `#17120E` |
|---|---|---|---|
| 100 | `#FDF3E0` | 1.05:1 ✗ | 16.89:1 ✓ AAA |
| 200 | `#FAE3B8` | 1.19:1 ✗ | 14.83:1 ✓ AAA |
| 300 | `#F5C766` | 1.51:1 ✗ | 11.73:1 ✓ AAA |
| 400 | `#EFA92B` | 1.92:1 ✗ | 9.19:1 ✓ AAA |
| 500 | `#DC7726` | 2.97:1 ✗ | 5.94:1 ✓ AA |
| 600 | `#C4521F` | 4.36:1 ⚠ só grande/UI | 4.05:1 ⚠ só grande/UI |
| 700 | `#A6321E` | 6.45:1 ✓ AA | 2.74:1 ✗ |
| 800 | `#7E2418` | 9.27:1 ✓ AAA | 1.91:1 ✗ |
| 900 | `#5A1B15` | 12.46:1 ✓ AAA | 1.42:1 ✗ |

Contrastes calculados pela fórmula da WCAG 2.2. Limiares: **4.5:1** para texto corrido, **3:1** para texto grande e componentes de interface.

### O que a tabela decide

**O mesmo hex não serve os dois temas.** A rampa se inverte: no tema claro só o extremo escuro (600–900) é legível; no tema escuro, só o extremo claro (100–500). Qualquer cor precisa ser referenciada por *token semântico*, nunca pelo passo da rampa, para que o tema troque o valor por baixo.

**Amarelo nunca é tinta.** O passo 400 dá 1.92:1 sobre fundo claro — reprova até como borda. Mas como **preenchimento com rótulo escuro** ele é excelente: `#1C1714` sobre `#EFA92B` dá **8.78:1**. O papel do amarelo é superfície, não texto.

**Laranja 500 engana.** Dá 2.97:1 sobre fundo claro — falha o limiar de 3:1 por três centésimos. Não serve como ícone nem borda no tema claro. E branco sobre laranja 500 dá só 3.13:1, insuficiente para rótulo de botão. Botão sólido no tema claro usa 600 ou mais escuro com texto branco (`#FFFFFF` sobre 600 = 4.59:1), ou 400/500 com texto escuro.

---

## 3. Semânticas e a colisão do vermelho

Estados de sistema precisam de cores próprias. Verde e azul ficam fora da família quente de propósito — dão o alívio cromático que uma paleta só quente não tem, e não competem com a marca.

| Papel | Claro | Sobre claro | Escuro | Sobre escuro |
|---|---|---|---|---|
| Perigo | `#B3261E` | 6.21:1 ✓ | `#F2766B` | 6.71:1 ✓ |
| Sucesso | `#2F6B4F` | 5.98:1 ✓ | `#6FBF95` | 8.47:1 ✓ |
| Informação | `#1F5F8B` | 6.51:1 ✓ | `#6FB3DC` | 8.11:1 ✓ |
| Aviso | rampa 600 | 4.36:1 ⚠ | rampa 400 | 9.19:1 ✓ |

### A colisão, medida

Vermelho de marca (`#A6321E`) contra vermelho de perigo (`#B3261E`): razão de luminância **1.04:1**. São praticamente idênticos em brilho.

> **Consequência direta:** a diferença entre "Publicar" e "Apagar post" **não pode depender da cor**. Quem tem daltonismo do tipo protanopia, ou está no sol, ou tem o brilho no mínimo, vê dois botões iguais.

**Regra: a forma carrega a distinção, a cor apenas reforça.**

- Ação primária — preenchimento sólido, rótulo que diz o que acontece (`Publicar`, não `Enviar`)
- Ação destrutiva — **contorno**, nunca preenchimento sólido; ícone obrigatório; e confirmação para o que não é reversível
- Aviso — tinta amarela é proibida; o amarelo entra como fundo tingido e borda, com ícone e texto na cor de tinta normal

Nenhuma informação do fórum pode ser transmitida só por cor. Vale para categorias, estados de tópico (fixado, trancado) e níveis de confiança — todos precisam de ícone, rótulo ou forma além da cor.

---

## 4. Neutros

Neutros com viés quente, para pertencerem à paleta em vez de conviverem com ela.

| Papel | Claro | Escuro |
|---|---|---|
| Fundo | `#FAF9F7` | `#17120E` |
| Superfície | `#FFFFFF` | `#1F1813` |
| Tinta | `#1C1714` (16.88:1) | `#F2EDE8` (15.99:1) |
| Tinta suave | `#6B605A` (5.79:1) | `#A79C95` (6.94:1) |

Tinta suave passa AA nos dois temas — texto secundário continua legível, e não vira decoração cinza.

---

## 5. Alternância de tema

**Três estados, não dois:** claro, escuro e *sistema*. Sistema é o padrão e segue `prefers-color-scheme`.

Alternar sem escolher "sistema" é um erro comum: quem muda o telemóvel para escuro à noite espera que o fórum acompanhe, a menos que tenha dito explicitamente o contrário.

### Onde isto colide com decisões já tomadas

Duas colisões reais, que precisam ser resolvidas no desenho e não descobertas depois.

**Colisão 1 — cache de página (§8).** A [§8](ARQUITETURA.md#8-cache-e-desempenho) guarda páginas inteiras de tópico em Redis para visitantes anônimos. Se o tema for decidido no servidor, cada página passa a existir em três versões e o cache triplica, com taxa de acerto proporcionalmente pior.

*Resolução:* o HTML é **neutro em relação ao tema**. Todas as cores vêm de custom properties CSS; o atributo `data-theme` no elemento raiz é escrito no cliente. Uma única entrada de cache serve os três estados.

**Colisão 2 — CSP sem `unsafe-inline` (§7.1).** Para não haver piscada de tema errado, o `data-theme` precisa ser aplicado **antes da primeira pintura**, o que exige um script inline — e a [§7.1](ARQUITETURA.md#71-conteúdo-gerado-por-usuário) proíbe `unsafe-inline`.

A saída conhecida é um `nonce`, mas **nonce e cache de página são incompatíveis**: o nonce precisa ser único por resposta, e uma página servida do cache carregaria um nonce velho que não bate com o cabeçalho gerado na requisição.

*Resolução:* CSP baseada em **hash** (`script-src 'sha256-…'`) para esse script. O script é estático, então o hash é estável e o cabeçalho não varia por requisição. Nonce fica reservado para o que for genuinamente dinâmico — hoje, nada.

### Desenho

- Preferência em `localStorage`, por dispositivo. **Não** sincronizada com o perfil no banco: além de forçar renderização no servidor e quebrar o cache, preferência por dispositivo é melhor mesmo — escuro no telemóvel à noite, claro no computador de dia.
- Script inline mínimo, antes do CSS, lendo `localStorage` e escrevendo `data-theme` na raiz.
- `color-scheme: light dark` no CSS, para que controles de formulário, barras de rolagem e campos nativos acompanhem.
- **Sem JavaScript a página continua correta**, seguindo `prefers-color-scheme`. O controle é melhoria, não requisito — mesma regra do HTMX no resto do projeto.
- O controle é um grupo de três opções com rótulo acessível e estado anunciado, não um interruptor de dois estados disfarçado.

---

## 6. Cores de categoria

`Category.color` hoje é um campo de texto livre com padrão `#8B6F47`, editável no admin. Duas consequências: o padrão não pertence à paleta nova, e quem modera pode escolher uma cor ilegível sem perceber.

**Plano:** substituir o campo livre por escolha entre um conjunto curado, derivado da rampa e verificado nos dois temas. Guardar o *nome do token*, não o hex — assim o tema resolve o valor e a mesma categoria fica legível nos dois.

Migração de dados mapeia as cores existentes para o token mais próximo. É mudança de schema: precisa ser retrocompatível (expand/contract), conforme o [CONTRIBUTING](../CONTRIBUTING.md).

---

## 7. Usabilidade

"Moderna" aqui significa critérios verificáveis, não estilo.

**Leitura primeiro.** Um fórum é lido muito mais do que é escrito, e majoritariamente no telemóvel. Medida de leitura entre 65 e 75 caracteres; corpo de post com espaçamento generoso; hierarquia tipográfica clara entre título de tópico, autor e corpo.

**Densidade adequada ao conteúdo.** Listagens de tópico são tabelas de varredura, não cartões. Cartão para tudo desperdiça espaço vertical e torna a lista mais lenta de percorrer.

**Alvos de toque de no mínimo 44×44 px.** Vale especialmente para o botão de reagir, que é pequeno por natureza.

**Teclado.** Foco sempre visível. Navegação entre posts por teclado — convenção que fóruns bons têm e os ruins não.

**Movimento.** `prefers-reduced-motion` respeitado. Nenhuma animação essencial para entender o estado.

**Sem deslocamento de layout.** Imagens e áreas de mídia com dimensão reservada.

**Acessibilidade é contínua, não uma auditoria final.** O roadmap tem "acessibilidade auditada" na Fase 4. Mantenha a auditoria, mas o alvo **WCAG 2.2 AA** vale desde a primeira tela — retrofitar acessibilidade custa muito mais do que construí-la, e este documento já traz os contrastes calculados justamente para que ninguém precise adivinhar.

---

## 8. Sequência

O design tem uma dependência que o roadmap ainda não expressa.

A Fase 2 vai construir botão de reagir, caixa e página de busca, editor e telas de edição. **Se o sistema de design chegar depois disso, tudo é reestilizado.** Se chegar antes, cada tela nasce usando os mesmos componentes.

Proposta: um item **2.0 — Sistema de design**, pré-requisito das demais partes da Fase 2. Escopo deliberadamente pequeno:

1. Tokens de cor em custom properties, três estados de tema
2. Escala tipográfica e espaçamento
3. Alternador de tema, com a CSP por hash resolvida
4. Componentes base: botão (primário, secundário, destrutivo), etiqueta, campo de formulário, linha de listagem, aviso
5. Página de referência viva, mostrando todos os componentes nos dois temas

O item 5 é o que impede a deriva: sem uma página onde os dois temas aparecem lado a lado, o tema escuro quebra sem ninguém notar.

---

## 9. Em aberto

1. **Tipografia.** Precisa cobrir português com acentos, diacríticos do Pāli (`anattā`, `saṅgha`) e, no conteúdo, devanágari, tibetano e CJK. A cobertura de fonte é requisito, não preferência estética.
2. **Identidade.** Logotipo e favicon — ligado à decisão de domínio, ainda pendente no [ROADMAP](ROADMAP.md#decisões-pendentes).
3. **Densidade configurável.** Alguns fóruns oferecem modo compacto. Fica para depois de haver conteúdo real para avaliar.
4. **Onde o alternador de tema vive.** Cabeçalho, rodapé ou preferências. Decidir junto com a navegação.
