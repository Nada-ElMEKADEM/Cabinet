from flask import Blueprint, jsonify
from services import patient_service

patient_bp = Blueprint('patient', __name__)

@patient_bp.route('/<patient_id>/consultations', methods=['GET'])
def historique(patient_id):
    consultations = patient_service.get_consultations_by_patient(patient_id)
    return jsonify(consultations)