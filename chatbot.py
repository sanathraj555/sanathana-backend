import os
import logging
import time
import re
import json
from datetime import datetime
from openai import OpenAI
from flask import Blueprint, request, jsonify, current_app
import gspread, base64
from oauth2client.service_account import ServiceAccountCredentials
import traceback

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

# === Helper: Extract birthdays by month ===
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

# === Helper: Find month-year from user question or fallback to current ===
def detect_month_year_from_question(question):
    """
    Tries to extract the month (and optionally year) from the user's question.
    Falls back to current month and year if not mentioned.
    Returns ("June", "2025") for "my leaves in June 2025"
    """
    # Example patterns: "june 2025", "july 2024", "june", "my july leaves"
    month_names = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"
    ]
    q_lower = question.lower()
    month = None
    year = None

    # Search for month+year, or just month
    for m in month_names:
        if m in q_lower:
            month = m.capitalize()
            # Look for 4-digit year after month
            match = re.search(rf"{m}\s+(\d{{4}})", q_lower)
            if match:
                year = match.group(1)
            break

    if not month:
        # Fallback: use current month
        now = datetime.now()
        month = now.strftime("%B")
    if not year:
        now = datetime.now()
        year = now.strftime("%Y")
    return month, year

# === Get leave data for EMP ID, and dynamic sheet based on month/year ===
def get_leave_data(emp_id, question=None):
    try:
        sh = client_gsheet.open_by_key(LEAVE_SPREADSHEET_ID)
        # Determine month/year from question or use current
        month, year = detect_month_year_from_question(question or "")
        worksheet_name = f"{month} {year}"
        logging.info(f"[LEAVE DATA] Trying worksheet: {worksheet_name}")
        try:
            sheet = sh.worksheet(worksheet_name)
        except Exception:
            return f"No leave data sheet found for {worksheet_name}."
        records = sheet.get_all_records()
        user_leaves = [row for row in records if str(row.get("EMP ID")).strip() == str(emp_id).strip()]
        if not user_leaves:
            return f"No leave data found for your EMP ID ({emp_id}) in {worksheet_name}."
        row = user_leaves[0]
        emp_name = row.get("EMP NAME") or row.get("EMPLOYEE NAME") or "N/A"
        msg = f"Attendance & Leave Details for **{emp_name}** (EMP ID: {emp_id}, {worksheet_name}):\n"
        msg += "\n"
        exclude = {"SL.NO", "EMP ID", "EMP NAME", "EMPLOYEE NAME"}
        for key, value in row.items():
            if key not in exclude and str(value).strip() != "":
                msg += f"- {key}: {value}\n"
        return msg.strip()
    except Exception as e:
        logging.error(f"[LEAVE DATA ERROR] {e}\n{traceback.format_exc()}")
        return "Error fetching leave data. Please try again later."

# === Ask DeepSeek with leave integration ===
def ask_deepseek(user_question, emp_id=None):
    try:
        user_question = user_question.strip()
        lower_question = user_question.lower()

        if lower_question in RESPONSE_CACHE:
            return RESPONSE_CACHE[lower_question]

        # Only show leave for the logged-in user, never others!
        if emp_id and ("leave" in lower_question or "leaves" in lower_question or "attendance" in lower_question):
            return get_leave_data(emp_id, user_question)

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

        # DeepSeek fallback for other queries
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

# === Add your endpoints and other code here (unchanged) ===


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
