from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from routes.admin_routes import admin_bp
from routes.medecin_routes import medecin_bp
from routes.patient_routes import patient_bp
from services import admin_service
from services.admin_service import create_patient, create_medecin, get_medecin_by_email, get_patient_by_email

app = Flask(__name__)
app.secret_key = 'change_this_secret'

# Enregistrement des blueprints
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(medecin_bp, url_prefix='/medecin')
app.register_blueprint(patient_bp, url_prefix='/patient')


# Routes pour la création depuis le formulaire admin
@app.route('/patient', methods=['POST'])
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

        nom = data['nom']
        prenom = data['prenom']
        email = data['email']
        numero = data.get('numero')
        mot_de_passe = data['mot_de_passe']

        # Appel à la fonction de création du patient
        success, result = create_patient(nom, prenom, email, numero, mot_de_passe)

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

        # Valider que les horaires ont un format correct
        if not isinstance(horaires, dict):
            return jsonify({"error": "Format des horaires invalide"}), 400

        # Nettoyer les horaires (supprimer les jours sans créneaux)
        horaires_clean = {}
        jours_semaine = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']

        for jour in jours_semaine:
            if jour in horaires and horaires[jour]:
                # S'assurer que chaque créneau a start et end
                creneaux_valides = []
                for creneau in horaires[jour]:
                    if isinstance(creneau, dict) and 'start' in creneau and 'end' in creneau:
                        creneaux_valides.append({
                            'start': creneau['start'],
                            'end': creneau['end']
                        })

                if creneaux_valides:
                    horaires_clean[jour] = creneaux_valides

        # Création du médecin
        medecin_data = {
            'nom': data['nom'],
            'prenom': data['prenom'],
            'email': data['email'],
            'mot_de_passe': data['mot_de_passe'],
            'specialite': data['specialite'],
            'horaires': horaires_clean
        }

        # Appel à la fonction de création
        medecin_id = create_medecin(
            data['nom'],
            data['prenom'],
            data['email'],
            data['specialite'],
            horaires_clean,
            data['mot_de_passe']
        )

        if not medecin_id[0]:  # Si la création a échoué
            return jsonify({"error": medecin_id[1]}), 400

        return jsonify({
            "msg": "Médecin créé avec succès",
            "id": medecin_id[1],  # Supposant que create_medecin retourne (True, id)
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
    return render_template('patient.html', patient=patient)


@app.route('/admin')
def admin():
    if session.get('user') != 'admin':
        flash("Veuillez vous connecter en tant qu'admin pour accéder à cette page.", "warning")
        return redirect(url_for('login'))
    return render_template('admin.html')


@app.route('/')
def index():
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)