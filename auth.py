from flask import Blueprint, request, jsonify, session
import mysql.connector
import bcrypt
import logging
from db import get_db_connection
from flask_cors import CORS, cross_origin

logging.basicConfig(level=logging.DEBUG)

auth_bp = Blueprint("auth", __name__)

CORS(auth_bp, supports_credentials=True, origins=[
    "https://yellow-hill-0dae7d700.6.azurestaticapps.net",
    "http://localhost:3000"
])


@auth_bp.route("/verify-empid", methods=["POST"])
@cross_origin(supports_credentials=True)
def verify_empid():
    print("✅ HIT: /verify-empid")

    try:
        # Parse request directly
        data = request.get_json(force=True)
        print("📦 Parsed JSON:", data)

        emp_id = data.get("user_id", "").strip()
        if not emp_id:
            return jsonify({"valid": False, "error": "Empty EMP ID"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employee_details WHERE emp_id = %s", (emp_id,))
        count = cursor.fetchone()[0]
        print(f"🔍 EMP ID = {emp_id}, Found = {count}")

        return jsonify({"valid": count > 0}), 200

    except Exception as e:
        print("❌ EMP ID Validation Exception:", str(e))
        return jsonify({"valid": False, "error": str(e)}), 400

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass


# Signup route
@auth_bp.route("/signup", methods=["POST"])
@cross_origin(supports_credentials=True)
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
        emp_exists = cursor.fetchone()["emp_exists"]
        
        if emp_exists == 0:
            return jsonify({"error": "Invalid EMP ID. Access restricted to employees only."}), 403

        cursor.execute("SELECT COUNT(*) AS user_count FROM users WHERE user_id = %s", (user_id,))
        user_count = cursor.fetchone()["user_count"]
        
        if user_count > 0:
            return jsonify({"error": "User ID already exists"}), 409

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute("INSERT INTO users (user_id, password) VALUES (%s, %s)", (user_id, hashed_password))
        conn.commit()

        return jsonify({"message": "Signup successful!"}), 201

    except mysql.connector.Error as err:
        logging.error("❌ Database error during signup: %s", err)
        return jsonify({"error": f"Database error: {err}"}), 500

    finally:
        cursor.close()
        conn.close()

# Login route
@auth_bp.route("/login", methods=["POST"])
@cross_origin(supports_credentials=True)
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

        session["user_id"] = user_id
        return jsonify({"message": "Login successful!"}), 200

    except mysql.connector.Error as err:
        logging.error("❌ Database error during login: %s", err)
        return jsonify({"error": f"Database error: {err}"}), 500

    finally:
        cursor.close()
        conn.close()

# Logout route
@auth_bp.route("/logout", methods=["POST"])
@cross_origin(supports_credentials=True)
def logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200

# Check Authentication
@auth_bp.route("/check", methods=["GET"])
@cross_origin(supports_credentials=True)
def check_auth():
    if "user_id" in session:
        return jsonify({"status": "ok"}), 200
    return jsonify({"error": "unauthenticated"}), 401
