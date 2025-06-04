from pymongo import MongoClient
from neo4j import GraphDatabase

mongo_client = MongoClient('mongodb://localhost:27017/')
mongo_db = mongo_client['cabinet_medical']

neo4j_driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "Naduda2004"))

def close_neo4j():
    neo4j_driver.close()