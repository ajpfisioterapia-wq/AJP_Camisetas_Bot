# ─────────────────────────────────────────────────────────────────────────────
# descargar_fotos.py
# Descarga fotos 26/27 de equipos La Liga desde soccer-jersey-yupoo.com
# Guarda en: C:\Users\Usuario\Desktop\CATALOGO\LA_LIGA\[EQUIPO]\2026-27\CAMISETAS\
# ─────────────────────────────────────────────────────────────────────────────
# Ejecutar con: descargar_fotos.bat
# ─────────────────────────────────────────────────────────────────────────────

import os
import sys
import subprocess
import time

def instalar(paquete):
    subprocess.check_call([sys.executable, "-m", "pip", "install", paquete, "--quiet"])

for pkg in ["requests", "Pillow"]:
    try:
        __import__("PIL" if pkg == "Pillow" else pkg)
    except ImportError:
        print(f"Instalando {pkg}...")
        instalar(pkg)

import requests
from PIL import Image
from io import BytesIO

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────

DEST_ROOT = r"C:\Users\Usuario\Desktop\CATALOGO\LA_LIGA"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://soccer-jersey-yupoo.com/",
}

# ── LISTA DE IMÁGENES (URLs verificadas) ──────────────────────────────────────
# equipo  : nombre de carpeta
# kit     : HOME | AWAY | THIRD
# publico : A (adulto) | N (niño)
# url     : enlace directo a la imagen .webp

IMAGENES = [
    # ── REAL MADRID ──────────────────────────────────────────────────────────
    {"equipo": "REAL_MADRID", "kit": "HOME",  "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/05/2026-27-Real-Madrid-Soccer-Jersey-0.webp"},
    {"equipo": "REAL_MADRID", "kit": "AWAY",  "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/06/26-27-Real-Madrid-away-Soccer-Jersey-0.webp"},
    {"equipo": "REAL_MADRID", "kit": "THIRD", "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/05/Real-Madrid-2026-27-Third-Soccer-Jersey-0.webp"},
    {"equipo": "REAL_MADRID", "kit": "HOME",  "publico": "N",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/04/Kids-2026-27-Real-Madrid-Home-Soccer-Jersey-0.webp"},
    {"equipo": "REAL_MADRID", "kit": "AWAY",  "publico": "N",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/08/Kids-Kit-26-27-RM-Away-Soccer-Jersey-2.webp"},
    {"equipo": "REAL_MADRID", "kit": "THIRD", "publico": "N",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/06/26-27-Real-Madrid-Away-Kid-Soccer-Jersey-0.webp"},

    # ── BARCELONA ─────────────────────────────────────────────────────────────
    {"equipo": "BARCELONA", "kit": "HOME",  "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/01/26-27-Barc-Home-Soccer-Jersey-0.webp"},
    {"equipo": "BARCELONA", "kit": "AWAY",  "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/06/26-27-barcelona-special-Black-Soccer-Jersey-0.webp"},
    {"equipo": "BARCELONA", "kit": "THIRD", "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/06/26-27-barcelona-special-Navy-Soccer-Jersey-0.webp"},

    # ── ATLÉTICO DE MADRID ────────────────────────────────────────────────────
    {"equipo": "ATLETICO_MADRID", "kit": "HOME", "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/08/Atletico-Madrid-2026-27-Home-PlayerJersey-0.webp"},
    {"equipo": "ATLETICO_MADRID", "kit": "AWAY", "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/07/2026-27-Atletico-Madrid-Away-Soccer-Jersey-0.webp"},

    # ── SEVILLA ───────────────────────────────────────────────────────────────
    {"equipo": "SEVILLA", "kit": "HOME", "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/07/Sevilla-2026-27-Home-Soccer-Jersey-0.webp"},
    {"equipo": "SEVILLA", "kit": "HOME", "publico": "N",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/06/25-26-Sevilla-FC-Home-Kid-Soccer-Jersey-0.webp"},

    # ── REAL BETIS ────────────────────────────────────────────────────────────
    {"equipo": "REAL_BETIS", "kit": "HOME", "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/07/Real-Betis-2026-27-Home-Soccer-Jersey-0.webp"},

    # ── ATHLETIC BILBAO ───────────────────────────────────────────────────────
    {"equipo": "ATHLETIC_BILBAO", "kit": "HOME", "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/07/Athletic-Bilbao-2026-27-Home-Soccer-Jersey-0.webp"},

    # ── VALENCIA ──────────────────────────────────────────────────────────────
    {"equipo": "VALENCIA", "kit": "HOME", "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/06/26-27-Valencia-Home-Soccer-Jersey-0.webp"},
    {"equipo": "VALENCIA", "kit": "AWAY", "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/07/26-27-Valencia-Away-Soccer-Jersey-0.webp"},

    # ── OSASUNA ───────────────────────────────────────────────────────────────
    {"equipo": "OSASUNA", "kit": "HOME", "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/07/2026-27-Osasuna-Home-Soccer-Jersey-1.webp"},

    # ── RAYO VALLECANO ────────────────────────────────────────────────────────
    {"equipo": "RAYO_VALLECANO", "kit": "HOME", "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/06/26-27-Rayo-Vallecano-Home-Soccer-Jersey-0.webp"},

    # ── GIRONA ────────────────────────────────────────────────────────────────
    {"equipo": "GIRONA", "kit": "AWAY", "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/08/2026-27-Girona-Away-Soccer-Jersey-0.webp"},

    # ── ESPANYOL ──────────────────────────────────────────────────────────────
    {"equipo": "ESPANYOL", "kit": "HOME", "publico": "A",
     "url": "https://soccer-jersey-yupoo.com/wp-content/uploads/2026/07/Espanyol-2026-27-Home-Soccer-Jersey-0.webp"},
]

# Equipos sin productos 26/27 en el proveedor (no incluidos):
# VILLARREAL, REAL_SOCIEDAD, GETAFE, LEGANES, LAS_PALMAS,
# ALAVES, CELTA_VIGO, VALLADOLID, MALLORCA

# ── LÓGICA ────────────────────────────────────────────────────────────────────

def nombre_archivo(equipo, kit, publico):
    pub_str = "adulto" if publico == "A" else "nino"
    return f"{equipo.lower().replace('_', '-')}-26-27-{kit.lower()}-{pub_str}.jpg"

def ruta_destino(equipo, kit, publico):
    carpeta = os.path.join(DEST_ROOT, equipo, "2026-27", "CAMISETAS")
    return os.path.join(carpeta, nombre_archivo(equipo, kit, publico))

def descargar(img):
    dest = ruta_destino(img["equipo"], img["kit"], img["publico"])
    nombre = nombre_archivo(img["equipo"], img["kit"], img["publico"])

    if os.path.exists(dest):
        print(f"  · Ya existe: {nombre}")
        return "existia"

    etiqueta = f"[{img['kit']}-{'A' if img['publico']=='A' else 'N'}]"
    print(f"  ↓ {etiqueta}  {nombre}")

    try:
        r = requests.get(img["url"], headers=HEADERS, timeout=30)
        if r.status_code == 404:
            print(f"      ✗  404 Not Found — URL puede haber cambiado")
            return "error"
        r.raise_for_status()

        # Convertir webp → jpg con Pillow
        imagen = Image.open(BytesIO(r.content)).convert("RGB")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        imagen.save(dest, "JPEG", quality=90)

        kb = os.path.getsize(dest) // 1024
        print(f"      ✓  {nombre}  ({kb} KB)")
        return "ok"
    except Exception as e:
        print(f"      ✗  Error: {e}")
        return "error"

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 62)
    print("  DESCARGA DE FOTOS — La Liga 26/27")
    print("  Fuente: soccer-jersey-yupoo.com")
    print(f"  Destino: {DEST_ROOT}")
    print("=" * 62)
    print()

    equipos_vistos = []
    ok = err = existia = 0

    for img in IMAGENES:
        if img["equipo"] not in equipos_vistos:
            equipos_vistos.append(img["equipo"])
            print(f"\n── {img['equipo']} {'─' * (40 - len(img['equipo']))}")

        resultado = descargar(img)
        if resultado == "ok":
            ok += 1
        elif resultado == "existia":
            existia += 1
        else:
            err += 1

        time.sleep(0.4)   # pausa cortés entre descargas

    print(f"\n{'=' * 62}")
    print(f"  COMPLETADO")
    print(f"  ✓ Descargadas   : {ok}")
    print(f"  · Ya existían   : {existia}")
    print(f"  ✗ Errores       : {err}")
    if err:
        print(f"\n  Si hay errores 404, es posible que el proveedor haya")
        print(f"  actualizado sus URLs. Visita soccer-jersey-yupoo.com")
        print(f"  manualmente para obtener las imágenes actualizadas.")
    print(f"{'=' * 62}")
    input("\nPulsa ENTER para cerrar...")


if __name__ == "__main__":
    main()
