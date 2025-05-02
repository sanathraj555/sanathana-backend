from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
import os
import logging

# ✅ Initialize Flask App
app = Flask(__name__, static_folder='frontend/build', static_url_path='')

# ✅ Setup Logging
logging.basicConfig(level=logging.INFO)

# ✅ Allow CORS for both local and deployed frontend
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "https://yellow-hill-0dae7d700.6.azurestaticapps.net"
        ]
    }
}, supports_credentials=True, methods=["GET", "POST", "OPTIONS"])

# ✅ Cosmos DB MongoDB vCore connection string (non-SRV format)
cosmos_uri = os.getenv('MONGO_URI', 'mongodb://sars:Sanathana123@sanathanadb.mongocluster.cosmos.azure.com:10255/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000')

# ✅ Connect to Cosmos MongoDB vCore
try:
    mongo_client = MongoClient(cosmos_uri, tls=True, tlsAllowInvalidCertificates=True)
    mongo_client.admin.command('ping')
    mongo_chatbot = mongo_client["sanathana_chatbot_v1"]
    app.logger.info("✅ Connected to Azure Cosmos DB (MongoDB vCore)!")
except Exception as e:
    app.logger.error(f"❌ Cosmos DB Connection Failed: {e}")
    mongo_chatbot = None

# ✅ Register Blueprints (APIs)
from auth import auth_bp
from chatbot import chatbot_bp

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(chatbot_bp, url_prefix="/chatbot")

# ✅ Serve static files (React build assets)
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(app.static_folder, 'static'), filename)

# ✅ Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

# ✅ Fallback route to serve index.html for non-API routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react_app(path):
    if path.startswith(("auth", "chatbot", "api")):
        return jsonify({"error": "API route not found"}), 404
    return send_from_directory(app.static_folder, 'index.html')

# ✅ Run Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
