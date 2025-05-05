# chatbot.py
import logging
from flask import Blueprint, request, jsonify, current_app

# ✅ Initialize Chatbot Blueprint (no prefix here)
chatbot_bp = Blueprint("chatbot", __name__)

# ✅ Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ✅ Helper: Get MongoDB collection
def get_mongo_chatbot():
    mongo_chatbot = current_app.mongo_chatbot
    if not mongo_chatbot:
        logging.error("❌ Database connection issue")
        raise Exception("Database connection issue")
    return mongo_chatbot

# ✅ Endpoint: Get main sections
@chatbot_bp.route("/sections", methods=["GET"])
def get_sections():
    try:
        mongo_chatbot = get_mongo_chatbot()
        sections_collection = mongo_chatbot["sections"]
        sections_cursor = sections_collection.find({}, {"_id": 0, "section_name": 1})

        sections_list = [s["section_name"] for s in sections_cursor if "section_name" in s]

        logging.info(f"✅ Sections retrieved: {sections_list}")
        if not sections_list:
            logging.warning("⚠️ No sections found in the database.")
        return jsonify({"sections": sections_list}), 200

    except Exception as e:
        logging.error(f"❌ Error fetching sections: {e}")
        return jsonify({"error": "Failed to fetch sections"}), 500

# ✅ Endpoint: Get sub-sections or questions
@chatbot_bp.route("/section-questions", methods=["GET"])
def get_section_questions():
    section_name = request.args.get("section", "").strip()
    if not section_name:
        return jsonify({"error": "Section name is required"}), 400

    try:
        mongo_chatbot = get_mongo_chatbot()
        sections_collection = mongo_chatbot["sections"]

        # Step 1: Direct match on main section
        section = sections_collection.find_one({"section_name": section_name})
        if section:
            if section.get("sub_sections"):
                return jsonify({
                    "sub_sections": [s["sub_section_name"] for s in section["sub_sections"]]
                }), 200
            return jsonify({"questions": section.get("questions", [])}), 200

        # Step 2: Match within first-level sub-sections
        parent = sections_collection.find_one({"sub_sections.sub_section_name": section_name})
        if parent:
            for sub in parent["sub_sections"]:
                if sub["sub_section_name"] == section_name:
                    return jsonify({
                        "sub_sections": [s["sub_section_name"] for s in sub.get("sub_sections", [])],
                        "questions": sub.get("questions", [])
                    }), 200

        # Step 3: Deep nested search
        def find_nested(subs, name):
            for sub in subs:
                if sub.get("sub_section_name") == name:
                    return sub
                if "sub_sections" in sub:
                    found = find_nested(sub["sub_sections"], name)
                    if found:
                        return found
            return None

        all_secs = sections_collection.find({}, {"_id": 0, "sub_sections": 1})
        for sec in all_secs:
            if "sub_sections" in sec:
                match = find_nested(sec["sub_sections"], section_name)
                if match:
                    return jsonify({
                        "sub_sections": [s["sub_section_name"] for s in match.get("sub_sections", [])],
                        "questions": match.get("questions", [])
                    }), 200

        return jsonify({"error": "Section not found"}), 404

    except Exception as e:
        logging.error(f"❌ Error fetching section questions: {e}")
        return jsonify({"error": "Failed to fetch questions"}), 500

# ✅ Endpoint: Get chatbot response for a question
@chatbot_bp.route("/chat-response", methods=["POST"])
def chatbot_reply():
    data = request.json
    if not data or "message" not in data or "section" not in data:
        return jsonify({"error": "Invalid request. 'message' and 'section' are required."}), 400

    user_input = data["message"].strip().lower()
    selected_section = data["section"].strip()

    try:
        mongo_chatbot = get_mongo_chatbot()
        sections_collection = mongo_chatbot["sections"]

        # 1) Main section questions
        section = sections_collection.find_one({"section_name": selected_section})
        if section and section.get("questions"):
            for q in section["questions"]:
                if q["question"].strip().lower() == user_input:
                    return jsonify({"response": q["answer"]}), 200

        # 2) First-level sub-section
        if section and section.get("sub_sections"):
            for sub in section["sub_sections"]:
                if sub["sub_section_name"] == selected_section:
                    for q in sub.get("questions", []):
                        if q["question"].strip().lower() == user_input:
                            return jsonify({"response": q["answer"]}), 200

        # 3) Deep nested
        def search_nested(subs):
            for sub in subs:
                if sub["sub_section_name"] == selected_section:
                    for q in sub.get("questions", []):
                        if q["question"].strip().lower() == user_input:
                            return jsonify({"response": q["answer"]}), 200
                if "sub_sections" in sub:
                    res = search_nested(sub["sub_sections"])
                    if res:
                        return res
            return None

        res = search_nested(section.get("sub_sections", []) if section else [])
        if res:
            return res

        return jsonify({"response": "Sorry, I don't have an answer for that."}), 200

    except Exception as e:
        logging.error(f"❌ Error fetching response: {e}")
        return jsonify({"error": "Failed to fetch response"}), 500
