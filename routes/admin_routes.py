from flask import Blueprint, request, jsonify, render_template

from config.database import mongo_db
from services import admin_service
from services.admin_service import get_all_medecins, get_all_patients

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

@admin_bp.route("/medecins")
def liste_medecins():
    users = get_all_medecins(mongo_db)
    return render_template("admin_users.html", users=users, role="Médecin")

@admin_bp.route("/patients")
def liste_patients():
    users = get_all_patients(mongo_db)
    return render_template("admin_users.html", users=users, role="Patient")