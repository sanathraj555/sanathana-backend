import os
import logging
import time
from datetime import datetime
import calendar
from openai import OpenAI
from flask import Blueprint, request, jsonify, current_app
from kb_content import knowledge_text

# === Configure DeepSeek ===
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
MODEL_NAME = "deepseek-chat"

# Initialize OpenAI client
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    timeout=200
)


# === Flask Setup ===
chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Simple cache
RESPONSE_CACHE = {
    "who are the founders of sanathana?": "Founders: Sri Ranganatha Raju, Srinatha Raju, Sainatha Raju",
    "when was sanathana founded?": "Founded in 2017",
    "what is sanathana?": "Sanathana Analytics is a rural tech company providing recruitment, research, and e-commerce services."
}



# === Ask DeepSeek with caching and Excel fallback ===
def ask_deepseek(user_question):
    try:
        user_question = user_question.strip()
        lower_question = user_question.lower()

        # 1. Check cache
        if lower_question in RESPONSE_CACHE:
            return RESPONSE_CACHE[lower_question]

        
       # 2. System prompt with knowledge base
        system_content = (
            "You are a concise Sanathana assistant. Prioritize brevity but adapt response length to the query.\n"
            "Rules:\n"
            "1. Use ONLY this knowledge: \n\n" + knowledge_text + "\n\n"
            "2. If answer isn't here, say 'I don't have that information'\n"
            "3. Be direct - no intros/outros\n"
            "4. Present key facts in minimal words\n"
            "5. Use simple language\n"
            "6. For list-based queries (e.g. birthdays):\n"
            "   - Use bullet points\n"
            "   - Omit full sentences\n"
            "   - Group similar items\n"
            "   - No line breaks between items\n"
            )

        # 3. Ask DeepSeek
        start_time = time.time()
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_question}
            ],
            temperature=1.0,
            max_tokens=400,
            stream=False
        )
        response_time = time.time() - start_time
        logging.info(f"DeepSeek response time: {response_time:.2f}s")

        reply = response.choices[0].message.content.strip()
        sentences = reply.split('. ')
        if len(sentences) > 2:
            reply = '. '.join(sentences[:2]) + '.'

        RESPONSE_CACHE[lower_question] = reply
        return reply

    except Exception as e:
        logging.error(f"DeepSeek Error: {str(e)}")

        # Fallback logic
        if "founder" in lower_question:
            return "Founders: Sri Ranganatha Raju, Srinatha Raju, Sainatha Raju"
        elif "founded" in lower_question or "when" in lower_question:
            return "Founded in 2017"
        elif "what" in lower_question and "sanathana" in lower_question:
            return "Sanathana Analytics is a rural tech company providing recruitment and tech services."

        return "I'm having trouble answering right now. Please try again."

# === MongoDB Access ===
def get_mongo_chatbot():
    db = current_app.mongo_chatbot
    if db is None:
        logging.error("❌ Database connection issue")
        raise RuntimeError("Database connection issue")
    return db

# === Flatten Mongo Questions ===
def flatten_questions(sections):
    flat = []
    for sec in sections:
        name = sec.get("section_name", "Unknown")
        for q in sec.get("questions", []):
            flat.append({"question": q["question"], "answer": q["answer"], "section": name})
        def _subs(subs):
            for s in subs:
                subn = s.get("sub_section_name", "")
                for q in s.get("questions", []):
                    flat.append({
                        "question": q["question"],
                        "answer": q["answer"],
                        "section": name,
                        "sub_section": subn
                    })
                if s.get("sub_sections"):
                    _subs(s["sub_sections"])
        if sec.get("sub_sections"):
            _subs(sec["sub_sections"])
    return flat

# === /sections endpoint ===
@chatbot_bp.route("/sections", methods=["GET"])
def get_sections():
    try:
        coll = get_mongo_chatbot()["sections"]
        docs = coll.find({}, {"_id": 0, "section_name": 1})
        lst = [d["section_name"] for d in docs]
        logging.info("✅ Sections fetched: %s", lst)
        return jsonify({"sections": lst}), 200
    except Exception as e:
        logging.error("❌ Error fetching sections: %s", e)
        return jsonify({"error": "Failed to fetch sections"}), 500

# === /section-questions endpoint ===
@chatbot_bp.route("/section-questions", methods=["GET"])
def get_section_questions():
    name = request.args.get("section", "").strip()
    if not name:
        return jsonify({"error": "Section name is required"}), 400
    try:
        coll = get_mongo_chatbot()["sections"]
        sec = coll.find_one({"section_name": name})
        if sec:
            if sec.get("sub_sections"):
                return jsonify({"sub_sections": [s["sub_section_name"] for s in sec["sub_sections"]]}), 200
            return jsonify({"questions": sec.get("questions", [])}), 200

        parent = coll.find_one({"sub_sections.sub_section_name": name})
        if parent:
            for s in parent["sub_sections"]:
                if s["sub_section_name"] == name:
                    return jsonify({
                        "sub_sections": [ss["sub_section_name"] for ss in s.get("sub_sections", [])],
                        "questions": s.get("questions", [])
                    }), 200

        def find_sub(subs):
            for s in subs:
                if s["sub_section_name"] == name:
                    return s
                if s.get("sub_sections"):
                    found = find_sub(s["sub_sections"])
                    if found:
                        return found
            return None

        for doc in coll.find({}, {"_id": 0, "sub_sections": 1}):
            if doc.get("sub_sections"):
                f = find_sub(doc["sub_sections"])
                if f:
                    return jsonify({
                        "sub_sections": [ss["sub_section_name"] for ss in f.get("sub_sections", [])],
                        "questions": f.get("questions", [])
                    }), 200

        return jsonify({"error": "Section not found"}), 404
    except Exception as e:
        logging.error("❌ get_section_questions: %s", e)
        return jsonify({"error": "Failed to fetch questions"}), 500

# === /chat-response endpoint ===
@chatbot_bp.route("/chat-response", methods=["POST"])
def chatbot_reply():
    try:
        data = request.get_json()
        user_input = data.get("message", "").strip()

        if not user_input or len(user_input) > 500:
            return jsonify({"error": "Invalid input"}), 400

        start_time = time.time()
        reply = ask_deepseek(user_input)
        response_time = time.time() - start_time

        logging.info(f"Total response time: {response_time:.2f}s | Chars: {len(reply)}")
        return jsonify({"response": reply}), 200

    except Exception as e:
        logging.error(f"Endpoint Error: {str(e)}")
        return jsonify({"response": "Internal server error"}), 500
