import mysql.connector
import os

def get_db_connection():
    return mysql.connector.connect(
        host="sanathanamysql.mysql.database.azure.com",
        user="techlabs@sanathanamysql",
        password="techlabs@123",
        database="sanathana_chatbot_db",
        ssl_ca=os.path.abspath("DigiCertGlobalRootG2.crt.pem")
    )
