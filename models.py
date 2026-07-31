"""
models.py — Schéma SQLite de la plateforme Bensa
-------------------------------------------------
Tables :
- entreprise : compte entreprise agricole (avec cycle d'essai 14 jours et une offre à deposer)
- etudiant   : compte étudiant (gratuit à vie)
- offre      : offres de stage publiées par les entreprises
- candidature: candidatures des étudiants sur les offres
- paiement   : preuves de paiement soumises par les entreprises
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("DATABASE_PATH", "instance/bensa.db")


def get_connection():
    """Retourne une connexion SQLite avec row_factory activé."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Initialise la base de données (à exécuter une fois au démarrage)."""
    conn = get_connection()
    c = conn.cursor()

    # --- Table entreprise ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS entreprise (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        nom               TEXT NOT NULL,
        email             TEXT UNIQUE NOT NULL,
        mot_de_passe_hash TEXT NOT NULL,
        telephone         TEXT,
        secteur_agricole  TEXT,
        description       TEXT,
        adresse           TEXT,
        date_inscription  TEXT NOT NULL,
        date_fin_essai    TEXT NOT NULL,
        statut            TEXT NOT NULL DEFAULT 'en_essai',
        publier_offre     INTEGER NOT NULL DEFAULT 0,       
        relance_envoyee   INTEGER NOT NULL DEFAULT 0,
        derniere_connexion TEXT
    );
    """)

    # --- Table etudiant ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS etudiant (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        nom               TEXT NOT NULL,
        prenom            TEXT NOT NULL,
        email             TEXT UNIQUE NOT NULL,
        mot_de_passe_hash TEXT NOT NULL,
        telephone         TEXT,
        ecole             TEXT,
        filiere           TEXT,
        niveau            TEXT,
        cv_url            TEXT,
        cv_public_id      TEXT,
        date_inscription  TEXT NOT NULL,
        derniere_connexion TEXT
    );
    """)

    # --- Table offre ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS offre (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        entreprise_id  INTEGER NOT NULL,
        titre          TEXT NOT NULL,
        description    TEXT NOT NULL,
        lieu           TEXT,
        duree          TEXT,
        competences    TEXT,
        date_publication TEXT NOT NULL,
        statut         TEXT NOT NULL DEFAULT 'ouverte',
        FOREIGN KEY (entreprise_id) REFERENCES entreprise(id) ON DELETE CASCADE
    );
    """)

    # --- Table candidature ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS candidature (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        offre_id       INTEGER NOT NULL,
        etudiant_id    INTEGER NOT NULL,
        message        TEXT,
        statut         TEXT NOT NULL DEFAULT 'envoyee',
        date_envoi     TEXT NOT NULL,
        FOREIGN KEY (offre_id)   REFERENCES offre(id) ON DELETE CASCADE,
        FOREIGN KEY (etudiant_id) REFERENCES etudiant(id) ON DELETE CASCADE,
        UNIQUE (offre_id, etudiant_id)
    );
    """)

    # --- Table paiement ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS paiement (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        entreprise_id  INTEGER NOT NULL,
        montant        INTEGER NOT NULL,
        preuve_url     TEXT,
        preuve_public_id TEXT,
        reference      TEXT,
        statut         TEXT NOT NULL DEFAULT 'en_attente',
        date_envoi     TEXT NOT NULL,
        date_validation TEXT,
        FOREIGN KEY (entreprise_id) REFERENCES entreprise(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()


# ==========================================================
#  Statuts possibles (à titre documentaire)
# ==========================================================
STATUTS_ENTREPRISE   = ("en_essai", "actif", "bloque")
STATUTS_OFFRE        = ("ouverte", "cloturee")
STATUTS_CANDIDATURE  = ("envoyee", "vue", "contactee", "refusee")
STATUTS_PAIEMENT     = ("en_attente", "valide", "rejete")
