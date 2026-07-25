# importation de library necessaire
import socket
from flask import Flask, request, jsonify, render_template
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash

# initialisation de l'application Flask
app = Flask(__name__)

# configuration de la base de donnes
DB_CONFIG = {
    "dbname": "uplab",
    "user": "postgres",
    "password": "Vayle123UpllabChecking2027#",
    "host": "localhost",
    "port": "5432"
}

# fonction et etablissement de connexion 
def get_db_connexion():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

# -------------Route de scan QR Code (Interface Web)------------------------
@app.route('/scan', methods=['GET'])
def scan_page():
    pc_code = request.args.get('pc', 'UPLAB-PC-01')
    return render_template('scan.html', pc_code=pc_code)

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

        # ----- envoie de l'ordre socket directement au pc du labo-----
        pc_ip = machine['ip_adress']
        socket_success = send_unlock_socket(pc_ip)

        if socket_success:
            return jsonify({"success": True, "message": f"Machine {machine_code} déverrouillée avec succès !"})
        else:
            return jsonify({"success": False, "message": "Inspection enregistrée mais la machine est injoignable (agent hors ligne)."})

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
    print("Serveur de déverrouillage UPLAB démarré sur http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)