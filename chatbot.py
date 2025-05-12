import os
import logging
import urllib.parse
from flask import Blueprint, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv

# === Load environment variables ===
load_dotenv()

# === Logging Configuration ===
logging.basicConfig(level=logging.INFO)

# === Initialize Chatbot Blueprint ===
chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")

# === MongoDB URI from Azure or .env ===
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://sanathana-mongodb:m1ErbvRoj8vA4M3tD56mvNTEch5tasOIP0mrvfxBtqiTZYNdEVz172UeCa5qK1YI5J8xZSItPwYNACDbmUcvzw%3D%3D@sanathana-mongodb.mongo.cosmos.azure.com:10255/?ssl=true&retrywrites=false&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@sanathana-mongodb@"
)

# === MongoDB Connection ===
try:
    mongo_client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
    db = mongo_client["sanathana_chatbot_v1"]
    sections_collection = db["sections"]
    logging.info("✅ Connected to MongoDB: sanathana_chatbot_v1")
except Exception as e:
    logging.error(f"❌ MongoDB Connection Error: {e}")
    sections_collection = None

# === Route: Get Main Sections ===
@chatbot_bp.route("/sections", methods=["GET"])
def get_sections():
    if sections_collection is None:
        return jsonify({"error": "Database connection issue"}), 500

    try:
        sections = sections_collection.find({}, {"_id": 0, "section_name": 1})
        return jsonify({"sections": [s["section_name"] for s in sections]})
    except Exception as e:
        logging.error(f"❌ Error fetching sections: {str(e)}")
        return jsonify({"error": "Failed to fetch sections"}), 500

# === Route: Get Sub-sections and/or Questions ===
@chatbot_bp.route("/section-questions", methods=["GET"])
def get_section_questions():
    if sections_collection is None:
        return jsonify({"error": "Database connection issue"}), 500

    section_name = request.args.get("section", "").strip()
    if not section_name:
        return jsonify({"error": "Section name is required"}), 400

    try:
        section = sections_collection.find_one({"section_name": section_name})
        if section:
            if "sub_sections" in section and section["sub_sections"]:
                return jsonify({"sub_sections": [s["sub_section_name"] for s in section["sub_sections"]]})
            return jsonify({"questions": section.get("questions", [])})

        # Fallback to nested search
        parent = sections_collection.find_one({"sub_sections.sub_section_name": section_name})
        if parent:
            for sub in parent["sub_sections"]:
                if sub["sub_section_name"] == section_name:
                    return jsonify({
                        "sub_sections": [s["sub_section_name"] for s in sub.get("sub_sections", [])],
                        "questions": sub.get("questions", [])
                    })

        def find_sub_section(subs, name):
            for sub in subs:
                if sub.get("sub_section_name") == name:
                    return sub
                if "sub_sections" in sub:
                    found = find_sub_section(sub["sub_sections"], name)
                    if found:
                        return found
            return None

        all_docs = sections_collection.find({}, {"_id": 0, "sub_sections": 1})
        for doc in all_docs:
            found = find_sub_section(doc.get("sub_sections", []), section_name)
            if found:
                return jsonify({
                    "sub_sections": [s["sub_section_name"] for s in found.get("sub_sections", [])],
                    "questions": found.get("questions", [])
                })

        return jsonify({"error": "Section not found"}), 404

    except Exception as e:
        logging.error(f"❌ Error fetching section questions: {str(e)}")
        return jsonify({"error": "Failed to fetch questions"}), 500

# === Route: Get Answer for a User Question ===
@chatbot_bp.route("/chat-response", methods=["POST"])
def chatbot_reply():
    if sections_collection is None:
        return jsonify({"error": "Database connection issue"}), 500

    data = request.json
    if not data or "message" not in data or "section" not in data:
        return jsonify({"error": "Invalid request. 'message' and 'section' are required."}), 400

    question = data["message"].strip().lower()
    section_name = data["section"].strip()

    try:
        section = sections_collection.find_one({"section_name": section_name})
        if section:
            for q in section.get("questions", []):
                if q["question"].strip().lower() == question:
                    return jsonify({"response": q["answer"]})
            for sub in section.get("sub_sections", []):
                for q in sub.get("questions", []):
                    if q["question"].strip().lower() == question:
                        return jsonify({"response": q["answer"]})

            def recursive(subs):
                for sub in subs:
                    for q in sub.get("questions", []):
                        if q["question"].strip().lower() == question:
                            return jsonify({"response": q["answer"]})
                    if "sub_sections" in sub:
                        result = recursive(sub["sub_sections"])
                        if result:
                            return result
                return None

            return recursive(section.get("sub_sections", [])) or jsonify({"response": "Sorry, I don't have an answer for that."})
        return jsonify({"response": "Sorry, section not found."})

    except Exception as e:
        logging.error(f"❌ Error fetching response: {str(e)}")
        return jsonify({"error": "Failed to fetch response"}), 500
