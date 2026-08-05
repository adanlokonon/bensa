"""
Test direct de connexion à Supabase — à lancer avec : python test_connexion.py
Remplace uniquement la valeur de MOT_DE_PASSE ci-dessous par ton vrai mot de passe.
"""
import psycopg2

MOT_DE_PASSE = "bensa2026salo2004"

print("Longueur du mot de passe :", len(MOT_DE_PASSE))
print("Premier caractère :", repr(MOT_DE_PASSE[0]) if MOT_DE_PASSE else "VIDE")
print("Dernier caractère :", repr(MOT_DE_PASSE[-1]) if MOT_DE_PASSE else "VIDE")

try:
    conn = psycopg2.connect(
        host="aws-1-eu-west-2.pooler.supabase.com",
        port=5432,
        dbname="postgres",
        user="postgres.tbhyphwjmmnooqcmuydy",
        password=MOT_DE_PASSE,
    )
    print("✅ CONNEXION REUSSIE")
    conn.close()
except Exception as e:
    print("❌ ECHEC DE CONNEXION")
    print(type(e).__name__, ":", e)
