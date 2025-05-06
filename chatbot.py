import logging
from flask import Blueprint, request, jsonify, current_app

# ✅ Initialize Chatbot Blueprint
chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")

# ✅ Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# ✅ Helper function to handle MongoDB connection and error handling
def get_mongo_chatbot():
    mongo_chatbot = current_app.mongo_chatbot
    if mongo_chatbot is None:
        logging.error("❌ Database connection issue")
        raise Exception("Database connection issue")
    
    logging.info("✅ MongoDB connection accessed: %s", mongo_chatbot)
    return mongo_chatbot


# ✅ Fetch Main Sections (Displayed inside chatbot messages)
@chatbot_bp.route("/sections", methods=["GET"])
def get_sections():
    """Fetch all main sections available in the chatbot."""
    try:
        mongo_chatbot = get_mongo_chatbot()
        sections_collection = mongo_chatbot["sections"]
        sections = sections_collection.find({}, {"_id": 0, "section_name": 1})
        sections_list = [s["section_name"] for s in sections]
        
        logging.info("✅ Sections fetched: %s", sections_list)

        return jsonify({"sections": sections_list}), 200
    except Exception as e:
        logging.error(f"❌ Error fetching sections: {str(e)}")
        return jsonify({"error": "Failed to fetch sections"}), 500


# ✅ Fetch sub-sections or questions for a selected section
@chatbot_bp.route("/section-questions", methods=["GET"])
def get_section_questions():
    section_name = request.args.get("section", "").strip()
    if not section_name:
        return jsonify({"error": "Section name is required"}), 400

    try:
        mongo_chatbot = get_mongo_chatbot()
        sections_collection = mongo_chatbot["sections"]

        section = sections_collection.find_one({"section_name": section_name})

        if section:
            if "sub_sections" in section and section["sub_sections"]:
                return jsonify({"sub_sections": [s["sub_section_name"] for s in section["sub_sections"]]}), 200
            return jsonify({"questions": section.get("questions", [])}), 200

        parent_section = sections_collection.find_one({"sub_sections.sub_section_name": section_name})
        if parent_section:
            for sub in parent_section["sub_sections"]:
                if sub["sub_section_name"] == section_name:
                    return jsonify({
                        "sub_sections": [s["sub_section_name"] for s in sub.get("sub_sections", [])],
                        "questions": sub.get("questions", [])
                    }), 200

        def find_sub_section(sub_sections, name):
            for sub in sub_sections:
                if sub["sub_section_name"] == name:
                    return sub
                if "sub_sections" in sub:
                    found = find_sub_section(sub["sub_sections"], name)
                    if found:
                        return found
            return None

        top_level_sections = sections_collection.find({}, {"_id": 0, "sub_sections": 1})
        for section in top_level_sections:
            if "sub_sections" in section:
                found_sub_section = find_sub_section(section["sub_sections"], section_name)
                if found_sub_section:
                    return jsonify({
                        "sub_sections": [s["sub_section_name"] for s in found_sub_section.get("sub_sections", [])],
                        "questions": found_sub_section.get("questions", [])
                    }), 200

        return jsonify({"error": "Section not found"}), 404

    except Exception as e:
        logging.error(f"❌ Error fetching section questions: {str(e)}")
        return jsonify({"error": "Failed to fetch questions"}), 500


# ✅ Fetch Response for a Specific Question
@chatbot_bp.route("/chat-response", methods=["POST"])
def chatbot_reply():
    data = request.json
    if not data or "message" not in data or "section" not in data:
        return jsonify({"error": "Invalid request. 'message' and 'section' are required."}), 400

    user_input = data["message"].strip()
    selected_section = data["section"].strip()

    try:
        mongo_chatbot = get_mongo_chatbot()
        sections_collection = mongo_chatbot["sections"]

        section = sections_collection.find_one({"section_name": selected_section})
        if section and "questions" in section:
            for q in section["questions"]:
                if q["question"].strip().lower() == user_input.lower():
                    return jsonify({"response": q["answer"]}), 200

        if section and "sub_sections" in section:
            for sub in section["sub_sections"]:
                if sub["sub_section_name"] == selected_section or selected_section == sub["sub_section_name"]:
                    for q in sub.get("questions", []):
                        if q["question"].strip().lower() == user_input.lower():
                            return jsonify({"response": q["answer"]}), 200

        def search_nested_sub_sections(sub_sections):
            for sub in sub_sections:
                if sub["sub_section_name"] == selected_section:
                    for q in sub.get("questions", []):
                        if q["question"].strip().lower() == user_input.lower():
                            return jsonify({"response": q["answer"]}), 200
                if "sub_sections" in sub:
                    result = search_nested_sub_sections(sub["sub_sections"])
                    if result:
                        return result
            return None

        result = search_nested_sub_sections(section.get("sub_sections", []))
        if result:
            return result

        return jsonify({"response": "Sorry, I don't have an answer for that."}), 200

    except Exception as e:
        logging.error(f"❌ Error fetching response: {str(e)}")
        return jsonify({"error": "Failed to fetch response"}), 500
