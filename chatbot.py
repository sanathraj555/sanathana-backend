import logging
from flask import Blueprint, request, jsonify, current_app

# === Initialize Chatbot Blueprint ===
chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")

# === Helper: MongoDB connection ===
def get_mongo_chatbot():
    mongo_db = current_app.mongo_chatbot
    if not mongo_db:
        logging.error("❌ Database connection issue")
        raise Exception("Database connection issue")
    return mongo_db

# === Fetch Main Sections ===
@chatbot_bp.route("/sections", methods=["GET"])
def get_sections():
    try:
        db = get_mongo_chatbot()
        coll = db["sections"]
        cursor = coll.find({}, {"_id": 0, "section_name": 1})
        sections = [doc["section_name"] for doc in cursor]
        logging.info(f"✅ Sections fetched: {sections}")
        return jsonify({"sections": sections}), 200
    except Exception:
        logging.exception("❌ Error fetching sections:")
        return jsonify({"error": "Failed to fetch sections"}), 500

# === Fetch Sub-sections or Questions ===
@chatbot_bp.route("/section-questions", methods=["GET"])
def get_section_questions():
    section_name = request.args.get("section", "").strip()
    if not section_name:
        return jsonify({"error": "Section name is required"}), 400

    try:
        db = get_mongo_chatbot()
        coll = db["sections"]

        # Try top-level section first
        section = coll.find_one({"section_name": section_name})
        if section:
            subs = section.get("sub_sections", [])
            if subs:
                names = [s["sub_section_name"] for s in subs]
                return jsonify({"sub_sections": names}), 200
            return jsonify({"questions": section.get("questions", [])}), 200

        # Recursive search in nested sub_sections
        def find_subtree(subs):
            for sub in subs:
                if sub["sub_section_name"] == section_name:
                    return sub
                deeper = sub.get("sub_sections", [])
                found = find_subtree(deeper)
                if found:
                    return found
            return None

        # Scan all documents for nested matches
        for doc in coll.find({}, {"_id": 0, "sub_sections": 1}):
            subtree = find_subtree(doc.get("sub_sections", []))
            if subtree:
                names = [s["sub_section_name"] for s in subtree.get("sub_sections", [])]
                questions = subtree.get("questions", [])
                return jsonify({"sub_sections": names, "questions": questions}), 200

        return jsonify({"error": "Section not found"}), 404

    except Exception:
        logging.exception("❌ Error fetching section questions:")
        return jsonify({"error": "Failed to fetch section questions"}), 500

# === Fetch Chatbot Response ===
@chatbot_bp.route("/chat-response", methods=["POST"])
def chat_response():
    data = request.get_json(force=True)
    if not data or "message" not in data or "section" not in data:
        return jsonify({"error": "Invalid request. 'message' and 'section' are required."}), 400

    user_msg = data["message"].strip().lower()
    section_name = data["section"].strip()

    try:
        db = get_mongo_chatbot()
        coll = db["sections"]

        # Helper to match a list of question dicts
        def match(questions):
            for q in questions:
                if q["question"].strip().lower() == user_msg:
                    return q["answer"]
            return None

        # Check top-level questions
        section = coll.find_one({"section_name": section_name})
        if section:
            ans = match(section.get("questions", []))
            if ans:
                return jsonify({"response": ans}), 200

            # Check immediate sub-sections
            for sub in section.get("sub_sections", []):
                ans = match(sub.get("questions", []))
                if ans:
                    return jsonify({"response": ans}), 200

            # Deep recursive search
            def deep_search(subs):
                for sub in subs:
                    ans = match(sub.get("questions", []))
                    if ans:
                        return ans
                    deeper = sub.get("sub_sections", [])
                    result = deep_search(deeper)
                    if result:
                        return result
                return None

            ans = deep_search(section.get("sub_sections", []))
            if ans:
                return jsonify({"response": ans}), 200

        return jsonify({"response": "Sorry, I don't have an answer for that."}), 200

    except Exception:
        logging.exception("❌ Error in chat-response:")
        return jsonify({"error": "Failed to fetch response"}), 500
