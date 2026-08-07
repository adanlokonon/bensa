"""
app.py — Application Flask principale de la plateforme Bensa
-------------------------------------------------------------
Ben-Stage-Agro : mise en relation entreprises agricoles ↔ étudiants.
Édition Lancement — 14 jours d'essai gratuit pour les entreprises.

Auteur : CODEMASTER
"""

import os
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, abort, jsonify, g
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

from models import init_db, get_connection
from security import (
    hasher_mot_de_passe, verifier_mot_de_passe,
    valider_email, valider_mot_de_passe, nettoyer_texte,
    login_requis, rate_limit, reinitialiser_rate_limit,
    connecter_utilisateur, deconnecter_utilisateur,
)
from notifications import (
    verifier_statut_entreprise, peut_publier_offre,
    calculer_date_fin_essai, date_iso,
)

# --- Cloudinary (optionnel — l'app fonctionne sans si non configuré) ---
try:
    import cloudinary
    import cloudinary.uploader
    CLOUDINARY_DISPO = bool(os.getenv("CLOUDINARY_CLOUD_NAME"))
    if CLOUDINARY_DISPO:
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True,
        )
except ImportError:
    CLOUDINARY_DISPO = False


# ==========================================================
#  Configuration Flask
# ==========================================================
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key-change-me")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 Mo max upload
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Protection CSRF sur tous les formulaires
csrf = CSRFProtect(app)

# Initialisation de la base au démarrage
with app.app_context():
    init_db()


# ==========================================================
#  Injections globales dans les templates
# ==========================================================
@app.context_processor
def inject_globals():
    return {
        "annee_courante": datetime.now().year,
        "contact_email": os.getenv("CONTACT_EMAIL", "jesukpegosalomon@gmail.com"),
        "contact_whatsap": os.getenv("CONTACT_WHATSAP", "47843499"),
        "payment_phone": os.getenv("PAYMENT_PHONE", "01 64 23 96 51"),
        "montant_abonnement": os.getenv("SUBSCRIPTION_AMOUNT_FCFA", "3000"),
        "session_role": session.get("user_role"),
        "session_nom": session.get("user_nom"),
        "session_user_id": session.get("user_id"),
    }


# ==========================================================
#  Pages publiques
# ==========================================================
@app.route("/")
def accueil():
    conn = get_connection()
    nb_offres = conn.execute("SELECT COUNT(*) AS n FROM offre WHERE statut='ouverte'").fetchone()["n"]
    nb_etudiants = conn.execute("SELECT COUNT(*) AS n FROM etudiant").fetchone()["n"]
    nb_entreprises = conn.execute("SELECT COUNT(*) AS n FROM entreprise").fetchone()["n"]
    conn.close()
    return render_template(
        "accueil.html",
        nb_offres=nb_offres,
        nb_etudiants=nb_etudiants,
        nb_entreprises=nb_entreprises,
    )


@app.route("/tarifs")
def tarifs():
    return render_template("tarifs.html")


@app.route("/a-propos")
def a_propos():
    return render_template("a_propos.html")


@app.route("/connexion")
def connexion_choix():
    return render_template("connexion_choix.html")


@app.route("/inscription")
def inscription_choix():
    return render_template("inscription_choix.html")


# ==========================================================
#  Inscription entreprise
# ==========================================================
@app.route("/inscription/entreprise", methods=["GET", "POST"])
def inscription_entreprise():
    if request.method == "POST":
        nom = nettoyer_texte(request.form.get("nom", ""), 100)
        email = nettoyer_texte(request.form.get("email", ""), 120).lower()
        mot_de_passe = request.form.get("password", "")
        telephone = nettoyer_texte(request.form.get("telephone", ""), 30)
        secteur = nettoyer_texte(request.form.get("secteur_agricole", ""), 100)
        description = nettoyer_texte(request.form.get("description", ""), 1000)
        adresse = nettoyer_texte(request.form.get("adresse", ""), 200)

        if not nom or not email or not mot_de_passe:
            flash("Tous les champs obligatoires doivent être remplis.", "danger")
            return render_template("inscription_entreprise.html", form=request.form)

        if not valider_email(email):
            flash("Adresse email invalide.", "danger")
            return render_template("inscription_entreprise.html", form=request.form)

        ok, msg = valider_mot_de_passe(mot_de_passe)
        if not ok:
            flash(msg, "danger")
            return render_template("inscription_entreprise.html", form=request.form)

        maintenant = datetime.now()
        date_fin = calculer_date_fin_essai(maintenant)

        conn = get_connection()
        try:
            row = conn.execute(
                """INSERT INTO entreprise
                   (nom, email, mot_de_passe_hash, telephone, secteur_agricole,
                    description, adresse, date_inscription, date_fin_essai, statut)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'en_essai')
                   RETURNING id""",
                (nom, email, hasher_mot_de_passe(mot_de_passe), telephone,
                 secteur, description, adresse, date_iso(maintenant), date_iso(date_fin))
            ).fetchone()
            new_id = row["id"]
            conn.commit()
        except Exception:
            conn.rollback()
            conn.close()
            flash("Cet email est déjà utilisé par une autre entreprise.", "danger")
            return render_template("inscription_entreprise.html", form=request.form)
        conn.close()

        connecter_utilisateur(new_id, "entreprise", nom)
        flash(
            "Bienvenue sur Bensa ! Votre essai gratuit de 14 jours démarre maintenant. "
            f"Fin d'essai prévue le {date_fin.strftime('%d/%m/%Y')}.",
            "success"
        )
        return redirect(url_for("tableau_bord_entreprise"))

    return render_template("inscription_entreprise.html", form={})


# ==========================================================
#  Inscription étudiant
# ==========================================================
@app.route("/inscription/etudiant", methods=["GET", "POST"])
def inscription_etudiant():
    if request.method == "POST":
        nom = nettoyer_texte(request.form.get("nom", ""), 100)
        prenom = nettoyer_texte(request.form.get("prenom", ""), 100)
        email = nettoyer_texte(request.form.get("email", ""), 120).lower()
        mot_de_passe = request.form.get("password", "")
        telephone = nettoyer_texte(request.form.get("telephone", ""), 30)
        ecole = nettoyer_texte(request.form.get("ecole", ""), 150)
        filiere = nettoyer_texte(request.form.get("filiere", ""), 100)
        niveau = nettoyer_texte(request.form.get("niveau", ""), 50)

        if not nom or not prenom or not email or not mot_de_passe:
            flash("Tous les champs obligatoires doivent être remplis.", "danger")
            return render_template("inscription_etudiant.html", form=request.form)

        if not valider_email(email):
            flash("Adresse email invalide.", "danger")
            return render_template("inscription_etudiant.html", form=request.form)

        ok, msg = valider_mot_de_passe(mot_de_passe)
        if not ok:
            flash(msg, "danger")
            return render_template("inscription_etudiant.html", form=request.form)

        conn = get_connection()
        try:
            row = conn.execute(
                """INSERT INTO etudiant
                   (nom, prenom, email, mot_de_passe_hash, telephone, ecole, filiere, niveau, date_inscription)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (nom, prenom, email, hasher_mot_de_passe(mot_de_passe),
                 telephone, ecole, filiere, niveau, date_iso(datetime.now()))
            ).fetchone()
            new_id = row["id"]
            conn.commit()
        except Exception:
            conn.rollback()
            conn.close()
            flash("Cet email est déjà utilisé.", "danger")
            return render_template("inscription_etudiant.html", form=request.form)
        conn.close()

        connecter_utilisateur(new_id, "etudiant", f"{prenom} {nom}")
        flash("Compte créé avec succès ! Bienvenue sur Bensa.", "success")
        return redirect(url_for("espace_etudiant"))

    return render_template("inscription_etudiant.html", form={})


# ==========================================================
#  Connexion
# ==========================================================
@app.route("/connexion/entreprise", methods=["GET", "POST"])
def connexion_entreprise():
    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        if not rate_limit(f"login_ent:{ip}", max_tentatives=5, fenetre_sec=300):
            flash("Trop de tentatives — veuillez réessayer dans 5 minutes.", "danger")
            return render_template("connexion_entreprise.html")

        email = nettoyer_texte(request.form.get("email", ""), 120).lower()
        mot_de_passe = request.form.get("password", "")

        conn = get_connection()
        row = conn.execute("SELECT * FROM entreprise WHERE email = %s", (email,)).fetchone()

        if not row or not verifier_mot_de_passe(row["mot_de_passe_hash"], mot_de_passe):
            conn.close()
            flash("Email ou mot de passe incorrect.", "danger")
            return render_template("connexion_entreprise.html")

        conn.execute("UPDATE entreprise SET derniere_connexion=%s WHERE id=%s",
                     (date_iso(datetime.now()), row["id"]))
        conn.commit()
        conn.close()

        reinitialiser_rate_limit(f"login_ent:{ip}")
        connecter_utilisateur(row["id"], "entreprise", row["nom"])

        # Vérification à la volée du statut d'essai
        infos = verifier_statut_entreprise(row["id"])
        if infos.get("doit_relancer"):
            flash(infos["message"], "warning")
        elif infos["statut"] == "bloque":
            flash(infos["message"], "danger")
        else:
            flash(f"Bienvenue {row['nom']} ! {infos['message']}", "success")

        return redirect(url_for("tableau_bord_entreprise"))

    return render_template("connexion_entreprise.html")


@app.route("/connexion/etudiant", methods=["GET", "POST"])
def connexion_etudiant():
    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        if not rate_limit(f"login_etu:{ip}", max_tentatives=5, fenetre_sec=300):
            flash("Trop de tentatives — veuillez réessayer dans 5 minutes.", "danger")
            return render_template("connexion_etudiant.html")

        email = nettoyer_texte(request.form.get("email", ""), 120).lower()
        mot_de_passe = request.form.get("mot_de_passe", "")

        conn = get_connection()
        row = conn.execute("SELECT * FROM etudiant WHERE email = %s", (email,)).fetchone()

        if not row or not verifier_mot_de_passe(row["mot_de_passe_hash"], mot_de_passe):
            conn.close()
            flash("Email ou mot de passe incorrect.", "danger")
            return render_template("connexion_etudiant.html")

        conn.execute("UPDATE etudiant SET derniere_connexion=%s WHERE id=%s",
                     (date_iso(datetime.now()), row["id"]))
        conn.commit()
        conn.close()

        reinitialiser_rate_limit(f"login_etu:{ip}")
        connecter_utilisateur(row["id"], "etudiant", f"{row['prenom']} {row['nom']}")
        flash(f"Bienvenue {row['prenom']} !", "success")
        return redirect(url_for("espace_etudiant"))

    return render_template("connexion_etudiant.html")


@app.route("/deconnexion")
def deconnexion():
    deconnecter_utilisateur()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("accueil"))


# ==========================================================
#  Espace entreprise
# ==========================================================
@app.route("/entreprise")
@login_requis(role="entreprise")
def tableau_bord_entreprise():
    eid = session["user_id"]
    infos = verifier_statut_entreprise(eid)

    conn = get_connection()
    entreprise = conn.execute("SELECT * FROM entreprise WHERE id=%s", (eid,)).fetchone()
    offres = conn.execute(
        "SELECT * FROM offre WHERE entreprise_id=%s ORDER BY date_publication DESC",
        (eid,)
    ).fetchall()
    candidatures = conn.execute("""
        SELECT c.*, o.titre AS offre_titre, e.nom AS etudiant_nom, e.prenom AS etudiant_prenom,
               e.email AS etudiant_email, e.cv_url AS etudiant_cv
        FROM candidature c
        JOIN offre o ON o.id = c.offre_id
        JOIN etudiant e ON e.id = c.etudiant_id
        WHERE o.entreprise_id = %s
        ORDER BY c.date_envoi DESC
    """, (eid,)).fetchall()
    conn.close()

    return render_template(
        "tableau_bord_entreprise.html",
        entreprise=entreprise,
        offres=offres,
        candidatures=candidatures,
        infos_essai=infos,
    )


@app.route("/entreprise/publier-offre", methods=["GET", "POST"])
@login_requis(role="entreprise")
def publier_offre():
    eid = session["user_id"]
    if not peut_publier_offre(eid):
        flash("Votre compte est bloqué. Veuillez régulariser votre paiement.", "danger")
        return redirect(url_for("abonnement_entreprise"))

    conn = get_connection()
    entreprise = conn.execute("SELECT statut FROM entreprise WHERE id=%s", (eid,)).fetchone()

    if entreprise["statut"] == "en_essai":
        nb_offres = conn.execute(
            "SELECT COUNT(*) AS n FROM offre WHERE entreprise_id=%s", (eid,)
        ).fetchone()["n"]
        if nb_offres >= 1:
            conn.close()
            flash(
                "Vous avez atteint la limite d'une offre pendant votre essai gratuit. "
                "Passez à l'abonnement pour publier davantage d'offres.",
                "warning"
            )
            return redirect(url_for("abonnement_entreprise"))
    conn.close()

    if request.method == "POST":
        titre = nettoyer_texte(request.form.get("titre", ""), 150)
        description = nettoyer_texte(request.form.get("description", ""), 2000)
        lieu = nettoyer_texte(request.form.get("lieu", ""), 150)
        duree = nettoyer_texte(request.form.get("duree", ""), 60)
        competences = nettoyer_texte(request.form.get("competences", ""), 500)

        if not titre or not description:
            flash("Le titre et la description sont obligatoires.", "danger")
            return render_template("publier_offre.html", form=request.form)

        conn = get_connection()
        conn.execute(
            """INSERT INTO offre (entreprise_id, titre, description, lieu, duree, competences, date_publication)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (eid, titre, description, lieu, duree, competences, date_iso(datetime.now()))
        )
        conn.commit()
        conn.close()
        flash("Offre publiée avec succès !", "success")
        return redirect(url_for("tableau_bord_entreprise"))

    return render_template("publier_offre.html", form={})
@app.route("/entreprise/offre/<int:offre_id>/cloturer", methods=["POST"])
@login_requis(role="entreprise")
def cloturer_offre(offre_id):
    eid = session["user_id"]
    conn = get_connection()
    row = conn.execute("SELECT * FROM offre WHERE id=%s AND entreprise_id=%s", (offre_id, eid)).fetchone()
    if not row:
        conn.close()
        abort(404)
    conn.execute("UPDATE offre SET statut='cloturee' WHERE id=%s", (offre_id,))
    conn.commit()
    conn.close()
    flash("Offre clôturée.", "info")
    return redirect(url_for("tableau_bord_entreprise"))


@app.route("/entreprise/candidature/<int:cid>/statut", methods=["POST"])
@login_requis(role="entreprise")
def maj_statut_candidature(cid):
    nouveau_statut = request.form.get("statut", "")
    if nouveau_statut not in ("envoyee", "vue", "contactee", "refusee"):
        abort(400)
    eid = session["user_id"]
    conn = get_connection()
    # Vérifier que la candidature appartient bien à une offre de cette entreprise
    row = conn.execute("""
        SELECT c.id FROM candidature c
        JOIN offre o ON o.id = c.offre_id
        WHERE c.id = %s AND o.entreprise_id = %s
    """, (cid, eid)).fetchone()
    if not row:
        conn.close()
        abort(403)
    conn.execute("UPDATE candidature SET statut=%s WHERE id=%s", (nouveau_statut, cid))
    conn.commit()
    conn.close()
    flash("Statut de la candidature mis à jour.", "success")
    return redirect(url_for("tableau_bord_entreprise"))


@app.route("/entreprise/liste-cv")
@login_requis(role="entreprise")
def liste_cv():
    eid = session["user_id"]
    if not peut_publier_offre(eid):
        flash("Votre compte est bloqué — accès aux CV désactivé.", "danger")
        return redirect(url_for("abonnement_entreprise"))

    conn = get_connection()
    etudiants = conn.execute(
        "SELECT id, prenom, nom, ecole, filiere, niveau, cv_url, email FROM etudiant WHERE cv_url IS NOT NULL ORDER BY date_inscription DESC"
    ).fetchall()
    conn.close()
    return render_template("liste_cv.html", etudiants=etudiants)


# ==========================================================
#  Abonnement & paiement manuel
# ==========================================================
@app.route("/entreprise/abonnement", methods=["GET", "POST"])
@login_requis(role="entreprise")
def abonnement_entreprise():
    eid = session["user_id"]
    conn = get_connection()
    entreprise = conn.execute("SELECT * FROM entreprise WHERE id=%s", (eid,)).fetchone()
    paiements = conn.execute(
        "SELECT * FROM paiement WHERE entreprise_id=%s ORDER BY date_envoi DESC",
        (eid,)
    ).fetchall()

    if request.method == "POST":
        reference = nettoyer_texte(request.form.get("reference", ""), 100)
        preuve_url = None
        preuve_public_id = None

        fichier = request.files.get("preuve")
        if fichier and fichier.filename:
            if CLOUDINARY_DISPO:
                try:
                    up = cloudinary.uploader.upload(
                        fichier,
                        folder="bensa/preuves",
                        resource_type="auto",
                    )
                    preuve_url = up.get("secure_url")
                    preuve_public_id = up.get("public_id")
                except Exception as e:
                    flash(f"Erreur upload preuve : {e}", "danger")
            else:
                flash("Cloudinary non configuré — la preuve n'a pas été stockée.", "warning")

        conn.execute("""
            INSERT INTO paiement (entreprise_id, montant, preuve_url, preuve_public_id,
                                  reference, statut, date_envoi)
            VALUES (%s, %s, %s, %s, %s, 'en_attente', %s)
        """, (eid, int(os.getenv("SUBSCRIPTION_AMOUNT_FCFA", "3000")),
              preuve_url, preuve_public_id, reference, date_iso(datetime.now())))
        conn.commit()
        conn.close()

        flash("Preuve de paiement envoyée — en attente de validation par CODEMASTER.", "success")
        return redirect(url_for("confirmation_paiement"))

    conn.close()
    return render_template(
        "abonnement_entreprise.html",
        entreprise=entreprise,
        paiements=paiements,
    )


@app.route("/entreprise/paiement/confirmation")
@login_requis(role="entreprise")
def confirmation_paiement():
    return render_template("confirmation_paiement.html")


# ==========================================================
#  Espace étudiant
# ==========================================================
@app.route("/etudiant")
@login_requis(role="etudiant")
def espace_etudiant():
    eid = session["user_id"]
    conn = get_connection()
    etudiant = conn.execute("SELECT * FROM etudiant WHERE id=%s", (eid,)).fetchone()
    candidatures = conn.execute("""
        SELECT c.*, o.titre AS offre_titre, o.lieu AS offre_lieu, e.nom AS entreprise_nom
        FROM candidature c
        JOIN offre o ON o.id = c.offre_id
        JOIN entreprise e ON e.id = o.entreprise_id
        WHERE c.etudiant_id = %s
        ORDER BY c.date_envoi DESC
    """, (eid,)).fetchall()
    conn.close()
    return render_template("espace_etudiant.html", etudiant=etudiant, candidatures=candidatures)


@app.route("/etudiant/depot-cv", methods=["GET", "POST"])
@login_requis(role="etudiant")
def depot_cv():
    eid = session["user_id"]
    if request.method == "POST":
        fichier = request.files.get("cv")
        if not fichier or not fichier.filename:
            flash("Veuillez sélectionner un fichier PDF.", "danger")
            return redirect(url_for("depot_cv"))

        if not fichier.filename.lower().endswith((".pdf", ".doc", ".docx")):
            flash("Format non autorisé — uniquement PDF ou Word.", "danger")
            return redirect(url_for("depot_cv"))

        if not CLOUDINARY_DISPO:
            flash("Cloudinary non configuré — impossible de stocker le CV. "
                  "Veuillez renseigner les clés dans le fichier .env.", "warning")
            return redirect(url_for("depot_cv"))

        try:
            up = cloudinary.uploader.upload(
                fichier,
                folder="bensa/cv",
                resource_type="auto",
            )
            cv_url = up.get("secure_url")
            public_id = up.get("public_id")

            conn = get_connection()
            conn.execute(
                "UPDATE etudiant SET cv_url=%s, cv_public_id=%s WHERE id=%s",
                (cv_url, public_id, eid)
            )
            conn.commit()
            conn.close()
            flash("CV déposé avec succès !", "success")
            return redirect(url_for("espace_etudiant"))
        except Exception as e:
            flash(f"Erreur lors de l'upload : {e}", "danger")
            return redirect(url_for("depot_cv"))

    return render_template("depot_cv.html")


@app.route("/etudiant/candidature/<int:cid>")
@login_requis(role="etudiant")
def candidature_statut(cid):
    eid = session["user_id"]
    conn = get_connection()
    cand = conn.execute("""
        SELECT c.*, o.titre AS offre_titre, o.description AS offre_description, o.lieu AS offre_lieu,
               e.nom AS entreprise_nom, e.email AS entreprise_email
        FROM candidature c
        JOIN offre o ON o.id = c.offre_id
        JOIN entreprise e ON e.id = o.entreprise_id
        WHERE c.id = %s AND c.etudiant_id = %s
    """, (cid, eid)).fetchone()
    conn.close()
    if not cand:
        abort(404)
    return render_template("candidature_statut.html", cand=cand)


# ==========================================================
#  Offres publiques & candidatures
# ==========================================================
@app.route("/offres")
def liste_offres_stage():
    q = nettoyer_texte(request.args.get("q", ""), 100)
    conn = get_connection()
    if q:
        rows = conn.execute("""
            SELECT o.*, e.nom AS entreprise_nom
            FROM offre o JOIN entreprise e ON e.id = o.entreprise_id
            WHERE o.statut='ouverte'
              AND (o.titre LIKE %s OR o.description LIKE %s OR o.lieu LIKE %s)
            ORDER BY o.date_publication DESC
        """, (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    else:
        rows = conn.execute("""
            SELECT o.*, e.nom AS entreprise_nom
            FROM offre o JOIN entreprise e ON e.id = o.entreprise_id
            WHERE o.statut='ouverte'
            ORDER BY o.date_publication DESC
        """).fetchall()
    conn.close()
    return render_template("liste_offres_stage.html", offres=rows, recherche=q)


@app.route("/offres/<int:offre_id>")
def detail_offre(offre_id):
    conn = get_connection()
    offre = conn.execute("""
        SELECT o.*, e.nom AS entreprise_nom, e.secteur_agricole, e.description AS entreprise_desc,
               e.email AS entreprise_email
        FROM offre o JOIN entreprise e ON e.id = o.entreprise_id
        WHERE o.id = %s
    """, (offre_id,)).fetchone()
    conn.close()
    if not offre:
        abort(404)
    # A-t-il déjà candidaté %s
    deja_candidate = False
    if session.get("user_role") == "etudiant":
        conn = get_connection()
        r = conn.execute(
            "SELECT id FROM candidature WHERE offre_id=%s AND etudiant_id=%s",
            (offre_id, session["user_id"])
        ).fetchone()
        conn.close()
        deja_candidate = r is not None
    return render_template("detail_offre.html", offre=offre, deja_candidate=deja_candidate)


@app.route("/offres/<int:offre_id>/candidater", methods=["POST"])
@login_requis(role="etudiant")
def candidater(offre_id):
    eid = session["user_id"]
    message = nettoyer_texte(request.form.get("message", ""), 1000)

    conn = get_connection()
    etu = conn.execute("SELECT cv_url FROM etudiant WHERE id=%s", (eid,)).fetchone()
    if not etu or not etu["cv_url"]:
        conn.close()
        flash("Vous devez déposer votre CV avant de candidater.", "warning")
        return redirect(url_for("depot_cv"))

    offre = conn.execute("SELECT id FROM offre WHERE id=%s AND statut='ouverte'", (offre_id,)).fetchone()
    if not offre:
        conn.close()
        flash("Cette offre n'est plus disponible.", "danger")
        return redirect(url_for("liste_offres_stage"))

    try:
        conn.execute(
            "INSERT INTO candidature (offre_id, etudiant_id, message, statut, date_envoi) VALUES (%s, %s, %s, 'envoyee', %s)",
            (offre_id, eid, message, date_iso(datetime.now()))
        )
        conn.commit()
        flash("Candidature envoyée avec succès !", "success")
    except Exception:
        flash("Vous avez déjà candidaté à cette offre.", "warning")
    conn.close()
    return redirect(url_for("detail_offre", offre_id=offre_id))


# ==========================================================
#  Handlers d'erreurs
# ==========================================================
@app.errorhandler(404)
def erreur_404(e):
    return render_template("erreur.html", code=404,
                           message="La page demandée est introuvable."), 404


@app.errorhandler(403)
def erreur_403(e):
    return render_template("erreur.html", code=403,
                           message="Accès refusé."), 403


@app.errorhandler(500)
def erreur_500(e):
    return render_template("erreur.html", code=500,
                           message="Erreur serveur — veuillez réessayer plus tard."), 500


# ==========================================================
#  Lancement local
# ==========================================================
if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_ENV") == "development",
            host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
from flask import Response

@app.route('/sitemap.xml')
def sitemap():
    base = 'https://bensa.onrender.com'
    pages = [
        {'loc': f'{base}/', 'priority': '1.0'},
        {'loc': f'{base}/detail_offres', 'priority': '0.9'},
        {'loc': f'{base}/tarifs', 'priority': '0.8'},
        {'loc': f'{base}/a_propos', 'priority': '0.6'},
        {'loc': f'{base}/inscription_entreprise', 'priority': '0.7'},
        {'loc': f'{base}/inscription_etudiant', 'priority': '0.7'},
    ]

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for page in pages:
        xml += '  <url>\n'
        xml += f'    <loc>{page["loc"]}</loc>\n'
        xml += f'    <priority>{page["priority"]}</priority>\n'
        xml += '  </url>\n'
    xml += '</urlset>'

    return Response(xml, mimetype='application/xml')