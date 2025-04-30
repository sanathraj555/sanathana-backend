import mysql.connector
import os

def get_db_connection():
    try:
        cert_path = os.path.abspath("DigiCertGlobalRootG2.crt.pem")  # ✅ Full absolute path to SSL cert

        conn = mysql.connector.connect(
            host="sanathanamysql.mysql.database.azure.com",   # ✅ Corrected host name
            user="techlabs@sanathanamysql",           # ✅ Corrected user (user@newserver)
            password="techlabs@123",                         # ✅ Same password if unchanged
            database="sanathana_chatbot_db",
            ssl_disabled=True
            
        )

        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE();")
        db_name = cursor.fetchone()[0]
        print(f"✅ Connected to Database: {db_name}")
        return conn

    except mysql.connector.Error as err:
        print(f"❌ Database Connection Error: {err}")
        return None