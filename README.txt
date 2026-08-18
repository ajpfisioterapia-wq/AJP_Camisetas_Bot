════════════════════════════════════════════════════════════════════
  BOT DE CAMISETAS — GUÍA DE CONFIGURACIÓN Y USO
════════════════════════════════════════════════════════════════════

PASO 1 — CREAR EL BOT EN TELEGRAM
──────────────────────────────────
1. Abre Telegram y busca @BotFather
2. Envía el comando:  /newbot
3. Pon un nombre visible, ej.:  Tienda Camisetas Álvaro
4. Pon un username (debe acabar en "bot"), ej.:  AlvaroCamisetasBot
5. BotFather te dará un TOKEN. Cópialo.

PASO 2 — OBTENER TU CHAT ID
──────────────────────────────────
1. Busca en Telegram:  @userinfobot
2. Envíale cualquier mensaje
3. Te responderá con tu "Id" — ese número es tu ADMIN_CHAT_ID

PASO 3 — CONFIGURAR EL BOT
──────────────────────────────────
Abre el archivo config.py con el Bloc de notas y rellena:

  BOT_TOKEN     = 8913785060:AAGqhQwvEyvFxMfKurEzssTWdS8Pl8lJX18
  ADMIN_CHAT_ID = 2083455694
  BIZUM_NUMERO  = +34625433376

Guarda el archivo.

PASO 4 — INSTALAR DEPENDENCIAS (solo la primera vez)
──────────────────────────────────
Haz doble clic en:  instalar.bat
Espera a que termine.

PASO 5 — ARRANCAR EL BOT
──────────────────────────────────
Haz doble clic en:  run.bat
Deja la ventana abierta. El bot estará activo mientras el PC esté encendido.

════════════════════════════════════════════════════════════════════
  CÓMO USA EL CLIENTE EL BOT
════════════════════════════════════════════════════════════════════

1. El cliente busca tu bot en Telegram (por su @username)
2. Envía /start
3. Selecciona equipo → producto → talla → personalización → cantidad
4. Ve el resumen y el precio total
5. Paga por Bizum y envía foto del comprobante
6. Tú recibes la notificación en Telegram con todos los detalles
7. Pulsas ✅ Confirmar → queda registrado en el Excel automáticamente
8. El cliente recibe confirmación

════════════════════════════════════════════════════════════════════
  COMANDOS DEL BOT
════════════════════════════════════════════════════════════════════

Para clientes:
  /start     → Iniciar un pedido
  /cancelar  → Cancelar el pedido en curso

Para ti (admin):
  /miid      → Ver tu Chat ID de Telegram (para configuración)
  /pedidos   → Ver pedidos pendientes de confirmación

════════════════════════════════════════════════════════════════════
  ARCHIVOS DEL SISTEMA
════════════════════════════════════════════════════════════════════

config.py           → Configuración (token, Bizum, rutas)
catalogo.py         → Catálogo de productos (para añadir/quitar)
bot.py              → Código principal del bot
pedidos.py          → Gestión de pedidos y Excel

C:\Users\Usuario\Desktop\Pedido Camisetas\
  PEDIDOS_BOT.xlsx          → Excel con todos los pedidos confirmados
  pedidos_pendientes.json   → Pedidos en espera de confirmación

════════════════════════════════════════════════════════════════════
  NOTAS IMPORTANTES
════════════════════════════════════════════════════════════════════

- El bot solo funciona mientras el ordenador esté encendido y
  la ventana de run.bat esté abierta.

- Los precios de coste NUNCA aparecen en el bot. Solo el PVP.

- Para añadir productos nuevos: editar catalogo.py.

- Si cambias el catálogo, reinicia el bot (cierra y vuelve a
  abrir run.bat).
