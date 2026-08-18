# ─────────────────────────────────────────────────────────────────────────────
# mover_fotos.py
# Mueve las fotos descargadas (desde Descargas) a las carpetas del catálogo
# ─────────────────────────────────────────────────────────────────────────────

import os
import shutil

DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")
DEST_ROOT  = r"C:\Users\Usuario\Desktop\CATALOGO\LA_LIGA"

# Lista de archivos a mover: (nombre_descargado, equipo, kit, publico)
FOTOS = [
    ("real-madrid-26-27-home-adulto.jpg",       "REAL_MADRID",     "HOME",  "A"),
    ("real-madrid-26-27-away-adulto.jpg",        "REAL_MADRID",     "AWAY",  "A"),
    ("real-madrid-26-27-third-adulto.jpg",       "REAL_MADRID",     "THIRD", "A"),
    ("real-madrid-26-27-home-nino.jpg",          "REAL_MADRID",     "HOME",  "N"),
    ("real-madrid-26-27-away-nino.jpg",          "REAL_MADRID",     "AWAY",  "N"),
    ("real-madrid-26-27-third-nino.jpg",         "REAL_MADRID",     "THIRD", "N"),
    ("barcelona-26-27-home-adulto.jpg",          "BARCELONA",       "HOME",  "A"),
    ("barcelona-26-27-away-adulto.jpg",          "BARCELONA",       "AWAY",  "A"),
    ("barcelona-26-27-third-adulto.jpg",         "BARCELONA",       "THIRD", "A"),
    ("atletico-madrid-26-27-home-adulto.jpg",    "ATLETICO_MADRID", "HOME",  "A"),
    ("atletico-madrid-26-27-away-adulto.jpg",    "ATLETICO_MADRID", "AWAY",  "A"),
    ("sevilla-26-27-home-adulto.jpg",            "SEVILLA",         "HOME",  "A"),
    ("sevilla-26-27-home-nino.jpg",              "SEVILLA",         "HOME",  "N"),
    ("real-betis-26-27-home-adulto.jpg",         "REAL_BETIS",      "HOME",  "A"),
    ("athletic-bilbao-26-27-home-adulto.jpg",    "ATHLETIC_BILBAO", "HOME",  "A"),
    ("valencia-26-27-home-adulto.jpg",           "VALENCIA",        "HOME",  "A"),
    ("valencia-26-27-away-adulto.jpg",           "VALENCIA",        "AWAY",  "A"),
    ("osasuna-26-27-home-adulto.jpg",            "OSASUNA",         "HOME",  "A"),
    ("rayo-vallecano-26-27-home-adulto.jpg",     "RAYO_VALLECANO",  "HOME",  "A"),
    ("girona-26-27-away-adulto.jpg",             "GIRONA",          "AWAY",  "A"),
    ("espanyol-26-27-home-adulto.jpg",           "ESPANYOL",        "HOME",  "A"),
]

ok = 0
no_encontrado = 0

for nombre, equipo, kit, pub in FOTOS:
    origen = os.path.join(DOWNLOADS, nombre)
    carpeta = os.path.join(DEST_ROOT, equipo, "2026-27", "CAMISETAS")
    destino = os.path.join(carpeta, nombre)

    if os.path.exists(destino):
        print(f"  · Ya existe: {nombre}")
        ok += 1
        continue

    if not os.path.exists(origen):
        print(f"  ✗ No encontrado en Descargas: {nombre}")
        no_encontrado += 1
        continue

    os.makedirs(carpeta, exist_ok=True)
    shutil.move(origen, destino)
    print(f"  ✓ Movido: {nombre}")
    ok += 1

print()
print(f"  Completado: {ok} fotos en catálogo, {no_encontrado} no encontradas")
