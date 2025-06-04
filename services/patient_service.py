from config.database import mongo_db

def get_consultations_by_patient(patient_id):
    consultations = list(mongo_db.consultations.find({"patient_id": patient_id}))
    for c in consultations:
        c['_id'] = str(c['_id'])
    return consultations