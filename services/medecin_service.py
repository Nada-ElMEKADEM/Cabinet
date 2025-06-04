from config.database import mongo_db

def add_consultation(consultation_data):
    result = mongo_db.consultations.insert_one(consultation_data)
    return str(result.inserted_id)