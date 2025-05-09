from flask import Blueprint, request, jsonify
import mysql.connector
import logging
import bcrypt
from db import get_db_connection

auth_bp = Blueprint("auth", __name__)
logging.basicConfig(level=logging.INFO)

# 🔁 Helper: fetch one row from DB
def fetch_one(query, params):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params)
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

# ✅ Signup
@auth_bp.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json(force=True)
        logging.info(f"✅ Parsed JSON: {data}")

        if not data or 'user_id' not in data or 'password' not in data:
            logging.warning("⚠️ Missing user_id or password in JSON.")
            return jsonify({"error": "Missing user_id or password"}), 400

        user_id = data['user_id'].strip()
        password = data['password'].strip()

        if not user_id or not password:
            logging.warning("⚠️ user_id or password is empty after stripping.")
            return jsonify({"error": "user_id or password is empty"}), 400

        logging.info(f"🔍 Checking EMP ID existence: {user_id}")
        emp_check = fetch_one("SELECT emp_id FROM employee_details WHERE emp_id = %s", (user_id,))
        if not emp_check:
            logging.warning(f"❌ EMP ID not found: {user_id}")
            return jsonify({"error": "Invalid EMP ID"}), 403

        logging.info(f"🔍 Checking if user already exists: {user_id}")
        user_check = fetch_one("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        if user_check:
            logging.warning(f"⚠️ User ID already exists: {user_id}")
            return jsonify({"error": "User ID already exists"}), 409

        logging.info(f"🔐 Hashing password for: {user_id}")
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        conn = get_db_connection()
        cursor = conn.cursor()
        logging.info(f"📝 Inserting new user: {user_id}")
        cursor.execute("INSERT INTO users (user_id, password) VALUES (%s, %s)", (user_id, hashed))
        conn.commit()
        cursor.close()
        conn.close()

        logging.info(f"✅ Signup successful for user: {user_id}")
        return jsonify({"message": "Signup successful!"}), 201

    except Exception as e:
        logging.exception("❌ Exception in signup:")
        return jsonify({"error": "Internal server error"}), 500


# ✅ Login
@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        raw = request.get_data(as_text=True)
        logging.info(f"📦 RAW LOGIN PAYLOAD: {raw}")

        try:
            data = request.get_json(force=True)
        except Exception as e:
            logging.warning(f"⚠️ JSON decode error: {e}")
            return jsonify({"error": "Invalid JSON body"}), 400

        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        user_id = data.get("user_id", "").strip()
        password = data.get("password", "").strip()

        if not user_id or not password:
            return jsonify({"error": "Missing user_id or password"}), 400

        user = fetch_one("SELECT * FROM users WHERE user_id = %s", (user_id,))
        if not user or not bcrypt.checkpw(password.encode(), user["password"].encode()):
            return jsonify({"error": "Invalid credentials"}), 401

        logging.info(f"✅ Login successful for user: {user_id}")
        return jsonify({"message": "Login successful!"}), 200

    except Exception as e:
        logging.exception("❌ Login error:")
        return jsonify({"error": "Internal server error"}), 500
