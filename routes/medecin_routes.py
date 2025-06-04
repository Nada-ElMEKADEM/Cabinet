from flask import Blueprint, request, jsonify
from services import medecin_service

medecin_bp = Blueprint('medecin', __name__)

@medecin_bp.route('/consultation', methods=['POST'])
def add_consultation():
    data = request.json
    consultation_id = medecin_service.add_consultation(data)
    return jsonify({"msg": "Consultation ajoutée", "id": consultation_id})