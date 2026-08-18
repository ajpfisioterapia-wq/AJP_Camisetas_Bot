# ─────────────────────────────────────────────────────────────────────────────
# config.py  —  Configuración del Bot de Camisetas
# ─────────────────────────────────────────────────────────────────────────────
# En LOCAL: los valores hardcodeados abajo sirven como fallback.
# En RAILWAY: pon las variables de entorno en el panel de Railway.
# ─────────────────────────────────────────────────────────────────────────────

import os

# ── BOT ──────────────────────────────────────────────────────────────────────
BOT_TOKEN     = os.environ.get("BOT_TOKEN",     "8913785060:AAGqhQwvEyvFxMfKurEzssTWdS8Pl8lJX18")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "2083455694"))

# ── BIZUM ─────────────────────────────────────────────────────────────────────
BIZUM_NUMERO = os.environ.get("BIZUM_NUMERO", "625 433 376")
BIZUM_NOMBRE = os.environ.get("BIZUM_NOMBRE", "Álvaro")

# ── RUTAS ─────────────────────────────────────────────────────────────────────
# En Railway: CATALOG_DIR=/data/CATALOGO  PEDIDOS_DIR=/data/pedidos
# En Railway el CATALOGO va junto al código en la carpeta /app/CATALOGO
_DEFAULT_CATALOG  = os.path.join(os.path.dirname(__file__), "CATALOGO")
_DEFAULT_PEDIDOS  = r"C:\Users\Usuario\Desktop\Pedido Camisetas"

CATALOG_DIR  = os.environ.get("CATALOG_DIR",  _DEFAULT_CATALOG)
_pedidos_dir = os.environ.get("PEDIDOS_DIR",  _DEFAULT_PEDIDOS)

PEDIDOS_XLSX = os.path.join(_pedidos_dir, "PEDIDOS_BOT.xlsx")
PEDIDOS_JSON = os.path.join(_pedidos_dir, "pedidos_pendientes.json")

# Crear la carpeta de pedidos si no existe (útil en Railway la primera vez)
os.makedirs(_pedidos_dir, exist_ok=True)

# ── PRECIOS SUPLEMENTO ────────────────────────────────────────────────────────
SUPLEM_NOMBRE_DORSAL = 3   # €  — añadido al PVP si el cliente pide personalización
SUPLEM_PARCHE_UCL    = 1   # €  — añadido al PVP si el cliente pide parche Champions

# ── CÓDIGOS DE DESCUENTO (privados — no mostrar al cliente) ───────────────────
CODIGOS_DESCUENTO = {
    "BETIS10": 10,   # 10 % de descuento
}

# ── TEXTOS DEL BOT ────────────────────────────────────────────────────────────
BIENVENIDA = (
    "👋 *¡Hola! Bienvenido a la tienda de camisetas* ⚽\n\n"
    "Selecciona el equipo que te interesa:"
)

TEXTO_PAGO = (
    "💳 *CÓMO PAGAR*\n\n"
    "Realiza el pago por *Bizum* a:\n"
    "📱 Número: `{numero}`\n"
    "👤 Nombre: {nombre}\n"
    "💬 Concepto: `PEDIDO-{ref}`\n\n"
    "Cuando hayas pagado, *envía aquí una foto del comprobante* 📸"
)
