import calendar
import os

import bcrypt
from bson import ObjectId
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config.database import mongo_db, neo4j_driver
from routes.admin_routes import admin_bp
from routes.medecin_routes import medecin_bp
from routes.patient_routes import patient_bp
from services.admin_service import create_patient, create_medecin, get_medecin_by_email, get_patient_by_email
from datetime import datetime, timedelta

from services.medecin_service import get_consultations_medecin

app = Flask(__name__)
app.secret_key = 'change_this_secret'

# Enregistrement des blueprints
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(medecin_bp, url_prefix='/medecin')
app.register_blueprint(patient_bp, url_prefix='/patient')


# Routes pour la création depuis le formulaire admin
@app.route('/patient', methods=['POST'])
def create_patient_route():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Aucune donnée reçue"}), 400

        required_fields = ['nom', 'prenom', 'email', 'mot_de_passe']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"error": f"Le champ '{field}' est requis"}), 400

        # Appel à la fonction de création du patient
        success, result = create_patient(
            nom=data['nom'],
            prenom=data['prenom'],
            email=data['email'],
            numero=data.get('numero'),
            mot_de_passe=data['mot_de_passe']
        )

        if not success:
            return jsonify({"error": result}), 400

        return jsonify({
            "msg": "Patient créé avec succès",
            "id": result
        }), 201

    except Exception as e:
        print(f"Erreur lors de la création du patient: {str(e)}")
        return jsonify({"error": f"Erreur serveur: {str(e)}"}), 500
@app.route('/profil')
def profil_patient():
    if session.get('user') != 'patient' or 'email' not in session:
        flash("Accès refusé", "danger")
        return redirect(url_for('login'))

    email = session['email'].strip().lower()
    patient = get_patient_by_email(email)

    if not patient:
        flash("Patient introuvable", "danger")
        return redirect(url_for('patient_page', email=email))

    # Requête insensible à la casse
    consultations = list(mongo_db.consultations.find({
        "patient_email": {"$regex": f"^{email}$", "$options": "i"}
    }))

    # Calculs dynamiques
    total = len(consultations)
    en_cours = sum(1 for c in consultations if c.get("statut") == "en_cours")
    terminees = sum(1 for c in consultations if c.get("statut") == "terminee")
    annulees = sum(1 for c in consultations if c.get("statut") == "annule")

    return render_template(
        "profil.html",
        patient=patient,
        total=total,
        en_cours=en_cours,
        terminees=terminees,
        annulees=annulees,
    )

@app.route('/profil_medecin')
def profil_medecin():
    if session.get('user_type') != 'medecin' or 'email' not in session:
        flash("Accès refusé", "danger")
        return redirect(url_for('login'))

    email = session['email'].strip().lower()
    print("Email du médecin connecté :", email)

    medecin = get_medecin_by_email(email)
    if not medecin:
        flash("Médecin introuvable", "danger")
        return redirect(url_for('login'))

    # Récupération des consultations via la fonction
    consultations = get_consultations_medecin(medecin['_id'])

    print("Nombre de consultations trouvées :", len(consultations))

    # Statistiques
    total = len(consultations)
    en_cours = sum(1 for c in consultations if c.get("statut") == "en_cours")
    terminees = sum(1 for c in consultations if c.get("statut") == "terminee")
    annulees = sum(1 for c in consultations if c.get("statut") == "annule")

    return render_template(
        'profil_medecin.html',
        medecin=medecin,
        consultations=consultations,
        total=total,
        en_cours=en_cours,
        terminees=terminees,
        annulees=annulees
    )


@app.route('/modifier_profil', methods=['GET', 'POST'])
def modifier_profil():
    if 'email' not in session:
        return redirect(url_for('login'))

    email_session = session['email']
    patient = get_patient_by_email(email_session)

    if request.method == 'POST':
        # Récupération des champs du formulaire
        nom = request.form.get('nom')
        prenom = request.form.get('prenom')
        new_email = request.form.get('email')
        numero = request.form.get('numero')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        update_fields = {
            "nom": nom,
            "prenom": prenom,
            "email": new_email,
            "numero": numero
        }

        # Si l'utilisateur veut changer son mot de passe
        if new_password or confirm_password:
            if new_password != confirm_password:
                return render_template("modifier_profil.html", patient=patient, error="Les nouveaux mots de passe ne correspondent pas.")

            mot_de_passe_hache = patient.get("mot_de_passe")
            if not current_password or not mot_de_passe_hache or not bcrypt.checkpw(current_password.encode('utf-8'), mot_de_passe_hache.encode('utf-8')):
                return render_template("modifier_profil.html", patient=patient, error="Mot de passe actuel incorrect.")

            # Hash du nouveau mot de passe
            hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            update_fields["mot_de_passe"] = hashed_new_password

        # Mise à jour dans MongoDB avec l'email en session pour identifier le patient
        mongo_db.patients.update_one({"email": email_session}, {"$set": update_fields})

        # Mise à jour de la session si l'email a changé
        if new_email != email_session:
            session['email'] = new_email

        flash("Profil mis à jour avec succès.")
        return redirect(url_for('modifier_profil'))

    return render_template("modifier_profil.html", patient=patient)




@app.route('/modifier_profil_medecin', methods=['GET', 'POST'])
def modifier_profil_medecin():
    if session.get('user') != 'medecin':
        flash("Accès refusé", "danger")
        return redirect(url_for('login'))

    email_session = session.get('email')
    medecin = get_medecin_by_email(email_session)

    if request.method == 'POST':
        # Récupération des données du formulaire
        nom = request.form.get('nom')
        prenom = request.form.get('prenom')
        email = request.form.get('email')
        specialite = request.form.get('specialite')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        update_data = {
            'nom': nom,
            'prenom': prenom,
            'email': email,
            'specialite': specialite
        }

        # Si l'utilisateur veut changer son mot de passe
        if new_password or confirm_password:
            # Vérifier que les deux mots de passe correspondent
            if new_password != confirm_password:
                return render_template('modifier_profil_medecin.html', medecin=medecin,
                                       erreur="Les nouveaux mots de passe ne correspondent pas")

            # Vérifier le mot de passe actuel
            if not current_password or not bcrypt.checkpw(current_password.encode('utf-8'), medecin['mot_de_passe'].encode('utf-8')):
                return render_template('modifier_profil_medecin.html', medecin=medecin,
                                       erreur="Mot de passe actuel incorrect")

            # Hacher le nouveau mot de passe et l'ajouter à la mise à jour
            hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            update_data['mot_de_passe'] = hashed

        # Mise à jour dans la base MongoDB
        mongo_db.medecins.update_one(
            {"email": email_session},  # On identifie par l'email de session pour éviter conflits
            {'$set': update_data}
        )

        # Mettre à jour la session email si modifié
        session['email'] = email

        # Recharger les données
        medecin.update(update_data)

        flash("Profil mis à jour avec succès", "success")
        return redirect(url_for('profil_medecin'))

    return render_template('modifier_profil_medecin.html', medecin=medecin)



@app.route('/medecin', methods=['POST'])
def create_medecin_route():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Aucune donnée reçue"}), 400

        # Validation des champs requis
        required_fields = ['nom', 'prenom', 'email', 'mot_de_passe', 'specialite']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"error": f"Le champ '{field}' est requis"}), 400

        # Récupération et validation des horaires
        horaires = data.get('horaires', {})

        if not isinstance(horaires, dict):
            return jsonify({"error": "Format des horaires invalide"}), 400

        # Nettoyer les horaires
        horaires_clean = {}
        jours_semaine = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']

        for jour in jours_semaine:
            if jour in horaires and horaires[jour]:
                creneaux_valides = [
                    creneau for creneau in horaires[jour]
                    if isinstance(creneau, dict) and 'start' in creneau and 'end' in creneau
                ]
                if creneaux_valides:
                    horaires_clean[jour] = creneaux_valides

        # Création du médecin
        success, medecin_id = create_medecin(
            nom=data['nom'],
            prenom=data['prenom'],
            email=data['email'],
            specialite=data['specialite'],
            horaires=horaires_clean,
            mot_de_passe=data['mot_de_passe']
        )

        if not success:
            return jsonify({"error": medecin_id}), 400

        return jsonify({
            "msg": "Médecin créé avec succès",
            "id": medecin_id,
            "horaires": horaires_clean
        }), 201

    except Exception as e:
        print(f"Erreur lors de la création du médecin: {str(e)}")
        return jsonify({"error": f"Erreur serveur: {str(e)}"}), 500


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']

        # Admin (non haché car défini en dur)
        if user == 'admin' and pwd == 'admin':
            session['user'] = 'admin'
            session['email'] = None
            return redirect(url_for('admin'))

        # Vérifier si utilisateur est un médecin
        medecin = get_medecin_by_email(user)
        if medecin:
            mot_de_passe_hache = medecin.get('mot_de_passe')
            if mot_de_passe_hache and bcrypt.checkpw(pwd.encode('utf-8'), mot_de_passe_hache.encode('utf-8')):
                session['user'] = 'medecin'
                session['email'] = medecin['email']
                return redirect(url_for('medecin_page', email=medecin['email']))

        # Vérifier si utilisateur est un patient
        patient = get_patient_by_email(user)
        if patient:
            mot_de_passe_hache = patient.get('mot_de_passe')
            if mot_de_passe_hache and bcrypt.checkpw(pwd.encode('utf-8'), mot_de_passe_hache.encode('utf-8')):
                session['user'] = 'patient'
                session['email'] = patient['email']
                return redirect(url_for('patient_page', email=patient['email']))

        # Mauvais identifiants
        return render_template('login.html', error='Mauvais identifiants')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("Déconnecté avec succès.", "success")
    return redirect(url_for('login'))



@app.route('/medecin/<email>')
def medecin_page(email):
    if session.get('user') != 'medecin' or session.get('email') != email:
        flash("Accès refusé", "danger")
        return redirect(url_for('login'))
    session['user_type'] = 'medecin'

    medecin = get_medecin_by_email(email)
    return render_template('medecin.html', medecin=medecin)


from datetime import datetime

@app.route('/patient/<email>')
def patient_page(email):
    if session.get('user') != 'patient' or session.get('email') != email:
        flash("Accès refusé", "danger")
        return redirect(url_for('login'))

    session['user_type'] = 'patient'
    patient = get_patient_by_email(email)
    consultations = list(mongo_db.consultations.find({"patient_email": email}))
    now = datetime.utcnow()

    for c in consultations:
        c["date"] = c.get("date", "N/A")
        c["heure"] = c.get("heure", "N/A")
        c["medecin_nom"] = c.get("medecin_nom", "N/A")
        c["specialite"] = c.get("specialite", "N/A")
        c["_id"] = str(c["_id"])

        # Convertir en datetime si ce sont des chaînes
        try:
            if isinstance(c.get("date_heure"), str):
                c["date_heure"] = datetime.fromisoformat(c["date_heure"])
        except Exception:
            c["date_heure"] = None

        try:
            if isinstance(c.get("heure_fin"), str):
                c["heure_fin"] = datetime.fromisoformat(c["heure_fin"])
        except Exception:
            c["heure_fin"] = None

        # Mise à jour du statut
        heure_fin = c.get("heure_fin")
        if c["statut"] == "en_cours" and isinstance(heure_fin, datetime) and heure_fin < now:
            mongo_db.db.consultations.update_one(
                {"_id": c["_id"]},
                {"$set": {"statut": "terminee"}}
            )
            c["statut"] = "terminee"

    return render_template('patient.html', patient=patient, consultations=consultations)


from bson import ObjectId




@app.route('/consultation/annuler_consultation/<consultation_id>')
def delete_consultation(consultation_id):
    consultation = mongo_db.consultations.find_one({"_id": ObjectId(consultation_id)})
    if consultation:
        mongo_db.consultations.update_one(
            {"_id": ObjectId(consultation_id)},
            {"$set": {"statut": "annule"}}
        )
        flash("Consultation annulée avec succès.", "info")
    return redirect(url_for('patient_page', email=session.get('email')))

@app.route('/consultation/update/<consultation_id>', methods=['GET'])
def update_consultation_form(consultation_id):
    if session.get('user') != 'patient':
        flash("Veuillez vous connecter en tant que patient", "danger")
        return redirect(url_for('login'))

    consultation = mongo_db.consultations.find_one({"_id": ObjectId(consultation_id)})
    if not consultation:
        flash("Consultation introuvable", "danger")
        return redirect(url_for('patient_page', email=session.get('email')))

    medecin = mongo_db.medecins.find_one({"_id": ObjectId(consultation['medecin_id'])})
    return render_template('update_consultation.html', consultation=consultation, medecin=medecin)


from datetime import datetime, time

@app.route('/consultation/update/submit', methods=['POST'])
def update_consultation_submit():
    if session.get('user') != 'patient':
        flash("Veuillez vous connecter en tant que patient", "danger")
        return redirect(url_for('login'))

    consultation_id = request.form.get('consultation_id')
    nouvelle_date = request.form.get('date')
    nouveau_creneau = request.form.get('creneau')

    if not consultation_id or not nouvelle_date or not nouveau_creneau:
        flash("Tous les champs sont requis.", "danger")
        return redirect(request.referrer)

    try:
        heure_debut, heure_fin = nouveau_creneau.split(' - ')
        start_datetime = datetime.strptime(f"{nouvelle_date} {heure_debut}", "%Y-%m-%d %H:%M")
        end_datetime = datetime.strptime(f"{nouvelle_date} {heure_fin}", "%Y-%m-%d %H:%M")
    except Exception as e:
        flash("Format invalide pour la date ou le créneau.", "danger")
        return redirect(request.referrer)

    consultation = mongo_db.consultations.find_one({"_id": ObjectId(consultation_id)})
    if not consultation:
        flash("Consultation non trouvée.", "danger")
        return redirect(url_for('patient_page', email=session.get('email')))

    # Vérifier si le créneau est déjà pris
    conflit = mongo_db.consultations.find_one({
        "_id": {"$ne": ObjectId(consultation_id)},
        "medecin_id": consultation['medecin_id'],
        "date_heure": start_datetime
    })
    if conflit:
        flash("⚠️ Ce créneau est déjà réservé.", "warning")
        return redirect(request.referrer)

    # Mise à jour
    mongo_db.consultations.update_one(
        {"_id": ObjectId(consultation_id)},
        {
            "$set": {
                "date_heure": start_datetime,
                "heure_fin": end_datetime
            }
        }
    )

    flash("✅ Consultation mise à jour avec succès.", "success")
    return redirect(url_for('patient_page', email=session.get('email')))


@app.route('/admin')
def admin():
    if session.get('user') != 'admin':
        flash("Veuillez vous connecter en tant qu'admin", "warning")
        return redirect(url_for('login'))
    return render_template('admin.html')


@app.route('/')
def home():
    return render_template('home.html')



@app.route('/book', methods=['GET', 'POST'])
def book():
    if session.get('user') != 'patient':
        flash("Veuillez vous connecter en tant que patient", "danger")
        return redirect(url_for('login'))
    if request.method == 'POST':
        data = request.form
        patient_email = session.get('email')
        try:
            specialite = data['specialite']
            medecin_id = data['medecin_id']
            date_choisie = data['date']  # "2025-06-15"
            creneau_selectionne = data['creneau']  # Ex: "08:00 - 10:00"
        except KeyError:
            flash("Tous les champs sont requis", "danger")
            return redirect(url_for('book'))
        medecin = mongo_db.medecins.find_one({"_id": ObjectId(medecin_id)})
        jour_semaine = calendar.day_name[datetime.strptime(date_choisie, "%Y-%m-%d").weekday()]  # ex: "Monday"
        try:
            heure_debut, heure_fin = creneau_selectionne.split(' - ')
            start_datetime = datetime.strptime(f"{date_choisie} {heure_debut}", "%Y-%m-%d %H:%M")
            end_datetime = datetime.strptime(f"{date_choisie} {heure_fin}", "%Y-%m-%d %H:%M")
        except:
            flash("Format de créneau invalide", "danger")
            return redirect(url_for('book'))
        deja_pris = mongo_db.consultations.find_one({
            "medecin_id": medecin_id,
            "date_heure": start_datetime
        })
        if deja_pris:
            flash("⚠️ Ce créneau est déjà réservé. Veuillez en choisir un autre.", "warning")
            return redirect(url_for('book'))
        consultation = {
            "patient_email": patient_email,
            "medecin_id": medecin_id,
            "medecin_nom": f"{medecin['prenom']} {medecin['nom']}",
            "specialite": specialite,
            "date_heure": start_datetime,
            "heure_fin": end_datetime,
            "created_at": datetime.utcnow(),
            "statut": "en_cours"
        }
        mongo_db.consultations.insert_one(consultation)
        flash("✅ Réservation confirmée", "success")
        return redirect(url_for('patient_page', email=patient_email))
    specialites = mongo_db.medecins.distinct("specialite")
    return render_template('book.html', specialites=specialites)
@app.route('/horaires_par_jour', methods=['GET'])
def horaires_par_jour():
    medecin_id = request.args.get('id')
    date_str = request.args.get('date') # "2025-06-15"
    if not medecin_id or not date_str:
        return jsonify([])

    try:
        jours_fr = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        jour = jours_fr[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
    except ValueError:
        return jsonify([])

    medecin = mongo_db.medecins.find_one({"_id": ObjectId(medecin_id)})

    if not medecin or "horaires" not in medecin or jour not in medecin["horaires"]:
        return jsonify([])

    horaires_jour = medecin["horaires"][jour]
    creneaux_2h = []

    for h in horaires_jour:
        start_time = datetime.strptime(h['start'], "%H:%M")
        end_time = datetime.strptime(h['end'], "%H:%M")
        current_time = start_time

        while current_time + timedelta(hours=2) <= end_time:
            creneau = {
                "start": current_time.strftime("%H:%M"),
                "end": (current_time + timedelta(hours=2)).strftime("%H:%M")
            }
            creneaux_2h.append(creneau)
            current_time += timedelta(hours=2)  # pour éviter chevauchement

    return jsonify(creneaux_2h)


@app.route('/admin/add-user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        nom = request.form['nom']
        prenom = request.form['prenom']
        email = request.form['email']
        role = request.form['role']

        # 🔄 À compléter : insérer l'utilisateur dans la base de données
        print(f"Ajout de : {nom} {prenom} ({role})")

        return redirect(url_for('admin_dashboard'))

    return render_template('add_user.html')

@app.route('/medecins_par_specialite')
def medecins_par_specialite():
    specialite = request.args.get('specialite')
    if not specialite:
        return jsonify([])

    medecins = list(mongo_db.medecins.find({"specialite": specialite}))
    for m in medecins:
        m['_id'] = str(m['_id'])
        m['nom_complet'] = f"{m.get('prenom', '')} {m.get('nom', '')}".strip()
    return jsonify(medecins)



@app.route('/horaires_medecin')
def horaires_medecin():
    medecin_id = request.args.get('id')
    if not medecin_id:
        return jsonify({})

    medecin = mongo_db.medecins.find_one({"_id": ObjectId(medecin_id)})
    if not medecin:
        return jsonify({})

    # Renvoie les horaires au format brut (objet start/end pour JS)
    horaires = medecin.get('horaires', {})
    return jsonify(horaires)
@app.route('/horaires_fixes')
def horaires_fixes():
    medecin_id = request.args.get('id')
    if not medecin_id:
        return jsonify({})

    medecin = mongo_db.medecins.find_one({"_id": ObjectId(medecin_id)})
    if not medecin:
        return jsonify({})

    horaires = medecin.get('horaires', {})
    creneaux_fixes = {}

    for jour, liste in horaires.items():
        decoupes = []
        for c in liste:
            try:
                start = datetime.strptime(c['start'], "%H:%M")
                end = datetime.strptime(c['end'], "%H:%M")
            except ValueError:
                continue  # Ignore les formats invalides

            # Découpe uniquement si le créneau fait au moins 2h
            while (end - start) >= timedelta(hours=2):
                slot_start = start.strftime("%H:%M")
                slot_end = (start + timedelta(hours=2)).strftime("%H:%M")
                decoupes.append({"start": slot_start, "end": slot_end})
                start += timedelta(hours=2)

        if decoupes:
            creneaux_fixes[jour] = decoupes

    return jsonify(creneaux_fixes)
@app.route("/medecin/delete/<email>")
def delete_medecin(email):
    try:
        medecin = mongo_db.medecins.find_one({"email": email})
        if medecin:
            mongo_db.medecins.delete_one({"email": email})
            medecin_id = str(medecin["_id"])
            with neo4j_driver.session() as session:
                session.run("MATCH (m:Medecin {id: $id}) DETACH DELETE m", id=medecin_id)
        return redirect(url_for("admin.liste_medecins"))

    except Exception as e:
        return str(e), 500

@app.route("/medecin/update/<email>")
def update_medecin_form(email):
    medecin = get_medecin_by_email(email)
    if not medecin:
        return "Médecin introuvable", 404
    return render_template("update_medecin.html", medecin=medecin)

from flask import request, redirect, url_for
from collections import defaultdict


@app.route("/medecin/update/submit", methods=["POST"])
def update_medecin_submit():
    try:
        email = request.form["email"]

        # Préparation des données de base
        updated_data = {
            "nom": request.form["nom"],
            "prenom": request.form["prenom"],
            "specialite": request.form["specialite"]
        }

        # Traitement des horaires
        horaires = {}
        for key in request.form:
            if key.startswith("horaires["):
                parts = key[9:-1].split("][")
                if len(parts) != 3:
                    continue

                jour, index, field = parts
                if jour not in horaires:
                    horaires[jour] = {}
                if index not in horaires[jour]:
                    horaires[jour][index] = {}

                horaires[jour][index][field] = request.form[key]

        # Conversion en format final (en filtrant les créneaux vides)
        horaires_final = {}
        for jour in horaires:
            horaires_final[jour] = []
            for index in horaires[jour]:
                start = horaires[jour][index].get("start", "").strip()
                end = horaires[jour][index].get("end", "").strip()

                if start and end:  # Ne garder que les créneaux valides
                    horaires_final[jour].append({
                        "start": start,
                        "end": end
                    })

        # Mise à jour MongoDB
        mongo_db.medecins.update_one(
            {"email": email},
            {
                "$set": {
                    **updated_data,
                    "horaires": horaires_final
                }
            }
        )

        # Mise à jour Neo4j (inchangée)
        medecin = mongo_db.medecins.find_one({"email": email})
        medecin_id = str(medecin["_id"])

        with neo4j_driver.session() as session:
            session.run("""
                MATCH (m:Medecin {id: $id})
                SET m.nom = $nom,
                    m.prenom = $prenom,
                    m.email = $email,
                    m.specialite = $specialite
            """, id=medecin_id,
                        nom=updated_data["nom"],
                        prenom=updated_data["prenom"],
                        email=email,
                        specialite=updated_data["specialite"])

        return redirect(url_for("admin.liste_medecins"))

    except Exception as e:
        return f"Erreur lors de la mise à jour : {str(e)}", 500



@app.route("/patient/update/<email>")
def update_patient_form(email):
    patient = get_patient_by_email(email)
    if not patient:
        return "Patient introuvable", 404
    return render_template("update_patient.html", patient=patient)
@app.route("/patient/update/submit", methods=["POST"])
def update_patient_submit():
    try:
        email = request.form["email"]
        updated_data = {
            "nom": request.form["nom"],
            "prenom": request.form["prenom"],
            "email": email,
            "numero": request.form["numero"]
        }

        # MongoDB
        mongo_db.patients.update_one({"email": email}, {"$set": updated_data})

        # Neo4j
        patient = mongo_db.patients.find_one({"email": email})
        patient_id = str(patient["_id"])

        with neo4j_driver.session() as session:
            session.run("""
                MATCH (p:Patient {id: $id})
                SET p.nom = $nom, p.prenom = $prenom, p.email = $email, p.numero = $numero
            """, id=patient_id, nom=updated_data["nom"], prenom=updated_data["prenom"],
                 email=email, numero=updated_data["numero"])

        return redirect(url_for("admin.liste_patients"))

    except Exception as e:
        return f"Erreur lors de la mise à jour : {str(e)}", 500
@app.route("/patient/delete/<email>")
def delete_patient(email):
    try:
        # MongoDB
        patient = mongo_db.patients.find_one({"email": email})
        if not patient:
            return "Patient introuvable", 404
        mongo_db.patients.delete_one({"email": email})

        # Neo4j
        patient_id = str(patient["_id"])
        with neo4j_driver.session() as session:
            session.run("MATCH (p:Patient {id: $id}) DETACH DELETE p", id=patient_id)

        return redirect(url_for("admin.liste_patients"))

    except Exception as e:
        return f"Erreur lors de la suppression : {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
