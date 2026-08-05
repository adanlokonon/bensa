# 🌾 Bensa — Ben-Stage-Agro

**Bensa** est une plateforme web de mise en relation entre les **entreprises agricoles** et les **étudiants stagiaires**.
Développée par **CODEMASTER**, Édition Lancement — Offre 14 jours gratuits.

---

## 📋 Sommaire

1. [Fonctionnalités](#-fonctionnalités)
2. [Stack technique](#-stack-technique)
3. [Structure du projet](#-structure-du-projet)
4. [Installation locale](#-installation-locale)
5. [Configuration Cloudinary](#-configuration-cloudinary)
6. [Règle métier — essai 14 jours](#-règle-métier--essai-14-jours)
7. [Déploiement sur Render](#-déploiement-sur-render)
8. [Sécurité](#-sécurité)
9. [Roadmap V2](#-roadmap-v2)
10. [Contact](#-contact)

---

## ✨ Fonctionnalités

### V1 — Livrée

- ✅ Inscription à deux profils (entreprise / étudiant)
- ✅ Déclenchement automatique de l'essai 14 jours (entreprise)
- ✅ Vérification « à la volée » du statut d'essai à chaque connexion
- ✅ Publication d'offres de stage (entreprise)
- ✅ Dépôt de CV en ligne via Cloudinary (étudiant)
- ✅ Consultation & recherche d'offres
- ✅ Candidature avec suivi de statut (envoyée / vue / contactée / refusée)
- ✅ Paiement manuel par preuve (Mobile Money) + réactivation
- ✅ Tableau de bord entreprise (publier, clôturer, gérer les candidatures)
- ✅ Design sobre & pro, responsive mobile
- ✅ Sécurité de base (hachage PBKDF2, CSRF, sessions HTTPOnly, rate-limit, validation)
- ✅ Footer « Créé par CODEMASTER » sur toutes les pages

---

## 🛠 Stack technique

- **Backend** : Python 3.11+ / Flask 3
- **Base de données** : PostgreSQL (Supabase)
- **Sécurité** : Flask-WTF (CSRF), Werkzeug (PBKDF2)
- **Stockage fichiers** : Cloudinary (CV & preuves de paiement)
- **Templates** : Jinja2
- **Frontend** : HTML5 + CSS externe (aucun framework JS)
- **Déploiement** : Gunicorn + Render (via `render.yaml`)

---

## 📂 Structure du projet

```
bensa/
├── app.py                  # Application Flask principale, toutes les routes
├── models.py               # Schéma PostgreSQL
├── security.py             # Hachage, CSRF, rate-limit, décorateurs
├── notifications.py        # Cycle d'essai 14 jours (J+12, J+15)
├── requirements.txt
├── render.yaml             # Config Render.com
├── Procfile
├── .env.example            # Variables d'environnement (à copier en .env)
├── .gitignore
├── README.md
├── instance/
│   └── bensa.db            # Créée automatiquement au démarrage
├── static/
│   ├── css/style.css       # Feuille de style unique
│   └── images/hero_agriculture.jpg
└── templates/
    ├── base.html
    ├── accueil.html
    ├── inscription_choix.html
    ├── inscription_entreprise.html
    ├── inscription_etudiant.html
    ├── connexion_choix.html
    ├── connexion_entreprise.html
    ├── connexion_etudiant.html
    ├── tarifs.html
    ├── a_propos.html
    ├── tableau_bord_entreprise.html
    ├── publier_offre.html
    ├── liste_cv.html
    ├── abonnement_entreprise.html
    ├── confirmation_paiement.html
    ├── espace_etudiant.html
    ├── depot_cv.html
    ├── liste_offres_stage.html
    ├── detail_offre.html
    ├── candidature_statut.html
    └── erreur.html
```

---

## 🚀 Installation locale

### 1. Cloner et créer l'environnement

```bash
git clone <votre-url>
cd bensa
python3 -m venv .venv
source .venv/bin/activate    # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurer les variables d'environnement

```bash
cp .env.example .env
# Puis éditer .env et renseigner :
# - SECRET_KEY (générer une longue chaîne aléatoire)
# - CLOUDINARY_CLOUD_NAME / API_KEY / API_SECRET (voir plus bas)
```

### 3. Lancer

```bash
python app.py
```

L'application démarre sur http://localhost:5000

La base SQLite `instance/bensa.db` est créée automatiquement.

---

## ☁ Configuration Cloudinary

Le dépôt de CV et les preuves de paiement passent par [Cloudinary](https://cloudinary.com) (offre gratuite suffisante).

1. Créer un compte gratuit sur https://cloudinary.com/users/register/free
2. Dans le dashboard, récupérer :
   - `Cloud Name`
   - `API Key`
   - `API Secret`
3. Les copier dans le fichier `.env` :

```
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

> Sans Cloudinary, l'app fonctionne, mais le dépôt de CV est désactivé.

---

## ⏰ Règle métier — essai 14 jours

Cycle de vie d'un compte entreprise :

| Jour | Statut | Accès |
|------|--------|-------|
| J0 | `en_essai` | Accès complet — début des 14 jours gratuits |
| J12 | `en_essai` | Notification de relance envoyée |
| J15 | `bloque` (si non payé) | Profil visible, publication & CV désactivés |
| J15 | `actif` (si payé) | Accès complet — abonnement en cours |

**Approche « à la volée » (recommandée V1)** — implémentée dans `notifications.py`.

À chaque connexion ou action d'une entreprise, `verifier_statut_entreprise()` compare la date du jour à `date_fin_essai` :
- Si J+15 dépassé et aucun paiement validé → passage automatique en `bloque`
- Si J+12 atteint et pas de relance envoyée → notification + flag `relance_envoyee = 1`

**Cette approche ne dépend d'aucun service externe** et garantit que le blocage est appliqué dès la première requête suivant l'échéance — parfait pour un hébergement gratuit type Render.

Approche cron optionnelle disponible : appeler `notifications.tache_planifiee_quotidienne()`.

---

## 🌐 Déploiement sur Render

### Étape 1 — Créer le dépôt GitHub

```bash
git init
git add .
git commit -m "Initial commit — Bensa V1"
git branch -M main
git remote add origin https://github.com/<votre-user>/bensa.git
git push -u origin main
```

### Étape 2 — Créer le service Render

1. Aller sur https://dashboard.render.com/
2. **New +** → **Web Service** → connecter le dépôt GitHub `bensa`
3. Render détecte automatiquement `render.yaml` — accepter la config
4. Dans l'onglet **Environment** du service, ajouter manuellement :
   - `CLOUDINARY_CLOUD_NAME`
   - `CLOUDINARY_API_KEY`
   - `CLOUDINARY_API_SECRET`
5. Cliquer **Deploy**

### Étape 3 — Vérifier

- URL de l'app : `https://bensa.onrender.com`
- Logs : onglet **Logs** du service Render
- Base SQLite : elle est créée automatiquement dans `instance/bensa.db` sur le disque Render

> ⚠️ Attention : sur l'offre gratuite Render, le disque n'est PAS persistant à 100 %. Pour la production, prévoir un disque persistant (payant) ou migrer vers PostgreSQL (roadmap V2).

---

## 🔒 Sécurité

- **Mots de passe** : hachés en PBKDF2-SHA256 avec sel via `werkzeug.security`
- **CSRF** : protection globale via `Flask-WTF` sur tous les formulaires POST
- **Sessions** : cookies `HttpOnly`, `SameSite=Lax`, durée 7 jours
- **Rate limit** : max 5 tentatives de connexion / 5 min / IP
- **Validation** : email regex + mot de passe fort (8+ car, lettre + chiffre)
- **Upload** : taille max 5 Mo, extensions PDF/DOC/DOCX/image contrôlées
- **SQL** : requêtes paramétrées (aucune interpolation directe)

---

## 🗺 Roadmap V2

- 📬 Messagerie interne (au-delà du mailto)
- 👮 Modération / validation des comptes entreprise (interface admin)
- 📧 Notifications email enrichies (nouvelle offre, changement de statut)
- 💳 Paiement automatisé (Mobile Money via agrégateur)
- 🗄 Migration vers PostgreSQL pour la production

---

## 📞 Contact

**CODEMASTER** — Développement web & solutions numériques

- Email : jesukpegosalomon@gmail.com
- Téléphone (paiement d'abonnement) : 01 64 23 96 51

---

*Créé par CODEMASTER — 2026*
