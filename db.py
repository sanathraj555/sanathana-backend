import mysql.connector
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_db_connection():
    return mysql.connector.connect(
        host="sanathanamysql.mysql.database.azure.com",
        user="techlabs@sanathanamysql",  # ✅ Remove @servername
        password="labs@123",
        database="sanathana_chatbot_db",
        ssl_ca=os.path.join(BASE_DIR, "DigiCertGlobalRootG2.crt.pem")
    )
