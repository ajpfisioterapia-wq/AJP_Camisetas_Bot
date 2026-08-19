# ─────────────────────────────────────────────────────────────────────────────
# bot.py  —  Bot principal de camisetas para Telegram
# ─────────────────────────────────────────────────────────────────────────────
# Ejecutar:  python bot.py
# Requisitos: pip install python-telegram-bot openpyxl
# ─────────────────────────────────────────────────────────────────────────────

import logging
import os
import importlib
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes,
)
from telegram.constants import ParseMode

from config import (
    BOT_TOKEN, ADMIN_CHAT_ID, BIZUM_NUMERO, BIZUM_NOMBRE,
    SUPLEM_NOMBRE_DORSAL, SUPLEM_PARCHE_UCL, BIENVENIDA, TEXTO_PAGO,
    CODIGOS_DESCUENTO,
)
from ticket import generar_ticket_pdf
import catalogo as _catalogo_mod
from catalogo import MENU, PRODUCTOS_POR_ID
from pedidos import (
    siguiente_ref, guardar_pedido_pendiente, obtener_pedido,
    marcar_confirmado, marcar_rechazado, marcar_comprobante_enviado,
    buscar_pedido_pendiente_por_usuario,
    registrar_pedido_excel, pedidos_pendientes_pago,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── ESTADOS del ConversationHandler ──────────────────────────────────────────
(
    ST_EQUIPO,
    ST_PRODUCTO,
    ST_PARCHE,
    ST_TALLA,
    ST_PERSONALIZACION,
    ST_NOMBRE,
    ST_NUMERO,
    ST_CANTIDAD,
    ST_CANTIDAD_MANUAL,
    ST_CONFIRMAR,
    ST_COMPROBANTE,
    ST_CUSTOM_EQUIPO,
    ST_CUSTOM_KIT,
    ST_CUSTOM_MANGA,
    ST_CUSTOM_PUBLICO,
    ST_CARRITO,
    ST_CARRITO_REVISAR,
    ST_ADMIN_CLIENTE,
) = range(18)

# ── HELPERS ───────────────────────────────────────────────────────────────────

def kb(botones, cols=2):
    """Construye InlineKeyboardMarkup desde lista de (texto, callback_data)."""
    filas, fila = [], []
    for i, (txt, cb) in enumerate(botones):
        fila.append(InlineKeyboardButton(txt, callback_data=cb))
        if len(fila) == cols:
            filas.append(fila); fila = []
    if fila:
        filas.append(fila)
    return InlineKeyboardMarkup(filas)

def nombre_cliente(user):
    partes = [p for p in [user.first_name, user.last_name] if p]
    return " ".join(partes) if partes else str(user.id)

def _fmt_eur(v):
    """Formatea un precio: €15 si es entero, €13.50 si tiene decimales."""
    return f"€{int(v)}" if v == int(v) else f"€{v:.2f}"

def resumen_texto(ctx):
    """Genera el texto de resumen del pedido a partir de context.user_data."""
    d = ctx.user_data
    precio = d["precio_unit"]
    cant   = d.get("cantidad", 1)
    total_bruto = precio * cant

    descuento_pct = d.get("descuento_pct", 0)
    ahorro        = round(total_bruto * descuento_pct / 100, 2) if descuento_pct else 0
    total_final   = round(total_bruto - ahorro, 2)

    lineas = [
        f"📋 *RESUMEN DE TU PEDIDO*\n",
        f"👕 *Producto:* {d['producto_nombre']}",
        f"📐 *Talla:* {d['talla']}",
    ]
    if d.get("parche") and d["parche"] != "No":
        lineas.append(f"🏅 *Parche:* {d['parche']}")
    pers = d.get("personalizaciones", [])
    if len(pers) == 1:
        lineas.append(f"✍️ *Nombre:* {pers[0]['nombre']}  |  *Dorsal:* {pers[0]['numero']}")
    elif len(pers) > 1:
        for i, p in enumerate(pers, 1):
            lineas.append(f"✍️ *Camiseta {i}:* {p['nombre']} #{p['numero']}")
    lineas += [
        f"📦 *Cantidad:* {cant}",
        f"💶 *Precio unit.:* {_fmt_eur(precio)}",
    ]
    if descuento_pct:
        lineas.append(f"🏷️ *Descuento {descuento_pct}%:* -{_fmt_eur(ahorro)}")
    lineas.append(f"💰 *TOTAL: {_fmt_eur(total_final)}*")
    return "\n".join(lineas)

async def enviar_foto_producto(update_or_query, producto, caption=""):
    """Intenta enviar foto del producto; si falla envía solo texto."""
    foto_path = producto.get("foto", "")
    chat_id = (
        update_or_query.message.chat_id
        if hasattr(update_or_query, "message")
        else update_or_query.message.chat_id
    )
    if os.path.exists(foto_path):
        try:
            with open(foto_path, "rb") as f:
                await update_or_query.message.reply_photo(
                    photo=f, caption=caption, parse_mode=ParseMode.MARKDOWN
                )
            return True
        except Exception as e:
            logger.warning(f"No se pudo enviar foto {foto_path}: {e}")
    await update_or_query.message.reply_text(
        f"_{caption}_" if caption else "_(sin foto disponible)_",
        parse_mode=ParseMode.MARKDOWN
    )
    return False

# ── CARRITO HELPERS ───────────────────────────────────────────────────────────

def _item_key(item):
    """Tupla para detectar duplicados exactos en el carrito."""
    return (
        item["producto_id"],
        item["talla"],
        item.get("parche", "No"),
        tuple(sorted(
            (p["nombre"], p["numero"])
            for p in item.get("personalizaciones", [])
        )),
    )

def _añadir_al_carrito(ctx):
    """Construye el item actual y lo añade al carrito en user_data."""
    d = ctx.user_data

    # Obtener equipo/temporada desde la sección
    seccion_key = d.get("seccion", "")
    if seccion_key == "custom":
        equipo    = d.get("custom_equipo", "").title()
        temporada = "Custom"
    else:
        seccion_info = MENU.get(seccion_key, {})
        equipo    = seccion_info.get("equipo", "")
        temporada = seccion_info.get("temporada", "")

    cantidad   = d.get("cantidad", 1)
    precio_unit = d.get("precio_unit", 0)
    subtotal   = round(precio_unit * cantidad, 2)

    nuevo_item = {
        "producto_id":      d.get("producto_id", ""),
        "producto_nombre":  d.get("producto_nombre", ""),
        "nombre_proveedor": d.get("nombre_proveedor", ""),
        "precio_unit":      precio_unit,
        "talla":            d.get("talla", ""),
        "parche":           d.get("parche", "No"),
        "personalizaciones": d.get("personalizaciones", []),
        "cantidad":         cantidad,
        "publico":          d.get("publico", ""),
        "equipo":           equipo,
        "temporada":        temporada,
        "subtotal":         subtotal,
        "foto":             d.get("foto", ""),
    }

    carrito       = d.get("carrito", [])
    editando_idx  = d.get("_editando_idx")

    if editando_idx is not None:
        # Restaurar en la posición original
        carrito.insert(editando_idx, nuevo_item)
    else:
        # Detectar duplicado
        key_nuevo = _item_key(nuevo_item)
        encontrado = False
        for item in carrito:
            if _item_key(item) == key_nuevo:
                item["cantidad"] += cantidad
                item["subtotal"] = round(item["precio_unit"] * item["cantidad"], 2)
                encontrado = True
                break
        if not encontrado:
            carrito.append(nuevo_item)

    # Limpiar user_data preservando carrito y descuento
    descuento = d.get("descuento_pct", 0)
    d.clear()
    d["carrito"]      = carrito
    d["descuento_pct"] = descuento

def _total_carrito(carrito, descuento_pct=0):
    """Retorna (total_bruto, ahorro, total_final)."""
    total_bruto = sum(item["subtotal"] for item in carrito)
    ahorro      = round(total_bruto * descuento_pct / 100, 2) if descuento_pct else 0
    total_final = round(total_bruto - ahorro, 2)
    return total_bruto, ahorro, total_final

def _texto_carrito(ctx):
    """Genera el texto formateado del carrito."""
    carrito      = ctx.user_data.get("carrito", [])
    descuento_pct = ctx.user_data.get("descuento_pct", 0)
    n = len(carrito)

    lineas = [f"🛒 *TU CARRITO* ({n} artículo{'s' if n != 1 else ''})\n"]

    for i, item in enumerate(carrito, 1):
        lineas.append(f"*{i}.* {item['producto_nombre']}")

        talla_parche = f"   📐 {item['talla']}"
        if item.get("parche") and item["parche"] != "No":
            talla_parche += f" · 🏅 {item['parche']}"
        lineas.append(talla_parche)

        for p in item.get("personalizaciones", []):
            lineas.append(f"   ✍️ {p['nombre']} #{p['numero']}")

        lineas.append(
            f"   {item['cantidad']} × {_fmt_eur(item['precio_unit'])} = *{_fmt_eur(item['subtotal'])}*"
        )
        lineas.append("")

    total_bruto, ahorro, total_final = _total_carrito(carrito, descuento_pct)
    lineas.append("━━━━━━━━━━━━")
    if ahorro:
        lineas.append(f"🏷️ Descuento {descuento_pct}%: -{_fmt_eur(ahorro)}")
    lineas.append(f"💰 *TOTAL: {_fmt_eur(total_final)}*")

    return "\n".join(lineas)

def _markup_carrito(carrito):
    """Genera el InlineKeyboardMarkup del carrito."""
    filas = []
    filas.append([InlineKeyboardButton("✅ Confirmar y pagar", callback_data="carrito_pagar")])
    filas.append([InlineKeyboardButton("➕ Añadir otra camiseta", callback_data="carrito_mas")])
    for i, item in enumerate(carrito):
        filas.append([
            InlineKeyboardButton(f"✏️ Editar {i+1}", callback_data=f"carrito_editar_{i}"),
            InlineKeyboardButton(f"🗑️ Eliminar {i+1}", callback_data=f"carrito_borrar_{i}"),
        ])
    filas.append([
        InlineKeyboardButton("🧹 Vaciar carrito", callback_data="carrito_vaciar"),
        InlineKeyboardButton("❌ Cancelar",       callback_data="cancelar"),
    ])
    return InlineKeyboardMarkup(filas)

async def _mostrar_carrito(target, ctx):
    """Envía o edita mensaje con el carrito. Retorna ST_CARRITO."""
    texto  = _texto_carrito(ctx)
    carrito = ctx.user_data.get("carrito", [])
    markup = _markup_carrito(carrito)
    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(
            texto, parse_mode=ParseMode.MARKDOWN, reply_markup=markup
        )
    else:
        await target.reply_text(
            texto, parse_mode=ParseMode.MARKDOWN, reply_markup=markup
        )
    return ST_CARRITO

def resumen_pedido_admin(pedido):
    """Formatea un pedido guardado (con items array) para notificación al admin."""
    lineas = [f"📋 *RESUMEN DEL PEDIDO* `{pedido.get('ref', '')}`\n"]
    items = pedido.get("items", [])

    if items:
        for i, item in enumerate(items, 1):
            lineas.append(f"*{i}.* {item.get('producto_nombre', '')}")
            parche = item.get("parche", "No")
            parche_txt = f" · 🏅 {parche}" if parche and parche != "No" else ""
            lineas.append(f"   📐 {item.get('talla', '')}{parche_txt}")
            for p in item.get("personalizaciones", []):
                lineas.append(f"   ✍️ {p['nombre']} #{p['numero']}")
            lineas.append(
                f"   {item.get('cantidad', 1)} × {_fmt_eur(item.get('precio_unit', 0))}"
                f" = *{_fmt_eur(item.get('subtotal', 0))}*"
            )
            lineas.append(f"   📦 Proveedor: `{item.get('nombre_proveedor', '')}`")
            lineas.append("")
    else:
        # Compatibilidad con pedidos planos (formato antiguo)
        lineas.append(f"👕 {pedido.get('producto_nombre', '')}")
        parche = pedido.get("parche", "No")
        lineas.append(f"📐 {pedido.get('talla', '')} | 🏅 {parche}")
        nombre = pedido.get("nombre_dorsal", "")
        numero = pedido.get("numero_dorsal", "")
        if nombre:
            lineas.append(f"✍️ {nombre} #{numero}")
        cant = pedido.get("cantidad", 1)
        pu   = pedido.get("precio_unit", 0)
        lineas.append(f"📦 {cant} × {_fmt_eur(pu)} = *{_fmt_eur(cant * pu)}*")
        lineas.append("")

    descuento_pct = pedido.get("descuento_pct", 0)
    total_final   = pedido.get("total_final") or pedido.get("total_con_descuento", 0)
    if descuento_pct:
        lineas.append(f"🏷️ Descuento: {descuento_pct}%")
    lineas.append(f"💰 *TOTAL: {_fmt_eur(total_final)}*")

    return "\n".join(lineas)

# ── /pedido  (admin: crear pedido en nombre de un cliente) ───────────────────

async def cmd_pedido_manual(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin inicia un pedido introduciendo primero el nombre del cliente."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Comando solo para administrador.")
        return ConversationHandler.END

    # Carrito limpio para este pedido manual
    ctx.user_data.clear()
    ctx.user_data["carrito"]      = []
    ctx.user_data["descuento_pct"] = 0
    ctx.user_data["pedido_manual"] = True

    await update.message.reply_text(
        "🧾 *Pedido manual*\n\n"
        "¿Cuál es el *nombre completo* del cliente?",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ST_ADMIN_CLIENTE

async def recibir_nombre_cliente_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Recibe el nombre del cliente e inicia el catálogo."""
    nombre = update.message.text.strip()
    if not nombre:
        await update.message.reply_text("Por favor escribe un nombre válido.")
        return ST_ADMIN_CLIENTE

    ctx.user_data["cliente_manual_nombre"] = nombre

    # Mostrar catálogo igual que /start
    botones = [
        (f"{v['emoji']} {v['nombre']}", f"equipo_{k}")
        for k, v in MENU.items()
    ]
    botones.append(("🔍 Otra camiseta (no en catálogo)", "equipo_custom"))
    botones.append(("❌ Cancelar", "cancelar"))
    await update.message.reply_text(
        f"👤 *Cliente:* {nombre}\n\n{BIENVENIDA}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb(botones, cols=2),
    )
    return ST_EQUIPO

# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Preservar carrito y descuento al hacer /start
    carrito  = ctx.user_data.get("carrito", [])
    descuento = ctx.user_data.get("descuento_pct", 0)
    ctx.user_data.clear()
    ctx.user_data["carrito"]      = carrito
    ctx.user_data["descuento_pct"] = descuento

    botones = []
    if carrito:
        _, _, total_final = _total_carrito(carrito, descuento)
        total_uds = sum(item.get("cantidad", 1) for item in carrito)
        botones.append((
            f"🛒 Ver carrito ({total_uds} uds — {_fmt_eur(total_final)})",
            "carrito_ver"
        ))

    botones += [
        (f"{v['emoji']} {v['nombre']}", f"equipo_{k}")
        for k, v in MENU.items()
    ]
    botones.append(("🔍 Otra camiseta (no en catálogo)", "equipo_custom"))
    botones.append(("❌ Cancelar", "cancelar"))
    await update.message.reply_text(
        BIENVENIDA, parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb(botones, cols=2),
    )
    return ST_EQUIPO

# ── SELECCIÓN DE EQUIPO ───────────────────────────────────────────────────────

async def elegir_equipo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancelar":
        return await cancelar(update, ctx)

    if query.data == "carrito_ver":
        return await _mostrar_carrito(query, ctx)

    if query.data == "equipo_custom":
        await query.edit_message_text(
            "🔍 *¿Qué camiseta buscas?*\n\n"
            "Escribe el nombre del equipo (ej: _Real Madrid_, _Bayern Munich_, _Argentina_...)",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ST_CUSTOM_EQUIPO

    clave = query.data.replace("equipo_", "")
    seccion = MENU[clave]
    ctx.user_data["seccion"] = clave

    botones = []
    for p in seccion["productos"]:
        if p.get("stock", True):
            label = f"{p['nombre']} — {p['publico']} | €{p['precio']}"
        else:
            label = f"🚫 {p['nombre']} — Sin stock"
        botones.append((label, f"prod_{p['id']}"))

    botones.append(("⬅️ Volver", "volver_inicio"))
    botones.append(("❌ Cancelar", "cancelar"))

    await query.edit_message_text(
        f"*{seccion['emoji']} {seccion['nombre']}*\n\nElige el producto:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb(botones, cols=1),
    )
    return ST_PRODUCTO

# ── SELECCIÓN DE PRODUCTO ─────────────────────────────────────────────────────

async def elegir_producto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancelar":
        return await cancelar(update, ctx)
    if query.data == "volver_inicio":
        return await _volver_inicio(query, ctx)

    prod_id = query.data.replace("prod_", "")
    prod    = PRODUCTOS_POR_ID[prod_id]

    # Producto sin stock: avisar y quedarse en la lista
    if not prod.get("stock", True):
        await query.answer(
            "😔 Sin stock de momento. ¡Pronto disponible!",
            show_alert=True,
        )
        return ST_PRODUCTO

    ctx.user_data.update({
        "producto_id":       prod_id,
        "producto_nombre":   prod["nombre"],
        "nombre_proveedor":  prod.get("nombre_proveedor", ""),
        "precio_unit":       prod["precio"],
        "publico":           prod["publico"],
        "personalizacion_disponible": prod["personalizacion"],
        "parche_tipo":       prod.get("parche"),
        "foto":              prod.get("foto", ""),
    })

    # Mostrar foto y datos del producto
    caption = (
        f"*{prod['nombre']}*\n"
        f"👤 {prod['publico']}  |  💶 €{prod['precio']}"
        + (f"\n✍️ _Admite nombre+dorsal (+€{SUPLEM_NOMBRE_DORSAL})_" if prod["personalizacion"] else "")
    )

    foto_path = prod.get("foto", "")
    if os.path.exists(foto_path):
        try:
            with open(foto_path, "rb") as f:
                await query.message.reply_photo(
                    photo=f, caption=caption, parse_mode=ParseMode.MARKDOWN
                )
        except Exception:
            await query.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN)
    else:
        await query.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN)

    # ¿Tiene parche opcional?
    parches = prod.get("parche")
    if parches:
        if isinstance(parches, str):
            parches = [parches]
        def _label_parche(p):
            if p == "UCL":
                return f"🏆 Parche Champions League (+€{SUPLEM_PARCHE_UCL})"
            return f"🏅 Parche {p}"
        botones = [(_label_parche(p), f"parche_{p.replace(' ', '_')}") for p in parches]
        botones += [
            ("❌ Sin parche", "parche_no"),
            ("⬅️ Volver",    "volver_productos"),
        ]
        ctx.user_data["parche_opciones"] = parches
        await query.message.reply_text(
            "🏅 *¿Quieres añadir algún parche?*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb(botones, cols=1),
        )
        return ST_PARCHE

    # Sin parche → ir directo a talla
    ctx.user_data["parche"] = "No"
    return await _pedir_talla(query.message, ctx)

# ── PARCHE ────────────────────────────────────────────────────────────────────

async def elegir_parche(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancelar":
        return await cancelar(update, ctx)
    if query.data == "volver_productos":
        return await _volver_productos(query, ctx)

    if query.data == "parche_no":
        ctx.user_data["parche"] = "No"
    else:
        nombre_parche = query.data.replace("parche_", "").replace("_", " ")
        ctx.user_data["parche"] = nombre_parche
        if nombre_parche == "UCL":
            ctx.user_data["precio_unit"] += SUPLEM_PARCHE_UCL
    return await _pedir_talla(query.message, ctx)

# ── TALLA ─────────────────────────────────────────────────────────────────────

async def _pedir_talla(msg, ctx):
    prod_id = ctx.user_data["producto_id"]
    prod    = PRODUCTOS_POR_ID.get(prod_id)
    if prod:
        tallas = prod["tallas"]
    else:
        # Producto custom o no encontrado: tallas estándar adulto
        tallas = ["XS", "S", "M", "L", "XL", "XXL", "XXXL"]
    botones = [(t, f"talla_{t}") for t in tallas]
    botones.append(("❌ Cancelar", "cancelar"))
    await msg.reply_text(
        "📐 *¿Qué talla necesitas?*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb(botones, cols=4),
    )
    return ST_TALLA

async def elegir_talla(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancelar":
        return await cancelar(update, ctx)

    talla = query.data.replace("talla_", "")
    ctx.user_data["talla"] = talla

    # ¿Admite personalización?
    if ctx.user_data.get("personalizacion_disponible"):
        botones = [
            (f"✍️ Sí, añadir nombre y dorsal (+€{SUPLEM_NOMBRE_DORSAL})", "pers_si"),
            ("👕 No, sin personalización",                                 "pers_no"),
            ("❌ Cancelar",                                                 "cancelar"),
        ]
        await query.edit_message_text(
            "¿Quieres añadir *nombre y número de dorsal*?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb(botones, cols=1),
        )
        return ST_PERSONALIZACION

    ctx.user_data["nombre_dorsal"]      = ""
    ctx.user_data["numero_dorsal"]      = ""
    ctx.user_data["quiere_personalizacion"] = False
    ctx.user_data["personalizaciones"]  = []
    return await _pedir_cantidad(query.message, ctx)

# ── PERSONALIZACIÓN ───────────────────────────────────────────────────────────

async def elegir_personalizacion(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancelar":
        return await cancelar(update, ctx)

    if query.data == "pers_no":
        ctx.user_data["nombre_dorsal"]      = ""
        ctx.user_data["numero_dorsal"]      = ""
        ctx.user_data["quiere_personalizacion"] = False
        ctx.user_data["personalizaciones"]  = []
        return await _pedir_cantidad(query.message, ctx)

    # pers_si → primero cantidad, luego nombre+dorsal por unidad
    ctx.user_data["precio_unit"] += SUPLEM_NOMBRE_DORSAL
    ctx.user_data["quiere_personalizacion"] = True
    ctx.user_data["personalizaciones"]  = []
    await query.edit_message_text(
        "✍️ *Perfecto, personalizarás cada camiseta.*\n\n¿Cuántas unidades necesitas?",
        parse_mode=ParseMode.MARKDOWN,
    )
    return await _pedir_cantidad(query.message, ctx)

async def recibir_nombre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip().upper()
    if not nombre:
        await update.message.reply_text("Por favor escribe un nombre válido.")
        return ST_NOMBRE
    ctx.user_data["_nombre_temp"] = nombre
    unidad = ctx.user_data.get("_unidad_actual", 0) + 1
    total  = ctx.user_data.get("cantidad", 1)
    await update.message.reply_text(
        f"✍️ *Camiseta {unidad} de {total}*\n¿Qué número de dorsal? (1-99)",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ST_NUMERO

async def recibir_numero(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if not texto.isdigit() or not (1 <= int(texto) <= 99):
        await update.message.reply_text("Por favor escribe un número entre 1 y 99.")
        return ST_NUMERO

    nombre = ctx.user_data.pop("_nombre_temp", "")
    ctx.user_data["personalizaciones"].append({"nombre": nombre, "numero": texto})
    ctx.user_data["_unidad_actual"] = ctx.user_data.get("_unidad_actual", 0) + 1

    if ctx.user_data["_unidad_actual"] < ctx.user_data.get("cantidad", 1):
        # Más unidades pendientes
        return await _pedir_nombre_unidad(update.message, ctx)

    # Todas las unidades personalizadas → añadir al carrito
    pers = ctx.user_data["personalizaciones"]
    ctx.user_data["nombre_dorsal"] = ", ".join(p["nombre"] for p in pers)
    ctx.user_data["numero_dorsal"] = ", ".join(p["numero"]  for p in pers)
    return await _mostrar_resumen(update.message, ctx)

# ── FLUJO CAMISETA PERSONALIZADA (no en catálogo) ─────────────────────────────

_KIT_MAP   = {"kit_home": "HOME",  "kit_away": "AWAY",  "kit_third": "THIRD"}
_MANGA_MAP = {"manga_ss": "SS",    "manga_ls": "LS"}

async def custom_recibir_equipo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    equipo = update.message.text.strip()
    if not equipo:
        await update.message.reply_text("Por favor escribe el nombre del equipo.")
        return ST_CUSTOM_EQUIPO
    ctx.user_data["custom_equipo"] = equipo.upper()
    botones = [
        ("1ª Equipación (Local)",    "kit_home"),
        ("2ª Equipación (Visitante)", "kit_away"),
        ("3ª Equipación",             "kit_third"),
        ("❌ Cancelar",               "cancelar"),
    ]
    await update.message.reply_text(
        f"⚽ *{equipo}*\n\n¿Qué equipación quieres?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb(botones, cols=1),
    )
    return ST_CUSTOM_KIT

async def custom_elegir_kit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancelar":
        return await cancelar(update, ctx)
    ctx.user_data["custom_kit"] = _KIT_MAP[query.data]
    botones = [
        ("👨 Adulto", "pub_adulto"),
        ("👦 Niño",   "pub_nino"),
        ("❌ Cancelar", "cancelar"),
    ]
    await query.edit_message_text(
        "¿Para adulto o para niño?",
        reply_markup=kb(botones, cols=2),
    )
    return ST_CUSTOM_PUBLICO

async def custom_elegir_publico(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancelar":
        return await cancelar(update, ctx)

    es_nino = query.data == "pub_nino"
    ctx.user_data["custom_publico"] = "Niño" if es_nino else "Adulto"

    if es_nino:
        # Niños → siempre manga corta, saltar al siguiente paso
        return await _custom_crear_producto_y_continuar(query.message, ctx, manga="SS")

    # Adultos → preguntar manga
    botones = [
        ("👕 Manga Corta (SS)", "manga_ss"),
        ("🧥 Manga Larga (LS)", "manga_ls"),
        ("❌ Cancelar",         "cancelar"),
    ]
    await query.edit_message_text(
        "¿Manga corta o manga larga?",
        reply_markup=kb(botones, cols=2),
    )
    return ST_CUSTOM_MANGA

async def custom_elegir_manga(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancelar":
        return await cancelar(update, ctx)
    manga = _MANGA_MAP[query.data]
    return await _custom_crear_producto_y_continuar(query.message, ctx, manga=manga)

async def _custom_crear_producto_y_continuar(msg, ctx, manga: str):
    """Construye el producto virtual y arranca el flujo normal desde talla."""
    equipo  = ctx.user_data["custom_equipo"]
    kit     = ctx.user_data["custom_kit"]
    publico = ctx.user_data["custom_publico"]
    es_nino = publico == "Niño"

    kit_es  = {"HOME": "Local", "AWAY": "Visitante", "THIRD": "Tercera"}[kit]
    nombre  = f"{equipo.title()} {kit_es} {publico}"
    nombre_prov = f"{equipo} - {kit} - {'KIDS' if es_nino else 'ADULT'} - {manga}"
    precio  = 20 if es_nino else 15

    ctx.user_data.update({
        "seccion":           "custom",
        "producto_id":       f"CUSTOM-{equipo}-{kit}",
        "producto_nombre":   nombre,
        "nombre_proveedor":  nombre_prov,
        "precio_unit":       precio,
        "publico":           publico,
        "personalizacion_disponible": True,
        "parche_tipo":       None,
        "parche":            "No",
        "personalizaciones": [],
        "quiere_personalizacion": False,
    })

    await msg.reply_text(
        f"✅ *{nombre}*\n"
        f"📋 Ref. proveedor: `{nombre_prov}`\n"
        f"💶 Precio: €{precio}\n\n"
        f"_(Si el precio no es correcto, te lo confirmo antes de que pagues)_",
        parse_mode=ParseMode.MARKDOWN,
    )
    return await _pedir_talla(msg, ctx)

# ─────────────────────────────────────────────────────────────────────────────

async def _pedir_nombre_unidad(msg, ctx):
    unidad = ctx.user_data.get("_unidad_actual", 0) + 1
    total  = ctx.user_data.get("cantidad", 1)
    await msg.reply_text(
        f"✍️ *Camiseta {unidad} de {total}*\n¿Qué nombre quieres?",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ST_NOMBRE

async def _siguiente_tras_cantidad(msg_or_query, ctx):
    """Tras elegir cantidad: si hay personalización, pide nombre por unidad; si no, añade al carrito."""
    if ctx.user_data.get("quiere_personalizacion"):
        ctx.user_data["_unidad_actual"]   = 0
        ctx.user_data["personalizaciones"] = []
        msg = msg_or_query.message if hasattr(msg_or_query, "edit_message_text") else msg_or_query
        return await _pedir_nombre_unidad(msg, ctx)
    # Sin personalización: añadir al carrito directamente
    _añadir_al_carrito(ctx)
    return await _mostrar_carrito(msg_or_query, ctx)

# ── CANTIDAD ──────────────────────────────────────────────────────────────────

async def _pedir_cantidad(msg, ctx):
    botones = [
        ("1️⃣  1", "cant_1"), ("2️⃣  2", "cant_2"),
        ("3️⃣  3", "cant_3"), ("4️⃣  4", "cant_4"),
        ("➕ Más cantidad", "cant_mas"),
        ("❌ Cancelar",     "cancelar"),
    ]
    await msg.reply_text(
        "📦 *¿Cuántas unidades?*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb(botones, cols=4),
    )
    return ST_CANTIDAD

async def elegir_cantidad(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancelar":
        return await cancelar(update, ctx)

    if query.data == "cant_mas":
        await query.edit_message_text(
            "📦 *¿Cuántas unidades?*\n_(Escribe el número)_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ST_CANTIDAD_MANUAL

    cant = int(query.data.replace("cant_", ""))
    ctx.user_data["cantidad"] = cant
    return await _siguiente_tras_cantidad(query, ctx)

async def recibir_cantidad_manual(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if not texto.isdigit() or int(texto) < 1 or int(texto) > 99:
        await update.message.reply_text("Por favor escribe un número entre 1 y 99.")
        return ST_CANTIDAD_MANUAL
    ctx.user_data["cantidad"] = int(texto)
    return await _siguiente_tras_cantidad(update.message, ctx)

async def _mostrar_resumen(query_or_msg, ctx):
    """Ahora añade el item al carrito y muestra el carrito."""
    _añadir_al_carrito(ctx)
    return await _mostrar_carrito(query_or_msg, ctx)

# ── CONFIRMACIÓN LEGACY (ya no se alcanza en el flujo normal, se mantiene por compatibilidad) ──

async def confirmar_pedido(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancelar":
        return await cancelar(update, ctx)
    if query.data == "volver_inicio":
        return await _volver_inicio(query, ctx)

    # Generar referencia y guardar pedido pendiente
    ref = siguiente_ref()
    user = query.from_user

    # Extraer datos de la sección del catálogo
    seccion_key = ctx.user_data.get("seccion", "")
    if seccion_key == "custom":
        equipo    = ctx.user_data.get("custom_equipo", "").title()
        temporada = "Custom"
    else:
        seccion_info = MENU.get(seccion_key, {})
        equipo    = seccion_info.get("equipo", "")
        temporada = seccion_info.get("temporada", "")

    precio_unit    = ctx.user_data.get("precio_unit", 0)
    cantidad       = ctx.user_data.get("cantidad", 1)
    descuento_pct  = ctx.user_data.get("descuento_pct", 0)
    total_bruto    = precio_unit * cantidad
    total_final    = round(total_bruto * (1 - descuento_pct / 100), 2) if descuento_pct else total_bruto

    pedido = {
        "ref":             ref,
        "cliente_id":      user.id,
        "cliente_nombre":  nombre_cliente(user),
        "cliente_username": user.username or "",
        "equipo":          equipo,
        "temporada":       temporada,
        "producto_id":     ctx.user_data["producto_id"],
        "producto_nombre": ctx.user_data["producto_nombre"],
        "publico":         ctx.user_data.get("publico", ""),
        "version":         "",
        "talla":           ctx.user_data.get("talla", ""),
        "nombre_proveedor": ctx.user_data.get("nombre_proveedor", ""),
        "nombre_dorsal":   ctx.user_data.get("nombre_dorsal", ""),
        "numero_dorsal":   ctx.user_data.get("numero_dorsal", ""),
        "parche":          ctx.user_data.get("parche", "No"),
        "cantidad":        cantidad,
        "precio_unit":     precio_unit,
        "descuento_pct":   descuento_pct,
        "total_con_descuento": total_final,
        "personalizaciones": ctx.user_data.get("personalizaciones", []),
    }
    guardar_pedido_pendiente(ref, pedido)
    ctx.user_data["ref_actual"] = ref

    msg_pago = TEXTO_PAGO.format(
        numero=BIZUM_NUMERO, nombre=BIZUM_NOMBRE, ref=ref
    )
    await query.edit_message_text(
        msg_pago, parse_mode=ParseMode.MARKDOWN,
    )
    return ST_COMPROBANTE

# ── CARRITO: GESTIÓN ──────────────────────────────────────────────────────────

async def gestionar_carrito(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handler para ST_CARRITO."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "carrito_mas":
        # Ir al menú de equipos SIN limpiar carrito
        carrito   = ctx.user_data.get("carrito", [])
        descuento = ctx.user_data.get("descuento_pct", 0)

        botones = []
        if carrito:
            _, _, total_final = _total_carrito(carrito, descuento)
            total_uds = sum(item.get("cantidad", 1) for item in carrito)
            botones.append((
                f"🛒 Ver carrito ({total_uds} uds — {_fmt_eur(total_final)})",
                "carrito_ver"
            ))
        botones += [
            (f"{v['emoji']} {v['nombre']}", f"equipo_{k}")
            for k, v in MENU.items()
        ]
        botones.append(("🔍 Otra camiseta (no en catálogo)", "equipo_custom"))
        botones.append(("❌ Cancelar", "cancelar"))
        await query.edit_message_text(
            BIENVENIDA, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb(botones, cols=2),
        )
        return ST_EQUIPO

    elif data == "carrito_ver":
        return await _mostrar_carrito(query, ctx)

    elif data == "carrito_pagar":
        texto = _texto_carrito(ctx)
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirmar y pagar", callback_data="confirmar_si")],
            [InlineKeyboardButton("✏️ Volver al carrito",  callback_data="volver_carrito")],
        ])
        await query.edit_message_text(
            f"⚠️ *REVISA TU PEDIDO*\n\n{texto}\n\n¿Todo correcto?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup,
        )
        return ST_CARRITO_REVISAR

    elif data == "carrito_vaciar":
        descuento = ctx.user_data.get("descuento_pct", 0)
        ctx.user_data.clear()
        ctx.user_data["carrito"]      = []
        ctx.user_data["descuento_pct"] = descuento
        return await _volver_inicio(query, ctx)

    elif data.startswith("carrito_borrar_"):
        idx     = int(data.replace("carrito_borrar_", ""))
        carrito = ctx.user_data.get("carrito", [])
        if 0 <= idx < len(carrito):
            carrito.pop(idx)
        ctx.user_data["carrito"] = carrito
        if not carrito:
            return await _volver_inicio(query, ctx)
        return await _mostrar_carrito(query, ctx)

    elif data.startswith("carrito_editar_"):
        idx     = int(data.replace("carrito_editar_", ""))
        carrito = ctx.user_data.get("carrito", [])
        if 0 <= idx < len(carrito):
            item = carrito.pop(idx)
            descuento = ctx.user_data.get("descuento_pct", 0)
            ctx.user_data.clear()
            ctx.user_data["carrito"]       = carrito
            ctx.user_data["descuento_pct"] = descuento
            ctx.user_data["_editando_idx"] = idx

            # Determinar seccion para el item editado
            prod = PRODUCTOS_POR_ID.get(item["producto_id"], {})
            ctx.user_data.update({
                "producto_id":               item["producto_id"],
                "producto_nombre":            item["producto_nombre"],
                "nombre_proveedor":           item.get("nombre_proveedor", ""),
                "precio_unit":                item["precio_unit"],
                "talla":                      item.get("talla", ""),
                "parche":                     item.get("parche", "No"),
                "personalizaciones":          item.get("personalizaciones", []),
                "cantidad":                   item.get("cantidad", 1),
                "publico":                    item.get("publico", ""),
                "personalizacion_disponible": prod.get("personalizacion", True),
                "quiere_personalizacion":     bool(item.get("personalizaciones", [])),
            })
        return await _pedir_talla(query.message, ctx)

    elif data == "cancelar":
        # No limpiar carrito
        return ConversationHandler.END

    return ST_CARRITO


async def revisar_pedido(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handler para ST_CARRITO_REVISAR."""
    query = update.callback_query
    await query.answer()

    if query.data == "confirmar_si":
        return await _procesar_pago_carrito(query, ctx)
    elif query.data == "volver_carrito":
        return await _mostrar_carrito(query, ctx)

    return ST_CARRITO_REVISAR


async def _procesar_pago_carrito(query, ctx):
    """Genera ref, guarda pedido con items array y muestra instrucciones de pago."""
    carrito = ctx.user_data.get("carrito", [])
    if not carrito:
        await query.edit_message_text("⚠️ Tu carrito está vacío. Escribe /start para empezar.")
        return ConversationHandler.END

    # Idempotencia: si ya existe ref y pedido, no crear nuevo
    ref_actual = ctx.user_data.get("ref_actual")
    if ref_actual:
        pedido_exist = obtener_pedido(ref_actual)
        if pedido_exist and pedido_exist.get("estado") in ("PENDIENTE_PAGO", "COMPROBANTE_ENVIADO"):
            msg_pago = TEXTO_PAGO.format(
                numero=BIZUM_NUMERO, nombre=BIZUM_NOMBRE, ref=ref_actual
            )
            await query.edit_message_text(msg_pago, parse_mode=ParseMode.MARKDOWN)
            return ST_COMPROBANTE

    ref           = siguiente_ref()
    user          = query.from_user
    descuento_pct = ctx.user_data.get("descuento_pct", 0)
    _, _, total_final = _total_carrito(carrito, descuento_pct)

    # Si es pedido manual (admin), usar el nombre introducido
    es_manual = ctx.user_data.get("pedido_manual", False)
    if es_manual:
        cli_nombre   = ctx.user_data.get("cliente_manual_nombre", "Cliente manual")
        cli_id       = 0          # sin ID de Telegram real
        cli_username = "(manual)"
    else:
        cli_nombre   = nombre_cliente(user)
        cli_id       = user.id
        cli_username = user.username or ""

    # Snapshot completo de cada item
    items = []
    for item in carrito:
        items.append({
            "producto_id":      item["producto_id"],
            "producto_nombre":  item["producto_nombre"],
            "nombre_proveedor": item.get("nombre_proveedor", ""),
            "precio_unit":      item["precio_unit"],
            "talla":            item["talla"],
            "parche":           item.get("parche", "No"),
            "personalizaciones": item.get("personalizaciones", []),
            "cantidad":         item["cantidad"],
            "publico":          item.get("publico", ""),
            "equipo":           item.get("equipo", ""),
            "temporada":        item.get("temporada", ""),
            "subtotal":         item["subtotal"],
            "foto":             item.get("foto", ""),
        })

    pedido = {
        "ref":             ref,
        "cliente_id":      cli_id,
        "cliente_nombre":  cli_nombre,
        "cliente_username": cli_username,
        "descuento_pct":   descuento_pct,
        "total_final":     total_final,
        "pedido_manual":   es_manual,
        "items":           items,
    }
    guardar_pedido_pendiente(ref, pedido)
    ctx.user_data["ref_actual"] = ref

    # Pedido manual: registrar directamente en Excel y confirmar
    if es_manual:
        registrar_pedido_excel(pedido)
        marcar_confirmado(ref)
        await _enviar_excel_admin(ctx.bot, ref)
        resumen = resumen_pedido_admin(pedido)
        await query.edit_message_text(
            f"✅ *Pedido manual registrado*\n\n"
            f"👤 Cliente: *{cli_nombre}*\n"
            f"🔖 Ref: `{ref}`\n\n"
            f"{resumen}\n\n"
            f"_(El Excel te acaba de llegar por aquí mismo)_",
            parse_mode=ParseMode.MARKDOWN,
        )
        ctx.user_data.clear()
        return ConversationHandler.END

    msg_pago = TEXTO_PAGO.format(
        numero=BIZUM_NUMERO, nombre=BIZUM_NOMBRE, ref=ref
    )
    await query.edit_message_text(msg_pago, parse_mode=ParseMode.MARKDOWN)

    # Enviar ticket PDF al cliente como resumen del pedido
    try:
        pdf_bytes = generar_ticket_pdf(pedido)
        await query.message.reply_document(
            document=pdf_bytes,
            filename=f"Pedido_{ref}.pdf",
            caption=f"🧾 *Aquí tienes el resumen de tu pedido* `{ref}`\nGuárdalo como referencia.",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.warning(f"No se pudo generar el ticket PDF: {e}")

    return ST_COMPROBANTE

# ── COMPROBANTE DE PAGO ────────────────────────────────────────────────────────

async def recibir_comprobante(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """El cliente envía la foto del comprobante de Bizum."""
    ref = ctx.user_data.get("ref_actual")

    # Si no hay ref en memoria (bot reiniciado), buscar en JSON por user ID
    if not ref:
        pedido_recuperado = buscar_pedido_pendiente_por_usuario(update.message.from_user.id)
        if pedido_recuperado:
            ref = pedido_recuperado["ref"]
            ctx.user_data["ref_actual"] = ref
        else:
            await update.message.reply_text(
                "⚠️ No tengo un pedido activo. Escribe /start para empezar."
            )
            return ConversationHandler.END

    pedido = obtener_pedido(ref)
    if not pedido:
        await update.message.reply_text("⚠️ Pedido no encontrado. Escribe /start.")
        return ConversationHandler.END

    # Bloquear comprobantes duplicados
    if pedido.get("estado") == "COMPROBANTE_ENVIADO":
        await update.message.reply_text(
            "✅ Ya recibí tu comprobante. Estoy revisando el pago, te confirmo en breve."
        )
        return ST_COMPROBANTE

    # Avisar al admin
    resumen  = resumen_pedido_admin(pedido)
    cliente  = nombre_cliente(update.message.from_user)
    username = (
        f"@{update.message.from_user.username}"
        if update.message.from_user.username
        else str(update.message.from_user.id)
    )

    caption_admin = (
        f"💳 *COMPROBANTE DE PAGO RECIBIDO*\n\n"
        f"🔖 Ref: `{ref}`\n"
        f"👤 Cliente: {cliente} ({username})\n\n"
        f"{resumen}\n\n"
        f"¿Confirmas el pago?"
    )
    botones_admin = [
        ("✅ Confirmar pago",  f"admin_ok_{ref}"),
        ("❌ Rechazar",        f"admin_ko_{ref}"),
    ]

    try:
        if update.message.photo:
            await ctx.bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=update.message.photo[-1].file_id,
                caption=caption_admin,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb(botones_admin, cols=2),
            )
        elif update.message.document:
            await ctx.bot.send_document(
                chat_id=ADMIN_CHAT_ID,
                document=update.message.document.file_id,
                caption=caption_admin,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb(botones_admin, cols=2),
            )
        else:
            await ctx.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=caption_admin + "\n\n_(el cliente no envió imagen)_",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb(botones_admin, cols=2),
            )
    except Exception as e:
        logger.error(f"No se pudo avisar al admin: {e}")

    marcar_comprobante_enviado(ref)
    await update.message.reply_text(
        f"✅ *¡Comprobante recibido!*\n\n"
        f"Tu referencia de pedido es: `{ref}`\n\n"
        f"Revisaré el pago y te confirmo en breve. ¡Gracias! 🙌",
        parse_mode=ParseMode.MARKDOWN,
    )
    # Pedido completado: limpiar todo
    ctx.user_data.clear()
    return ConversationHandler.END

async def _enviar_excel_admin(bot, ref: str):
    """Envía el Excel actualizado al admin por Telegram."""
    from config import PEDIDOS_XLSX
    if not os.path.exists(PEDIDOS_XLSX):
        return
    try:
        with open(PEDIDOS_XLSX, "rb") as f:
            await bot.send_document(
                chat_id=ADMIN_CHAT_ID,
                document=f,
                filename="PEDIDOS_BOT.xlsx",
                caption=f"📊 Excel actualizado — Pedido `{ref}` añadido.",
                parse_mode=ParseMode.MARKDOWN,
            )
    except Exception as e:
        logger.error(f"No se pudo enviar el Excel: {e}")

async def _editar_mensaje_admin(query, texto: str):
    """Edita el mensaje del admin funcione con foto (caption) o con texto."""
    try:
        await query.edit_message_caption(caption=texto, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        try:
            await query.edit_message_text(text=texto, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.warning(f"No se pudo editar mensaje admin: {e}")

# ── ADMIN: CONFIRMAR / RECHAZAR ────────────────────────────────────────────────

async def admin_confirmar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_CHAT_ID:
        await query.answer("⛔ Solo el administrador puede confirmar pedidos.", show_alert=True)
        return

    ref = query.data.replace("admin_ok_", "")
    pedido = obtener_pedido(ref)
    if not pedido:
        await _editar_mensaje_admin(query, f"⚠️ Pedido `{ref}` no encontrado.")
        return

    marcar_confirmado(ref)
    registrar_pedido_excel(pedido)
    await _enviar_excel_admin(ctx.bot, ref)

    # Notificar al cliente
    try:
        await ctx.bot.send_message(
            chat_id=pedido["cliente_id"],
            text=(
                f"🎉 *¡Pedido confirmado!*\n\n"
                f"✅ Tu pedido `{ref}` ha sido confirmado.\n"
                f"🙏 ¡Gracias por tu compra! Te avisaré cuando esté listo."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error(f"No se pudo notificar al cliente: {e}")

    await _editar_mensaje_admin(query, f"✅ *Pedido {ref} CONFIRMADO* y registrado en Excel.")

async def admin_rechazar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_CHAT_ID:
        await query.answer("⛔ Solo el administrador puede gestionar pedidos.", show_alert=True)
        return

    ref = query.data.replace("admin_ko_", "")
    pedido = obtener_pedido(ref)
    marcar_rechazado(ref)

    if pedido:
        try:
            await ctx.bot.send_message(
                chat_id=pedido["cliente_id"],
                text=(
                    f"⚠️ *Pago no confirmado* — Pedido `{ref}`\n\n"
                    f"No hemos podido verificar tu pago. "
                    f"Por favor contáctame directamente para resolverlo. 🙏"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    await _editar_mensaje_admin(query, f"❌ *Pedido {ref} rechazado.*")

# ── COMANDOS DE ADMIN ──────────────────────────────────────────────────────────

async def cmd_miid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Muestra el Chat ID del usuario (útil para configurar ADMIN_CHAT_ID)."""
    uid = update.effective_user.id
    await update.message.reply_text(
        f"🆔 Tu Chat ID es: `{uid}`\n\nCópialo en config.py → ADMIN_CHAT_ID",
        parse_mode=ParseMode.MARKDOWN,
    )

async def cmd_descuento(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Aplica un código de descuento al pedido en curso. Uso: /descuento CODIGO"""
    partes = update.message.text.strip().split()
    if len(partes) < 2:
        await update.message.reply_text("Formato: /descuento CODIGO")
        return
    codigo = partes[1].strip().upper()
    pct = CODIGOS_DESCUENTO.get(codigo)
    if pct is None:
        await update.message.reply_text("❌ Código no válido.")
        return
    ctx.user_data["descuento_pct"]    = pct
    ctx.user_data["descuento_codigo"] = codigo
    await update.message.reply_text(
        f"✅ Código aplicado: *{pct}% de descuento* en tu pedido.",
        parse_mode=ParseMode.MARKDOWN,
    )

async def cmd_recargar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Recarga el catálogo desde disco sin reiniciar el bot (solo admin)."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Comando solo para administrador.")
        return
    global MENU, PRODUCTOS_POR_ID
    try:
        importlib.reload(_catalogo_mod)
        MENU             = _catalogo_mod.MENU
        PRODUCTOS_POR_ID = _catalogo_mod.PRODUCTOS_POR_ID
        n_equipos   = len(MENU)
        n_productos = len(PRODUCTOS_POR_ID)
        await update.message.reply_text(
            f"✅ *Catálogo recargado*\n"
            f"📂 {n_equipos} equipos · {n_productos} productos cargados.",
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info("Catálogo recargado manualmente por el admin.")
    except Exception as e:
        logger.error(f"Error al recargar catálogo: {e}")
        await update.message.reply_text(f"❌ Error al recargar catálogo:\n`{e}`", parse_mode=ParseMode.MARKDOWN)

async def cmd_pedidos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Lista pedidos pendientes de confirmación (solo admin)."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Comando solo para administrador.")
        return
    pendientes = pedidos_pendientes_pago()
    if not pendientes:
        await update.message.reply_text("✅ No hay pedidos pendientes de confirmación.")
        return
    lineas = ["*PEDIDOS PENDIENTES DE CONFIRMAR:*\n"]
    for ref, p in pendientes.items():
        items = p.get("items", [])
        if items:
            total = p.get("total_final", 0)
            lineas.append(
                f"🔖 `{ref}` — {len(items)} prod. | "
                f"{_fmt_eur(total)} | {p.get('cliente_nombre', '')}"
            )
        else:
            lineas.append(
                f"🔖 `{ref}` — {p.get('producto_nombre','')} | {p.get('talla','')} | "
                f"{_fmt_eur(p.get('precio_unit',0)*p.get('cantidad',1))} | {p.get('cliente_nombre','')}"
            )
    await update.message.reply_text(
        "\n".join(lineas), parse_mode=ParseMode.MARKDOWN
    )

# ── NAVEGACIÓN ────────────────────────────────────────────────────────────────

async def _volver_inicio(query_or_msg, ctx):
    # Preservar carrito y descuento al volver al inicio
    carrito  = ctx.user_data.get("carrito", [])
    descuento = ctx.user_data.get("descuento_pct", 0)
    ctx.user_data.clear()
    ctx.user_data["carrito"]      = carrito
    ctx.user_data["descuento_pct"] = descuento

    botones = []
    if carrito:
        _, _, total_final = _total_carrito(carrito, descuento)
        total_uds = sum(item.get("cantidad", 1) for item in carrito)
        botones.append((
            f"🛒 Ver carrito ({total_uds} uds — {_fmt_eur(total_final)})",
            "carrito_ver"
        ))

    botones += [
        (f"{v['emoji']} {v['nombre']}", f"equipo_{k}")
        for k, v in MENU.items()
    ]
    botones.append(("🔍 Otra camiseta (no en catálogo)", "equipo_custom"))
    botones.append(("❌ Cancelar", "cancelar"))

    if hasattr(query_or_msg, "edit_message_text"):
        await query_or_msg.edit_message_text(
            BIENVENIDA, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb(botones, cols=2),
        )
    else:
        await query_or_msg.message.reply_text(
            BIENVENIDA, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb(botones, cols=2),
        )
    return ST_EQUIPO

async def _volver_productos(query, ctx):
    clave   = ctx.user_data.get("seccion", "")
    seccion = MENU.get(clave, {})
    botones = [
        (f"{p['nombre']} — {p['publico']} | €{p['precio']}", f"prod_{p['id']}")
        for p in seccion.get("productos", [])
    ]
    botones.append(("⬅️ Volver al inicio", "volver_inicio"))
    await query.edit_message_text(
        f"*{seccion.get('emoji','')} {seccion.get('nombre','')}*\n\nElige el producto:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb(botones, cols=1),
    )
    return ST_PRODUCTO

async def cancelar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Preservar carrito al cancelar (el cliente puede retomar)
    carrito  = ctx.user_data.get("carrito", [])
    descuento = ctx.user_data.get("descuento_pct", 0)
    ctx.user_data.clear()
    ctx.user_data["carrito"]      = carrito
    ctx.user_data["descuento_pct"] = descuento

    msg = update.message or (update.callback_query and update.callback_query.message)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "❌ Pedido cancelado. Escribe /start cuando quieras empezar de nuevo."
        )
    elif msg:
        await msg.reply_text(
            "❌ Pedido cancelado. Escribe /start cuando quieras empezar de nuevo."
        )
    return ConversationHandler.END

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    if BOT_TOKEN == "TU_TOKEN_AQUI":
        print("❌ ERROR: Configura el BOT_TOKEN en config.py antes de arrancar.")
        return
    if ADMIN_CHAT_ID == 0:
        print("⚠️  AVISO: ADMIN_CHAT_ID no configurado. Escribe /miid en el bot para obtenerlo.")

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start",  start),
            CommandHandler("pedido", cmd_pedido_manual),
        ],
        conversation_timeout=86400,  # 24h — limpia conversaciones abandonadas
        states={
            ST_EQUIPO: [
                CallbackQueryHandler(elegir_equipo),
            ],
            ST_PRODUCTO: [
                CallbackQueryHandler(elegir_producto),
            ],
            ST_PARCHE: [
                CallbackQueryHandler(elegir_parche),
            ],
            ST_TALLA: [
                CallbackQueryHandler(elegir_talla),
            ],
            ST_PERSONALIZACION: [
                CallbackQueryHandler(elegir_personalizacion),
            ],
            ST_NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre),
            ],
            ST_NUMERO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_numero),
            ],
            ST_CANTIDAD: [
                CallbackQueryHandler(elegir_cantidad),
            ],
            ST_CANTIDAD_MANUAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cantidad_manual),
            ],
            ST_CONFIRMAR: [
                CallbackQueryHandler(confirmar_pedido),
            ],
            ST_COMPROBANTE: [
                MessageHandler(
                    (filters.PHOTO | filters.Document.ALL | filters.TEXT) & ~filters.COMMAND,
                    recibir_comprobante
                ),
            ],
            ST_CUSTOM_EQUIPO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_recibir_equipo),
            ],
            ST_CUSTOM_KIT: [
                CallbackQueryHandler(custom_elegir_kit),
            ],
            ST_CUSTOM_PUBLICO: [
                CallbackQueryHandler(custom_elegir_publico),
            ],
            ST_CUSTOM_MANGA: [
                CallbackQueryHandler(custom_elegir_manga),
            ],
            ST_CARRITO: [
                CallbackQueryHandler(gestionar_carrito),
            ],
            ST_CARRITO_REVISAR: [
                CallbackQueryHandler(revisar_pedido),
            ],
            ST_ADMIN_CLIENTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre_cliente_admin),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar),
            CommandHandler("start",    start),
        ],
        allow_reentry=True,
    )

    # Admin handlers en grupo -1 (prioridad máxima, antes del ConversationHandler)
    app.add_handler(CallbackQueryHandler(admin_confirmar, pattern=r"^admin_ok_"), group=-1)
    app.add_handler(CallbackQueryHandler(admin_rechazar,  pattern=r"^admin_ko_"), group=-1)

    # Grupo -1: prioridad máxima, funcionan dentro de cualquier estado
    app.add_handler(CommandHandler("descuento", cmd_descuento), group=-1)
    app.add_handler(CommandHandler("recargar",  cmd_recargar),  group=-1)

    app.add_handler(conv)
    app.add_handler(CommandHandler("miid",    cmd_miid))
    app.add_handler(CommandHandler("pedidos", cmd_pedidos))

    print("✅ Bot arrancado. Pulsa Ctrl+C para detener.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main()
