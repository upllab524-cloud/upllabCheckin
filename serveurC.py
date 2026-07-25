import os
import socket
import datetime
import jinja2
from flask import Flask, request, jsonify, render_template
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv
from supabase import Client, create_client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_DATABASE_URL = os.environ.get("SUPABASE_DATABASE_URL") or os.environ.get("DATABASE_URL")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DATABASE_URL") or SUPABASE_DATABASE_URL
    if db_url:
        # Supabase et Heroku utilisent parfois postgres://, psycopg2 attend postgresql://
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        # Activation automatique de SSL si la connexion pointe vers Supabase
        if "supabase" in db_url and "sslmode" not in db_url:
            return psycopg2.connect(db_url, cursor_factory=RealDictCursor, sslmode='require')
        return psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


def serialize_row(row):
    serialized = {}
    for key, value in row.items():
        if isinstance(value, (datetime.datetime, datetime.date)):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    return serialized


def add_machine_record(machine_code, ip_adress=None, statut='VERROUILLEE'):
    machine_code = (machine_code or '').strip()
    if not machine_code:
        raise ValueError("Le code de la machine est obligatoire.")

    ip_adress = (ip_adress or '').strip() or None
    statut = (statut or 'VERROUILLEE').strip().upper()

    conn = None
    cursor = None
    try:
        if is_supabase_enabled():
            existing = supabase_fetch_machine(machine_code)
            if existing:
                return existing

            inserted = supabase_insert('machines', {
                'machine_code': machine_code,
                'ip_adress': ip_adress,
                'statut': statut
            })
            if inserted:
                return inserted[0] if isinstance(inserted, list) else inserted
            return {'machine_code': machine_code, 'ip_adress': ip_adress, 'statut': statut}

        conn = get_db_connexion()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, machine_code, ip_adress, statut FROM machines WHERE machine_code=%s",
            (machine_code,)
        )
        existing = cursor.fetchone()
        if existing:
            return serialize_row(existing)

        cursor.execute(
            """
            INSERT INTO machines (machine_code, ip_adress, statut)
            VALUES (%s, %s, %s)
            RETURNING id, machine_code, ip_adress, statut
            """,
            (machine_code, ip_adress, statut)
        )
        row = cursor.fetchone()
        conn.commit()
        return serialize_row(row) if row else {'machine_code': machine_code, 'ip_adress': ip_adress, 'statut': statut}
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def is_supabase_enabled():
    return supabase is not None


def supabase_fetch_student(matricule, active=True):
    if not is_supabase_enabled():
        return None
    query = supabase.table('students').select('*').eq('matricule', matricule)
    if active:
        query = query.eq('is_active', True)
    try:
        result = query.execute()
        if not result.data:
            return None
        return result.data[0]
    except Exception:
        return None


def supabase_fetch_machine(machine_code):
    if not is_supabase_enabled():
        return None
    try:
        result = supabase.table('machines').select('*').eq('machine_code', machine_code).execute()
        if not result.data:
            return None
        return result.data[0]
    except Exception:
        return None


def supabase_insert(table, record):
    if not is_supabase_enabled():
        return None
    result = supabase.table(table).insert(record).execute()
    return result.data


def supabase_update(table, match, record):
    if not is_supabase_enabled():
        return None
    query = supabase.table(table).update(record)
    for k, v in match.items():
        query = query.eq(k, v)
    result = query.execute()
    return result.data


def init_db():
    """Initialise la structure de la base de données au démarrage si nécessaire"""
    if is_supabase_enabled() and not SUPABASE_DATABASE_URL:
        print("[BDD] Supabase activé sans URL PostgreSQL. Ignorer l'initialisation locale.")
        return
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
        if is_supabase_enabled():
            machine = supabase_fetch_machine(machine_code)
            if machine and machine.get('statut') == 'DEVERROUILLEE':
                unlocked_machines.add(machine_code)
                return jsonify({"unlocked": True, "message": "Déverrouillé (Supabase)"})
        else:
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
        if is_supabase_enabled():
            existing = supabase_fetch_student(matricule, active=False)
            if existing:
                return jsonify({"success": False, "message": "Ce matricule est déjà enregistré. Veuillez vous connecter."}), 400

            hashed_password = generate_password_hash(password)
            supabase_insert('students', {
                'nom': nom,
                'postnom': postnom,
                'prenom': prenom,
                'faculte': faculte,
                'filiere': filiere,
                'promotion': promotion,
                'matricule': matricule,
                'password_hash': hashed_password,
                'is_active': True
            })
        else:
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
        if is_supabase_enabled():
            student = supabase_fetch_student(matricule, active=True)

            if not student:
                return jsonify({"success": False, "message": "Identité inconnue. Veuillez d'abord créer un compte."}), 401

            if not check_password_hash(student['password_hash'], password):
                return jsonify({"success": False, "message": "Mot de passe incorrect."}), 401

            machine = supabase_fetch_machine(machine_code)
            if not machine:
                machine = add_machine_record(machine_code, statut='DEVERROUILLEE')

            supabase_insert('inspection', {
                'student_id': student['id'],
                'machine_id': machine['id'],
                'has_mouse': has_mouse,
                'has_keyboard': has_keyboard,
                'has_power_cable': has_power_cable,
                'has_hdmi_cable': has_hdmi_cable,
                'has_power_extension': has_power_extension,
                'comments': comments
            })

            supabase_update('machines', {'machine_code': machine_code}, {'statut': 'DEVERROUILLEE'})
        else:
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
            machine = add_machine_record(machine_code, statut='DEVERROUILLEE')
            if not machine:
                return jsonify({"success": False, "message": "Impossible de préparer la machine."}), 500

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


@app.route('/api/admin/machines', methods=['GET'])
def list_machines_endpoint():
    try:
        if is_supabase_enabled():
            result = supabase.table('machines').select('*').order('id', desc=False).execute()
            machines = [serialize_row(row) for row in (result.data or [])]
            return jsonify({"success": True, "machines": machines})

        conn = get_db_connexion()
        cursor = conn.cursor()
        cursor.execute("SELECT id, machine_code, ip_adress, statut FROM machines ORDER BY id ASC")
        rows = cursor.fetchall()
        machines = [serialize_row(row) for row in rows]
        return jsonify({"success": True, "machines": machines})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/admin/machines', methods=['POST'])
def add_machine_endpoint():
    data = request.json or {}
    machine_code = (data.get('machine_code') or '').strip()
    ip_adress = (data.get('ip_adress') or '').strip()
    statut = (data.get('statut') or 'VERROUILLEE').strip().upper()

    if not machine_code:
        return jsonify({"success": False, "message": "Le code de la machine est obligatoire."}), 400

    try:
        machine = add_machine_record(machine_code, ip_adress=ip_adress, statut=statut)
        return jsonify({
            "success": True,
            "message": f"Machine {machine_code} ajoutée avec succès.",
            "machine": machine
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Erreur lors de l'ajout de la machine: {str(e)}"}), 500


@app.route('/api/admin/machines/<int:machine_id>', methods=['PUT'])
def update_machine_endpoint(machine_id):
    data = request.json or {}
    machine_code = (data.get('machine_code') or '').strip()
    ip_adress = (data.get('ip_adress') or '').strip()
    statut = (data.get('statut') or 'VERROUILLEE').strip().upper()

    if not machine_code:
        return jsonify({"success": False, "message": "Le code de la machine est obligatoire."}), 400

    try:
        if is_supabase_enabled():
            result = supabase.table('machines').update({
                'machine_code': machine_code,
                'ip_adress': ip_adress or None,
                'statut': statut
            }).eq('id', machine_id).execute()
            machine = (result.data or [None])[0]
            return jsonify({"success": True, "message": "Machine mise à jour.", "machine": serialize_row(machine) if machine else None})

        conn = get_db_connexion()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE machines SET machine_code=%s, ip_adress=%s, statut=%s WHERE id=%s RETURNING id, machine_code, ip_adress, statut",
            (machine_code, ip_adress or None, statut, machine_id)
        )
        row = cursor.fetchone()
        conn.commit()
        return jsonify({"success": True, "message": "Machine mise à jour.", "machine": serialize_row(row) if row else None})
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.rollback()
        return jsonify({"success": False, "message": f"Erreur lors de la mise à jour: {str(e)}"}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/admin/machines/<int:machine_id>', methods=['DELETE'])
def delete_machine_endpoint(machine_id):
    try:
        if is_supabase_enabled():
            supabase.table('inspection').delete().eq('machine_id', machine_id).execute()
            supabase.table('machines').delete().eq('id', machine_id).execute()
            return jsonify({"success": True, "message": "Machine supprimée."})

        conn = get_db_connexion()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM inspection WHERE machine_id=%s", (machine_id,))
        cursor.execute("DELETE FROM machines WHERE id=%s", (machine_id,))
        conn.commit()
        return jsonify({"success": True, "message": "Machine supprimée."})
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.rollback()
        return jsonify({"success": False, "message": f"Erreur lors de la suppression: {str(e)}"}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/admin', methods=['GET'])
def admin_page():
    return render_template('admin.html')


@app.route('/api/admin/students', methods=['GET'])
def admin_get_students():
    search = (request.args.get('q') or '').strip().lower()
    try:
        if is_supabase_enabled():
            result = supabase.table('students').select('*').order('created_at', desc=True).execute()
            students = [serialize_row(row) for row in (result.data or [])]
            if search:
                students = [s for s in students if any(search in str(s.get(field, '') or '').lower() for field in ['matricule', 'nom', 'postnom', 'prenom', 'faculte', 'filiere', 'promotion'])]
            return jsonify({"success": True, "students": students})

        conn = get_db_connexion()
        cursor = conn.cursor()
        if search:
            search_pattern = f"%{search}%"
            cursor.execute(
                """
                SELECT id, nom, postnom, prenom, faculte, filiere, promotion, matricule, is_active, created_at
                FROM students
                WHERE matricule ILIKE %s OR nom ILIKE %s OR postnom ILIKE %s OR prenom ILIKE %s OR faculte ILIKE %s OR filiere ILIKE %s OR promotion ILIKE %s
                ORDER BY created_at DESC
                """,
                (search_pattern, search_pattern, search_pattern, search_pattern, search_pattern, search_pattern, search_pattern)
            )
        else:
            cursor.execute(
                "SELECT id, nom, postnom, prenom, faculte, filiere, promotion, matricule, is_active, created_at "
                "FROM students ORDER BY created_at DESC"
            )
        rows = cursor.fetchall()
        students = [serialize_row(row) for row in rows]
        return jsonify({"success": True, "students": students})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/admin/summary', methods=['GET'])
def admin_summary():
    try:
        if is_supabase_enabled():
            students_result = supabase.table('students').select('*').execute()
            machines_result = supabase.table('machines').select('*').execute()
            inspections_result = supabase.table('inspection').select('*').execute()

            students = students_result.data or []
            machines = machines_result.data or []
            inspections = inspections_result.data or []

            return jsonify({
                "success": True,
                "summary": {
                    "total_students": len(students),
                    "active_students": sum(1 for s in students if s.get('is_active')),
                    "total_machines": len(machines),
                    "total_inspections": len(inspections)
                }
            })

        conn = get_db_connexion()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total_students, SUM(CASE WHEN is_active THEN 1 ELSE 0 END) AS active_students FROM students")
        student_counts = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) AS total_machines FROM machines")
        machines_count = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) AS total_inspections FROM inspection")
        inspection_count = cursor.fetchone()

        return jsonify({
            "success": True,
            "summary": {
                "total_students": student_counts.get('total_students', 0),
                "active_students": student_counts.get('active_students', 0) or 0,
                "total_machines": machines_count.get('total_machines', 0),
                "total_inspections": inspection_count.get('total_inspections', 0)
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
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