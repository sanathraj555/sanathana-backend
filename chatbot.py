import logging
from flask import Blueprint, request, jsonify, current_app

# === Initialize Chatbot Blueprint ===
chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")

# === Setup Logging ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === MongoDB Access Helper ===
def get_mongo_chatbot():
    db = current_app.mongo_chatbot
    if not db:
        logging.error("❌ MongoDB is not connected")
        raise Exception("MongoDB is not connected")
    return db

# === Route: Get Main Sections ===
@chatbot_bp.route("/sections", methods=["GET"])
def get_sections():
    try:
        db = get_mongo_chatbot()
        coll = db["sections"]
        cursor = coll.find({}, {"_id": 0, "section_name": 1})
        sections = [doc["section_name"] for doc in cursor]
        logging.info(f"✅ Sections fetched: {sections}")
        return jsonify({"sections": sections}), 200
    except Exception as e:
        logging.exception("❌ Failed to fetch sections")
        return jsonify({"error": "Failed to fetch sections"}), 500

# === Route: Get Sub-sections and/or Questions for a Section ===
@chatbot_bp.route("/section-questions", methods=["GET"])
def get_section_questions():
    section_name = request.args.get("section", "").strip()
    if not section_name:
        return jsonify({"error": "Section name is required"}), 400

    try:
        db = get_mongo_chatbot()
        coll = db["sections"]

        # 1️⃣ Direct match with section
        section = coll.find_one({"section_name": section_name})
        if section:
            sub_sections = section.get("sub_sections", [])
            questions = section.get("questions", [])
            return jsonify({
                "sub_sections": [s["sub_section_name"] for s in sub_sections],
                "questions": questions
            }), 200

        # 2️⃣ Deep recursive search in nested sub-sections
        def search_nested(subs):
            for sub in subs:
                if sub.get("sub_section_name") == section_name:
                    return sub
                nested = sub.get("sub_sections", [])
                result = search_nested(nested)
                if result:
                    return result
            return None

        for doc in coll.find({}, {"sub_sections": 1, "_id": 0}):
            found = search_nested(doc.get("sub_sections", []))
            if found:
                return jsonify({
                    "sub_sections": [s["sub_section_name"] for s in found.get("sub_sections", [])],
                    "questions": found.get("questions", [])
                }), 200

        logging.warning(f"⚠️ Section '{section_name}' not found.")
        return jsonify({"sub_sections": [], "questions": []}), 200

    except Exception:
        logging.exception("❌ Error in section-questions")
        return jsonify({"error": "Failed to fetch section questions"}), 500

# === Route: Get Response to a Question ===
@chatbot_bp.route("/chat-response", methods=["POST"])
def chat_response():
    data = request.get_json(force=True)
    if not data or "message" not in data or "section" not in data:
        return jsonify({"error": "Invalid request. 'message' and 'section' are required."}), 400

    message = data["message"].strip().lower()
    section_name = data["section"].strip()

    try:
        db = get_mongo_chatbot()
        coll = db["sections"]

        def find_answer(questions):
            for q in questions:
                if q["question"].strip().lower() == message:
                    return q["answer"]
            return None

        # 1️⃣ Direct match with section
        section = coll.find_one({"section_name": section_name})
        if section:
            answer = find_answer(section.get("questions", []))
            if answer:
                return jsonify({"response": answer}), 200

            # 2️⃣ Search in direct sub-sections
            for sub in section.get("sub_sections", []):
                answer = find_answer(sub.get("questions", []))
                if answer:
                    return jsonify({"response": answer}), 200

            # 3️⃣ Deep recursive search
            def recursive_search(subs):
                for sub in subs:
                    answer = find_answer(sub.get("questions", []))
                    if answer:
                        return answer
                    if "sub_sections" in sub:
                        result = recursive_search(sub["sub_sections"])
                        if result:
                            return result
                return None

            answer = recursive_search(section.get("sub_sections", []))
            if answer:
                return jsonify({"response": answer}), 200

        logging.info(f"🔍 No match found for '{message}' in section '{section_name}'")
        return jsonify({"response": "Sorry, I don't have an answer for that."}), 200

    except Exception:
        logging.exception("❌ Error in chat-response")
        return jsonify({"error": "Failed to fetch response"}), 500
