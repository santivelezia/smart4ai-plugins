# CHANGELOG · radar-tienda

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
