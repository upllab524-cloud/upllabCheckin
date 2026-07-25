import socket
import threading
import subprocess
import time
import os
import base64
from flask import Flask, render_template_string, send_file

app = Flask(__name__)

def get_logo_b64():
    """Charge le logo en base64 depuis le fichier local logo.png ou logo_b64.txt"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    png_path = os.path.join(base_dir, "logo.png")
    if os.path.exists(png_path):
        try:
            with open(png_path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception:
            pass
            
    txt_path = os.path.join(base_dir, "logo_b64.txt")
    if os.path.exists(txt_path):
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

# --- Écran de verrouillage full screen blanc avec logo UPL ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Poste Verrouillé - Université Protestante de Lubumbashi</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif;
        }

        body {
            background-color: #ffffff;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(0, 51, 170, 0.03) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(245, 158, 11, 0.03) 0%, transparent 40%),
                radial-gradient(circle at 50% 50%, rgba(239, 68, 68, 0.02) 0%, transparent 60%);
            height: 100vh;
            width: 100vw;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            align-items: center;
            color: #1e293b;
            overflow: hidden;
            user-select: none;
        }

        /* Barre supérieure */
        .top-bar {
            width: 100%;
            padding: 24px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .clock-container {
            text-align: left;
        }

        .clock-time {
            font-size: 28px;
            font-weight: 700;
            color: #002677;
            letter-spacing: -0.5px;
        }

        .clock-date {
            font-size: 13px;
            font-weight: 500;
            color: #64748b;
            text-transform: capitalize;
        }

        .system-status {
            display: flex;
            align-items: center;
            gap: 10px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 8px 18px;
            border-radius: 30px;
            font-size: 13px;
            font-weight: 600;
            color: #334155;
            box-shadow: 0 2px 6px rgba(0,0,0,0.02);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background-color: #10b981;
            border-radius: 50%;
            box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.2);
            animation: pulse-green 2s infinite;
        }

        /* Carte principale centrale */
        .main-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            width: 100%;
            max-width: 620px;
            padding: 0 20px;
            text-align: center;
        }

        .card {
            background: #ffffff;
            border: 1px solid rgba(226, 232, 240, 0.9);
            border-radius: 32px;
            padding: 40px 36px;
            width: 100%;
            box-shadow: 
                0 25px 60px -15px rgba(0, 38, 119, 0.07),
                0 10px 20px -5px rgba(0, 0, 0, 0.03);
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        /* Logo de l'Université */
        .logo-wrapper {
            position: relative;
            margin-bottom: 22px;
            width: 150px;
            height: 150px;
            background: #ffffff;
            border-radius: 50%;
            box-shadow: 0 6px 20px rgba(0, 38, 119, 0.08);
            border: 4px solid #f1f5f9;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .logo-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 50%;
            display: block;
        }

        /* Titres institutionnels */
        .univ-title {
            font-size: 19px;
            font-weight: 700;
            color: #002677;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-bottom: 4px;
        }

        .univ-sub {
            font-size: 13.5px;
            color: #64748b;
            font-weight: 500;
            margin-bottom: 20px;
        }

        .divider {
            width: 60px;
            height: 3px;
            background: linear-gradient(90deg, #002677, #f59e0b, #ef4444);
            border-radius: 3px;
            margin-bottom: 20px;
        }

        /* Badges de statut et PC */
        .badge-group {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }

        .lock-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: #fef2f2;
            color: #dc2626;
            border: 1px solid #fee2e2;
            padding: 7px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }

        .pc-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: #f0f9ff;
            color: #0284c7;
            border: 1px solid #e0f2fe;
            padding: 7px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 700;
        }

        /* Instructions */
        .instruction-box {
            background: #f8fafc;
            border: 1px dashed #cbd5e1;
            border-radius: 16px;
            padding: 18px 20px;
            width: 100%;
        }

        .instruction-header {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            margin-bottom: 8px;
            font-weight: 700;
            font-size: 14px;
            color: #002677;
        }

        .instruction-text {
            color: #334155;
            font-size: 14.5px;
            line-height: 1.6;
            font-weight: 400;
        }

        .instruction-text b {
            color: #002677;
            font-weight: 600;
        }

        /* Pied de page */
        .footer-bar {
            width: 100%;
            padding: 24px;
            text-align: center;
            font-size: 12px;
            color: #94a3b8;
            font-weight: 500;
        }

        @keyframes pulse-green {
            0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
            70% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
            100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    </style>
</head>
<body>

    <!-- Barre Supérieure -->
    <div class="top-bar">
        <div class="clock-container">
            <div class="clock-time" id="clock-time">00:00:00</div>
            <div class="clock-date" id="clock-date">Chargement...</div>
        </div>
        <div class="system-status">
            <div class="status-dot"></div>
            <span>SmartLocker • En attente</span>
        </div>
    </div>

    <!-- Conteneur Principal -->
    <div class="main-container">
        <div class="card">
            <!-- Logo Université -->
            <div class="logo-wrapper">
                <img src="data:image/png;base64,{{ logo_b64 }}" alt="Logo UPL" class="logo-img" onerror="this.src='/logo.png'">
            </div>

            <!-- Titres -->
            <h1 class="univ-title">Université Protestante de Lubumbashi</h1>
            <p class="univ-sub">Laboratoire Informatique • Système SmartLocker</p>

            <div class="divider"></div>

            <!-- Badges -->
            <div class="badge-group">
                <div class="lock-badge">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                    </svg>
                    <span>POSTE VERROUILLÉ</span>
                </div>
                <div class="pc-badge">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                        <line x1="8" y1="21" x2="16" y2="21"></line>
                        <line x1="12" y1="17" x2="12" y2="21"></line>
                    </svg>
                    <span>UPLLAB-PC-20</span>
                </div>
            </div>

            <!-- Box d'Instructions -->
            <div class="instruction-box">
                <div class="instruction-header">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#002677" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="3" y="3" width="7" height="7" rx="1"></rect>
                        <rect x="14" y="3" width="7" height="7" rx="1"></rect>
                        <rect x="14" y="14" width="7" height="7" rx="1"></rect>
                        <rect x="3" y="14" width="7" height="7" rx="1"></rect>
                    </svg>
                    <span>Scanner le QR Code</span>
                </div>
                <p class="instruction-text">
                    Pour utiliser cet ordinateur, veuillez scanner le <b>QR Code</b> collé sur l'écran ou la table à l'aide de votre smartphone.
                </p>
            </div>
        </div>
    </div>

    <!-- Pied de Page -->
    <div class="footer-bar">
        © Université Protestante de Lubumbashi — VÉRITÉ ET LIBERTÉ
    </div>

    <script>
        // Horloge temps réel en français
        function updateClock() {
            const now = new Date();
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            const seconds = String(now.getSeconds()).padStart(2, '0');
            document.getElementById('clock-time').textContent = `${hours}:${minutes}:${seconds}`;

            const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
            document.getElementById('clock-date').textContent = now.toLocaleDateString('fr-FR', options);
        }
        updateClock();
        setInterval(updateClock, 1000);

        // Vérifie toutes les secondes si la machine a reçu l'ordre de déverrouillage
        setInterval(async () => {
            try {
                let res = await fetch('/status');
                let data = await res.json();
                if (data.unlocked) {
                    window.close(); // Ferme le navigateur
                }
            } catch(e) {
                console.error("Erreur statut:", e);
            }
        }, 1000);
    </script>
</body>
</html>
"""

is_unlocked = False

@app.route('/')
def index():
    logo_data = get_logo_b64()
    return render_template_string(HTML_TEMPLATE, logo_b64=logo_data)

@app.route('/logo.png')
def serve_logo():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    png_path = os.path.join(base_dir, "logo.png")
    if os.path.exists(png_path):
        return send_file(png_path, mimetype='image/png')
    return "", 404

@app.route('/status')
def status():
    return {"unlocked": is_unlocked}

def listen_socket():
    global is_unlocked
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('0.0.0.0', 65432))
    s.listen(1)
    
    while True:
        try:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(1024).decode('utf-8')
                if data in ["UNLOCK_NOW", "DEVERROUILLAGE"]:
                    is_unlocked = True
                    # Ferme le navigateur Edge/Chrome sous Windows
                    subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], capture_output=True)
                    break
        except Exception:
            pass

if __name__ == '__main__':
    # 1. Lancer l'écoute Socket dans un thread
    threading.Thread(target=listen_socket, daemon=True).start()
    
    # 2. Ouvrir Edge en mode Kiosk plein écran sur la page Flask locale
    threading.Thread(target=lambda: (
        time.sleep(1),
        subprocess.run(["start", "msedge", "--kiosk", "http://localhost:5001", "--edge-kiosk-type=fullscreen"], shell=True)
    ), daemon=True).start()

    # 3. Démarrer le serveur Flask de l'agent PC
    app.run(port=5001)