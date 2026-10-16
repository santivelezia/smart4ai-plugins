# Radar a Tienda · Manual de usuario

Versión 1.0 · Smart4AI · Feria Effix 2026

---

## 1 · Qué es y qué no es

**Radar a Tienda** es un plugin para Claude. Le das la foto o el enlace de un producto y, en unos minutos, te devuelve dos cosas: un **estudio de mercado** (cuántos anuncios hay, a qué precio se vende, cuánto te deja) y el **producto ya montado en tu tienda de Shopify**, con fotos, combos, anuncio y video.

**La analogía.** Piensa en un asistente de compras con una lupa. Antes de que tú pongas un peso, sale a mirar quién ya vende lo mismo, a cuánto y desde cuándo. Si ve que el negocio no da, te lo dice. Un buen asistente no es el que siempre dice "sí": es el que te frena a tiempo.

**Qué es:**
- Un estudio de mercado hecho con datos públicos (la Biblioteca de anuncios de Meta, tiendas online, Mercado Libre), con fuente y fecha en cada dato.
- Un montaje de tu tienda **en borrador**, listo para que lo revises.
- Un borrador de anuncio y de video corto.

**Qué no es:**
- No es una bola de cristal: no te garantiza ventas ni ganancias.
- No publica, no pauta y no cobra. Eso lo haces tú.
- No es asesoría legal, médica ni financiera.
- No reemplaza al proveedor: las fotos con IA son ilustrativas, y antes de vender de verdad las cambias por fotos reales del producto.

---

## 2 · Qué necesitas

### Cómo se llaman las cosas según dónde lo uses

El plugin trae cinco skills (habilidades). Se llaman distinto según la app:

| Qué quieres | En Claude Code (escribes el comando) | En claude.ai o Cowork (hablas normal) |
|---|---|---|
| Primer uso y configuración | `/radar-tienda:radar-configurar` | "configura el radar", "acabo de instalar el plugin" |
| Estudiar un producto | `/radar-tienda:radar-producto` | "estudia este producto" |
| Del producto a la tienda | `/radar-tienda:radar-a-tienda <foto o enlace> exprés` | "corre el radar con este producto", "monta este producto en mi tienda" |
| Comparar de 2 a 4 productos | `/radar-tienda:radar-comparar` | "compara estos productos", "cuál de estos lanzo" |
| Ayuda | `/radar-tienda:radar-ayuda` | "ayuda con el radar", "no entiendo este error" |

En Claude Code, al escribir `/` y las primeras letras de `radar`, el app te completa el nombre. En claude.ai y Cowork no hace falta escribir comandos: las skills se activan solas al hablar normal. Si alguna no se activa, nómbrala ("usa radar-tienda").

### Los tres niveles

El plugin funciona en tres niveles. `/radar-tienda:radar-configurar` revisa lo que tienes y te dice en cuál estás.

| | **Completo** | **Conectores** | **Solo estudio** |
|---|---|---|---|
| Dónde | Claude Code, en la app de escritorio | claude.ai o Cowork (o Claude Code sin Python) | Cualquiera |
| Qué hace | Todo: estudio, validación, fotos con IA, tienda, anuncio, video y **tablero en vivo** | Estudio + validación hecha por Claude + producto en Shopify en borrador (sin tablero) | Estudio, brief y anuncio; si hay imágenes, también un archivo de importación para Shopify |
| Cuenta de Claude Pro o Max | Sí | Sí | Sí |
| Shopify + conector de Shopify en Claude | Sí | Sí | No |
| Python 3 instalado | Sí | No | No |
| Fotos del producto | Conector de imágenes, OpenRouter o tus fotos | Conector de imágenes o tus fotos (OpenRouter necesita Python) | No hace falta |
| Conector de Meta Ads | Recomendado | Recomendado | Recomendado |
| Extensión Claude in Chrome | Recomendada | Recomendada | Recomendada |

Detalles que conviene saber:

- **Conector de Meta Ads:** cuenta los anuncios. Meta exige que tengas una **cuenta publicitaria activa** para usarlo. Se conecta en Configuración → Conectores.
- **Extensión Claude in Chrome:** sirve para ver la antigüedad y el texto de los anuncios en la Biblioteca. Funciona con tu sesión de Facebook abierta. Se instala desde https://claude.com/chrome.
- **Sin Meta o sin Chrome** el estudio sale igual, pero con menos detalle (el conteo de anuncios queda "no verificado" y la confianza máxima baja a Baja), y te lo dice en "Limitaciones".
- **Video (opcional):** si tienes una herramienta de video conectada (tipo Clipkit), el plugin arma el video corto. Si no, sigue sin video y lo anota en el recibo.
- **Fotos del producto:** en `/radar-tienda:radar-configurar` eliges cómo las quieres, en este orden: **(a) conector**: con una herramienta de imágenes que ya tengas conectada en Claude (por ejemplo un gestor de imágenes en la nube, Gemini, Canva o Figma), sin clave; **(b) openrouter**: Gemini con tu propia clave de OpenRouter, unos **US$0,03 a US$0,14 por imagen** (una corrida exprés, con 2 imágenes, ronda los US$0,17; la completa, con 3, unos US$0,31); **(c) mis-fotos**: solo tus propias fotos, sin costo. Puedes cambiar después volviendo a correr la configuración.
- **Clave de OpenRouter (solo si eliges la opción b):** la skill te da un comando para guardarla en un archivo de tu computador, `~/.radar-tienda/.env`, dentro de una línea `OPENROUTER_API_KEY=...`. La variable se llama exactamente **`OPENROUTER_API_KEY`**. **Nunca se pega en el chat.** El comando exacto está en la sección 3D.

---

## 3 · Instalación paso a paso

Instálalo **una sola vez, en un solo lugar**. Si lo instalas en tu cuenta de claude.ai, llega solo a Cowork. Instalarlo dos veces crea dos copias que se estorban.

### 3A · Claude Code (nivel Completo) · ≈ 3 minutos

1. Abre la app de escritorio de Claude y entra a la pestaña **Code**.
2. Escribe y pulsa Enter:
   `/plugin marketplace add santivelezia/smart4ai-plugins`
   **Vas a ver:** un mensaje de que el marketplace quedó agregado. [capturar pantalla: marketplace agregado en Claude Code]
3. Escribe y pulsa Enter:
   `/plugin install radar-tienda@smart4ai-plugins`
   **Vas a ver:** la confirmación de que `radar-tienda` quedó instalado y las preguntas de configuración (ver 3E). [capturar pantalla: plugin instalado]
4. Si no aparecen las skills, cierra y vuelve a abrir Claude Code.
5. Escribe `/radar-tienda` y comprueba que salen `/radar-tienda:radar-configurar`, `/radar-tienda:radar-producto`, `/radar-tienda:radar-a-tienda`, `/radar-tienda:radar-comparar` y `/radar-tienda:radar-ayuda`. [capturar pantalla: lista de comandos con radar-tienda]
6. Sigue con la sección 4. Shopify lo conectas ahí, guiado.

### 3B · claude.ai o Cowork (nivel Conectores) · ≈ 4 minutos

1. Entra a Claude → **Configuración → Personalizar → Plugins**. [capturar pantalla: menú Personalizar]
2. Pulsa **Agregar → Agregar marketplace → Agregar desde un repositorio**.
3. Escribe `santivelezia/smart4ai-plugins` y pulsa **Sincronizar**. [capturar pantalla: marketplace sincronizado]
4. En la pestaña **Descubrir**, busca **radar-tienda** y pulsa **Agregar**.
5. **Plan B:** si prefieres el archivo, usa **Agregar → Subir plugin** y elige el `.zip` que te llegó por correo. No lo vuelvas a comprimir.
6. Sigue con la sección 4. Shopify lo conectas ahí, guiado.

En claude.ai y Cowork no escribes comandos con `/`: hablas normal ("configura el radar", "estudia este producto"). Si una skill no se activa sola, nómbrala: "usa radar-tienda para configurar".

### 3C · Conectar Shopify y Meta Ads · ≈ 3 minutos cada uno

No tienes que hacerlo de memoria: la configuración revisa si Shopify está conectado y, si no, **se detiene y te muestra estos pasos**:

1. En claude.ai, abre **Configuración → Conectores**.
2. Busca **Shopify** y pulsa **Conectar**. Inicia sesión con tu tienda y acepta los permisos. [capturar pantalla: conector de Shopify conectado]
3. Si estás en Claude Code, el conector de tu cuenta aparece solo en la siguiente sesión; si no aparece, conéctalo primero en claude.ai.
4. Vuelve al chat y **avísale a Claude que ya quedó**. Él retoma desde ahí.

**Vas a ver:** Shopify con la marca de "Conectado". Si decides no conectarlo (o todavía no tienes tienda), el plugin queda en nivel **Solo estudio**.

Aparte, opcional pero recomendado: conecta **Meta Ads** (necesita una cuenta publicitaria activa) e instala en Chrome la extensión **Claude in Chrome** con tu sesión de Facebook abierta. Mejoran el estudio.

### 3D · Python y fotos (solo nivel Completo) · ≈ 10 minutos

1. Revisa si tienes Python 3: la configuración lo prueba por ti (`py`, `python3` o `python`). Si no, instálalo desde https://www.python.org/downloads/ y vuelve a correr la configuración. En Windows, si `python` abre la Microsoft Store en vez de Python, no cuenta como instalado.
2. Elige cómo quieres las fotos (la skill te lo pregunta): conector de imágenes que ya tengas, OpenRouter o tus propias fotos.
3. Si eliges OpenRouter, crea una clave en https://openrouter.ai/settings/keys, recarga créditos y guárdala **sin pegarla en el chat**. La skill te da este comando para que lo pegues en TU terminal (pide la clave escondida):

   **Windows (PowerShell):**
   `$k = Read-Host "Pega tu clave de OpenRouter" -AsSecureString; $t = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($k)); New-Item -ItemType Directory -Force -Path "$HOME\.radar-tienda" | Out-Null; Set-Content -Path "$HOME\.radar-tienda\.env" -Value "OPENROUTER_API_KEY=$t" -Encoding ASCII; Remove-Variable k, t; "Clave guardada"`

   **Mac (Terminal):**
   `read -s "k?Pega tu clave de OpenRouter: "; mkdir -p ~/.radar-tienda; printf 'OPENROUTER_API_KEY=%s\n' "$k" > ~/.radar-tienda/.env; chmod 600 ~/.radar-tienda/.env; unset k; echo; echo Clave guardada`

   **Vas a ver:** el mensaje "Clave guardada". Después la configuración comprueba que la clave esté "presente" (nunca la muestra). Si la clave se te pegó en el chat por error, revócala en https://openrouter.ai/settings/keys y crea otra.

### 3E · Los 9 campos que el plugin te pregunta al instalarlo

Al instalar el plugin, Claude Code te pregunta estos nueve datos. **Todos tienen un valor por defecto**: si no sabes qué poner, deja el que viene y pulsa Enter. Puedes cambiarlos después.

| # | Campo | Valor por defecto | Para qué sirve |
|---|---|---|---|
| 1 | País de venta | `CO` | Código de dos letras del país donde vendes (CO, MX, PE, CL, EC…); define la moneda y las reglas de precio. |
| 2 | Colección de Shopify | `radar` | Nombre de la colección donde quedan los productos; si no existe, la configuración la crea vacía. |
| 3 | Vendedor (marca) en Shopify | `Radar` | Lo que aparece en el campo "Vendedor" de cada producto. |
| 4 | Etiqueta de prueba | `radar-prueba` | Etiqueta que llevan todos los productos creados, para encontrarlos o borrarlos juntos. |
| 5 | Código de descuento (opcional) | vacío | Si escribes un código, se propone un 10 % desde 2 unidades, solo cuando el margen es 25 % o más y el estudio no dice NO RECOMENDABLE ni PRECAUCIÓN. Vacío = nunca se crea. |
| 6 | Mi tienda tiene pago contra entrega activo | apagado (`false`) | Actívalo solo si en Shopify ya configuraste el pago contra entrega; apagado, la página y el SEO no lo prometen. |
| 7 | Cómo se hacen las imágenes | `conector` | `conector` (una herramienta de imágenes conectada a Claude), `openrouter` (Gemini con tu clave) o `mis-fotos` (solo tus fotos). |
| 8 | Carpeta de las corridas | `~/radar-tienda/corridas` | Dónde se guarda cada corrida (estudio, brief, imágenes, tablero); nunca dentro del plugin. |
| 9 | Título del tablero | `Radar a Tienda` | La marca que se ve arriba del tablero en vivo. |

La configuración (`/radar-tienda:radar-configurar`) lee estos valores, los confirma y los guarda en `~/.radar-tienda/config.json`, un archivo sin claves.

---

## 4 · Primer uso: la configuración

Es la skill del primer día. En Claude Code escribe:

`/radar-tienda:radar-configurar`

En claude.ai o Cowork, di: "configura el radar".

Hace esto, en orden:

1. **Revisa qué tienes:** Python (el nivel Completo lo necesita), el conector de Shopify, el de Meta, la extensión de Chrome y, si hay, una herramienta de video.
2. **Shopify guiado:** si no está conectado, se detiene, te muestra los pasos de la sección 3C y espera a que le avises. Sin Shopify el plugin queda en nivel "Solo estudio".
3. **Te pregunta cómo quieres las fotos:** conector de imágenes que ya tengas, OpenRouter o tus propias fotos. Si eliges OpenRouter, te da el comando de la sección 3D para guardar la clave sin pegarla en el chat. Puedes cambiar después corriendo de nuevo la configuración.
4. **Te pregunta si tu tienda ya tiene pago contra entrega** y te dice dónde se activa en Shopify (Configuración → Pagos → Métodos de pago manuales).
5. **Prepara tu tienda:** busca la colección `radar` (o el nombre que elegiste) y, si no existe, **te avisa y la crea vacía**. Es lo único que crea en tu tienda.
6. **Guarda tu configuración** en `~/.radar-tienda/config.json` y, con Python, **corre las pruebas y abre un tablero de ensayo en el navegador** (cerca de un minuto) para confirmar que todo conversa.

Al final te dice **tu nivel** en una frase, por ejemplo: "Estás en nivel Conectores: tienes estudio y tienda, sin tablero", con una tabla de ✅/❌ y qué te falta para subir de nivel. [capturar pantalla: resultado de la configuración]

**Si algo falta**, te dice qué es y cómo conseguirlo. No te asustes con un "falta": el plugin sigue sirviendo en un nivel más bajo.

**Si te saltas este paso:** al correr `/radar-tienda:radar-a-tienda` sin haber configurado, el plugin te manda primero a `/radar-tienda:radar-configurar`.

---

## 5 · Tu primer producto en 10 minutos (modo exprés)

Elige un producto que ya conozcas. En Claude Code escribe:

`/radar-tienda:radar-a-tienda <foto o enlace> exprés`

En claude.ai o Cowork, di por ejemplo: "corre el radar con este producto, en exprés" y adjunta la foto o pega el enlace.

Puedes arrastrar la foto al chat o pegar el enlace. Si ya sabes cuánto te cuesta con tu proveedor, **dilo**: ese número es el que más cambia el veredicto. Si no, el estudio calcula hasta cuánto podría costar para que el negocio funcione.

**Lo que pasa, estación por estación:**

| # | Estación | Qué hace | Qué vas a ver |
|---|---|---|---|
| 1 | **Radar** | Estudio de mercado: anuncios, precios, competencia, margen | Archivos del estudio y del brief |
| 2 | **Puente** | Revisa el brief: sin promesas médicas, sin testimonios inventados, sin descuentos falsos | Un informe de validación |
| 3 | **Fotos** | Genera imágenes con IA (conector u OpenRouter) o usa tu foto: 2 imágenes en exprés, 3 en el modo completo | Imágenes del producto |
| 4 | **Tienda** | Crea el producto en Shopify, **en borrador** | Producto en tu admin de Shopify |
| 5 | **Anuncio y video** | Textos del anuncio (validados con las mismas reglas) y video corto si tienes la herramienta, sin publicar | Archivo del anuncio y enlace al video |

[capturar pantalla: tablero en vivo con las estaciones]

**Tiempos medidos:** el estudio completo toma unos **8 a 14 minutos** de punta a punta; el **exprés**, **3 a 5 minutos**. Sin la palabra "exprés" (o "rápido") corre el modo completo, con más búsquedas y una imagen más.

**Al final** Claude te resume: veredicto, precios de los combos, anuncios y anunciantes, los dolores del cliente, el ángulo recomendado, el mayor riesgo, el enlace de vista previa de tu tienda y un **recibo** (tiempo, consultas aproximadas, costo de las imágenes y nivel). [capturar pantalla: resumen final]

**Dónde quedan tus archivos:** cada corrida en su propia carpeta, `~/radar-tienda/corridas/AAAA-MM-DD_HHMM_<producto>/`, con el estudio, el brief, `validacion.md`, el anuncio, las imágenes, `recibo.md` y, en el nivel Completo, `tablero.html`.

**Importante:** el producto nace siempre en **BORRADOR**. Nadie lo ve hasta que tú lo actives.

---

## 6 · Cómo leer el veredicto

El veredicto es lo primero que ves. Hay cinco posibles, y todos son útiles.

| Veredicto | Qué significa | Qué haces tú |
|---|---|---|
| **PROBAR** | Hay demanda comprobada, el margen es sano (20 % o más) y la competencia no te tapa | Revisa la tienda en borrador, consigue fotos reales y prueba con un presupuesto pequeño |
| **PROBAR SI EL COSTO ≤ $X** | El negocio funciona, pero el costo del proveedor era una estimación. $X es lo máximo que te puede costar cada unidad | Pregunta tu costo real. Si es menor o igual a $X, adelante. Si es mayor, no lances |
| **PRECAUCIÓN** | El margen es justo, hay mucha competencia sin un ángulo claro, o hay un riesgo de registro sanitario o de políticas de Meta | Lee la sección de riesgos del estudio y decide si tienes un ángulo distinto o cómo resolver el riesgo |
| **NO RECOMENDABLE** | Con esos números perderías plata | No lances. Prueba otro producto, otro proveedor o un precio distinto |
| **DATOS INSUFICIENTES** | No se pudo identificar el producto o no hay datos para comparar | Dale una foto más clara, un enlace mejor o el nombre exacto, y corre de nuevo |

**Qué pasa con un NO RECOMENDABLE o un PRECAUCIÓN.** El plugin lo dice con claridad, **no crea código de descuento** y marca el producto en tu tienda con la etiqueta `no-recomendado` (o `precaucion`). En un NO RECOMENDABLE además te muestra una advertencia en rojo, y si luego pides publicar, te la repite y te pide confirmar otra vez. Eso es una virtud: te ahorró la plata de pauta de un producto que no deja margen.

**El descuento.** Solo existe si escribiste un código al instalar, el margen es 25 % o más y el veredicto no es NO RECOMENDABLE ni PRECAUCIÓN. Si no se crea, el resumen te dice por qué.

**La confianza.** Junto al veredicto verás una confianza **Alta, Media o Baja**. Baja no significa malo: significa que hubo pocos datos verificados. Úsala para saber cuánto fiarte.

**Todo dato lleva fuente.** Lo que no se pudo comprobar aparece como "no verificable". Es una **muestra, no un censo**: el estudio mira lo que encontró, no todas las tiendas del país.

---

## 7 · Comparar varios productos

¿Dudas entre varios productos? En Claude Code escribe:

`/radar-tienda:radar-comparar <producto 1> <producto 2> <producto 3>`

En claude.ai o Cowork, di: "compara estos productos" y pasa las fotos o los enlaces.

Acepta de **2 a 4 productos**. Hace un estudio exprés de cada uno, **en paralelo**, los pone lado a lado en una tabla y te dice **cuál lanzar primero** y por qué. La regla es fija: primero el veredicto, luego la confianza, luego el margen. Si todos salen NO RECOMENDABLE, la respuesta honesta es "ninguno por ahora". **Tarda unos 5 a 10 minutos en total.** Al final te ofrece montar el ganador en tu tienda, reutilizando su estudio. La comparación no necesita Shopify. [capturar pantalla: tabla de comparación]

---

## 8 · Publicar la tienda (lo haces tú, en Shopify)

El plugin deja el producto listo, pero **la decisión de publicar es tuya**. Pasos:

1. **Abre el producto en tu admin de Shopify.** El enlace viene en el resumen final. [capturar pantalla: producto en borrador]
2. **Revisa el texto.** Cambia lo que no sea cierto para tu negocio (garantía, tiempos de entrega, ciudades). Lo que el estudio dejó "por confirmar" no se publica hasta que lo confirmes.
3. **Cambia las fotos.** Las imágenes con IA son ilustrativas. Antes de vender, sube las fotos reales de tu proveedor.
4. **Activa el pago contra entrega** en Shopify (Configuración → Pagos → Métodos de pago manuales), si lo vas a ofrecer. El plugin lo menciona en la página solo si lo marcaste como activo. [capturar pantalla: ajustes de pago contra entrega]
5. **Revisa el código de descuento,** si se creó. Confirma que el margen lo aguanta.
6. **Verifica lo legal del producto:** si el estudio avisa de registro sanitario (por ejemplo INVIMA), resuélvelo antes de vender.
7. **Mira la vista previa** como lo vería tu cliente.
8. **Cuando estés seguro, cambia el estado de Borrador a Activo.** Solo ahí sale al público.

Los anuncios los publicas tú, en tu cuenta de Meta. El plugin deja los textos y el video listos, nada más.

---

## 9 · Preguntas frecuentes

**1 · ¿Por qué no se activa?**
En Claude Code prueba con el nombre completo: `/radar-tienda:radar-a-tienda`. En claude.ai y Cowork las skills no son comandos: se activan al hablar normal, y a veces conviene nombrarlas ("usa radar-tienda"). Si ni así aparece, cierra y abre la app, y revisa que no lo hayas instalado dos veces (cuenta y carpeta local a la vez).

**2 · ¿Me cobra algo?**
El plugin es gratis. Pagas lo que ya usarías: tu plan de Claude, tu Shopify y, si quieres fotos con IA por OpenRouter, los créditos de esa cuenta (unos US$0,03 a US$0,14 por imagen).

**3 · ¿Sirve en México, Perú u otro país?**
El estudio puede adaptarse a otro país: el primero de los 9 campos de instalación es el país de venta. Pero lo probamos con Colombia, precios en pesos y pago contra entrega. En otros países, trátalo como una primera aproximación y verifica monedas, transportadoras y normas. [completar: países probados]

**4 · ¿Qué pasa si no tengo Shopify?**
Sigues en el nivel **Solo estudio**: recibes el estudio, el brief y el anuncio, y un archivo de importación (`shopify_import.csv`) que puedes subir a una tienda cuando la tengas (Shopify → Productos → Importar). Cuando tengas tienda, vuelve a correr la configuración.

**5 · ¿Es legal?**
Usa datos públicos, como la Biblioteca de anuncios de Meta. Pero el estudio no es asesoría legal: las normas de tu producto (registro sanitario, publicidad, derecho de retracto) las verificas tú. Más en la sección 11.

**6 · ¿Y si me da NO RECOMENDABLE?**
Es el plugin haciendo su trabajo. Prueba otro producto, otro proveedor o ajusta el costo. Si cambia un dato (por ejemplo, tu costo real), corre de nuevo.

**7 · ¿Cómo salen las fotos del producto y puedo cambiarlo?**
Al configurar eliges: un conector de imágenes que ya tengas en Claude (un gestor de imágenes en la nube, Gemini, Canva u otro), sin clave; OpenRouter, con tu propia clave y unos US$0,03 a US$0,14 por imagen; o tus propias fotos, sin costo. Para cambiar, corre la configuración otra vez (`/radar-tienda:radar-configurar`, o "quiero cambiar cómo se hacen las fotos" en claude.ai y Cowork).

**8 · ¿Publica mi tienda o mis anuncios?**
Nunca. Todo queda en borrador. Publicar y pautar son órdenes tuyas.

**9 · ¿Por qué tarda?**
Está investigando de verdad: anuncios, tiendas, precios y cuentas. El exprés toma 3 a 5 minutos; el completo, 8 a 14; comparar varios productos, 5 a 10.

**10 · ¿Qué pasa si no tengo la extensión de Chrome o el conector de Meta?**
El estudio sale con menos detalle (menos precisión en antigüedad y conteo de anuncios, confianza máxima Baja sin Chrome) y lo escribe en "Limitaciones". No se detiene.

**11 · ¿Mis datos y mi clave están seguros?**
La clave de fotos vive en un archivo en tu computador (`~/.radar-tienda/.env`) y no se pega en el chat; la configuración (`config.json`) nunca guarda claves. Los datos del estudio salen de fuentes públicas. [completar: aviso de privacidad definitivo]

**12 · ¿Puedo usarlo para productos de salud o belleza?**
Con cuidado. El revisor bloquea promesas médicas ("cura", "adelgaza") y testimonios inventados. Pero registros sanitarios y permisos de publicidad los verificas tú.

**13 · ¿Reemplaza a mi proveedor o a mi criterio?**
No. Te quita el trabajo pesado de investigar y montar. Elegir proveedor, conseguir fotos reales, atender al cliente y decidir cuándo publicar sigue siendo tuyo.

**14 · ¿Cómo actualizo el plugin?**
En claude.ai y Cowork, con "Sincronizar automáticamente" las mejoras llegan solas. En Claude Code, hay dos caminos: en una terminal, `claude plugin update radar-tienda@smart4ai-plugins`; o dentro de la app, escribe `/plugin`, entra a la pestaña **Installed**, elige radar-tienda y pulsa **Update now**. Luego escribe `/reload-plugins` o abre una sesión nueva. (No existe el comando `/plugin update`; verificado en la documentación oficial el 2026-10-16.)

**15 · ¿Dónde pregunto si algo falla?**
En Claude Code escribe `/radar-tienda:radar-ayuda` (o en claude.ai y Cowork, "ayuda con el radar") y pregúntale a la propia skill, o escribe a santi@smart4ai.io.

---

## 10 · Problemas comunes

| Qué pasa | Por qué | Qué haces |
|---|---|---|
| No salen los comandos `/radar-tienda:...` | El plugin no cargó | Cierra y abre la app. Revisa que esté instalado, y una sola vez |
| La skill no se activa sola | En claude.ai y Cowork a veces no ocurre | Nómbrala: "usa radar-tienda para estudiar este producto". En Claude Code, escribe el comando completo, por ejemplo `/radar-tienda:radar-a-tienda` |
| "No encuentro tu tienda de Shopify" | El conector no está conectado | Configuración → Conectores → Shopify → Conectar. Luego `/radar-tienda:radar-configurar` |
| El conteo de anuncios sale vacío o "no verificado" | Falta el conector de Meta o la cuenta publicitaria activa | Conecta Meta Ads. Si no tienes cuenta publicitaria, sigue sin él: el estudio sale con menos detalle |
| Chrome pide iniciar sesión | La Biblioteca de anuncios usa tu sesión de Facebook | Inicia sesión tú en Facebook y repite. El plugin no inicia sesión por ti |
| No se generan fotos con IA | No elegiste una opción de fotos, falta la clave o los créditos de OpenRouter, o falta Python | Corre la configuración y elige otra opción. Mientras tanto usa tus propias fotos |
| Error 401 en las fotos | La clave de OpenRouter es inválida o fue revocada | Crea una nueva en OpenRouter y guárdala con el comando de la sección 3D |
| Error 402 en las fotos | No hay créditos en OpenRouter | Recarga créditos o usa tus fotos |
| Error "429" o "saturado" en las fotos | El servicio de imágenes está lleno | Espera unos minutos y repite, o usa tu foto. El plugin intenta solo con un modelo más liviano |
| `/radar-tienda:radar-a-tienda` me manda a `/radar-tienda:radar-configurar` | Aún no configuraste el plugin | Corre `/radar-tienda:radar-configurar` una vez y repite |
| Salió "PUENTE · RECHAZADO" | El validador encontró algo que no se puede publicar (promesa de salud, testimonio inventado, combos mal escalonados) | Es a propósito. Claude corrige el brief y repite hasta 2 veces; si sigue, te lo dice |
| No hay tablero | Estás en claude.ai/Cowork o no hay Python | Es normal en esos niveles. El resultado igual queda en archivos y en el chat |
| El producto no aparece en mi tienda | Quedó en borrador o hubo un error en la estación Tienda | Busca en Shopify → Productos → filtro "Borrador". Si no está, dile a Claude "reintenta la estación Tienda" |
| Salió DATOS INSUFICIENTES | Foto borrosa o producto con varios objetos | Manda una foto limpia o el enlace del proveedor |
| El ZIP no sube | Se comprimió mal | Usa el `.zip` original del correo; no lo recomprimas |
| Algo más | — | Escribe `/radar-tienda:radar-ayuda` con el mensaje de error, o escribe a santi@smart4ai.io con el error copiado, el nivel que dijo la configuración y, si puedes, `validacion.md` o `recibo.md` de la corrida. Nunca envíes tu clave |

---

## 11 · Límites y responsabilidad

- El estudio es una **muestra de datos públicos**, no un censo del mercado. Algunos precios, costos de proveedor y márgenes son **estimaciones** y se marcan como tales.
- El plugin **no garantiza ventas, ganancias ni resultados**.
- **No es asesoría legal, médica ni financiera.** Registros sanitarios, publicidad, derechos del consumidor, impuestos y normas de Meta y de Shopify son tuyos de verificar.
- Las imágenes con IA son **ilustrativas**; no las uses como foto real del producto.
- **Tú decides** qué se publica, qué se pauta y qué se cobra. El plugin nunca lo hace.
- No pegues claves ni contraseñas en el chat.
- Si el estudio avisa de un riesgo regulatorio, resuélvelo antes de vender.

---

## 12 · Créditos y licencia

- **Estudio de mercado** (`/radar-tienda:radar-producto`): skill creada por Carlos Jiménez, incluida con su autorización.
- **Plugin, puente de validación, tablero, manual y demás skills:** Smart4AI · Santiago Vélez · Medellín · smart4ai.io.
- **Licencia:** Creative Commons Atribución-NoComercial 4.0 (CC BY-NC 4.0). Puedes usarlo y compartirlo citando a sus autores, sin fines comerciales de reventa del plugin.
- **Soporte:** las preguntas frecuentes de este manual, `/radar-tienda:radar-ayuda` y santi@smart4ai.io.

*Versión 1.0 · octubre de 2026.*
