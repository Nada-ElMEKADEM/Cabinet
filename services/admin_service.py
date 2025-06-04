from datetime import datetime

from config.database import mongo_db, neo4j_driver


def create_patient(nom, prenom, email, numero=None, mot_de_passe=None):
    try:
        patient_data = {
            "nom": nom,
            "prenom": prenom,
            "email": email,
            "numero": numero,
            "mot_de_passe": mot_de_passe
        }
        result = mongo_db.patients.insert_one(patient_data)
        patient_id = str(result.inserted_id)

        with neo4j_driver.session() as session:
            session.run("""
                CREATE (p:Patient {
                    id: $id,
                    nom: $nom,
                    prenom: $prenom,
                    email: $email,
                    numero: $numero
                })""",
                id=patient_id, nom=nom, prenom=prenom, email=email, numero=numero
            )
        return True, "Patient créé"
    except Exception as e:
        return False, str(e)


def create_medecin(nom, prenom, email, specialite=None, horaires=None, mot_de_passe=None):
    try:
        # Si les paramètres viennent d'un dictionnaire (cas de create_medecin_route)
        if isinstance(nom, dict):
            data = nom
            nom = data.get('nom')
            prenom = data.get('prenom')
            email = data.get('email')
            specialite = data.get('specialite')
            horaires = data.get('horaires', {})
            mot_de_passe = data.get('mot_de_passe')

        # Validation des champs obligatoires
        if not all([nom, prenom, email, mot_de_passe, specialite]):
            return False, "Tous les champs obligatoires doivent être fournis"

        # Préparation des données pour MongoDB
        medecin_data = {
            "nom": nom,
            "prenom": prenom,
            "email": email,
            "specialite": specialite,
            "horaires": horaires or {},
            "mot_de_passe": mot_de_passe

        }

        # Insertion dans MongoDB
        result = mongo_db.medecins.insert_one(medecin_data)
        medecin_id = str(result.inserted_id)

        # Création dans Neo4j
        with neo4j_driver.session() as session:
            session.run("""
                CREATE (m:Medecin {
                    id: $id,
                    nom: $nom,
                    prenom: $prenom,
                    email: $email,
                    specialite: $specialite
                })""",
                id=medecin_id,
                nom=nom,
                prenom=prenom,
                email=email,
                specialite=specialite
            )

        return True, medecin_id

    except Exception as e:
        print(f"Erreur dans create_medecin: {str(e)}")
        return False, str(e)

def get_medecin_by_email(email):
    medecin = mongo_db.medecins.find_one({"email": email})
    if medecin:
        medecin['_id'] = str(medecin['_id'])
    return medecin


def get_patient_by_email(email):
    patient = mongo_db.patients.find_one({"email": email})
    if patient:
        patient['_id'] = str(patient['_id'])
    return patient
