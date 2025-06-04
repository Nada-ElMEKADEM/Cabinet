
from bson import ObjectId
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from config.database import mongo_db
from routes.admin_routes import admin_bp
from routes.medecin_routes import medecin_bp
from routes.patient_routes import patient_bp
from services.admin_service import create_patient, create_medecin, get_medecin_by_email, get_patient_by_email
from datetime import datetime, timedelta

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

        if user == 'admin' and pwd == 'admin':
            session['user'] = 'admin'
            session['email'] = None
            return redirect(url_for('admin'))

        medecin = get_medecin_by_email(user)
        if medecin and medecin.get('mot_de_passe') == pwd:
            session['user'] = 'medecin'
            session['email'] = medecin['email']
            return redirect(url_for('medecin_page', email=medecin['email']))

        patient = get_patient_by_email(user)
        if patient and patient.get('mot_de_passe') == pwd:
            session['user'] = 'patient'
            session['email'] = patient['email']
            return redirect(url_for('patient_page', email=patient['email']))

        return render_template('login.html', error='Mauvais identifiants')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('email', None)
    return redirect(url_for('login'))


@app.route('/medecin/<email>')
def medecin_page(email):
    if session.get('user') != 'medecin' or session.get('email') != email:
        flash("Accès refusé", "danger")
        return redirect(url_for('login'))

    medecin = get_medecin_by_email(email)
    return render_template('medecin.html', medecin=medecin)


@app.route('/patient/<email>')
def patient_page(email):
    if session.get('user') != 'patient' or session.get('email') != email:
        flash("Accès refusé", "danger")
        return redirect(url_for('login'))

    patient = get_patient_by_email(email)
    consultations = list(mongo_db.consultations.find({"patient_email": email}))

    for c in consultations:
        c["date"] = c.get("date", "N/A")
        c["heure"] = c.get("heure", "N/A")
        c["medecin_nom"] = c.get("medecin_nom", "N/A")
        c["specialite"] = c.get("specialite", "N/A")

    return render_template('patient.html', patient=patient, consultations=consultations)


@app.route('/admin')
def admin():
    if session.get('user') != 'admin':
        flash("Veuillez vous connecter en tant qu'admin", "warning")
        return redirect(url_for('login'))
    return render_template('admin.html')


@app.route('/')
def index():
    return redirect(url_for('login'))


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
            creneau = data['creneau']
        except KeyError:
            flash("Tous les champs sont requis", "danger")
            return redirect(url_for('book'))
        medecin = mongo_db.medecins.find_one({"_id": ObjectId(medecin_id)})

        try:
            # Format attendu : "lundi 08:00 - 10:00"
            jour_creneau, heure_debut, _, heure_fin = creneau.split()
        except Exception:
            flash("Créneau invalide", "danger")
            return redirect(url_for('book'))

        # ⚠️ Vérification si le créneau est déjà pris
        deja_pris = mongo_db.consultations.find_one({
            "medecin_id": medecin_id,
            "date": jour_creneau,
            "heure": heure_debut
        })

        if deja_pris:
            flash("⚠️ Ce créneau est déjà réservé. Veuillez en choisir un autre.", "warning")
            return redirect(url_for('book'))

        consultation = {
            "patient_email": patient_email,
            "medecin_id": medecin_id,
            "medecin_nom": f"{medecin['prenom']} {medecin['nom']}",
            "specialite": specialite,
            "date": jour_creneau,
            "heure": heure_debut,
            "heure_fin": heure_fin,
            "created_at": datetime.datetime.utcnow()
        }
        mongo_db.consultations.insert_one(consultation)



        flash("✅ Réservation confirmée", "success")
        return redirect(url_for('patient_page', email=patient_email))

    # 👇 En cas de GET, affichage du formulaire
    specialites = mongo_db.medecins.distinct("specialite")
    return render_template('book.html', specialites=specialites)

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
if __name__ == '__main__':
    app.run(debug=True)