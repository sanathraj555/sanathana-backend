import mysql.connector
import os
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_PATH = os.path.join(BASE_DIR, "DigiCertGlobalRootG2.crt.pem")

def get_db_connection():
    try:
        if not os.path.exists(CERT_PATH):
            logging.error(f"❌ SSL certificate not found at: {CERT_PATH}")
        else:
            logging.info(f"✅ SSL certificate loaded from: {CERT_PATH}")

        conn = mysql.connector.connect(
            host="sanathanamysql.mysql.database.azure.com",
            user="techlabs",
            password="labs@123",
            database="sanathana_chatbot_db",
            ssl_ca=CERT_PATH
        )
        logging.info("✅ DB Connection successful.")
        return conn

    except mysql.connector.Error as err:
        logging.error(f"❌ DB Connection failed: {err}")
        raise
