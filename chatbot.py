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

        # Prepare structured message
        msg = f"Hello {emp_name} (EMP ID: {emp_id}),\n\n"
        msg += f"Here is your attendance and leave summary for {worksheet_name}:\n\n"

        # Friendly sentences for main leave/attendance fields
        def line(k, v):
            return f"• {k}: {v}\n" if str(v).strip() != "" else ""

        msg += line("Present Days", row.get("PRESENT COUNT", "N/A"))
        msg += line("Absent Days", row.get("ABSENT COUNT", "N/A"))
        msg += line("Casual Leaves Taken", row.get("CASUAL LEAVE COUNT", "N/A"))
        msg += line("Casual Leave Balance", row.get("CASUAL LEAVE BALANCE", "N/A"))
        msg += line("Sick Leaves Taken", row.get("SICK LEAVE COUNT", "N/A"))
        msg += line("Sick Leave Balance", row.get("SICK LEAVE BALANCE", "N/A"))
        msg += line("Half Day Leaves", row.get("HALF DAY LEAVE COUNT", "N/A"))
        msg += line("Holidays Count", row.get("HOLI DAYS COUNT", "N/A"))
        msg += line("Loss of Pay Days", row.get("LOSS OF PAY COUNT", "N/A"))
        msg += line("Half Sick Leaves", row.get("HALF SICK LEAVE COUNT", "N/A"))

        msg += "\nIf you have questions about your leave or attendance, please reach out to HR."

        return msg.strip()
    except Exception as e:
        logging.error(f"[LEAVE DATA ERROR] {e}\n{traceback.format_exc()}")
        return "Error fetching leave data. Please try again later."

def ask_deepseek(user_question, emp_id=None):
    import time

    def call_deepseek_with_retry(messages, model=MODEL_NAME, max_tokens=600, max_retries=3):
        delays = [1, 2, 4]
        last_exception = None
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=1.0,
                    max_tokens=max_tokens,
                    stream=False
                )
                duration = time.time() - start_time
                if duration > 8:
                    logging.warning(f"[DeepSeek SLOW] Took {duration:.2f}s")
                return response
            except Exception as e:
                last_exception = e
                logging.warning(f"DeepSeek attempt {attempt+1} failed: {str(e)}")
                if attempt < len(delays):
                    time.sleep(delays[attempt])
        raise RuntimeError(f"DeepSeek API failed after {max_retries} retries. Last error: {last_exception}")

    def find_birthday_by_name(name, kb_text):
        # Robust name search (allows partial names)
        pattern = re.compile(r"EMPLOYEE NAME\s*:\s*(.+?)\s*[\r\n,].*?DATE OF BIRTH\s*:\s*([0-9\-]+)", re.IGNORECASE | re.DOTALL)
        matches = pattern.findall(kb_text)
        for emp_name, dob in matches:
            if name.lower() in emp_name.lower():
                try:
                    dob_dt = datetime.strptime(dob, "%d-%m-%Y")
                    return f"{emp_name.strip()}'s birthday is {dob_dt.strftime('%d-%b-%Y')}."
                except Exception:
                    return f"{emp_name.strip()}'s birthday is {dob}."
        return None

    try:
        user_question = user_question.strip()
        lower_question = user_question.lower()

        # 1. Fast cache for popular queries
        if lower_question in RESPONSE_CACHE:
            return RESPONSE_CACHE[lower_question]

        # 2. Local logic (leave data)
        if emp_id and ("leave" in lower_question or "leaves" in lower_question or "attendance" in lower_question):
            return get_leave_data(emp_id, user_question)

        # 3. Direct name-based birthday lookup (if user asks for someone's birthday)
        if ("birthday" in lower_question or "birth date" in lower_question):
            # Extract possible name from the question, e.g., "What is Amruth's birthday?"
            name_match = re.search(r"(?i)birthday of (\w+)", user_question)
            if not name_match:
                name_match = re.search(r"(?i)(\w+)'s birthday", user_question)
            if not name_match:
                # fallback: look for any word before "birthday"
                name_match = re.search(r"(?i)what is (\w+)[’'s ]*birthday", user_question)
            if name_match:
                name = name_match.group(1)
                result = find_birthday_by_name(name, knowledge_text)
                if result:
                    RESPONSE_CACHE[lower_question] = result
                    return result
            # fallback to months extraction if a month is in the question
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

        # 4. Compose DeepSeek system prompt
        system_content = (
            "You are a concise and resourceful Sanathana assistant. "
            "Always use the knowledge provided to find and present helpful answers, even if the exact information is not available. "
            "Carefully search, analyze, and extract any facts or related content that may assist the user. "
            "If there is no exact answer, present the most closely related information, summaries, or inferred details from the knowledge base.\n\n"
            "Knowledge Base:\n"
            + knowledge_text +
            "\n\n"
            "Instructions:\n"
            "1. Use ONLY the knowledge provided—never make up facts.\n"
            "2. If you cannot find an exact match, provide any relevant, related, or inferred information from the knowledge base.\n"
            "3. Never respond with phrases like 'I don't have that information' or 'I am unable to answer'.\n"
            "4. Be direct—avoid greetings, sign-offs, or apologies.\n"
            "5. Always keep sentences short and crisp.\n"
            "6. Use clear, simple language that is easy to understand.\n"
            "7. For list-type queries (such as 'list features' or 'show benefits'):\n"
            "   - Present information as bullet points\n"
            "   - Group related items together logically\n"
            "   - Avoid blank lines between bullets\n"
            "8. For all other queries, respond with brief, fact-based sentences using the most relevant knowledge.\n"
            "9. Only include contact details if specifically requested.\n"
            "10. Always try to give the user the most useful response possible using the available knowledge.\n"
        )


        # 5. Call DeepSeek with retry logic
        start_time = time.time()
        response = call_deepseek_with_retry(
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_question}
            ],
            max_tokens=600  # Lower for faster reply, can adjust
        )
        response_time = time.time() - start_time
        logging.info(f"DeepSeek response time: {response_time:.2f}s")

        # 6. Truncate answer to keep short (first two sentences)
        reply = response.choices[0].message.content.strip()
        sentences = reply.split('. ')
        if len(sentences) > 2:
            reply = '. '.join(sentences[:2]) + '.'

        # 7. Store in cache
        RESPONSE_CACHE[lower_question] = reply
        return reply

    except Exception as e:
        logging.error(f"DeepSeek Error: {str(e)}")
        # Optional: fallback for common queries
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
