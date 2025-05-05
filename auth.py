from flask import Blueprint, request, jsonify, make_response, session
import mysql.connector
import bcrypt
import logging
from db import get_db_connection

logging.basicConfig(level=logging.DEBUG)
auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/verify-empid", methods=["POST"])
def verify_empid():
    print("✅ HIT /auth/verify-empid")
    data = request.get_json(force=True, silent=True)
    print("📥 Incoming Payload:", data)

    user_id = data.get("user_id", "").strip()
    if not user_id:
        return jsonify({"error": "Missing EMP ID"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS emp_exists FROM employee_details WHERE emp_id = %s", (user_id,))
        emp_check = cursor.fetchone()
        print("✅ EMP Check Result:", emp_check)

        return jsonify({"valid": emp_check["emp_exists"] == 1}), 200

    except Exception as e:
        print(f"❌ DB error in /verify-empid: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


# === Signup ===
@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(force=True, silent=True)
    user_id = data.get("user_id")
    password = data.get("password")
    if not user_id or not password:
        return jsonify({"error": "Missing user_id or password"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS emp_exists FROM employee_details WHERE emp_id = %s", (user_id,))
        emp_check = cursor.fetchone()
        if not emp_check or emp_check["emp_exists"] == 0:
            return jsonify({"error": "Invalid EMP ID. Access restricted to employees only."}), 403

        cursor.execute("SELECT COUNT(*) AS user_count FROM users WHERE user_id = %s", (user_id,))
        user_check = cursor.fetchone()
        if user_check and user_check["user_count"] > 0:
            return jsonify({"error": "User ID already exists"}), 409

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute("INSERT INTO users (user_id, password) VALUES (%s, %s)", (user_id, hashed_password))
        conn.commit()
        return jsonify({"message": "Signup successful!"}), 201
    except mysql.connector.Error as err:
        return jsonify({"error": f"Database error: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# === Login ===
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True)
    user_id = data.get("user_id")
    password = data.get("password")

    if not user_id or not password:
        return jsonify({"error": "Missing user_id or password"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        if not bcrypt.checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):
            return jsonify({"error": "Invalid password"}), 401

        session["user_id"] = user_id  # ✅ Store in session
        return jsonify({"message": "Login successful!"}), 200
    except mysql.connector.Error as err:
        return jsonify({"error": f"Database error: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# === Logout ===
@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200

# === Check Auth Session ===
@auth_bp.route("/check", methods=["GET"])
def check_auth():
    if "user_id" in session:
        return jsonify({"status": "ok"}), 200
    return jsonify({"error": "unauthenticated"}), 401
