import sqlite3
import os
import sys
import socket
import datetime

def test_write_access(directory_path):
    """Intenta crear el directorio y escribir un archivo de prueba para validar el acceso real."""
    try:
        os.makedirs(directory_path, exist_ok=True)
        test_file = os.path.join(directory_path, ".write_test")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception:
        return False


def get_user_data_dir():
    """Retorna una ruta absoluta y escribible para los datos del usuario."""
    # 1. Intentar LOCALAPPDATA
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        path = os.path.join(local_appdata, "Nexus")
        if test_write_access(path):
            return path

    # 2. Intentar APPDATA
    appdata = os.environ.get("APPDATA")
    if appdata:
        path = os.path.join(appdata, "Nexus")
        if test_write_access(path):
            return path

    # 3. Intentar USERPROFILE
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        path = os.path.join(user_profile, "AppData", "Local", "Nexus")
        if test_write_access(path):
            return path

    # 4. Fallback al directorio del ejecutable o CWD
    if getattr(sys, 'frozen', False):
        path = os.path.join(os.path.dirname(sys.executable), ".nexus")
    else:
        path = os.path.abspath(".nexus")
    if test_write_access(path):
        return path

    # 5. Último recurso absoluto: Carpeta temporal de Windows (siempre escribible)
    import tempfile
    return tempfile.gettempdir()


DB_PATH = os.path.join(get_user_data_dir(), 'audit_logs.db')

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de transferencias / instalaciones
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            hostname TEXT NOT NULL,
            profile_name TEXT,
            src TEXT,
            dst TEXT,
            duration TEXT,
            status TEXT,
            details TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def log_transfer(profile_name, src, dst, duration, status, details=""):
    """Registra una transferencia en la base de datos."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        hostname = socket.gethostname()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Asegurar que src y dst sean cadenas de texto
        if isinstance(src, list):
            src = ", ".join(src)
        if isinstance(dst, list):
            dst = ", ".join(dst)
            
        cursor.execute('''
            INSERT INTO transfers (timestamp, hostname, profile_name, src, dst, duration, status, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (now, hostname, profile_name, src, dst, duration, status, details))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging to DB: {e}")

def get_stats():
    """Obtiene estadísticas generales para el dashboard."""
    stats = {
        "total_transfers": 0,
        "success_rate": 0,
        "recent_logs": []
    }
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Total
        cursor.execute('SELECT COUNT(*) FROM transfers')
        total = cursor.fetchone()[0]
        stats["total_transfers"] = total
        
        # Success Rate
        cursor.execute('SELECT COUNT(*) FROM transfers WHERE status = "Success"')
        success = cursor.fetchone()[0]
        if total > 0:
            stats["success_rate"] = int((success / total) * 100)
            
        # Recent logs (last 5)
        cursor.execute('SELECT timestamp, profile_name, duration, status, src, dst, details FROM transfers ORDER BY id DESC LIMIT 5')
        logs = cursor.fetchall()
        stats["recent_logs"] = [{
            "date": l[0],
            "profile": l[1] or "Manual",
            "duration": l[2],
            "status": l[3],
            "src": l[4],
            "dst": l[5],
            "details": l[6]
        } for l in logs]
        
        conn.close()
    except Exception as e:
        print(f"Error getting stats from DB: {e}")
        
    return stats

# Inicializar DB al cargar el módulo
if not os.path.exists(DB_PATH):
    init_db()
