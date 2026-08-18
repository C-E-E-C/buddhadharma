# Contribuindo

Obrigado pelo interesse. Este documento é curto de propósito.

## Antes de começar

Leia [docs/ARQUITETURA.md](docs/ARQUITETURA.md), pelo menos a §10 (decisões
registradas) e a §11 (roadmap). Boa parte do que parece estranho no código está
explicado lá, com o motivo.

Se discorda de uma decisão registrada, abra uma issue para discutir **antes** de
escrever código. Mudança de arquitetura por pull request pronto costuma
desperdiçar o trabalho de quem escreveu.

## Fluxo

1. Abra uma issue descrevendo o problema ou a proposta.
2. Branch a partir de `main`.
3. `make check` precisa passar.
4. Pull request explicando **o porquê**, não só o quê.

## Padrões

- Código, nomes de variáveis e identificadores em **inglês**.
- Comentários, docstrings, mensagens de commit e textos de interface em
  **português**.
- Todo texto visível ao usuário passa por `gettext` (`_("...")`), mesmo havendo
  um só idioma. Retrofitar i18n depois é trabalho penoso; fazer desde já custa
  quase nada.
- Comentário explica **por quê**, não o quê. Se o código precisa de comentário
  para dizer o que faz, reescreva o código.

## Migrações

Precisam ser **retrocompatíveis**. Durante um deploy, código antigo e novo
rodam ao mesmo tempo.

Nada de renomear ou remover coluna numa migração só. Use expand/contract:

1. adiciona a coluna nova;
2. migra os dados;
3. troca o código para usar a nova;
4. remove a antiga **numa release posterior**.

## Testes

- Toda correção de bug começa por um teste que falha.
- Testes de segurança (sanitização, homóglifos, autorização) não podem ser
  relaxados para fazer passar. Se um deles falha, o defeito é do código.
- Teste em português, nome descritivo: `test_imagem_remota_vira_link`.

## Desempenho

Nenhuma listagem pode ter N+1. Use `select_related` e `prefetch_related`
explicitamente. Se acrescentou uma consulta por item numa listagem, o pull
request não passa.

## Conteúdo

Este é um fórum sobre Budismo, com pessoas de tradições diferentes. Ao
escrever textos de interface, mensagens de erro ou conteúdo de exemplo:

- não privilegie uma escola em detrimento de outra;
- transliterações de Pāli e sânscrito com os diacríticos corretos
  (`anattā`, `saṅgha`, `Saṃyutta`) — a busca já é insensível a eles;
- na dúvida sobre terminologia, pergunte na issue.

## Licença

Ao contribuir, você concorda em licenciar sua contribuição sob AGPL-3.0-or-later.
