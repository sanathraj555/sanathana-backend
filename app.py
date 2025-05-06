from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import logging
from pymongo import MongoClient

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

# === MongoDB (Cosmos DB) Setup with pymongo ===
cosmos_uri = os.getenv(
    'MONGO_URI',
    'mongodb://sanathana-mongodb:m1ErbvRoj8vA4M3tD56mvNTEch5tasOIP0mrvfxBtqiTZYNdEVz172UeCa5qK1YI5J8xZSItPwYNACDbmUcvzw==@sanathana-mongodb.mongo.cosmos.azure.com:10255/?ssl=true&retrywrites=false&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@sanathana-mongodb@'
)

try:
    client = MongoClient(cosmos_uri, tls=True, tlsAllowInvalidCertificates=True)
    client.admin.command("ping")
    app.mongo_chatbot = client["sanathana_chatbot_v1"]
    app.logger.info("✅ Connected to MongoDB: sanathana_chatbot_v1")
except Exception as e:
    app.logger.error(f"❌ MongoDB connection failed: {e}")
    app.mongo_chatbot = None

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
