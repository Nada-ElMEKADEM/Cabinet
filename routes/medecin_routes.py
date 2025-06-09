from flask import Blueprint, request, jsonify, render_template, session
from datetime import datetime

from config.database import mongo_db
from services import medecin_service
from services.medecin_service import get_consultations_medecin

medecin_bp = Blueprint('medecin', __name__)

# Fonction utilitaire pour convertir une chaîne ISO en objet datetime
def parse_datetime_field(value):
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return value

@medecin_bp.route('/consultation', methods=['POST'])
def add_consultation():
    data = request.get_json()
    consultation_id = medecin_service.add_consultation(data)
    return jsonify({"msg": "Consultation ajoutée", "id": consultation_id})

@medecin_bp.route('/consultations')
def voir_consultations():
    if session.get('user') != 'medecin':
        return "Accès non autorisé", 403

    medecin_email = session.get('email')
    medecin = mongo_db.medecins.find_one({"email": medecin_email})
    if not medecin:
        return "Médecin introuvable", 404

    medecin_id = str(medecin['_id'])
    consultations = get_consultations_medecin(medecin_id)

    # Conversion des champs string en datetime
    for c in consultations:
        c['date_heure'] = parse_datetime_field(c.get('date_heure'))
        c['heure_fin'] = parse_datetime_field(c.get('heure_fin'))

    return render_template('medecin_consultations.html', consultations=consultations)
