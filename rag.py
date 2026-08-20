#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rag.py — Moteur de recherche CGI 2026 pour Fisca AI (squelette v1).

Logique : recherche vectorielle -> articles pivot -> expansion par renvois
explicites (1 seul niveau) -> construction du contexte -> LLM -> vérification
anti-hallucination des numéros d'articles cités.

Ce fichier suppose une connexion psycopg2/asyncpg déjà configurée (`db`) et
une fonction `embed(text) -> list[float]` qui appelle gemini-embedding-001.
Il tourne sur Render (accès réseau), pas dans l'environnement de préparation.
"""

import re
from dataclasses import dataclass, field


TOP_K_VECTOR = 5          # nb d'articles récupérés par similarité vectorielle
MAX_EXPANSION_PER_ARTICLE = 4  # nb max de renvois ajoutés par article pivot


@dataclass
class RetrievedArticle:
    article_id: str
    text: str
    livre_titre: str = ""
    chapitre_titre: str = ""
    section_titre: str = ""
    role: str = "pivot"   # 'pivot' | 'lie'  (article lié via renvoi)


def search_pivot_articles(db, query_embedding, top_k=TOP_K_VECTOR):
    """Étape 1 : recherche vectorielle pure -> articles pivot."""
    rows = db.execute(
        """
        SELECT article_id, text, livre_titre, chapitre_titre, section_titre
        FROM cgi_articles
        ORDER BY embedding <=> %s
        LIMIT %s
        """,
        (query_embedding, top_k),
    ).fetchall()
    return [
        RetrievedArticle(
            article_id=r["article_id"], text=r["text"],
            livre_titre=r["livre_titre"], chapitre_titre=r["chapitre_titre"],
            section_titre=r["section_titre"], role="pivot",
        )
        for r in rows
    ]


def expand_via_refs(db, pivots, max_per_article=MAX_EXPANSION_PER_ARTICLE):
    """Étape 2 : pour chaque article pivot, ajoute les articles qu'il cite
    explicitement (renvois extraits par extract_refs.py). Un seul niveau
    d'expansion — pas de multi-hop pour l'instant."""
    pivot_ids = {a.article_id for a in pivots}
    linked = []
    seen = set(pivot_ids)

    for p in pivots:
        rows = db.execute(
            """
            SELECT r.target_article_id, r.ref_type,
                   c.text, c.livre_titre, c.chapitre_titre, c.section_titre
            FROM article_refs r
            JOIN cgi_articles c ON c.article_id = r.target_article_id
            WHERE r.source_article_id = %s
            LIMIT %s
            """,
            (p.article_id, max_per_article),
        ).fetchall()
        for r in rows:
            if r["target_article_id"] in seen:
                continue
            seen.add(r["target_article_id"])
            linked.append(
                RetrievedArticle(
                    article_id=r["target_article_id"], text=r["text"],
                    livre_titre=r["livre_titre"], chapitre_titre=r["chapitre_titre"],
                    section_titre=r["section_titre"], role="lie",
                )
            )
    return linked


def build_context_blocks(pivots, linked):
    """Étape 3 : construit le contexte envoyé au LLM avec des blocs distincts,
    pour que le modèle distingue la source principale des sources d'appui."""
    blocks = ["ARTICLES PRINCIPAUX (correspondance directe à la question) :\n"]
    for a in pivots:
        blocks.append(f"[Art. {a.article_id}] ({a.chapitre_titre or a.livre_titre})\n{a.text}\n")
    if linked:
        blocks.append("\nARTICLES LIÉS (référencés explicitement par les articles ci-dessus) :\n")
        for a in linked:
            blocks.append(f"[Art. {a.article_id}] ({a.chapitre_titre or a.livre_titre})\n{a.text}\n")
    return "\n".join(blocks)


RE_CITED_ARTICLE = re.compile(r"[Aa]rticle\s+(\d+)\s*(bis|ter|quater)?", re.IGNORECASE)


def check_no_hallucinated_articles(answer_text, context_article_ids):
    """Garde-fou anti-hallucination : vérifie que chaque numéro d'article cité
    dans la réponse du LLM figure bien parmi les articles réellement envoyés
    en contexte. Retourne la liste des numéros suspects (à ne jamais afficher
    tels quels, ou à faire vérifier avant affichage)."""
    cited = set()
    for m in RE_CITED_ARTICLE.finditer(answer_text):
        num = m.group(1)
        suf = (m.group(2) or "").lower()
        cited.add(f"{num}{suf}")
        cited.add(num)  # tolère la citation sans suffixe

    context_set = set(context_article_ids)
    suspect = sorted({c for c in cited if c not in context_set}, key=lambda x: int(re.sub(r"\D", "", x)))
    return suspect


def answer_query(db, user_question, embed_fn, llm_fn):
    """Orchestration complète (à adapter selon le client LLM utilisé)."""
    q_emb = embed_fn(user_question)

    pivots = search_pivot_articles(db, q_emb)
    linked = expand_via_refs(db, pivots)

    context = build_context_blocks(pivots, linked)
    all_ids = [a.article_id for a in pivots + linked]

    prompt = (
        "Tu es un assistant fiscal spécialisé sur le Code Général des Impôts "
        "du Niger (CGI 2026). Réponds UNIQUEMENT à partir des articles fournis "
        "ci-dessous. Cite systématiquement le ou les numéros d'article sur "
        "lesquels tu bases ta réponse. Si les articles fournis ne permettent "
        "pas de répondre avec certitude, dis-le explicitement plutôt que "
        "d'improviser.\n\n"
        f"{context}\n\nQuestion : {user_question}"
    )

    answer = llm_fn(prompt)

    suspects = check_no_hallucinated_articles(answer, all_ids)
    if suspects:
        answer += (
            "\n\n⚠️ Vérification automatique : les articles "
            f"{', '.join(suspects)} cités ci-dessus n'étaient pas dans les "
            "sources consultées pour cette réponse — à vérifier manuellement."
        )

    return {
        "answer": answer,
        "sources": all_ids,
        "suspects": suspects,
    }
