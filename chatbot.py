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

# === Route: Get Sub-sections or Questions ===
@chatbot_bp.route("/section-questions", methods=["GET"])
def get_section_questions():
    section_name = request.args.get("section", "").strip()
    if not section_name:
        return jsonify({"error": "Section name is required"}), 400

    try:
        db = get_mongo_chatbot()
        coll = db["sections"]

        # 1️⃣ Direct match
        section = coll.find_one({"section_name": section_name})
        if section:
            sub_sections = section.get("sub_sections", [])
            if sub_sections:
                return jsonify({
                    "sub_sections": [s["sub_section_name"] for s in sub_sections]
                }), 200
            return jsonify({
                "questions": section.get("questions", [])
            }), 200

        # 2️⃣ Deep search for nested match
        def search_nested(subs):
            for sub in subs:
                if sub["sub_section_name"] == section_name:
                    return sub
                if "sub_sections" in sub:
                    found = search_nested(sub["sub_sections"])
                    if found:
                        return found
            return None

        for doc in coll.find({}, {"sub_sections": 1, "_id": 0}):
            found = search_nested(doc.get("sub_sections", []))
            if found:
                return jsonify({
                    "sub_sections": [s["sub_section_name"] for s in found.get("sub_sections", [])],
                    "questions": found.get("questions", [])
                }), 200

        return jsonify({"error": "Section not found"}), 404

    except Exception:
        logging.exception("❌ Error in section-questions")
        return jsonify({"error": "Failed to fetch section questions"}), 500

# === Route: Get Answer to a Question ===
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

        # 1️⃣ Top-level section match
        section = coll.find_one({"section_name": section_name})
        if section:
            ans = find_answer(section.get("questions", []))
            if ans:
                return jsonify({"response": ans}), 200

            # 2️⃣ Check direct sub-sections
            for sub in section.get("sub_sections", []):
                ans = find_answer(sub.get("questions", []))
                if ans:
                    return jsonify({"response": ans}), 200

            # 3️⃣ Deep recursive search
            def recursive_search(subs):
                for sub in subs:
                    ans = find_answer(sub.get("questions", []))
                    if ans:
                        return ans
                    if "sub_sections" in sub:
                        result = recursive_search(sub["sub_sections"])
                        if result:
                            return result
                return None

            ans = recursive_search(section.get("sub_sections", []))
            if ans:
                return jsonify({"response": ans}), 200

        return jsonify({"response": "Sorry, I don't have an answer for that."}), 200

    except Exception:
        logging.exception("❌ Error in chat-response")
        return jsonify({"error": "Failed to fetch response"}), 500
