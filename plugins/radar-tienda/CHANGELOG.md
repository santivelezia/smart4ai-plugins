# CHANGELOG · radar-tienda

## 1.1.1 · 2026-10-16

- Cabina: el QR de la pantalla lleva a `smart4ai.io/radar-tienda` (el regalo del plugin) en vez de `/radar-cola`; texto «Llévate el plugin gratis: escanea el QR». La cola pública por ntfy sigue funcionando para quien tenga el enlace de `/radar-cola`.

## 1.1.0 · 2026-10-16

**Cabina Radar** (nuevo): `/radar-tienda:radar-cabina` abre una página local (`http://127.0.0.1:8765`, o el siguiente puerto libre) con botones para operar la línea en vivo sin escribir en el chat. La página es el mesero y Claude el cocinero: cada botón escribe una orden en `~/radar-tienda/cabina/orden.json`; Claude, en la misma sesión y con los conectores de siempre, la toma con `esperar_orden.py`, la ejecuta y vuelve a esperar.
- `scripts/cabina/servidor.py`: servidor solo con la librería estándar, solo en 127.0.0.1. Cola local (máx. 30, sin duplicados), lanzar exprés o completo, comparar los 3 primeros, pedir publicar (Claude pide el sí en el chat), quitar, destrabar. Cola pública opcional por ntfy.sh (tema `radar-effix-cola-k7m3q9`): solo mensajes nuevos desde el arranque, extrae el primer enlace de un texto, descarta dominios y mensajes de prueba. Sin internet, sigue con la cola local. Rechaza POST de otros orígenes y lo que no sea JSON.
- `scripts/cabina/esperar_orden.py`: espera la orden (tope 1.500 s, sale con `SIN_ORDEN`), la marca en curso, y con `--terminar` la registra en el historial con su tiempo y veredicto.
- `scripts/cabina/cabina.html`: tres zonas (Entrada · Tablero en vivo · Resultado), las 5 estaciones con el mismo estilo del tablero, contador de productos de la noche con el tiempo de cada uno, QR del público a `smart4ai.io/radar-cola`, QR de la vista previa de Shopify, extracto del anuncio, **modo proyector** (tecla P: fondo negro, letra grande, veredicto a pantalla completa con animación y sonido generado con WebAudio; tecla V repite la celebración).
- `scripts/cabina/pruebas_cabina.py`: 14 pruebas (parser de la cola pública, servidor real en puerto de prueba, flujo pedido → orden → espera → terminar → contador, publicar, comparar, tope, entradas raras, puerto ocupado).
- Arreglo encontrado por las pruebas: en Windows, `ThreadingHTTPServer` deja que dos servidores tomen el mismo puerto; la cabina apaga `allow_reuse_address` para que salte al siguiente libre.

## 1.0.0 · 2026-10-16

Primera versión como plugin portable (Windows y Mac), a partir de la automatización de la hackatón Feria Effix.

**Skills**
- `radar-configurar`: primer uso. Detecta Python (py → python3 → python, descarta el atajo falso de la Microsoft Store), prueba Shopify con `get-shop-info` (si no responde, se detiene y explica cómo conectarlo), Meta, Chrome, video, vía de imágenes (conector / openrouter / mis-fotos), pago contra entrega; crea la colección si falta; guarda `~/.radar-tienda/config.json`; corre las pruebas y la demo; dice el nivel (Completo / Conectores / Solo estudio).
- `radar-a-tienda`: orquestador portable con chequeo de arranque, 3 niveles, plan B por dependencia, Radar delegado a un ayudante Sonnet, tablero y recibo.
- `radar-comparar` (nuevo): 2 a 4 productos en exprés y en paralelo, tabla y ganador con regla fija.
- `radar-ayuda`: responde con `docs/MANUAL_DE_USUARIO.md`; soporte por correo.
- `radar-producto`: skill de Carlos Jiménez, intacta salvo la línea de crédito y la `description` puesta entre comillas (mismo texto: sin comillas no era YAML válido y claude.ai rechazaría el plugin).

**Puente (`scripts/puente/puente.py`)**
- Filtro de promesas ampliado: alivia, reduce, previene, desinflama, adelgaza, quema grasa, elimina arrugas, trata, terapéutico; autoridad (INVIMA, FDA, clínicamente, científicamente, médico); "¿sufres…?"; antes y después; urgencia sin dato; "resultados en N días". Avisos legales permitidos ("no reemplaza la consulta con un profesional", "consulta a tu médico").
- Detector de `[CONFIRMAR…]` / `[PENDIENTE…]`: lista en `validacion.md`; los temas marcados (días de entrega, manual o contenido de la caja, autonomía) se quitan de la página aunque el JSON los traiga sin marca; error si algo llega al título, la página o el SEO.
- El puente decide: margen < 25 %, NO RECOMENDABLE o PRECAUCIÓN → sin descuento y etiqueta `no-recomendado` / `precaucion`; NO RECOMENDABLE → `advertencia` en el paquete.
- Vendedor, etiqueta, colección (por handle), código de descuento y contra entrega salen de la configuración. Nada fijo.
- `--anuncio`: valida `anuncio-meta.md` con los mismos filtros (ignora la sección de frases prohibidas).
- `--resumen`: tabla ordenada de varios estudios (para comparar).
- `shopify_import.csv` con el formato oficial de importación de Shopify (verificado 2026-10-16), `--imagen` para llenar imágenes.
- Filtro de instrucciones: "pasos visuales", "visuales", "destacar", "mostrar", "(no médico", "tono:" y "fotos" (solo como orden de diseño).
- Retracto sin duplicar.

**Imágenes**: `generar.py` (OpenRouter en Python puro, clave desde la variable de entorno o `~/.radar-tienda/.env`, errores en JSON, caída al modelo Lite si Gemini Pro da 429, registro de costos en `~/radar-tienda/costos.csv`) y `subir_shopify.py` (PUT a la URL de `stagedUploadsCreate` sin PowerShell).

**Tablero**: título configurable, advertencia en rojo, recibo de corrida (`recibo.md` + tablero), orden `abrir` con el navegador por defecto, demo en la carpeta de datos del usuario.

**Quitado**: rutas del PC de Santiago, IDs de su tienda y colección, la marca fija de la feria, el código de descuento fijo, la vía de imágenes anterior, comandos solo de Windows.

## Pendiente para 1.1

- Probar la instalación desde cero en un Mac real y en Cowork (el comando de la clave para Mac está escrito pero no se probó en zsh).
- Probar `subir_shopify.py` contra una URL real de `stagedUploadsCreate` (hoy probado sin red; el original en PowerShell sí dio 200).
- Estudio en PDF con la marca del usuario.
- Reglas por país (terminación de precios, texto legal de retracto) para México, Perú, Chile y Ecuador.
- `claude plugin eval` con 6 casos como prueba de regresión.
- Leer el estado real de pago contra entrega desde Shopify en vez de preguntarlo.
- Campo `userConfig.proveedor_imagenes` como lista cerrada (`options`) cuando todos los usuarios tengan Claude Code 2.1.271 o superior.
