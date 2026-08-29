#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm_judge.py — Juge par lots les vraies conversations de Fisca AI
(journal_conversations), pour detecter mauvaises reponses, incomprehension,
et surtout ABSENCE de dispositions pertinentes (pas seulement la fidelite
aux articles deja envoyes).

Cout : 1 appel Gemini (generation) par conversation jugee, tire du quota
rare (20/jour en gratuit) - + des appels embedding (abondants, 1000/jour)
pour la recherche elargie. A lancer par petits lots (--limite 20-50),
jamais en continu.

Usage, depuis le Shell Render :
    python llm_judge.py --limite 20
"""
import argparse
import json
import os
import time

import psycopg2
import psycopg2.extras
from google import genai
from google.genai import types as genai_types

from rag import recherche_hybride, embed_question, _METADONNEES_PAR_ARTICLE

GEMINI_MODEL = "gemini-2.5-flash"
TOP_K_RECHERCHE_ELARGIE = 15

PROMPT_JUGE = """Tu es un juge expert en fiscalite nigerienne, charge d'evaluer la qualite d'une reponse deja donnee par un assistant fiscal (Fisca AI), en te basant UNIQUEMENT sur les textes officiels fournis ci-dessous - jamais sur tes propres connaissances.

QUESTION POSEE PAR L'UTILISATEUR :
{question}

REPONSE DONNEE PAR FISCA AI :
{reponse}

ARTICLES REELLEMENT ENVOYES A FISCA AI POUR REPONDRE (leur texte complet) :
{articles_utilises_texte}

AUTRES ARTICLES POTENTIELLEMENT PERTINENTS, TROUVES PAR UNE RECHERCHE PLUS LARGE MAIS PAS ENVOYES A FISCA AI (uniquement leurs numeros et themes, pas leur texte complet) :
{articles_elargis_liste}

LIENS DEJA CONNUS DE NOTRE BASE (articles/procedures generalement associes aux articles utilises, meme si non envoyes) :
{liens_connus}

Evalue cette reponse selon DEUX AXES DISTINCTS, puis reponds UNIQUEMENT en JSON valide, sans aucun texte avant ou apres, selon exactement ce format :

{{
  "fidelite": {{
    "score": <entier 0-100, a quel point la reponse est fidele aux articles reellement envoyes>,
    "hallucination": <true si la reponse invente ou deforme un fait absent des articles envoyes, sinon false>,
    "details": "<une phrase expliquant le score>"
  }},
  "completude": {{
    "dispositions_manquantes": <true si des articles pertinents semblent absents de ce qui a ete envoye a Fisca AI>,
    "articles_suggeres": [<liste de numeros d'articles parmi ceux listes plus haut qui auraient du etre envoyes, vide si aucun>],
    "raison": "<une phrase expliquant pourquoi, vide si dispositions_manquantes est false>"
  }},
  "incomprehension": <true si Fisca AI semble avoir mal compris la question elle-meme (hors-sujet, contresens), sinon false>,
  "recommandation": "<une phrase concrete et actionnable pour ameliorer ce cas precis, ou vide si tout est bon>"
}}
"""


def construire_liens_connus(articles_ids):
    """Rassemble les liens_implicites et procedures_generales_associees
    deja presents dans nos donnees (Phase 5) pour les articles utilises -
    sans nouvel appel, cette info est deja calculee."""
    liens = []
    for aid in articles_ids:
        meta = _METADONNEES_PAR_ARTICLE.get(aid, {})
        li = meta.get("liens_implicites", {})
        procs = li.get("procedures_generales_meme_theme", [])
        if procs:
            liens.append(f"Article {aid} — procédures générales associées : {', '.join(procs)}")
        for theme, ids in (li.get("meme_matiere_autres_themes") or {}).items():
            if ids:
                liens.append(f"Article {aid} — autres articles du thème « {theme} » : {', '.join(ids[:5])}")
    return "\n".join(liens) if liens else "(aucun lien connu recensé pour ces articles)"


def executer_recherche_elargie(db, client, question):
    """Recherche elargie (15 candidats) faite specifiquement pour le
    jugement, independante de ce qui a ete reellement utilise en
    production - permet au juge de voir ce qui EXISTE meme si non envoye."""
    try:
        vecteur = embed_question(client, question)
        pivots = recherche_hybride(db, vecteur, question, top_k=TOP_K_RECHERCHE_ELARGIE)
        return [(a.article_id, a.matiere_fiscale) for a in pivots]
    except Exception as e:
        print(f"    (recherche élargie échouée : {type(e).__name__}: {e})")
        return []


def recuperer_texte_articles(db, articles_ids):
    if not articles_ids:
        return "(aucun article n'a été envoyé à Fisca AI pour cette réponse)"
    cur = db.cursor()
    blocs = []
    for aid in articles_ids:
        cur.execute("SELECT text FROM cgi_articles WHERE article_id = %s", (aid,))
        row = cur.fetchone()
        if row:
            blocs.append(f"[Article {aid}]\n{row['text']}")
    return "\n\n".join(blocs) if blocs else "(articles introuvables)"


def juger_conversation(db, client, conversation):
    question = conversation["question_brute"]
    reponse = conversation["reponse"] or ""
    articles_ids = json.loads(conversation["articles_utilises"]) if conversation["articles_utilises"] else []

    articles_texte = recuperer_texte_articles(db, articles_ids)
    elargis = executer_recherche_elargie(db, client, question)
    elargis_hors_utilises = [(aid, mat) for aid, mat in elargis if aid not in articles_ids]
    elargis_texte = (
        "\n".join(f"- Article {aid} ({mat})" for aid, mat in elargis_hors_utilises)
        if elargis_hors_utilises else "(aucun autre article trouvé par la recherche élargie)"
    )
    liens_connus = construire_liens_connus(articles_ids)

    prompt = PROMPT_JUGE.format(
        question=question, reponse=reponse,
        articles_utilises_texte=articles_texte,
        articles_elargis_liste=elargis_texte,
        liens_connus=liens_connus,
    )

    reponse_brute = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            max_output_tokens=800,
            response_mime_type="application/json",
        ),
    )
    texte = (reponse_brute.text or "").strip()
    return json.loads(texte)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=20, help="Nombre de conversations à juger dans ce lot")
    args = parser.parse_args()

    DATABASE_URL = os.environ["DATABASE_URL"]
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    cur = conn.cursor()
    cur.execute(
        "SELECT id, question_brute, reponse, articles_utilises FROM journal_conversations "
        "WHERE juge = FALSE ORDER BY date_heure ASC LIMIT %s",
        (args.limite,),
    )
    conversations = cur.fetchall()

    print(f"=== LLM Judge — {len(conversations)} conversation(s) à juger (lot demandé : {args.limite}) ===\n")

    nb_juges = 0
    nb_hallucinations = 0
    nb_incompletes = 0
    nb_incomprehensions = 0

    for conv in conversations:
        print(f"[id={conv['id']}] {conv['question_brute'][:70]}")
        try:
            jugement = juger_conversation(conn, client, conv)

            cur.execute(
                "UPDATE journal_conversations SET juge = TRUE, date_jugement = NOW(), score_judge = %s, judge_details = %s WHERE id = %s",
                (jugement.get("fidelite", {}).get("score"), json.dumps(jugement, ensure_ascii=False), conv["id"]),
            )
            nb_juges += 1
            if jugement.get("fidelite", {}).get("hallucination"):
                nb_hallucinations += 1
                print(f"    🔴 HALLUCINATION détectée — {jugement['fidelite']['details']}")
            if jugement.get("completude", {}).get("dispositions_manquantes"):
                nb_incompletes += 1
                print(f"    ⚠️  Dispositions manquantes — suggéré : {jugement['completude']['articles_suggeres']}")
            if jugement.get("incomprehension"):
                nb_incomprehensions += 1
                print(f"    ⚠️  Incompréhension détectée")
            if not any([jugement.get("fidelite", {}).get("hallucination"),
                        jugement.get("completude", {}).get("dispositions_manquantes"),
                        jugement.get("incomprehension")]):
                print(f"    ✅ Score fidélité : {jugement.get('fidelite', {}).get('score')}/100")

        except Exception as e:
            print(f"    ❌ Jugement échoué : {type(e).__name__}: {e}")
        time.sleep(1)
        print()

    print("=" * 60)
    print(f"Conversations jugées ce lot : {nb_juges}/{len(conversations)}")
    print(f"  🔴 Hallucinations détectées      : {nb_hallucinations}")
    print(f"  ⚠️  Dispositions manquantes       : {nb_incompletes}")
    print(f"  ⚠️  Incompréhensions détectées    : {nb_incomprehensions}")

    cur.execute("SELECT COUNT(*) AS n FROM journal_conversations WHERE juge = FALSE")
    restantes = cur.fetchone()["n"]
    print(f"\nConversations restant à juger : {restantes}")

    conn.close()


if __name__ == "__main__":
    main()
