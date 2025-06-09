from datetime import datetime

from flask import current_app

from config.database import mongo_db, neo4j_driver
import bcrypt


def create_patient(nom, prenom, email, numero=None, mot_de_passe=None):
    try:
        # Hachage du mot de passe
        if not mot_de_passe:
            return False, "Le mot de passe est requis"
        hashed_pw = bcrypt.hashpw(mot_de_passe.encode('utf-8'), bcrypt.gensalt())

        patient_data = {
            "nom": nom,
            "prenom": prenom,
            "email": email,
            "numero": numero,
            "mot_de_passe": hashed_pw.decode('utf-8')  # Stocké en tant que string
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
        # Si les paramètres viennent d'un dictionnaire
        if isinstance(nom, dict):
            data = nom
            nom = data.get('nom')
            prenom = data.get('prenom')
            email = data.get('email')
            specialite = data.get('specialite')
            horaires = data.get('horaires', {})
            mot_de_passe = data.get('mot_de_passe')

        if not all([nom, prenom, email, mot_de_passe, specialite]):
            return False, "Tous les champs obligatoires doivent être fournis"

        # Hachage du mot de passe
        hashed_pw = bcrypt.hashpw(mot_de_passe.encode('utf-8'), bcrypt.gensalt())

        medecin_data = {
            "nom": nom,
            "prenom": prenom,
            "email": email,
            "specialite": specialite,
            "horaires": horaires or {},
            "mot_de_passe": hashed_pw.decode('utf-8')  # Stocké sous forme de chaîne
        }

        result = mongo_db.medecins.insert_one(medecin_data)
        medecin_id = str(result.inserted_id)

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

def get_all_medecins(mongo_db):
    return list(mongo_db.medecins.find())

def get_all_patients(mongo_db):
    return list(mongo_db.patients.find())