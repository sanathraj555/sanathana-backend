from flask import Flask, request, jsonify, send_from_directory, current_app
from flask_cors import CORS
import os
import logging
from pymongo import MongoClient

# === Initialize Flask App ===
app = Flask(__name__, static_folder="frontend/build", static_url_path="")

# === Logging Setup ===
logging.basicConfig(level=logging.INFO)
app.logger.info("🚀 Starting Flask App")

# === Enable CORS ===
CORS(app, supports_credentials=True, origins=[
    "https://yellow-hill-0dae7d700.6.azurestaticapps.net"
])

# === MongoDB (CosmosDB) Setup ===
cosmos_uri = os.getenv("MONGO_URI", "mongodb://sanathana-mongodb:m1ErbvRoj8vA4M3tD56mvNTEch5tasOIP0mrvfxBtqiTZYNdEVz172UeCa5qK1YI5J8xZSItPwYNACDbmUcvzw%3D%3D@sanathana-mongodb.mongo.cosmos.azure.com:10255/?ssl=true&retrywrites=false&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@sanathana-mongodb@")

try:
    client = MongoClient(cosmos_uri, tls=True, tlsAllowInvalidCertificates=True)
    client.admin.command("ping")
    app.mongo_chatbot = client["sanathana_chatbot_v1"]
    app.logger.info("✅ Connected to MongoDB: sanathana_chatbot_v1")
except Exception as e:
    app.logger.error(f"❌ MongoDB connection failed: {e}")
    app.mongo_chatbot = None

# === Register Blueprints ===
from chatbot import chatbot_bp
app.register_blueprint(chatbot_bp, url_prefix="/chatbot")

# === Health Check Endpoint ===
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200

# === Serve Static Files for React ===
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(os.path.join(app.static_folder, "static"), filename)

# === Fallback to React SPA ===
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react_app(path):
    if path.startswith(("api", "chatbot", "auth")):
        return jsonify({"error": "API route not found"}), 404
    return send_from_directory(app.static_folder, "index.html")

# === Run Flask App ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
