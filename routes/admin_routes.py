from flask import Blueprint, request, jsonify
from services import admin_service

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/patient', methods=['POST'])
def add_patient():
    data = request.json
    patient_id = admin_service.add_patient(data)
    return jsonify({"msg": "Patient ajouté", "id": patient_id})

@admin_bp.route('/medecin', methods=['POST'])
def add_medecin():
    data = request.json
    medecin_id = admin_service.add_medecin(data)
    return jsonify({"msg": "Médecin ajouté", "id": medecin_id})