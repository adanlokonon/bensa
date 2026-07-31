"""
security.py — Couches de sécurité de la plateforme Bensa
--------------------------------------------------------
- Hachage / vérification des mots de passe (Werkzeug PBKDF2)
- Décorateurs de contrôle d'accès (login requis, entreprise, étudiant)
- Validation des entrées (email, mot de passe fort)
- Rate limiting basique en mémoire (anti brute force)
"""

import re
import time
from functools import wraps
from collections import defaultdict, deque
from flask import session, redirect, url_for, flash, request, abort
from werkzeug.security import generate_password_hash, check_password_hash


# ==========================================================
#  Hachage des mots de passe
# ==========================================================
def hasher_mot_de_passe(mot_de_passe: str) -> str:
    """Retourne le hash PBKDF2-SHA256 salé."""
    return generate_password_hash(mot_de_passe, method="pbkdf2:sha256", salt_length=16)


def verifier_mot_de_passe(hash_stocke: str, mot_de_passe: str) -> bool:
    """Vérifie qu'un mot de passe correspond au hash stocké."""
    if not hash_stocke or not mot_de_passe:
        return False
    return check_password_hash(hash_stocke, mot_de_passe)


# ==========================================================
#  Validation des entrées utilisateur
# ==========================================================
REGEX_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def valider_email(email: str) -> bool:
    if not email or len(email) > 120:
        return False
    return bool(REGEX_EMAIL.match(email.strip()))


def valider_mot_de_passe(mot_de_passe: str) -> tuple[bool, str]:
    """Un mot de passe doit contenir >=8 caractères, 1 chiffre, 1 lettre."""
    if not mot_de_passe or len(mot_de_passe) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères."
    if not re.search(r"[A-Za-z]", mot_de_passe):
        return False, "Le mot de passe doit contenir au moins une lettre."
    if not re.search(r"\d", mot_de_passe):
        return False, "Le mot de passe doit contenir au moins un chiffre."
    return True, ""


def nettoyer_texte(texte: str, longueur_max: int = 500) -> str:
    """Nettoyage basique — évite les entrées vides et trop longues."""
    if not texte:
        return ""
    return texte.strip()[:longueur_max]


# ==========================================================
#  Décorateurs de contrôle d'accès
# ==========================================================
def login_requis(role: str | None = None):
    """
    Décorateur : vérifie qu'un utilisateur est connecté.
    role = 'entreprise' | 'etudiant' | None (peu importe)
    """
    def wrapper(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session or "user_role" not in session:
                flash("Veuillez vous connecter pour accéder à cette page.", "warning")
                return redirect(url_for("connexion_choix"))
            if role and session.get("user_role") != role:
                flash("Accès refusé — vous n'avez pas les droits nécessaires.", "danger")
                return redirect(url_for("accueil"))
            return view(*args, **kwargs)
        return wrapped
    return wrapper


# ==========================================================
#  Rate limiting (protection anti brute-force)
# ==========================================================
_tentatives = defaultdict(lambda: deque(maxlen=10))


def rate_limit(cle: str, max_tentatives: int = 5, fenetre_sec: int = 300) -> bool:
    """
    Retourne True si l'action est autorisée, False si trop de tentatives.
    Utilisation : rate_limit(f"login:{ip}")
    """
    maintenant = time.time()
    q = _tentatives[cle]
    # Purge les vieilles entrées
    while q and (maintenant - q[0]) > fenetre_sec:
        q.popleft()
    if len(q) >= max_tentatives:
        return False
    q.append(maintenant)
    return True


def reinitialiser_rate_limit(cle: str):
    _tentatives.pop(cle, None)


# ==========================================================
#  Helpers session
# ==========================================================
def connecter_utilisateur(user_id: int, role: str, nom_affichage: str):
    session.clear()
    session["user_id"] = user_id
    session["user_role"] = role
    session["user_nom"] = nom_affichage
    session.permanent = True


def deconnecter_utilisateur():
    session.clear()
