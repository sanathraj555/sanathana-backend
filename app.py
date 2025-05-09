from flask import Flask, request, jsonify, send_from_directory, current_app
from flask_cors import CORS
import os
import logging
from pymongo import MongoClient

# === Flask App Config ===
app = Flask(__name__, static_folder="frontend/build", static_url_path="")

# === Logging Setup ===
logging.basicConfig(level=logging.INFO)
app.logger.info("🚀 Starting Flask App")

# === CORS Config ===
CORS(app, supports_credentials=True, origins=[
    os.getenv("FRONTEND_URL", "http://localhost:3000"),
    "https://yellow-hill-0dae7d700.6.azurestaticapps.net"
])

# === MongoDB Setup (Azure CosmosDB with Mongo API) ===
cosmos_uri = os.getenv("MONGO_URI", "mongodb://sanathana-mongodb:dfoQCX7oTznqVCzevEviz22giZEgbHpoF04YOXOTTMMuOOUCIcbqMzBSvBrCNNHJafuW7FqSHjRhACDbwmAgPw==@sanathana-mongodb.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@sanathana-mongodb@")

try:
    client = MongoClient(cosmos_uri, tls=True, tlsAllowInvalidCertificates=True)
    client.admin.command("ping")
    app.mongo_chatbot = client["sanathana_chatbot_v1"]
    app.logger.info("✅ Connected to MongoDB: sanathana_chatbot_v1")
except Exception as e:
    app.logger.error(f"❌ MongoDB connection failed: {e}")
    app.mongo_chatbot = None

# === Register Chatbot Blueprint ===
from chatbot import chatbot_bp
app.register_blueprint(chatbot_bp, url_prefix="/chatbot")

# === Health Check ===
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200

# === Debug: Mongo Status ===
@app.route("/debug/mongo", methods=["GET"])
def debug_mongo():
    try:
        if app.mongo_chatbot:
            collections = app.mongo_chatbot.list_collection_names()
            return jsonify({"status": "ok", "collections": collections}), 200
        return jsonify({"error": "mongo_chatbot is None"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === Debug: Seed Sample Data ===
@app.route("/debug/seed", methods=["POST"])
def seed_sections():
    try:
        data = [
            {
                "section_name": "Recruitment",
                "questions": [{"question": "What is the hiring process?", "answer": "Screening, interviews, and onboarding."}]
            },
            {
                "section_name": "Tech Solutions",
                "questions": [{"question": "What services do you offer?", "answer": "AI, automation, and custom development."}]
            }
        ]
        app.mongo_chatbot["sections"].insert_many(data)
        return jsonify({"message": "✅ Sections seeded successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === Serve React Static Files ===
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(os.path.join(app.static_folder, "static"), filename)

# === Catch-all Route (React SPA fallback) ===
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react_app(path):
    if path.startswith(("api", "chatbot", "auth")):
        return jsonify({"error": "API route not found"}), 404
    return send_from_directory(app.static_folder, "index.html")

# === Run Server ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
