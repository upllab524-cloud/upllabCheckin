import os
import qrcode
from PIL import Image, ImageDraw, ImageFont

# Configuration
SERVER_IP = "192.168.1.100"  # IP du serveur central
SERVER_PORT = "5000"
TOTAL_MACHINES = 2
OUTPUT_DIR = "qr_codes_labo"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Charger le logo si présent
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")

logo_img = None
if os.path.exists(LOGO_PATH):
    try:
        logo_img = Image.open(LOGO_PATH).convert("RGBA")
    except Exception as e:
        print(f"Attention: Impossible de charger logo.png ({e})")

# Polices système Windows
def get_font(name, size):
    try:
        return ImageFont.truetype(name, size)
    except Exception:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            return ImageFont.load_default()

font_header = get_font("segoeuib.ttf", 16)
font_badge = get_font("segoeuib.ttf", 18)
font_sub = get_font("segoeui.ttf", 13)

def create_compact_qr_sticker(pc_name, url):
    # Format autocollant compact (500x500 px - idéal pour étiquette physique)
    size = 480
    
    img = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # 1. Bordure extérieure d'autocollant avec coins arrondis
    draw.rounded_rectangle([4, 4, size - 4, size - 4], radius=24, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
    
    # Ligne supérieure colorée
    draw.rounded_rectangle([4, 4, size - 4, 12], radius=6, fill=(0, 38, 119))
    
    # 2. En-tête compact avec Logo UPL
    current_y = 20
    if logo_img:
        logo_size = 42
        resized_logo = logo_img.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        img.paste(resized_logo, (24, current_y), resized_logo)
        
        # Texte à côté du logo
        draw.text((76, current_y + 4), "UPL — SmartLocker", fill=(0, 38, 119), font=font_header)
        draw.text((76, current_y + 24), "Scannez pour déverrouiller", fill=(100, 116, 139), font=font_sub)
    else:
        title_text = "UPL — SmartLocker Lab"
        bbox = draw.textbbox((0, 0), title_text, font=font_header)
        text_w = bbox[2] - bbox[0]
        draw.text(((size - text_w) // 2, current_y), title_text, fill=(0, 38, 119), font=font_header)
    
    current_y += 52

    # Ligne séparatrice fine
    draw.line([(24, current_y), (size - 24, current_y)], fill=(241, 245, 249), width=1)
    current_y += 14

    # 3. QR Code bleu marine
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="#002677", back_color="white").convert("RGBA")
    qr_display_size = 280
    qr_img_resized = qr_img.resize((qr_display_size, qr_display_size), Image.Resampling.LANCZOS)
    
    qr_x = (size - qr_display_size) // 2
    img.paste(qr_img_resized, (qr_x, current_y), qr_img_resized)
    current_y += qr_display_size + 14

    # 4. Badge du nom du poste (ex: UPLAB-PC-01)
    badge_text = f"POSTE : {pc_name}"
    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    badge_w = (bbox[2] - bbox[0]) + 32
    badge_h = (bbox[3] - bbox[1]) + 12
    badge_x = (size - badge_w) // 2
    
    draw.rounded_rectangle([badge_x, current_y, badge_x + badge_w, current_y + badge_h], radius=12, fill=(239, 246, 255), outline=(191, 219, 254), width=1)
    draw.text((badge_x + 16, current_y + 6), badge_text, fill=(29, 78, 216), font=font_badge)

    return img.convert("RGB")

print(f"Génération de {TOTAL_MACHINES} étiquettes/autocollants QR Code compacts...")

for i in range(1, TOTAL_MACHINES + 1):
    pc_name = f"UPLAB-PC-{i:02d}"
    url = f"http://{SERVER_IP}:{SERVER_PORT}/scan?pc={pc_name}"
    
    sticker = create_compact_qr_sticker(pc_name, url)
    file_path = os.path.join(OUTPUT_DIR, f"{pc_name}.png")
    sticker.save(file_path, "PNG", quality=95)

print(f"[OK] Terminé ! Les {TOTAL_MACHINES} étiquettes QR Code compactes sont enregistrées dans '{OUTPUT_DIR}'.")