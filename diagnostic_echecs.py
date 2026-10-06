#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnostic_echecs.py — DIAGNOSTIC EN LECTURE SEULE des questions en échec.

Pour chaque question, refait exactement la recherche du moteur de tests
(question élargie -> vecteur -> recherche hybride) et montre OÙ se situe
l'article attendu dans chacune des deux recherches :
  - recherche par SENS (vecteurs)      : rang de l'article attendu ;
  - recherche par MOTS-CLÉS (texte)    : rang de l'article attendu ;
  - classement FINAL (fusion + bonus)  : rang de l'article attendu ;
ainsi que les 5 premiers articles du classement final avec leur chapitre.

Ne modifie rien. Coût : 1 vecteur par question (quota d'embeddings seulement).

Usage, depuis le Shell Render :
    python diagnostic_echecs.py                 (les 15 échecs connus)
    python diagnostic_echecs.py T124 T129       (questions choisies)
"""
import json
import os
import sys

import psycopg2
import psycopg2.extras

import llm
from rag import recherche_hybride, search_keywords, search_pivot_articles, detecter_matiere_dans_question
from vocabulaire import elargir_question

ECHECS = ["T018", "T019", "T195", "T124", "T129", "T100", "T103", "T104",
          "T135", "T140", "T044", "T085", "T130", "T235", "T236"]
PROFONDEUR = 30


def rang(ids, attendus):
    for i, a in enumerate(ids, start=1):
        if a in attendus:
            return str(i)
    return f">{len(ids)}"


def main():
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True

    with open("banque_200_questions.json", encoding="utf-8") as f:
        banque = {t["id"]: t for t in json.load(f)}
    ids = sys.argv[1:] or ECHECS

    for tid in ids:
        t = banque.get(tid)
        if not t:
            print(f"[{tid}] introuvable dans la banque\n")
            continue
        attendus = set(t.get("articles_attendus") or [])
        q = elargir_question(t["question"])
        vecteur = llm.vectoriser_question(q)

        sens = [a.article_id for a in search_pivot_articles(conn, vecteur, top_k=PROFONDEUR)]
        mots = [a.article_id for a in search_keywords(conn, q, top_k=PROFONDEUR)]
        final = recherche_hybride(conn, vecteur, q, top_k=10)
        ids_final = [a.article_id for a in final]

        print(f"[{tid}] {t['question']}")
        print(f"  attendu {sorted(attendus)} | rang SENS {rang(sens, attendus)} | "
              f"MOTS {rang(mots, attendus) if mots else 'aucun résultat'} | FINAL {rang(ids_final, attendus)}")
        print(f"  matière détectée : {detecter_matiere_dans_question(t['question']) or '-'}")
        if q.strip() != t["question"].strip():
            print(f"  question élargie : {q[:160]}")
        print("  top 5 : " + " ; ".join(
            f"{a.article_id} ({(a.chapitre_titre or a.livre_titre or '')[:28]})" for a in final[:5]))
        print()
    conn.close()


if __name__ == "__main__":
    main()
