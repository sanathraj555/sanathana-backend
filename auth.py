from flask import Blueprint, request, jsonify
import mysql.connector
import logging
import bcrypt
from db import get_db_connection

logging.basicConfig(level=logging.INFO)
auth_bp = Blueprint("auth", __name__)

# Helper to run a query and fetch one row
def fetch_one(query, params):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params)
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

# ======================
# ✅ Verify EMP ID
# ======================
@auth_bp.route("/verify-empid", methods=["POST"])
def verify_empid():
    data = request.get_json(force=True, silent=True)
    user_id = data.get("user_id", "").strip()
    if not user_id:
        return jsonify({"error": "Missing EMP ID"}), 400

    try:
        result = fetch_one("SELECT COUNT(*) AS emp_exists FROM employee_details WHERE emp_id = %s", (user_id,))
        return jsonify({"valid": result["emp_exists"] == 1}), 200
    except Exception as e:
        logging.error(f"❌ Verify EMP ID error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ======================
# ✅ Signup
# ======================
@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(force=True, silent=True)
    user_id = data.get("user_id")
    password = data.get("password")
    if not user_id or not password:
        return jsonify({"error": "Missing user_id or password"}), 400

    try:
        if fetch_one("SELECT COUNT(*) AS emp_exists FROM employee_details WHERE emp_id = %s", (user_id,))["emp_exists"] == 0:
            return jsonify({"error": "Invalid EMP ID"}), 403
        if fetch_one("SELECT COUNT(*) AS user_count FROM users WHERE user_id = %s", (user_id,))["user_count"] > 0:
            return jsonify({"error": "User ID already exists"}), 409

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (user_id, password) VALUES (%s, %s)", (user_id, hashed))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Signup successful!"}), 201
    except Exception as e:
        logging.error(f"❌ Signup error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ======================
# ✅ Login
# ======================
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True)
    user_id = data.get("user_id")
    password = data.get("password")
    if not user_id or not password:
        return jsonify({"error": "Missing user_id or password"}), 400

    try:
        user = fetch_one("SELECT * FROM users WHERE user_id = %s", (user_id,))
        if not user or not bcrypt.checkpw(password.encode(), user["password"].encode()):
            return jsonify({"error": "Invalid credentials"}), 401

        return jsonify({"message": "Login successful!"}), 200
    except Exception as e:
        logging.error(f"❌ Login error: {e}")
        return jsonify({"error": "Internal server error"}), 500
