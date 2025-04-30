from flask import Blueprint, request, jsonify
import mysql.connector
import bcrypt
import logging
from database import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash

# Setup logging
logging.basicConfig(level=logging.DEBUG)  # Configure logging for production

auth_bp = Blueprint("auth", __name__)

# Rate limiting can be added here

@auth_bp.route("/verify-empid", methods=["POST"])
def verify_empid():
    """Checks if EMP ID exists in employee_details"""
    data = request.json
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "Missing EMP ID"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) AS emp_exists FROM employee_details WHERE emp_id = %s", (user_id,))
        emp_check = cursor.fetchone()
        if emp_check["emp_exists"] == 1:
            return jsonify({"valid": True}), 200
        else:
            return jsonify({"valid": False}), 200
    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({"error": "Database error"}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/signup", methods=["POST"])
def signup():
    """Handles Employee Signup with EMP ID Verification"""
    data = request.json
    user_id = data.get("user_id")
    password = data.get("password")

    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Step 1: Check if the user ID exists in employee_details
        cursor.execute("SELECT COUNT(*) AS emp_exists FROM employee_details WHERE emp_id = %s", (user_id,))
        emp_check = cursor.fetchone()

        if not emp_check or emp_check["emp_exists"] == 0:
            return jsonify({"error": "Invalid EMP ID. Access restricted to employees only."}), 403

        # Step 2: Check if user already signed up
        cursor.execute("SELECT COUNT(*) AS user_count FROM users WHERE user_id = %s", (user_id,))
        user_check = cursor.fetchone()
        if user_check and user_check["user_count"] > 0:
            return jsonify({"error": "User ID already exists"}), 409

        # Step 3: If EMP ID is valid and not signed up, hash password & register
        if not password:
            return jsonify({"error": "Missing password"}), 400

        hashed_password = generate_password_hash(password, method='sha256')  # Use werkzeug's password hashing
        cursor.execute("INSERT INTO users (user_id, password) VALUES (%s, %s)", (user_id, hashed_password))
        conn.commit()

        return jsonify({"message": "Signup successful!"}), 201

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({"error": f"Database error: {err}"}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/login", methods=["POST"])
def login():
    """Handles User Login"""
    data = request.json
    user_id = data.get("user_id")
    password = data.get("password")

    if not user_id or not password:
        return jsonify({"error": "Missing user_id or password"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch user from MySQL
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404  # User doesn't exist

        stored_password = user["password"]

        # Verify password using werkzeug's check_password_hash
        if not check_password_hash(stored_password, password):
            return jsonify({"error": "Invalid password"}), 401  # Wrong password

        return jsonify({"message": "Login successful!"}), 200

    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({"error": f"Database error: {err}"}), 500

    finally:
        cursor.close()
        conn.close()
