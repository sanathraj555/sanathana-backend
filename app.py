from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_pymongo import PyMongo
import mysql.connector
import os
import logging

# === Initialize Flask App ===
app = Flask(__name__, static_folder='frontend/build', static_url_path='')

# === Logging ===
logging.basicConfig(level=logging.INFO)

# === CORS Setup ===
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "https://yellow-hill-0dae7d700.6.azurestaticapps.net"
        ]
    }
}, supports_credentials=True, methods=["GET", "POST", "OPTIONS"])

# === MongoDB (Cosmos DB) Setup ===
cosmos_uri = os.getenv(
    'MONGO_URI',
    'mongodb://sanathana-mongodb:m1ErbvRoj8vA4M3tD56mvNTEch5tasOIP0mrvfxBtqiTZYNdEVz172UeCa5qK1YI5J8xZSItPwYNACDbmUcvzw==@sanathana-mongodb.mongo.cosmos.azure.com:10255/?ssl=true&retrywrites=false&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@sanathana-mongodb@'
)
app.config["MONGO_URI"] = cosmos_uri

try:
    mongo = PyMongo(app)
    mongo.cx.admin.command('ping')
    app.logger.info("✅ Connected to Azure Cosmos DB (MongoDB API)!")
    mongo_chatbot = mongo.cx.get_database("sanathana_chatbot_v1")
except Exception as e:
    app.logger.error(f"❌ Cosmos DB Connection Failed: {e}")
    mongo = None
    mongo_chatbot = None

# === MySQL EMP ID Validation Endpoint ===
@app.route('/validate_emp_id', methods=['POST'])
def validate_emp_id():
    data = request.get_json()
    emp_id = data.get('emp_id')

    try:
        conn = mysql.connector.connect(
            host="sanathanamysql.mysql.database.azure.com",     # ✅ Azure MySQL host
            user="techlabs@sanathanamysql",                    # ✅ Azure MySQL user
            password="techlabs@123",                           # ✅ Azure MySQL password
            database="sanathana_chatbot_db",
            ssl_disabled=True                                  # ✅ Use ssl_ca if needed for prod
        )
        cursor = conn.cursor()
        cursor.execute("SELECT emp_id FROM employee_details WHERE emp_id = %s", (emp_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return jsonify({'valid': True})
        else:
            return jsonify({'valid': False}), 404

    except Exception as e:
        app.logger.error(f"❌ MySQL Error: {e}")
        return jsonify({'valid': False, 'error': str(e)}), 500

# === Register Blueprints ===
from auth import auth_bp
from chatbot import chatbot_bp
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(chatbot_bp, url_prefix="/chatbot")

# === Serve React Static Files ===
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(app.static_folder, 'static'), filename)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react_app(path):
    if path.startswith("auth") or path.startswith("chatbot") or path.startswith("api"):
        return jsonify({"error": "API route not found"}), 404
    return send_from_directory(app.static_folder, 'index.html')

# === Health Check ===
@app.route('/health', methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200

# === Start Flask App ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
