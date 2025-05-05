from flask import Blueprint, request, jsonify
import mysql.connector
import logging
from db import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash

# Setup logging
logging.basicConfig(level=logging.DEBUG)
auth_bp = Blueprint("auth", __name__)

# ======================
# ✅ Verify EMP ID
# ======================
@auth_bp.route("/verify-empid", methods=["POST"])
def verify_empid():
    print("✅ Route /auth/verify-empid HIT")
    data = request.get_json(force=True, silent=True)
    print("📥 Payload:", data)

    user_id = data.get("user_id", "").strip()
    if not user_id:
        return jsonify({"error": "Missing EMP ID"}), 400

    try:
        conn = get_db_connection()
        print("🟢 DB Connection Success")
        cursor = conn.cursor(dictionary=True)
        print(f"🔎 Executing query with user_id = '{user_id}'")
        cursor.execute("SELECT COUNT(*) AS emp_exists FROM employee_details WHERE emp_id = %s", (user_id,))
        emp_check = cursor.fetchone()
        print("✅ Query Result:", emp_check)

        return jsonify({"valid": emp_check["emp_exists"] == 1}), 200

    except mysql.connector.Error as err:
        print(f"❌ MySQL error: {err}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        print(f"❗ Other error: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# ======================
# ✅ Signup
# ======================
@auth_bp.route("/signup", methods=["POST"])
def signup():
    print("✅ Route /auth/signup HIT")
    data = request.get_json(force=True, silent=True)
    print("📥 Payload:", data)

    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

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

        hashed_password = generate_password_hash(password, method='sha256')
        cursor.execute("INSERT INTO users (user_id, password) VALUES (%s, %s)", (user_id, hashed_password))
        conn.commit()

        print("✅ Signup successful")
        return jsonify({"message": "Signup successful!"}), 201

    except mysql.connector.Error as err:
        logging.error(f"❌ Signup DB error: {err}")
        return jsonify({"error": f"Database error: {err}"}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

# ======================
# ✅ Login
# ======================
@auth_bp.route("/login", methods=["POST"])
def login():
    print("✅ Route /auth/login HIT")
    data = request.get_json(force=True, silent=True)
    print("📥 Payload:", data)

    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

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

        stored_password = user["password"]
        if not check_password_hash(stored_password, password):
            return jsonify({"error": "Invalid password"}), 401

        print("✅ Login successful")
        return jsonify({"message": "Login successful!"}), 200

    except mysql.connector.Error as err:
        logging.error(f"❌ Login DB error: {err}")
        return jsonify({"error": f"Database error: {err}"}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass
