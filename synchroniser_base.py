#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
synchroniser_base.py — Met la base du RAG en accord avec cgi2026_articles_complet.json.

Corrige exactement ce que verifier_base.py a révélé :
  - ajoute les articles absents de la base (ex. les 14 articles 394 sexies à 394 novies decies) ;
  - remplace les anciens textes par les textes corrigés ;
  - aligne les titres (livre, titre, chapitre, section, sous-section) et autres métadonnées ;
  - recalcule le vecteur UNIQUEMENT des articles dont le texte ou le titre de chapitre
    a changé (le vecteur dépend de ces deux éléments) — environ 135 vecteurs.

Sécurité :
  - Par défaut, MODE SIMULATION : affiche ce qui serait fait, sans rien modifier
    et sans consommer de quota.
  - Avec --appliquer : effectue les modifications. Chaque article est traité dans
    sa propre transaction : son texte n'est remplacé que si son nouveau vecteur a
    bien été calculé. Une base ne se retrouve jamais avec un texte neuf et un vecteur
    ancien.
  - Reprise automatique : en cas de coupure ou de quota épuisé, relancer la même
    commande traite seulement ce qui reste.

Usage, depuis le Shell Render :
    python synchroniser_base.py              (simulation)
    python synchroniser_base.py --appliquer  (exécution)
Puis vérifier :
    python verifier_base.py
"""
import argparse
import json
import os
import re
import sys
import time

import psycopg2
import psycopg2.extras

import llm

FICHIER_SOURCE = "cgi2026_articles_complet.json"
COLONNES = [
    "article_num", "article_suffix", "page", "livre_num", "livre_titre", "titre_num", "titre_titre",
    "chapitre_num", "chapitre_titre", "section_num", "section_titre", "ssection_num", "ssection_titre", "text",
]
MAX_ESSAIS = 3
PAUSE_ENTRE_ARTICLES_S = 0.3
MARQUEURS_QUOTA_JOURNALIER = ["per day", "perday", "requests per day"]


def norm(texte):
    return re.sub(r"\s+", " ", str(texte if texte is not None else "")).strip()


def titre_contexte(a):
    """Même contexte que generer_embeddings.py, pour des vecteurs homogènes."""
    return f"Article {a['article_num']}{a.get('article_suffix') or ''} - {a.get('chapitre_titre') or a.get('livre_titre') or ''}"


def vecteur_sql(vecteur):
    return "[" + ",".join(repr(float(x)) for x in vecteur) + "]"


def calculer_vecteur(article):
    for essai in range(1, MAX_ESSAIS + 1):
        try:
            return llm.vectoriser_document(article["text"], titre_contexte(article))
        except Exception as e:
            message = str(e).lower()
            if any(m in message for m in MARQUEURS_QUOTA_JOURNALIER):
                raise
            print(f"    essai {essai}/{MAX_ESSAIS} échoué ({type(e).__name__}: {e})")
            if essai < MAX_ESSAIS:
                time.sleep(5 * essai)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--appliquer", action="store_true", help="Effectue réellement les modifications.")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERREUR : DATABASE_URL absente. À lancer depuis le Shell Render.")
        sys.exit(1)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    with open(FICHIER_SOURCE, encoding="utf-8") as f:
        source = json.load(f)

    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(f"SELECT article_id, {', '.join(COLONNES)}, (embedding IS NULL) AS sans_vecteur FROM cgi_articles")
    base = {r["article_id"]: r for r in cur.fetchall()}

    a_inserer, a_revectoriser, a_metadonnees = [], [], []
    for a in source:
        b = base.get(a["article_id"])
        if b is None:
            a_inserer.append(a)
        elif (norm(b["text"]) != norm(a["text"]) or b["sans_vecteur"]
              or norm(titre_contexte(b)) != norm(titre_contexte(a))):
            a_revectoriser.append(a)
        elif any(norm(b[c]) != norm(a.get(c)) for c in COLONNES):
            a_metadonnees.append(a)

    print(f"=== SYNCHRONISATION DE LA BASE — {'EXÉCUTION' if args.appliquer else 'SIMULATION (rien ne sera modifié)'} ===\n")
    print(f"Source : {FICHIER_SOURCE} ({len(source)} articles) — base : {len(base)} articles\n")
    print(f"Articles à AJOUTER (avec vecteur)                 : {len(a_inserer)}")
    print(f"Articles à METTRE À JOUR et revectoriser          : {len(a_revectoriser)}")
    print(f"Articles à mettre à jour (titres seuls, sans quota) : {len(a_metadonnees)}")
    print(f"=> Vecteurs à calculer : {len(a_inserer) + len(a_revectoriser)}\n")

    if not args.appliquer:
        for libelle, liste in (("Ajouts", a_inserer), ("Revectorisations", a_revectoriser), ("Titres seuls", a_metadonnees)):
            if liste:
                ids = [a["article_id"] for a in liste]
                print(f"{libelle} : {', '.join(ids[:40])}{' …' if len(ids) > 40 else ''}")
        print("\nSimulation terminée. Pour appliquer : python synchroniser_base.py --appliquer")
        conn.close()
        return

    if not llm.disponible() and (a_inserer or a_revectoriser):
        print("ERREUR : aucun fournisseur d'IA disponible pour calculer les vecteurs. Arrêt.")
        sys.exit(1)

    conn.autocommit = False
    reussis, echecs = 0, []

    # 1) Titres seuls : aucune consommation de quota
    for a in a_metadonnees:
        cur.execute(
            f"UPDATE cgi_articles SET {', '.join(f'{c} = %({c})s' for c in COLONNES)} WHERE article_id = %(article_id)s",
            {c: a.get(c) for c in COLONNES + ["article_id"]},
        )
    conn.commit()
    if a_metadonnees:
        print(f"Titres mis à jour : {len(a_metadonnees)} article(s).\n")

    # 2) Ajouts et revectorisations : un article = une transaction
    travaux = [("ajout", a) for a in a_inserer] + [("mise à jour", a) for a in a_revectoriser]
    for i, (nature, a) in enumerate(travaux, start=1):
        try:
            vecteur = calculer_vecteur(a)
        except Exception as e:
            print(f"\n🛑 Quota journalier épuisé à l'article {a['article_id']} ({e}).")
            print("   Ce qui est fait est conservé : relancez la même commande demain pour terminer.")
            break
        if vecteur is None:
            echecs.append(a["article_id"])
            print(f"  [{i}/{len(travaux)}] Art. {a['article_id']} — ÉCHEC, ignoré (sera retenté au prochain lancement).")
            continue

        valeurs = {c: a.get(c) for c in COLONNES + ["article_id"]}
        valeurs["embedding"] = vecteur_sql(vecteur)
        try:
            if nature == "ajout":
                cur.execute(
                    f"""INSERT INTO cgi_articles (article_id, {', '.join(COLONNES)}, embedding)
                        VALUES (%(article_id)s, {', '.join(f'%({c})s' for c in COLONNES)}, %(embedding)s::vector)""",
                    valeurs,
                )
            else:
                cur.execute(
                    f"""UPDATE cgi_articles SET {', '.join(f'{c} = %({c})s' for c in COLONNES)},
                        embedding = %(embedding)s::vector WHERE article_id = %(article_id)s""",
                    valeurs,
                )
            conn.commit()
            reussis += 1
        except Exception as e:
            conn.rollback()
            echecs.append(a["article_id"])
            print(f"  [{i}/{len(travaux)}] Art. {a['article_id']} — erreur base ({type(e).__name__}: {e}), annulé.")
            continue

        if i % 10 == 0 or i == len(travaux):
            print(f"  [{i}/{len(travaux)}] progression — dernier traité : Art. {a['article_id']} ({nature})")
        time.sleep(PAUSE_ENTRE_ARTICLES_S)

    conn.close()
    print(f"\nTerminé : {reussis} article(s) ajouté(s) ou mis à jour avec leur vecteur, {len(echecs)} échec(s).")
    if echecs:
        print(f"En échec (relancez la commande pour réessayer) : {', '.join(echecs)}")
    print("Vérification conseillée : python verifier_base.py")


if __name__ == "__main__":
    main()
