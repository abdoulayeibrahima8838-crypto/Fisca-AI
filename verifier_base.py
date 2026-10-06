#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verifier_base.py — DIAGNOSTIC EN LECTURE SEULE de la base PostgreSQL du RAG.

Ne modifie RIEN (ni la base, ni les fichiers). Compare le contenu de la
table cgi_articles (celle qu'interroge réellement le RAG) avec les deux
fichiers du corpus :
  - cgi2026_articles_complet.json  (version contenant les corrections de texte)
  - cgi2026_articles_corrige.json  (version utilisée à l'origine pour remplir la base)

But : savoir si les corrections d'articles (textes complétés, article 394quinquies
scindé, titres de chapitres) sont bien arrivées dans la base, ou si le RAG
travaille encore sur les anciens textes.

Usage, depuis le Shell Render :
    python verifier_base.py
"""
import json
import os
import re
import sys

import psycopg2
import psycopg2.extras


def charger(nom):
    try:
        with open(nom, encoding="utf-8") as f:
            return {a["article_id"]: a for a in json.load(f)}
    except FileNotFoundError:
        print(f"  (fichier {nom} absent)")
        return {}


def norm(texte):
    return re.sub(r"\s+", " ", (texte or "")).strip()


def apercu(liste, n=25):
    liste = sorted(liste, key=lambda x: (int(re.sub(r"\D", "", x) or 0), x))
    return ", ".join(liste[:n]) + (f" … (+{len(liste) - n})" if len(liste) > n else "")


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERREUR : DATABASE_URL absente. À lancer depuis le Shell Render.")
        sys.exit(1)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    complet = charger("cgi2026_articles_complet.json")
    corrige = charger("cgi2026_articles_corrige.json")

    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute("""SELECT article_id, text, livre_titre, chapitre_titre, section_titre,
                          (embedding IS NULL) AS sans_vecteur
                   FROM cgi_articles""")
    base = {r["article_id"]: r for r in cur.fetchall()}
    conn.close()

    print("=== DIAGNOSTIC DE LA BASE DU RAG (lecture seule) ===\n")
    print(f"Articles en base : {len(base)}")
    print(f"Articles dans cgi2026_articles_complet.json : {len(complet)}")
    print(f"Articles dans cgi2026_articles_corrige.json : {len(corrige)}\n")

    sans_vecteur = [i for i, r in base.items() if r["sans_vecteur"]]
    print(f"1) Articles en base SANS vecteur (invisibles à la recherche) : {len(sans_vecteur)}")
    if sans_vecteur:
        print(f"   {apercu(sans_vecteur)}")

    reference = complet or corrige
    absents = [i for i in reference if i not in base]
    en_trop = [i for i in base if i not in reference]
    print(f"\n2) Articles du fichier complet ABSENTS de la base : {len(absents)}")
    if absents:
        print(f"   {apercu(absents)}")
    print(f"   Articles en base absents du fichier complet : {len(en_trop)}")
    if en_trop:
        print(f"   {apercu(en_trop)}")

    communs = [i for i in complet if i in base]
    textes_diff = [i for i in communs if norm(base[i]["text"]) != norm(complet[i]["text"])]
    ancienne_version = [i for i in textes_diff if i in corrige and norm(base[i]["text"]) == norm(corrige[i]["text"])]
    print(f"\n3) Textes différents entre la base et le fichier complet : {len(textes_diff)}")
    print(f"   dont textes identiques à l'ANCIENNE version (corrige.json) : {len(ancienne_version)}")
    if textes_diff:
        print(f"   {apercu(textes_diff)}")

    for numero, champ, libelle in ((4, "chapitre_titre", "chapitres"), (5, "livre_titre", "livres"), (6, "section_titre", "sections")):
        diff = [i for i in communs if (base[i][champ] or "") != (complet[i].get(champ) or "")]
        print(f"\n{numero}) Titres de {libelle} différents entre la base et le fichier complet : {len(diff)}")
        if diff:
            print(f"   {apercu(diff)}")

    print("\n=== CONCLUSION ===")
    if not (sans_vecteur or absents or textes_diff):
        print("La base est à jour : le RAG travaille sur les textes corrigés.")
    else:
        print("La base n'est PAS entièrement à jour : envoyez cette capture à Claude pour")
        print("préparer la synchronisation (mise à jour des textes et des vecteurs concernés).")


if __name__ == "__main__":
    main()
