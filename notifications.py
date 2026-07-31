"""
notifications.py — Gestion du cycle d'essai 14 jours (Bensa)
-------------------------------------------------------------
Approche « à la volée » (recommandée V1) :
- Vérifie le statut d'essai à chaque connexion / action entreprise.
- Envoie la relance J+12 par flash-message + journalisation (SMTP optionnel).
- Bascule le compte en « bloque » à J+15 si aucun paiement validé.

Approche cron (optionnelle) :
- La fonction tache_planifiee_quotidienne() peut être appelée par un cron
  si l'hébergement le permet (Render + service worker, ou APScheduler).
"""

from datetime import datetime, timedelta
from models import get_connection
import os
TRIAL_DURATION_DAYS = int(os.getenv("TRIAL_DURATION_DAYS", "14"))
TRIAL_REMINDER_DAY = int(os.getenv("TRIAL_REMINDER_DAY", "12"))
TRIAL_BLOCK_DAY = int(os.getenv("TRIAL_BLOCK_DAY", "15"))


def date_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parser_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def calculer_date_fin_essai(date_inscription: datetime) -> datetime:
    """Retourne date_inscription + 14 jours."""
    return date_inscription + timedelta(days=TRIAL_DURATION_DAYS)


def a_paiement_valide(entreprise_id: int) -> bool:
    """Retourne True si l'entreprise a au moins un paiement validé."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM paiement WHERE entreprise_id = ? AND statut = 'valide'",
        (entreprise_id,),
    ).fetchone()
    conn.close()
    return row["n"] > 0


def verifier_statut_entreprise(entreprise_id: int) -> dict:
    """
    Vérification « à la volée » du statut d'une entreprise.
    Retourne un dict : {statut, jours_restants, message, doit_relancer}
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT id, date_inscription, date_fin_essai, statut, relance_envoyee FROM entreprise WHERE id = ?",
        (entreprise_id,),
    ).fetchone()

    if not row:
        conn.close()
        return {"statut": "inexistant", "message": "Compte introuvable."}

    maintenant = datetime.now()
    date_fin_essai = parser_date(row["date_fin_essai"])
    date_inscription = parser_date(row["date_inscription"])
    statut_actuel = row["statut"]
    relance_envoyee = row["relance_envoyee"]
    jours_ecoules = (maintenant - date_inscription).days
    jours_restants = (date_fin_essai - maintenant).days

    resultat = {
        "statut": statut_actuel,
        "jours_restants": jours_restants,
        "jours_ecoules": jours_ecoules,
        "message": "",
        "doit_relancer": False,
    }

    # --- Cas 1 : compte déjà actif (paiement à jour) ---
    if statut_actuel == "actif":
        resultat["message"] = "Abonnement actif."
        conn.close()
        return resultat

    # --- Cas 2 : compte déjà bloqué ---
    if statut_actuel == "bloque":
        resultat["message"] = "Compte bloqué — veuillez régulariser votre paiement."
        conn.close()
        return resultat

    # --- Cas 3 : en essai — vérifier les échéances ---
    if statut_actuel == "en_essai":
        # J+15 dépassé et pas de paiement validé → blocage
        if jours_ecoules >= TRIAL_BLOCK_DAY:
            if a_paiement_valide(entreprise_id):
                conn.execute(
                    "UPDATE entreprise SET statut = 'actif' WHERE id = ?",
                    (entreprise_id,),
                )
                resultat["statut"] = "actif"
                resultat["message"] = "Paiement validé — abonnement activé."
            else:
                conn.execute(
                    "UPDATE entreprise SET statut = 'bloque' WHERE id = ?",
                    (entreprise_id,),
                )
                resultat["statut"] = "bloque"
                resultat["message"] = (
                    "Votre période d'essai est terminée. Compte bloqué — "
                    "veuillez soumettre une preuve de paiement pour réactivation."
                )
        # J+12 → relance
        elif jours_ecoules >= TRIAL_REMINDER_DAY and not relance_envoyee:
            conn.execute(
                "UPDATE entreprise SET relance_envoyee = 1 WHERE id = ?",
                (entreprise_id,),
            )
            resultat["doit_relancer"] = True
            resultat["message"] = (
                f"⚠️ Votre essai gratuit se termine dans {max(jours_restants, 0)} jour(s). "
                "Pensez à envoyer votre preuve de paiement (3 000 FCFA)."
            )
        else:
            resultat["message"] = f"Essai gratuit — {jours_restants} jour(s) restant(s)."

    conn.commit()
    conn.close()
    return resultat


def peut_publier_offre(entreprise_id: int) -> bool:
    """Vérifie qu'une entreprise a le droit de publier / consulter les CV."""
    infos = verifier_statut_entreprise(entreprise_id)
    return infos["statut"] in ("en_essai", "actif")


def tache_planifiee_quotidienne():
    """
    Approche cron (optionnelle) — à lancer une fois par jour.
    Parcourt toutes les entreprises en_essai et applique les règles.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT id FROM entreprise WHERE statut = 'en_essai'"
    ).fetchall()
    conn.close()

    resultats = []
    for r in rows:
        resultats.append((r["id"], verifier_statut_entreprise(r["id"])))
    return resultats


# ==========================================================
#  Envoi d'email (stub — à brancher sur SMTP réel si besoin)
# ==========================================================
def envoyer_email_relance(email: str, jours_restants: int) -> bool:
    """
    Stub d'envoi d'email. Sur PythonAnywhere gratuit / Render, SMTP sortant
    est souvent restreint. On journalise pour l'instant.
    """
    print(f"[EMAIL] Relance envoyée à {email} — {jours_restants} jour(s) restant(s).")
    return True
