#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
creer_table_journal.py — A LANCER UNE SEULE FOIS depuis le Shell Render.

Cree la table qui stocke chaque question/reponse reelle de Fisca AI, avec
toute la tracabilite necessaire pour un futur LLM Judge par lots (tous les
~3000 questions, comme prevu) : quel moteur a repondu, quels articles ont
ete envoyes en contexte, la reponse etait-elle verifiee, combien de temps
ca a pris.

Objectif direct : remplacer le "Golden Dataset" redige a la main (§4 du
document de conception) par du vrai trafic utilisateur, gratuit et deja
naturellement varie - la ou le document proposait de payer un fiscaliste
pour rediger 500 questions, ici les vrais utilisateurs les fournissent
tout seuls.

Usage :
    python creer_table_journal.py
"""
import os
import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

SCHEMA = """
CREATE TABLE IF NOT EXISTS journal_conversations (
    id SERIAL PRIMARY KEY,
    date_heure TIMESTAMP DEFAULT NOW(),

    -- La question et la reponse telles que vues par l'utilisateur
    question_brute TEXT NOT NULL,
    reponse TEXT,

    -- Tracabilite du parcours (§11 "mode debug interne" du document)
    moteur TEXT,              -- 'rag', 'rag_acte', 'rag_procedure', 'rag_fiche',
                               -- 'ia_openai', 'local_enrichi', 'indisponible'
    niveau INTEGER,           -- 1 (redaction complete), 2 (texte brut), 3 (local)
    articles_utilises TEXT,   -- JSON : liste des numeros d'articles envoyes en contexte
    verified BOOLEAN,         -- issu du garde-fou anti-hallucination existant
    suspects TEXT,            -- JSON : articles cites mais absents du contexte, si detecte
    duree_secondes REAL,

    -- Reserve pour le LLM Judge par lots (rempli plus tard, jamais a la volee)
    juge BOOLEAN DEFAULT FALSE,
    score_judge INTEGER,
    judge_details TEXT        -- JSON : detail complet du jugement (fiscal_accuracy,
                               -- faithfulness, hallucination, etc. - meme structure
                               -- que le LLM Judge du document de conception, §17)
);

CREATE INDEX IF NOT EXISTS idx_journal_juge ON journal_conversations(juge);
CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_conversations(date_heure);
"""

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute(SCHEMA)
conn.commit()
print("Table 'journal_conversations' créée (ou déjà existante).")

cur.execute("SELECT COUNT(*) FROM journal_conversations")
print(f"Nombre de conversations déjà enregistrées : {cur.fetchone()[0]}")

conn.close()
