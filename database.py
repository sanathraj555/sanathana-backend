import mysql.connector

def get_db_connection():
    """Returns a local MySQL database connection."""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="sanath@sars",  # ✅ your local password
            database="sanathana_chatbot",
            auth_plugin="mysql_native_password"
        )
        return conn
    except mysql.connector.Error as err:
        print(f"❌ Database Connection Error: {err}")
        return None
