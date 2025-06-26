import os
import logging
import time
import re
import json
from datetime import datetime
from openai import OpenAI
from flask import Blueprint, request, jsonify, current_app
import gspread,base64
from oauth2client.service_account import ServiceAccountCredentials


# === Load knowledge base from txt file ===
KB_PATH = os.path.join(os.path.dirname(__file__), "kb_content.txt")
with open(KB_PATH, "r", encoding="utf-8") as f:
    knowledge_text = f.read()

# === Configure DeepSeek ===
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
MODEL_NAME = "deepseek-chat"
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# === Google Sheets Config ===
LEAVE_SPREADSHEET_ID = os.getenv("LEAVE_SPREADSHEET_ID")

scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive'
        ]


creds_data = base64.b64decode(os.getenv("GOOGLE_CREDS_BASE64"))
creds_dict = json.loads(creds_data)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client_gsheet = gspread.authorize(creds)
# === Flask Setup ===
chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Simple cache
RESPONSE_CACHE = {
    "who are the founders of sanathana?": "Founders: Sri Ranganatha Raju, Srinatha Raju, Sainatha Raju",
    "when was sanathana founded?": "Founded in 2017",
    "what is sanathana?": "Sanathana Analytics is a rural tech company providing recruitment, research, and e-commerce services."
}

# === Structured extraction for birthdays ===
def extract_birthdays_by_month(month_name):
    pattern = re.compile(
        r'EMPLOYEE NAME\s*:\s*([^,\n]+).*?DATE OF BIRTH\s*:\s*([0-9\-]+)', re.IGNORECASE | re.DOTALL)
    matches = pattern.findall(knowledge_text)
    try:
        month_num = datetime.strptime(month_name, "%B").month
    except Exception:
        return []
    results = []
    for name, dob in matches:
        try:
            dob_dt = datetime.strptime(dob, "%d-%m-%Y")
            if dob_dt.month == month_num:
                results.append(f"{name.strip()} - {dob_dt.strftime('%d-%b')}")
        except Exception:
            continue
    return results

# === Get leave data for EMP ID ===
def get_leave_data(emp_id):
    try:
        sheet = client_gsheet.open_by_key(LEAVE_SPREADSHEET_ID).worksheet("June 2025")
        records = sheet.get_all_records()
        user_leaves = [row for row in records if row.get("EMP ID") == emp_id]

        if not user_leaves:
            return f"No leave data found for EMP ID {emp_id}."

        row = user_leaves[0]
        leave_summary = f"Leave Summary for EMP ID {emp_id} (June 2025):\n"
        leave_summary += f"- Casual Leave Taken: {row.get('Casual Leave', '0')}\n"
        leave_summary += f"- Sick Leave Taken: {row.get('Sick Leave', '0')}\n"
        leave_summary += f"- Earned Leave Taken: {row.get('Earned Leave', '0')}\n"
        leave_summary += f"- Total Leaves Taken: {row.get('Total Used', '0')}\n"
        leave_summary += f"- Leaves Remaining: {row.get('Leaves Left', '0')}"
        return leave_summary

    except Exception as e:
        logging.error(f"Google Sheets Error: {e}")
        return "Error fetching leave data. Please try again later."

# === Ask DeepSeek with leave integration ===
def ask_deepseek(user_question, emp_id=None):
    try:
        user_question = user_question.strip()
        lower_question = user_question.lower()

        if lower_question in RESPONSE_CACHE:
            return RESPONSE_CACHE[lower_question]

        if emp_id and ("leave" in lower_question or "leaves" in lower_question):
            return get_leave_data(emp_id)

        if "birthday" in lower_question or "birthdays" in lower_question:
            months = [
                "january", "february", "march", "april", "may", "june",
                "july", "august", "september", "october", "november", "december"
            ]
            for m in months:
                if m in lower_question:
                    bdays = extract_birthdays_by_month(m.capitalize())
                    if bdays:
                        reply = f"Birthdays in {m.capitalize()}:\n- " + "\n- ".join(bdays)
                    else:
                        reply = f"No birthdays found in {m.capitalize()}."
                    RESPONSE_CACHE[lower_question] = reply
                    return reply

        system_content = (
            "You are a concise Sanathana assistant. Answer using only the knowledge provided, but form sentences if helpful.\n\n"
            "Knowledge Base:\n"
            + knowledge_text +
            "\n\n"
            "Rules:\n"
            "1. Use ONLY this knowledge\n"
            "2. If the answer is not found, reply: 'I don't have that information'\n"
            "3. Be direct — no greetings or sign-offs\n"
            "4. Prefer short, crisp sentences\n"
            "5. Use clear, simple language\n"
            "6. For bullet-friendly queries (like 'list features' or 'show benefits'):\n"
            "   - Use bullet points\n"
            "   - Group related items\n"
            "   - No blank lines between bullets\n"
            "7. For all other queries, respond in brief sentences using the relevant facts\n"
            "8. Include contact details only if specifically requested\n"
        )

        start_time = time.time()
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_question}
            ],
            temperature=1.0,
            max_tokens=1000,
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

        if "founder" in lower_question:
            return "Founders: Sri Ranganatha Raju, Srinatha Raju, Sainatha Raju"
        elif "founded" in lower_question or "when" in lower_question:
            return "Founded in 2017"
        elif "what" in lower_question and "sanathana" in lower_question:
            return "Sanathana Analytics is a rural tech company providing recruitment and tech services."

        return "I'm having trouble answering right now. Please try again."

# ...rest of your code remains unchanged...

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
        emp_id = data.get("emp_id")  # <-- Get emp_id from request

        if not user_input or len(user_input) > 500:
            return jsonify({"error": "Invalid input"}), 400

        start_time = time.time()
        reply = ask_deepseek(user_input, emp_id)  # <-- Pass emp_id here!
        response_time = time.time() - start_time

        logging.info(f"Total response time: {response_time:.2f}s | Chars: {len(reply)}")
        return jsonify({"response": reply}), 200

    except Exception as e:
        logging.error(f"Endpoint Error: {str(e)}")
        return jsonify({"response": "Internal server error"}), 500
