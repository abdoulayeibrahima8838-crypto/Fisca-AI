# -*- coding: utf-8 -*-
"""
Moteur de comprehension de Fisca AI - PHASE TEST.

Reproduit en local (sans API OpenAI) la logique decrite dans le plan :
- tolerance aux fautes de frappe
- reconnaissance de mots-cles / synonymes proches
- reponse a 3 niveaux (certaine / absence de reponse)

Ce moteur est volontairement simple : il sert a tester l'experience et le
contenu, pas a remplacer le vrai moteur GPT + File Search prevu pour la
version connectee.
"""
import re
import unicodedata
import difflib

from cache_data import QA_LIBRARY


def normaliser(texte):
    """Minuscule, sans accents, sans ponctuation - pour comparer sans se
    faire piquer par une majuscule ou un accent oublie."""
    texte = texte.lower().strip()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    texte = re.sub(r"[^\w\s]", " ", texte)
    texte = re.sub(r"\s+", " ", texte)
    return texte


def _score_entree(mots_question, entree):
    """Calcule un score de correspondance entre la question posee et une
    entree de la bibliotheque, en tolerant les fautes de frappe (distance
    de similarite) et pas seulement une correspondance exacte."""
    score = 0
    for mot_cle in entree["keywords"]:
        mot_cle_norm = normaliser(mot_cle)
        # Correspondance directe (le mot-cle, ou une partie, est dans la question)
        if mot_cle_norm in mots_question:
            score += 2
            continue
        # Tolerance aux fautes de frappe : on compare chaque mot de la
        # question a chaque mot du mot-cle, avec une similarite >= 0.8
        for mot_q in mots_question.split():
            for mot_k in mot_cle_norm.split():
                if len(mot_k) < 4:
                    continue
                ratio = difflib.SequenceMatcher(None, mot_q, mot_k).ratio()
                if ratio >= 0.8:
                    score += 1
    return score


def repondre(question_brute):
    """Retourne un dict {niveau, reponse, source, question_comprise} en
    tentant de comprendre la question meme si elle contient des fautes."""
    mots_question = normaliser(question_brute)

    meilleur = None
    meilleur_score = 0
    for entree in QA_LIBRARY:
        score = _score_entree(mots_question, entree)
        if score > meilleur_score:
            meilleur_score = score
            meilleur = entree

    if meilleur and meilleur_score >= 2:
        return {
            "niveau": 1,
            "reponse": meilleur["answer"],
            "source": meilleur["source"],
            "verified": meilleur["verified"],
            "question_comprise": meilleur["question_type"],
        }

    return {
        "niveau": 3,
        "reponse": (
            "Aucune information suffisamment precise n'a ete trouvee dans les "
            "documents actuellement integres. Essayez de reformuler, ou "
            "precisez votre question."
        ),
        "source": None,
        "verified": None,
        "question_comprise": question_brute,
    }
