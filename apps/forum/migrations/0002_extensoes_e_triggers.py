"""Extensões PostgreSQL e triggers — §4.5 e §5 da arquitetura.

Duas coisas que ficam no banco, e não na aplicação:

1. **Contagem de reações.** Trigger e não sinal do Django, porque a garantia
   precisa valer em todo caminho de escrita — importação em massa, correção
   manual via psql, migração de dados — e não apenas no que passa pelo ORM.

2. **Vetor de busca.** Trigger e não coluna GENERATED, porque ``unaccent()``
   não é IMMUTABLE no PostgreSQL e portanto não pode aparecer em coluna gerada
   nem em índice de expressão. O trigger calcula e grava um valor comum, o que
   contorna a restrição sem abrir mão do ``unaccent``.
"""

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension
from django.db import migrations

REACTION_COUNT_TRIGGER = """
CREATE OR REPLACE FUNCTION forum_bump_reaction_count() RETURNS trigger AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO forum_reactioncount (post_id, emoji_id, count)
        VALUES (NEW.post_id, NEW.emoji_id, 1)
        ON CONFLICT (post_id, emoji_id)
        DO UPDATE SET count = forum_reactioncount.count + 1;
    ELSIF (TG_OP = 'DELETE') THEN
        UPDATE forum_reactioncount
           SET count = GREATEST(count - 1, 0)
         WHERE post_id = OLD.post_id AND emoji_id = OLD.emoji_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER forum_reaction_count_trigger
AFTER INSERT OR DELETE ON forum_reaction
FOR EACH ROW EXECUTE FUNCTION forum_bump_reaction_count();
"""

REACTION_COUNT_TRIGGER_REVERSE = """
DROP TRIGGER IF EXISTS forum_reaction_count_trigger ON forum_reaction;
DROP FUNCTION IF EXISTS forum_bump_reaction_count();
"""

# Pesos: A para o título do tópico, B para o corpo do post. O ts_rank do
# PostgreSQL trata A como mais relevante — casar no título vale mais.
SEARCH_VECTOR_TRIGGER = """
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

CREATE TRIGGER forum_post_search_vector_trigger
BEFORE INSERT OR UPDATE OF body_md, topic_id ON forum_post
FOR EACH ROW EXECUTE FUNCTION forum_post_search_vector();
"""

SEARCH_VECTOR_TRIGGER_REVERSE = """
DROP TRIGGER IF EXISTS forum_post_search_vector_trigger ON forum_post;
DROP FUNCTION IF EXISTS forum_post_search_vector();
"""


class Migration(migrations.Migration):
    dependencies = [("forum", "0001_initial")]

    operations = [
        # unaccent: busca insensível a acento — quem digita "meditacao" precisa
        # encontrar "meditação". Remove também os diacríticos do Pāli, de modo
        # que "anatta" encontra "anattā" e "sangha" encontra "saṅgha" (§5).
        UnaccentExtension(),
        # pg_trgm: cobre a lacuna das escritas sem stemmer no PostgreSQL —
        # tibetano, devanágari, CJK — e dá tolerância a erro de digitação.
        TrigramExtension(),
        migrations.RunSQL(REACTION_COUNT_TRIGGER, REACTION_COUNT_TRIGGER_REVERSE),
        migrations.RunSQL(SEARCH_VECTOR_TRIGGER, SEARCH_VECTOR_TRIGGER_REVERSE),
        migrations.AddIndex(
            model_name="post",
            index=GinIndex(
                fields=["body_md"],
                opclasses=["gin_trgm_ops"],
                name="post_trigrama_idx",
            ),
        ),
    ]
