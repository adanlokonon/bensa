"""
models.py — Schéma PostgreSQL (Supabase) de la plateforme Bensa
Tables :
- entreprise : compte entreprise agricole (avec cycle d'essai 14 jours)
- etudiant   : compte étudiant (gratuit à vie)
- offre      : offres de stage publiées par les entreprises
- candidature: candidatures des étudiants sur les offres
- paiement   : preuves de paiement soumises par les entreprises
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")


class ConnWrapper:
    """
    Petit adaptateur pour garder une syntaxe proche de sqlite3 :
    conn.execute(sql, params).fetchone() / .fetchall()
    au lieu de devoir gérer un curseur séparé partout dans app.py.
    """
    def __init__(self, pg_conn):
        self._conn = pg_conn
        self._cursor = pg_conn.cursor()

    def execute(self, sql, params=None):
        # Convertit les placeholders "?" (style SQLite) en "%s" (style psycopg2) si jamais oubliés
        self._cursor.execute(sql, params or ())
        return self._cursor

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._cursor.close()
        self._conn.close()


def get_connection():
    """Retourne un wrapper de connexion PostgreSQL, utilisable comme l'ancienne connexion sqlite3."""
    pg_conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return ConnWrapper(pg_conn)


def init_db():
    """Initialise la base de données (à exécuter une fois au démarrage)."""
    conn = get_connection()

    # --- Table entreprise ---
    conn.execute("""
    CREATE TABLE IF NOT EXISTS entreprise (
        id                SERIAL PRIMARY KEY,
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
        offres_utilisees  INTEGER NOT NULL DEFAULT 0,
        relance_envoyee   INTEGER NOT NULL DEFAULT 0,
        derniere_connexion TEXT
    );
    """)

    # --- Table etudiant ---
    conn.execute("""
    CREATE TABLE IF NOT EXISTS etudiant (
        id                SERIAL PRIMARY KEY,
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
    conn.execute("""
    CREATE TABLE IF NOT EXISTS offre (
        id             SERIAL PRIMARY KEY,
        entreprise_id  INTEGER NOT NULL REFERENCES entreprise(id) ON DELETE CASCADE,
        titre          TEXT NOT NULL,
        description    TEXT NOT NULL,
        lieu           TEXT,
        duree          TEXT,
        competences    TEXT,
        date_publication TEXT NOT NULL,
        statut         TEXT NOT NULL DEFAULT 'ouverte'
    );
    """)

    # --- Table candidature ---
    conn.execute("""
    CREATE TABLE IF NOT EXISTS candidature (
        id             SERIAL PRIMARY KEY,
        offre_id       INTEGER NOT NULL REFERENCES offre(id) ON DELETE CASCADE,
        etudiant_id    INTEGER NOT NULL REFERENCES etudiant(id) ON DELETE CASCADE,
        message        TEXT,
        statut         TEXT NOT NULL DEFAULT 'envoyee',
        date_envoi     TEXT NOT NULL,
        UNIQUE (offre_id, etudiant_id)
    );
    """)

    # --- Table paiement ---
    conn.execute("""
    CREATE TABLE IF NOT EXISTS paiement (
        id             SERIAL PRIMARY KEY,
        entreprise_id  INTEGER NOT NULL REFERENCES entreprise(id) ON DELETE CASCADE,
        montant        INTEGER NOT NULL,
        preuve_url     TEXT,
        preuve_public_id TEXT,
        reference      TEXT,
        statut         TEXT NOT NULL DEFAULT 'en_attente',
        date_envoi     TEXT NOT NULL,
        date_validation TEXT
    );
    """)

    conn.commit()
    conn.close()


# ==========================================================
# Statuts possibles (à titre documentaire)
# ==========================================================
STATUTS_ENTREPRISE   = ("en_essai", "actif", "bloque")
STATUTS_OFFRE        = ("ouverte", "cloturee")
STATUTS_CANDIDATURE  = ("envoyee", "vue", "contactee", "refusee")
STATUTS_PAIEMENT     = ("en_attente", "valide", "rejete")