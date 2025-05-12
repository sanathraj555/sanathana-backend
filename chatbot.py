import logging
from flask import Blueprint, request, jsonify, current_app

# === Logging Configuration ===
logging.basicConfig(level=logging.INFO)

# === Initialize Chatbot Blueprint ===
chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")

# === MongoDB Access Helper ===
def get_sections_collection():
    db = current_app.mongo_chatbot
    if not db:
        logging.error("❌ MongoDB is not connected through app context.")
        raise Exception("MongoDB not connected.")
    return db["sections"]

# === Route: Get Main Sections ===
@chatbot_bp.route("/sections", methods=["GET"])
def get_sections():
    try:
        coll = get_sections_collection()
        cursor = coll.find({}, {"_id": 0, "section_name": 1})
        sections = [doc["section_name"] for doc in cursor]
        return jsonify({"sections": sections})
    except Exception as e:
        logging.exception("❌ Failed to fetch sections")
        return jsonify({"error": "Failed to fetch sections"}), 500

# === Route: Get Sub-sections and/or Questions ===
@chatbot_bp.route("/section-questions", methods=["GET"])
def get_section_questions():
    section_name = request.args.get("section", "").strip()
    if not section_name:
        return jsonify({"error": "Section name is required"}), 400

    try:
        coll = get_sections_collection()
        section = coll.find_one({"section_name": section_name})

        if section:
            if "sub_sections" in section and section["sub_sections"]:
                return jsonify({
                    "sub_sections": [s["sub_section_name"] for s in section["sub_sections"]],
                    "questions": []
                })
            return jsonify({"questions": section.get("questions", [])})

        # Fallback: look into nested sub-sections
        parent = coll.find_one({"sub_sections.sub_section_name": section_name})
        if parent:
            for sub in parent["sub_sections"]:
                if sub["sub_section_name"] == section_name:
                    return jsonify({
                        "sub_sections": [s["sub_section_name"] for s in sub.get("sub_sections", [])],
                        "questions": sub.get("questions", [])
                    })

        # Deep recursive search
        def find_nested(subs):
            for sub in subs:
                if sub.get("sub_section_name") == section_name:
                    return sub
                if "sub_sections" in sub:
                    found = find_nested(sub["sub_sections"])
                    if found:
                        return found
            return None

        for doc in coll.find({}, {"sub_sections": 1}):
            found = find_nested(doc.get("sub_sections", []))
            if found:
                return jsonify({
                    "sub_sections": [s["sub_section_name"] for s in found.get("sub_sections", [])],
                    "questions": found.get("questions", [])
                })

        return jsonify({"error": "Section not found"}), 404

    except Exception as e:
        logging.exception("❌ Error in section-questions")
        return jsonify({"error": "Failed to fetch questions"}), 500

# === Route: Get Answer for a Question ===
@chatbot_bp.route("/chat-response", methods=["POST"])
def chatbot_reply():
    data = request.get_json(force=True)
    if not data or "message" not in data or "section" not in data:
        return jsonify({"error": "Invalid request. 'message' and 'section' are required."}), 400

    question = data["message"].strip().lower()
    section_name = data["section"].strip()

    try:
        coll = get_sections_collection()
        section = coll.find_one({"section_name": section_name})

        def match_question(questions):
            for q in questions:
                if q["question"].strip().lower() == question:
                    return q["answer"]
            return None

        if section:
            answer = match_question(section.get("questions", []))
            if answer:
                return jsonify({"response": answer})

            for sub in section.get("sub_sections", []):
                answer = match_question(sub.get("questions", []))
                if answer:
                    return jsonify({"response": answer})

                def deep_search(subs):
                    for sub in subs:
                        ans = match_question(sub.get("questions", []))
                        if ans:
                            return ans
                        if "sub_sections" in sub:
                            result = deep_search(sub["sub_sections"])
                            if result:
                                return result
                    return None

                answer = deep_search(sub.get("sub_sections", []))
                if answer:
                    return jsonify({"response": answer})

        return jsonify({"response": "Sorry, I don't have an answer for that."})

    except Exception as e:
        logging.exception("❌ Error in chat-response")
        return jsonify({"error": "Failed to fetch response"}), 500
