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

# ✅ Verify EMP ID
@auth_bp.route("/verify-empid", methods=["POST"])
def verify_empid():
    try:
        # Log raw payload
        raw = request.get_data(as_text=True)
        logging.info(f"📦 Raw request payload: {raw}")

        # Parse JSON
        data = request.get_json(force=True)
        if not data or "user_id" not in data:
            logging.error("🔴 EMP ID missing in JSON body")
            return jsonify({"error": "Missing EMP ID"}), 400

        user_id = data.get("user_id", "").strip()
        if not user_id:
            logging.error("🔴 EMP ID value is empty")
            return jsonify({"error": "Empty EMP ID"}), 400

        # DB lookup
        result = fetch_one("SELECT emp_id FROM employee_details WHERE emp_id = %s", (user_id,))
        is_valid = result is not None
        logging.info(f"✅ EMP ID exists: {is_valid}")

        return jsonify({"valid": is_valid}), 200

    except Exception as e:
        logging.exception("❌ Exception occurred in verify_empid:")
        return jsonify({"error": "Internal server error"}), 500

# ✅ Signup
@auth_bp.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json(force=True, silent=True)
        user_id = data.get("user_id", "").strip()
        password = data.get("password", "").strip()

        if not user_id or not password:
            return jsonify({"error": "Missing user_id or password"}), 400

        # Check if EMP ID is valid
        emp_check = fetch_one("SELECT emp_id FROM employee_details WHERE emp_id = %s", (user_id,))
        if not emp_check:
            return jsonify({"error": "Invalid EMP ID"}), 403

        # Check if user already exists
        user_check = fetch_one("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        if user_check:
            return jsonify({"error": "User ID already exists"}), 409

        # Hash password and insert
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (user_id, password) VALUES (%s, %s)", (user_id, hashed))
        conn.commit()
        cursor.close()
        conn.close()

        logging.info(f"✅ Signup successful for user: {user_id}")
        return jsonify({"message": "Signup successful!"}), 201

    except Exception as e:
        logging.exception("❌ Signup error:")
        return jsonify({"error": "Internal server error"}), 500

# ✅ Login
@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json(force=True, silent=True)
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
