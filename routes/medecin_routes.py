from flask import Blueprint, request, jsonify, render_template, session

from config.database import mongo_db
from services import medecin_service
from services.medecin_service import get_consultations_medecin

medecin_bp = Blueprint('medecin', __name__)

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
    return render_template('medecin_consultations.html', consultations=consultations)