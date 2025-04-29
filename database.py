import mysql.connector
import os

def get_db_connection():
    try:
        cert_path = os.path.abspath("DigiCertGlobalRootG2.crt.pem")  # ✅ Full absolute path to SSL cert

        conn = mysql.connector.connect(
            host="sanathanasql.mysql.database.azure.com",   # ✅ Corrected host name
            user="sanathanatechlabs@sanathanasql",           # ✅ Corrected user (user@newserver)
            password="Techlabs!123",                         # ✅ Same password if unchanged
            database="sanathana_chatbot",
            ssl_ca=cert_path,
            ssl_verify_cert=True,
            auth_plugin="mysql_native_password",
            pool_name="azurepool",
            pool_reset_session=True
        )

        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE();")
        db_name = cursor.fetchone()[0]
        print(f"✅ Connected to Database: {db_name}")
        return conn

    except mysql.connector.Error as err:
        print(f"❌ Database Connection Error: {err}")
        return None