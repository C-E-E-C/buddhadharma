"""Corrige a busca: acento e radical deixam de ser excludentes — §5.

O defeito
---------

A migração 0002 montava o vetor como ``to_tsvector('portuguese', unaccent(txt))``.
Parece razoável e está errado: ``unaccent()`` roda **antes** do stemmer, e o
stemmer snowball do português reconhece os sufixos pelos acentos. Sem eles, cai
em regras genéricas.

Medido neste banco:

    to_tsvector('portuguese', unaccent('meditações'))  ->  'meditaco'
    to_tsvector('portuguese', unaccent('meditação'))   ->  'meditaca'
    to_tsvector('portuguese', 'meditações')            ->  'medit'
    to_tsvector('portuguese', 'meditação')             ->  'medit'

Ou seja: com ``unaccent`` na frente, singular e plural param de casar. O
stemming, que era a razão de usar a configuração ``portuguese``, ficava
desligado na prática.

Trocar ``unaccent()`` inline pela receita canônica — ``unaccent`` como
dicionário na cadeia da configuração — **não resolve**: a ordem continua sendo
unaccent, depois stem. Também foi medido.

A solução
---------

As duas propriedades são genuinamente conflitantes numa única configuração, e
as duas importam:

* **radical** — `meditações` precisa encontrar `meditação`;
* **acento** — quem digita `meditacao` no celular precisa encontrar algo.

Então indexamos os dois vetores e consultamos os dois:

    to_tsvector('portuguese',  txt)  ||  to_tsvector('pt_unaccent', txt)

Resultado medido:

    consulta 'meditação'   -> acha 'meditações' e 'meditação'   (radical funciona)
    consulta 'meditações'  -> acha 'meditações' e 'meditação'   (radical funciona)
    consulta 'meditacao'   -> acha 'meditação'                  (acento ignorado)
    consulta 'anatta'      -> acha 'anattā'                     (diacrítico do Pāli)
    consulta 'sangha'      -> acha 'saṅgha'                     (diacrítico do Pāli)

Limitação que permanece
-----------------------

Consulta **sem acento** numa **flexão diferente** da que está no texto —
`meditacao` contra um post que só diz `meditações` — continua não casando por
full-text. É o caso que o índice trigrama da 0002 cobre.

Custo
-----

O vetor fica maior, porque guarda os lexemas das duas configurações. É a
troca aceita: espaço de índice é barato, busca que não encontra é cara.
"""

from django.db import migrations

CRIAR_CONFIG = """
DROP TEXT SEARCH CONFIGURATION IF EXISTS pt_unaccent;

CREATE TEXT SEARCH CONFIGURATION pt_unaccent (COPY = portuguese);

ALTER TEXT SEARCH CONFIGURATION pt_unaccent
    ALTER MAPPING FOR hword, hword_part, word
    WITH unaccent, portuguese_stem;
"""

REMOVER_CONFIG = """
DROP TEXT SEARCH CONFIGURATION IF EXISTS pt_unaccent;
"""

# `public.` explícito: a função roda com o search_path de quem dispara o
# trigger, que não é necessariamente o mesmo de quem aplicou a migração.
TRIGGER = """
CREATE OR REPLACE FUNCTION forum_post_search_vector() RETURNS trigger AS $$
DECLARE
    topic_title text;
BEGIN
    SELECT title INTO topic_title FROM forum_topic WHERE id = NEW.topic_id;

    NEW.search_vector :=
        setweight(to_tsvector('portuguese', coalesce(topic_title, '')), 'A') ||
        setweight(to_tsvector('public.pt_unaccent', coalesce(topic_title, '')), 'A') ||
        setweight(to_tsvector('portuguese', coalesce(NEW.body_md, '')), 'B') ||
        setweight(to_tsvector('public.pt_unaccent', coalesce(NEW.body_md, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

TRIGGER_ANTERIOR = """
CREATE OR REPLACE FUNCTION forum_post_search_vector() RETURNS trigger AS $$
DECLARE
    topic_title text;
BEGIN
    SELECT title INTO topic_title FROM forum_topic WHERE id = NEW.topic_id;

    NEW.search_vector :=
        setweight(
            to_tsvector('portuguese', unaccent(coalesce(topic_title, ''))), 'A'
        ) ||
        setweight(
            to_tsvector('portuguese', unaccent(coalesce(NEW.body_md, ''))), 'B'
        );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# O trigger é BEFORE UPDATE OF body_md, e dispara quando a coluna aparece no
# SET — mesmo atribuindo o próprio valor. É o jeito de reindexar sem tocar nos
# dados. Numa base grande isto deve ser feito em lotes, não de uma vez.
REINDEXAR = "UPDATE forum_post SET body_md = body_md;"


class Migration(migrations.Migration):
    dependencies = [("forum", "0002_extensoes_e_triggers")]

    operations = [
        migrations.RunSQL(CRIAR_CONFIG, REMOVER_CONFIG),
        migrations.RunSQL(TRIGGER, TRIGGER_ANTERIOR),
        migrations.RunSQL(REINDEXAR, migrations.RunSQL.noop),
    ]
