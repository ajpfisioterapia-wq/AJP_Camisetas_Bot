# ─────────────────────────────────────────────────────────────────────────────
# ticket.py  —  Genera un PDF de ticket/resumen de pedido para el cliente
# ─────────────────────────────────────────────────────────────────────────────

import io
import datetime
from fpdf import FPDF

def _fmt_eur(v):
    return f"{int(v)} EUR" if v == int(v) else f"{v:.2f} EUR"


def generar_ticket_pdf(pedido: dict) -> bytes:
    """
    Genera un PDF con el resumen del pedido.
    Devuelve los bytes del PDF listos para enviar por Telegram.
    """
    ref           = pedido.get("ref", "")
    cliente       = pedido.get("cliente_nombre", "")
    fecha         = pedido.get("fecha", datetime.datetime.now().isoformat())[:10]
    items         = pedido.get("items", [])
    descuento_pct = pedido.get("descuento_pct", 0)
    total_final   = pedido.get("total_final", 0)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── CABECERA ──────────────────────────────────────────────────────────────
    pdf.set_fill_color(26, 35, 126)   # azul oscuro
    pdf.rect(0, 0, 210, 38, "F")

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_xy(20, 8)
    pdf.cell(0, 10, "AJP CAMISETAS", ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(20, 20)
    pdf.cell(0, 6, "Tu tienda de camisetas de futbol", ln=True)

    # Ref en la esquina derecha
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(130, 10)
    pdf.cell(60, 6, f"Ref: {ref}", align="R", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(130, 18)
    pdf.cell(60, 6, f"Fecha: {fecha}", align="R", ln=True)

    pdf.set_text_color(0, 0, 0)
    pdf.ln(20)

    # ── DATOS CLIENTE ─────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(232, 245, 233)
    pdf.cell(0, 8, f"  Cliente: {cliente}", fill=True, ln=True)
    pdf.ln(4)

    # ── LÍNEA CABECERA TABLA ──────────────────────────────────────────────────
    pdf.set_fill_color(40, 53, 147)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(80, 7, "  Producto", fill=True)
    pdf.cell(22, 7, "Talla", align="C", fill=True)
    pdf.cell(30, 7, "Personaliz.", align="C", fill=True)
    pdf.cell(18, 7, "Cant.", align="C", fill=True)
    pdf.cell(20, 7, "Precio", align="C", fill=True)
    pdf.cell(20, 7, "Subtotal", align="C", fill=True)
    pdf.ln()

    # ── FILAS DE PRODUCTOS ────────────────────────────────────────────────────
    pdf.set_text_color(0, 0, 0)
    fila_par = True
    for item in items:
        nombre     = item.get("producto_nombre", "")
        talla      = item.get("talla", "")
        parche     = item.get("parche", "No")
        cantidad   = item.get("cantidad", 1)
        precio     = item.get("precio_unit", 0)
        subtotal   = item.get("subtotal", precio * cantidad)
        pers       = item.get("personalizaciones", [])

        # Color alterno de filas
        if fila_par:
            pdf.set_fill_color(245, 245, 245)
        else:
            pdf.set_fill_color(255, 255, 255)
        fila_par = not fila_par

        # Texto de personalización
        if pers:
            pers_txt = ", ".join(f"{p['nombre']} #{p['numero']}" for p in pers)
        else:
            pers_txt = "-"

        # Parche
        parche_txt = parche if parche and parche != "No" else "-"

        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(80, 6, f"  {nombre[:38]}", fill=True)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(22, 6, talla, align="C", fill=True)
        pdf.cell(30, 6, pers_txt[:18], align="C", fill=True)
        pdf.cell(18, 6, str(cantidad), align="C", fill=True)
        pdf.cell(20, 6, _fmt_eur(precio), align="C", fill=True)
        pdf.cell(20, 6, _fmt_eur(subtotal), align="C", fill=True)
        pdf.ln()

        # Línea de parche si lo tiene
        if parche and parche != "No":
            pdf.set_font("Helvetica", "I", 7)
            pdf.set_fill_color(255, 255, 255) if not fila_par else pdf.set_fill_color(245, 245, 245)
            pdf.cell(80, 5, f"    Parche: {parche_txt}", fill=True)
            pdf.cell(90, 5, "", fill=True)
            pdf.ln()

    # ── TOTALES ───────────────────────────────────────────────────────────────
    pdf.ln(3)
    pdf.set_draw_color(26, 35, 126)
    pdf.set_line_width(0.5)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(3)

    if descuento_pct:
        total_bruto = sum(i.get("subtotal", 0) for i in items)
        ahorro = round(total_bruto * descuento_pct / 100, 2)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(150, 7, f"Descuento {descuento_pct}%:", align="R")
        pdf.cell(20, 7, f"-{_fmt_eur(ahorro)}", align="C", ln=True)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_fill_color(26, 35, 126)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(150, 9, "TOTAL:", align="R", fill=True)
    pdf.cell(20, 9, _fmt_eur(total_final), align="C", fill=True, ln=True)

    # ── INSTRUCCIONES DE PAGO ─────────────────────────────────────────────────
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)
    pdf.set_fill_color(255, 243, 224)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, "  INSTRUCCIONES DE PAGO", fill=True, ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.ln(2)
    pdf.set_fill_color(255, 248, 240)
    pdf.cell(0, 6, f"  Envia el pago por Bizum con concepto: PEDIDO-{ref}", fill=True, ln=True)
    pdf.cell(0, 6, "  Adjunta el comprobante de Bizum en el chat del bot.", fill=True, ln=True)
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, "  Una vez confirmado el pago recibirás la confirmación por Telegram.", ln=True)

    # ── PIE ───────────────────────────────────────────────────────────────────
    pdf.ln(6)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "Gracias por tu confianza  -  AJP Camisetas", align="C", ln=True)

    # Devolver bytes
    return bytes(pdf.output())
