import os
import socket
import jinja2
from flask import Flask, request, jsonify, render_template
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialisation de l'application Flask
app = Flask(__name__, template_folder=BASE_DIR, static_folder=BASE_DIR)

# Permet à Flask de trouver les templates à la racine '.' et dans 'templates/'
app.jinja_loader = jinja2.ChoiceLoader([
    jinja2.FileSystemLoader(BASE_DIR),
    jinja2.FileSystemLoader(os.path.join(BASE_DIR, 'templates'))
])

# Configuration BDD (Render DATABASE_URL ou variables d'environnement)
DATABASE_URL = os.environ.get("DATABASE_URL")

DB_CONFIG = {
    "dbname": os.environ.get("DB_NAME", "uplab"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "Vayle123UpllabChecking2027#"),
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432")
}

def get_db_connexion():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def init_db():
    """Initialise la structure de la base de données au démarrage si nécessaire"""
    conn = None
    cursor = None
    try:
        conn = get_db_connexion()
        cursor = conn.cursor()
        
        # Table des étudiants
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY,
                nom VARCHAR(100),
                postnom VARCHAR(100),
                prenom VARCHAR(100),
                faculte VARCHAR(150),
                filiere VARCHAR(150),
                promotion VARCHAR(50),
                matricule VARCHAR(50) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Ajout explicite des colonnes si la table existait déjà sans elles
        for col in [
            ("nom", "VARCHAR(100)"),
            ("postnom", "VARCHAR(100)"),
            ("prenom", "VARCHAR(100)"),
            ("faculte", "VARCHAR(150)"),
            ("filiere", "VARCHAR(150)"),
            ("promotion", "VARCHAR(50)")
        ]:
            cursor.execute(f"ALTER TABLE students ADD COLUMN IF NOT EXISTS {col[0]} {col[1]};")

        # Table des machines
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS machines (
                id SERIAL PRIMARY KEY,
                machine_code VARCHAR(50) UNIQUE NOT NULL,
                ip_adress VARCHAR(50),
                statut VARCHAR(50) DEFAULT 'VERROUILLEE'
            );
        """)

        # Table des inspections
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inspection (
                id SERIAL PRIMARY KEY,
                student_id INT REFERENCES students(id),
                machine_id INT REFERENCES machines(id),
                has_mouse BOOLEAN DEFAULT TRUE,
                has_keyboard BOOLEAN DEFAULT TRUE,
                has_power_cable BOOLEAN DEFAULT TRUE,
                has_hdmi_cable BOOLEAN DEFAULT TRUE,
                has_power_extension BOOLEAN DEFAULT TRUE,
                comments TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        print("[BDD] Tables vérifiées et initialisées avec succès.")
    except Exception as e:
        if conn: conn.rollback()
        print(f"[BDD Warning] Erreur d'initialisation BDD: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# Tente d'initialiser les tables BDD au chargement
try:
    init_db()
except Exception:
    pass

# Mémoire vive des machines déverrouillées (accessible à l'agent local PC)
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
        scan_path = os.path.join(BASE_DIR, 'scan.html')
        if not os.path.exists(scan_path):
            scan_path = os.path.join(BASE_DIR, 'templates', 'scan.html')
        with open(scan_path, 'r', encoding='utf-8') as f:
            content = f.read().replace('{{ pc_code }}', pc_code)
            return content, 200, {'Content-Type': 'text/html; charset=utf-8'}

# -------------Route d'inscription étudiant-------------------------------
@app.route('/api/register', methods=['POST'])
def register_student():
    data = request.json or {}
    nom = (data.get('nom') or '').strip()
    postnom = (data.get('postnom') or '').strip()
    prenom = (data.get('prenom') or '').strip()
    faculte = (data.get('faculte') or '').strip()
    filiere = (data.get('filiere') or '').strip()
    promotion = (data.get('promotion') or '').strip()
    matricule = (data.get('matricule') or '').strip()
    password = data.get('password') or ''

    if not matricule or not password:
        return jsonify({"success": False, "message": "Le matricule et le mot de passe sont obligatoires."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connexion()
        cursor = conn.cursor()

        # 1. Vérifier si le matricule existe déjà
        cursor.execute("SELECT id FROM students WHERE matricule = %s", (matricule,))
        existing = cursor.fetchone()
        if existing:
            return jsonify({"success": False, "message": "Ce matricule est déjà enregistré. Veuillez vous connecter."}), 400

        # 2. Hacher le mot de passe
        hashed_password = generate_password_hash(password)

        # 3. Insérer le nouvel étudiant
        cursor.execute("""
            INSERT INTO students (nom, postnom, prenom, faculte, filiere, promotion, matricule, password_hash, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        """, (nom, postnom, prenom, faculte, filiere, promotion, matricule, hashed_password))
        conn.commit()

        return jsonify({
            "success": True, 
            "message": f"Compte créé avec succès pour {prenom} {nom} ! Vous pouvez maintenant vous connecter."
        })
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"success": False, "message": f"Erreur lors de la création du compte: {str(e)}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# -------------Route de déverrouillage / connexion------------------------
@app.route('/api/unlock', methods=['POST'])
def unlock_machine():
    data = request.json or {}
    machine_code = data.get('machine_code') or data.get('pc') or 'UPLAB-PC-01'
    matricule = (data.get('matricule') or '').strip()
    password = data.get('password') or ''
    
    # Éléments de check list
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

        # 1. Vérification de l'étudiant
        cursor.execute("SELECT * FROM students WHERE matricule=%s AND is_active = TRUE", (matricule,))
        student = cursor.fetchone()

        if not student:
            return jsonify({"success": False, "message": "Identité inconnue. Veuillez d'abord créer un compte."}), 401

        if not check_password_hash(student['password_hash'], password):
            return jsonify({"success": False, "message": "Mot de passe incorrect."}), 401

        # 2. Vérification / Création automatique de la machine
        cursor.execute("SELECT * FROM machines WHERE machine_code=%s", (machine_code,))
        machine = cursor.fetchone()

        if not machine:
            # Créer automatiquement la machine si elle n'existe pas encore dans la BDD
            cursor.execute("""
                INSERT INTO machines (machine_code, statut) 
                VALUES (%s, 'DEVERROUILLEE') 
                RETURNING id, machine_code, ip_adress, statut
            """, (machine_code,))
            machine = cursor.fetchone()
            conn.commit()

        # 3. Enregistrement de l'inspection dans la BDD
        cursor.execute("""
            INSERT INTO inspection(student_id, machine_id, has_mouse, has_keyboard, has_power_cable, has_hdmi_cable, has_power_extension, comments)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (student['id'], machine['id'], has_mouse, has_keyboard, has_power_cable, has_hdmi_cable, has_power_extension, comments))

        # 4. Mise à jour de l'état de la machine
        cursor.execute("UPDATE machines SET statut = 'DEVERROUILLEE' WHERE id = %s", (machine['id'],))
        conn.commit()

        # Enregistrer la machine comme déverrouillée en mémoire vive (pour Render)
        if machine_code:
            unlocked_machines.add(machine_code)

        # Envoi d'ordre socket optionnel si IP locale présente
        pc_ip = machine.get('ip_adress')
        if pc_ip:
            send_unlock_socket(pc_ip)

        nom_complet = f"{student.get('prenom', '')} {student.get('nom', '')}".strip() or matricule
        return jsonify({"success": True, "message": f"Bienvenue {nom_complet} ! Machine {machine_code} déverrouillée."})

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": f"Erreur serveur: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def send_unlock_socket(ip_address, port=65432):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((ip_address, port))
        s.sendall(b"DEVERROUILLAGE")
        s.close()
        return True
    except Exception:
        return False

# Definition du port d'ecoute
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"Serveur de déverrouillage UPLAB démarré sur http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)