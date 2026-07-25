import os
import socket
import jinja2
from flask import Flask, request, jsonify, render_template
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# initialisation de l'application Flask
app = Flask(__name__, template_folder=BASE_DIR, static_folder=BASE_DIR)

# Permet à Flask de trouver les fichiers templates directement à la racine '.' (hors dossier) ou dans le dossier 'templates'
app.jinja_loader = jinja2.ChoiceLoader([
    jinja2.FileSystemLoader(BASE_DIR),
    jinja2.FileSystemLoader(os.path.join(BASE_DIR, 'templates'))
])

# configuration de la base de données (Supporte Render DATABASE_URL / Env Variables)
DATABASE_URL = os.environ.get("DATABASE_URL")

DB_CONFIG = {
    "dbname": os.environ.get("DB_NAME", "uplab"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "Vayle123UpllabChecking2027#"),
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432")
}

# fonction et etablissement de connexion 
def get_db_connexion():
    if DATABASE_URL:
        # En hébergement Render/PostgreSQL Cloud
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

# Mémoire vive des machines déverrouillées (accessible à l'agent local)
unlocked_machines = set()

# -------------Route de vérification du statut par l'agent local PC-------------
@app.route('/api/status/<machine_code>', methods=['GET'])
def check_machine_status(machine_code):
    """Permet à l'agent local (agentv.py) sur le PC du labo d'interroger Render"""
    if machine_code in unlocked_machines:
        return jsonify({"unlocked": True, "message": "Déverrouillé"})
    
    conn = None
    cursor = None
    try:
        conn = get_db_connexion()
        cursor = conn.cursor()
        cursor.execute("SELECT statut FROM machines WHERE machine_code=%s", (machine_code,))
        machine = cursor.fetchone()
        if machine and machine.get('statut') == 'DEVERROUILLEE':
            unlocked_machines.add(machine_code)
            return jsonify({"unlocked": True, "message": "Déverrouillé (BDD)"})
    except Exception:
        pass
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
        
    return jsonify({"unlocked": False})

# -------------Route de scan QR Code (Interface Web)------------------------
@app.route('/', methods=['GET'])
@app.route('/scan', methods=['GET'])
def scan_page():
    pc_code = request.args.get('pc', 'UPLAB-PC-01')
    try:
        return render_template('scan.html', pc_code=pc_code)
    except Exception as e:
        # Solution de secours infaillible : lecture directe de scan.html si le loader Jinja signale une exception
        scan_path = os.path.join(BASE_DIR, 'scan.html')
        if not os.path.exists(scan_path):
            scan_path = os.path.join(BASE_DIR, 'templates', 'scan.html')
        with open(scan_path, 'r', encoding='utf-8') as f:
            content = f.read().replace('{{ pc_code }}', pc_code)
            return content, 200, {'Content-Type': 'text/html; charset=utf-8'}

# -------------Route de deverouillages smartlocker--------------------------
@app.route('/api/unlock', methods=['POST'])
def unlock_machine():
    data = request.json or {}
    machine_code = data.get('machine_code') or data.get('pc')
    matricule = data.get('matricule')
    password = data.get('password')
    
    # Elements de check list
    has_mouse = data.get('has_mouse', True)
    has_keyboard = data.get('has_keyboard', True)
    has_power_cable = data.get('has_power_cable', True)
    has_hdmi_cable = data.get('has_hdmi_cable', True)
    has_power_extension = data.get('has_power_extension', True)
    comments = data.get('comments', '')

    conn = None
    cursor = None

    try:
        conn = get_db_connexion()
        cursor = conn.cursor()

        # 1------premiere verification de l'etudiant-----
        cursor.execute("SELECT * FROM students WHERE matricule=%s AND is_active = TRUE", (matricule,))
        student = cursor.fetchone()

        if not student or not check_password_hash(student['password_hash'], password):
            return jsonify({"success": False, "message": "Matricule ou mot de passe incorrect"}), 401

        # 2-------verification des infos sur machines-------
        cursor.execute("SELECT * FROM machines WHERE machine_code=%s", (machine_code,))
        machine = cursor.fetchone()

        if not machine:
            return jsonify({"success": False, "message": "Machine non trouvée"}), 404

        # 3-------enregistrement de l'inspection BDD
        cursor.execute("""
        INSERT INTO inspection(student_id, machine_id, has_mouse, has_keyboard, has_power_cable, has_hdmi_cable, has_power_extension, comments)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (student['id'], machine['id'], has_mouse, has_keyboard, has_power_cable, has_hdmi_cable, has_power_extension, comments))
        conn.commit()

        # -----Mise a jours de l'etat de la machine-----
        cursor.execute("UPDATE machines SET statut = 'DEVERROUILLEE' WHERE id = %s", (machine['id'],))
        conn.commit()

        # Enregistrer la machine comme déverrouillée
        if machine_code:
            unlocked_machines.add(machine_code)

        # ----- envoie de l'ordre socket si possible (local IP) -----
        pc_ip = machine.get('ip_adress')
        if pc_ip:
            send_unlock_socket(pc_ip)

        return jsonify({"success": True, "message": f"Machine {machine_code} déverrouillée avec succès !"})

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": f"Erreur serveur: {str(e)}"}), 500
    finally:
        # fermeture de la connexion
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def send_unlock_socket(ip_address, port=65432):
    """envoie un message socket simple pour deverrouiller le pc"""
    try:
        # message 
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((ip_address, port))

        # envoie du message 
        message = b"DEVERROUILLAGE"
        s.sendall(message)
        s.close()

        return True
    except Exception as e:
        return False

# ----------definition du port d'ecoute---------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"Serveur de déverrouillage UPLAB démarré sur http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)