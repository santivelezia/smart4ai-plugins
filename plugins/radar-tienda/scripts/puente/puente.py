# -*- coding: utf-8 -*-
"""
puente.py · Estación 2 del plugin radar-tienda ("Del producto a la tienda").

Lee el brief de landing que produce la skill radar-producto (de Carlos), lo VALIDA con
reglas fijas (sin IA: lo crítico es determinista) y, si pasa, genera el paquete listo
para crear el producto en Shopify en borrador. El puente decide; el modelo no.

Uso (<python> es el intérprete que detectó la configuración: py, python3 o python):
    <python> puente.py "<brief.md>" --estudio "<estudio.md>" --salida "<carpeta>" [opciones]
    <python> puente.py --anuncio "<anuncio-meta.md>" [--salida "<carpeta>"]
    <python> puente.py --resumen "<estudio1.md>" "<estudio2.md>" ...     (tabla para comparar)

Opciones (si no se pasan, salen de ~/.radar-tienda/config.json o de los valores por defecto):
    --vendedor "Radar"  --etiqueta-prueba "radar-prueba"  --coleccion "radar"
    --codigo-descuento ""  (vacío = no se propone descuento)  --pago-contra-entrega si|no
    --imagen "<URL https>" (repetible: llena las imágenes del CSV de importación)
    --config "<config.json>"

Salida del modo brief:
    <salida>/shopify_payload.json   (solo si NO hay errores)
    <salida>/shopify_import.csv     (solo si NO hay errores; formato de importación de Shopify)
    <salida>/validacion.md          (siempre: errores, avisos y qué se generó)

Códigos de salida:
    0 = aprobado (puede haber avisos) · 1 = rechazado por errores de validación
    2 = no se pudo leer un archivo de entrada o faltan argumentos

Solo librería estándar de Python. No se conecta a internet ni a Shopify.
"""

import argparse
import csv
import html
import json
import os
import re
import sys
import unicodedata
from datetime import datetime

# Configuración compartida del plugin (fail-open: si no se puede importar, valores por defecto).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "comun"))
try:
    import entorno  # noqa: E402
except Exception:  # pragma: no cover
    entorno = None

# =====================================================================================
# CONFIGURACIÓN (editable sin tocar la lógica)
# =====================================================================================

# Promesas prohibidas. Cada regla: (expresión regular, nombre corto, tipo).
# Se buscan sobre el texto normalizado: minúsculas y sin tildes ("migraña" -> "migrana").
# Tipos: médico (promesa de salud) · de autoridad (sello o respaldo que no se puede probar) ·
#        de urgencia (escasez sin dato) · de resultados (plazo prometido) · de miedo (pregunta-dolor).
_OBJ_SALUD = (r"(el\s+|la\s+|los\s+|las\s+|tu\s+|tus\s+|su\s+|sus\s+)?"
              r"(dolor|dolores|inflamacion|hinchazon|grasa|celulitis|arrugas|estrias|peso|kilos|medidas|"
              r"tallas|varices|ansiedad|estres|insomnio|migrana|sintomas|molestias|colesterol|presion|"
              r"azucar|tension|contracturas?|acne|manchas|flacidez|caida\s+del\s+cabello)")
CLAIMS_PROHIBIDOS = [
    (r"\bcura(r|s|n)?\b", "cura", "médico"),
    (r"\bcurativ[oa]s?\b", "curativo", "médico"),
    (r"\belimina(r|s|n)?\s+(el\s+|tu\s+|su\s+|todo\s+el\s+|cualquier\s+)?dolor", "elimina el dolor", "médico"),
    (r"\belimina(r|s|n)?\s+(la\s+|tu\s+|su\s+)?migrana", "elimina la migraña", "médico"),
    (r"\belimina(r|s|n)?\s+(las\s+|tus\s+|sus\s+|la\s+|tu\s+|su\s+)?"
     r"(arrugas|celulitis|grasa|estrias|manchas|acne|varices|flacidez)", "elimina arrugas o grasa", "médico"),
    (r"\bquita(r|s|n)?\s+(la\s+|tu\s+|su\s+)?migrana", "quita la migraña", "médico"),
    (r"\bquita(r|s|n)?\s+(el\s+|tu\s+|su\s+|todo\s+el\s+)?dolor", "quita el dolor", "médico"),
    (r"garantizad[oa]\s+(al\s+)?100\s*%|100\s*%\s+garantizad[oa]", "garantizado 100%", "médico"),
    # "sana" solo como verbo ("sana tu espalda"); "postura sana" (adjetivo) no se bloquea.
    (r"\bsana(r|s|n)?\s+(tu|su|el|la|los|las|tus|sus)\b", "sana (como verbo)", "médico"),
    (r"\bsanar\b", "sanar", "médico"),
    (r"\btrata(r|s|n)?\s+(la\s+|las\s+|tu\s+|tus\s+|su\s+|sus\s+|el\s+|los\s+)?"
     r"(enfermedad|escoliosis|hernia|lesion|artritis|artrosis|cifosis|lordosis|dolor|inflamacion|"
     r"ansiedad|insomnio|acne|migrana|diabetes|hipertension)", "trata la enfermedad", "médico"),
    (r"\bcorrige(n)?\s+(la\s+|tu\s+|su\s+)?(escoliosis|hernia|cifosis|lordosis)", "corrige una enfermedad", "médico"),
    (r"\badios\s+al\s+dolor\b", "adiós al dolor", "médico"),
    (r"\bfin\s+del\s+dolor\b", "fin del dolor", "médico"),
    (r"\bsin\s+dolor\s+para\s+siempre\b", "sin dolor para siempre", "médico"),
    (r"\breemplaza(r|n)?\s+(al\s+|el\s+|a\s+tu\s+|tu\s+)?(medico|fisioterapeuta|medicamento|tratamiento)",
     "reemplaza al médico o tratamiento", "médico"),
    # Verbos de efecto sobre el cuerpo (2026-10-16, auditoría: estas frases pasaban).
    (r"\balivi(a|an|ar|as)\b", "alivia", "médico"),
    (r"\balivio\s+(del?\s+|inmediato|para|de\s+tu)", "alivio del dolor", "médico"),
    (r"\breduce(n|s)?\s+" + _OBJ_SALUD, "reduce (dolor, grasa, medidas…)", "médico"),
    (r"\bdisminuye(n|s)?\s+" + _OBJ_SALUD, "disminuye (dolor, grasa…)", "médico"),
    (r"\bprevien(e|en|es)\b|\bprevenir\b|\bprevencion\s+de\b", "previene", "médico"),
    (r"\bdesinflam\w*", "desinflama", "médico"),
    (r"\badelgaz\w*", "adelgaza", "médico"),
    (r"\bquema(r|n|s)?\s+(la\s+|tu\s+)?(grasa|calorias)|\bquemagrasa", "quema grasa", "médico"),
    (r"\bbaja(r|s|n)?\s+de\s+peso\b|\bpierde(s|n)?\s+(peso|kilos|tallas)\b", "baja de peso", "médico"),
    (r"\bterapeutic[oa]s?\b|\bterapia\b", "terapéutico", "médico"),
    # Autoridad que el vendedor no puede probar.
    (r"\binvima\b", "INVIMA", "de autoridad"),
    (r"\bfda\b", "FDA", "de autoridad"),
    (r"\bclinicamente\b", "clínicamente", "de autoridad"),
    (r"\bcientificamente\b", "científicamente", "de autoridad"),
    (r"\bmedic[oa]s?\b", "médico", "de autoridad"),
    (r"\b(aprobado|avalado|recomendado|certificado)s?\s+por\s+(expertos|especialistas|doctores|dermatologos)",
     "avalado por expertos", "de autoridad"),
    # Miedo y comparación corporal.
    (r"¿\s*sufres\b|^\s*sufres\s+de\b", "¿sufres…?", "de miedo"),
    (r"\bantes\s+y\s+despues\b", "antes y después", "de resultados"),
    (r"\bresultados?\s+(visibles\s+|garantizados\s+)?(en|desde)\s+(solo\s+|apenas\s+)?(el\s+)?(primer\s+|\d+\s+)"
     r"(dia|dias|semana|semanas|hora|horas|minutos?)\b", "resultados en N días", "de resultados"),
    (r"\ben\s+(solo\s+)?\d+\s+(dias|semanas)\s+(veras|notaras|sentiras)\b", "resultados en N días", "de resultados"),
    # Urgencia o escasez sin dato.
    (r"\bquedan\s+(pocas|pocos|muy\s+pocas|las\s+ultimas|solo\s+\d+)\b", "quedan pocas unidades", "de urgencia"),
    (r"\bultimas\s+unidades\b", "últimas unidades", "de urgencia"),
    (r"\bsolo\s+(por\s+)?hoy\b", "solo hoy", "de urgencia"),
    (r"\b(stock|unidades|existencias)\s+limitad[oa]s?\b|\bpor\s+tiempo\s+limitado\b", "stock limitado", "de urgencia"),
    (r"\bse\s+(estan\s+)?agota(n|ndo)\b", "se agota", "de urgencia"),
]

# Frases permitidas que contienen palabras de la lista (avisos legales). Se quitan del texto
# ANTES de buscar promesas, para no dar falsos positivos.
FRASES_PERMITIDAS = [
    r"no\s+(reemplaza|sustituye)\s+(la\s+|el\s+|a\s+|al\s+|tu\s+|a\s+tu\s+)?"
    r"(consulta|atencion|diagnostico|valoracion|tratamiento|medico|fisioterapeuta|medicamento)"
    r"(\s+medic[oa])?(\s+(con|de)\s+(un|tu|su)\s+(medico|profesional|especialista)(\s+de\s+la\s+salud)?)?",
    r"consulta(r|lo)?\s+(a\s+|con\s+)?(tu|un|su)\s+(medico|profesional\s+de\s+la\s+salud|especialista)",
    r"no\s+es\s+(un\s+)?(dispositivo|producto|tratamiento|equipo|instrumento)\s+medico",
    r"no\s+es\s+(un\s+)?medicamento",
    r"\(?\s*no\s+medic[oa]\s*[,)]?",
]

# Marcadores de dato por confirmar: «[CONFIRMAR…]», «[POR CONFIRMAR…]», «[PENDIENTE…]».
# (El marcador [TESTIMONIO REAL PENDIENTE] empieza por TESTIMONIO y NO cuenta aquí.)
RE_POR_CONFIRMAR = re.compile(r"\[\s*(?:por\s+)?(?:confirmar|pendiente)[^\]]*\]", re.I)

# Frases que prometen pago contra entrega (se quitan si la tienda no lo tiene activo).
RE_CONTRA_ENTREGA = re.compile(r"contra\s*entrega|contraentrega|paga(s|r)?\s+al\s+recibir|pago\s+al\s+recibir", re.I)

# Umbral de margen para proponer un código de descuento (decisión del proyecto).
MARGEN_MINIMO_DESCUENTO = 25.0

# Moneda que corresponde a cada país (código ISO).
MONEDA_POR_PAIS = {
    "CO": "COP", "MX": "MXN", "PE": "PEN", "CL": "CLP", "EC": "USD", "GT": "GTQ",
    "PA": "USD", "AR": "ARS", "BO": "BOB", "PY": "PYG", "CR": "CRC", "DO": "DOP",
    "US": "USD", "UY": "UYU", "SV": "USD", "HN": "HNL",
}
NOMBRE_A_PAIS = {
    "colombia": "CO", "col": "CO", "mexico": "MX", "peru": "PE", "chile": "CL",
    "ecuador": "EC", "guatemala": "GT", "panama": "PA", "argentina": "AR", "bolivia": "BO",
    "paraguay": "PY", "costa rica": "CR", "republica dominicana": "DO",
    "estados unidos": "US", "usa": "US", "uruguay": "UY", "el salvador": "SV", "honduras": "HN",
}
GENTILICIO_EN = {
    "CO": "Colombian", "MX": "Mexican", "PE": "Peruvian", "CL": "Chilean", "EC": "Ecuadorian",
    "GT": "Guatemalan", "PA": "Panamanian", "AR": "Argentinian",
}

# Datos del paquete para Shopify: salen de la configuración del usuario (ver leer_opciones).
DESCUENTO_PORCENTAJE = 10
DESCUENTO_MINIMO_UNIDADES = 2
MAX_TITULO_SEO = 70
MAX_DESCRIPCION_SEO = 160
MAX_PROMESA = 140

# Marcador obligatorio donde iría prueba social real.
MARCADOR_TESTIMONIO = "[TESTIMONIO REAL PENDIENTE]"

# Líneas que HABLAN de lo prohibido (meta-texto: "evita decir «cura»") y no lo afirman.
# Se excluyen del escaneo del brief. El HTML final se escanea SIN esta excepción.
MARCAS_METATEXTO = ["evita", "prohib", "no uses", "no usar", "no digas", "no decir",
                    "en vez de", "en lugar de", "no inventes", "no prometas", "no pongas"]

# Secciones del brief que son instrucciones para la IA o para el diseño, no copy (no se escanean).
# El HTML final se escanea igual, sin excepciones: si algo de aquí se cuela, se detecta allá.
SECCIONES_SIN_ESCANEO = ["instrucciones", "estilo"]

# Palabras tras un guion que indican una FUENTE, no el nombre de un cliente.
NO_SON_NOMBRES = {"fuente", "comentario", "resena", "cliente", "clienta", "usuario", "usuaria",
                  "anuncio", "anunciante", "tiktok", "youtube", "reddit", "aliexpress", "amazon",
                  "mercado", "facebook", "instagram", "meta", "google", "foro", "copy",
                  "competencia", "tienda", "pregunta", "estudio"}

# =====================================================================================
# UTILIDADES DE TEXTO
# =====================================================================================


def norm(texto):
    """Minúsculas y sin tildes, para comparar sin depender de la ortografía."""
    texto = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def slug(texto, maximo=60):
    """Convierte un texto en un identificador ascii: 'Corrector de Postura' -> 'corrector-de-postura'."""
    s = re.sub(r"[^a-z0-9]+", "-", norm(texto)).strip("-")
    if len(s) > maximo:
        s = s[:maximo].rsplit("-", 1)[0] if "-" in s[:maximo] else s[:maximo]
    return s


# Palabras que no deben quedar al final de una etiqueta o un genérico ("...con sensor de").
CONECTORES = {"de", "del", "la", "el", "los", "las", "con", "para", "y", "e", "o", "u", "en",
              "a", "al", "sin", "por", "un", "una", "su", "sus"}


def slug_palabras(texto, max_palabras=4, quitar_conectores=False):
    """Slug por palabras completas, nunca cortado a media palabra ni terminado en preposición.
    'Corrector de postura con sensor de vibración' -> 'corrector-de-postura' (4 palabras, sin 'con')."""
    palabras = re.findall(r"[a-z0-9]+", norm(texto))
    if quitar_conectores:
        palabras = [p for p in palabras if p not in CONECTORES]
    palabras = palabras[:max_palabras]
    while palabras and palabras[-1] in CONECTORES:
        palabras.pop()
    return "-".join(palabras)


def generico_corto(producto, max_palabras=5):
    """'Corrector de postura con sensor de vibración' -> 'Corrector de postura con sensor'."""
    palabras = str(producto or "").split()[:max_palabras]
    while palabras and norm(palabras[-1]).strip(".,;:") in CONECTORES:
        palabras.pop()
    t = " ".join(palabras).strip(" ,;:.")
    return t[:1].upper() + t[1:]


def recortar(texto, maximo):
    """Recorta en el último espacio antes del máximo (sin cortar palabras)."""
    texto = re.sub(r"\s+", " ", str(texto)).strip()
    if len(texto) <= maximo:
        return texto
    corte = texto[:maximo]
    if " " in corte:
        corte = corte.rsplit(" ", 1)[0]
    return corte.rstrip(" ,;:-–—")


def pesos(valor):
    """Formato de precio colombiano: 89900 -> '$89.900'."""
    return "$" + f"{int(round(valor)):,}".replace(",", ".")


def limpiar_md(texto):
    """Quita marcas de markdown de una celda o línea (negritas, comillas de código)."""
    return re.sub(r"[*`]", "", str(texto)).strip()


def a_numero(valor):
    """Devuelve el número si es numérico (o texto tipo '$89.900'); si no, None."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        t = valor.strip().replace("$", "").replace(" ", "").replace("COP", "")
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", t):        # 89.900 (miles con punto)
            return float(t.replace(".", ""))
        if re.fullmatch(r"\d{1,3}(,\d{3})+", t):          # 89,900 (miles con coma)
            return float(t.replace(",", ""))
        if re.fullmatch(r"\d+(\.\d+)?", t):
            return float(t)
    return None


# =====================================================================================
# LECTURA DEL BRIEF
# =====================================================================================

RE_BLOQUE_CODIGO = re.compile(r"```[ \t]*([A-Za-z]*)[ \t]*\r?\n(.*?)```", re.S)


def json_tolerante(texto):
    """json.loads que perdona comas finales, comillas tipográficas y comentarios //."""
    try:
        return json.loads(texto)
    except ValueError:
        pass
    t = texto.replace("“", '"').replace("”", '"')
    t = re.sub(r"(?m)^\s*//.*$", "", t)
    t = re.sub(r",\s*([}\]])", r"\1", t)
    return json.loads(t)


def normalizar_claves(obj):
    """'Nombre comercial' -> 'nombre_comercial' en todos los niveles del JSON."""
    if isinstance(obj, dict):
        return {re.sub(r"[^a-z0-9]+", "_", norm(k)).strip("_"): normalizar_claves(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalizar_claves(v) for v in obj]
    return obj


def extraer_json(texto):
    """Busca el bloque ```json de datos estructurados. Devuelve (datos, inicio, fin, error)."""
    candidatos = list(RE_BLOQUE_CODIGO.finditer(texto))
    # Primero los marcados como json; dentro de ellos, el último (Datos estructurados va al final).
    ordenados = [m for m in candidatos if m.group(1).lower() == "json"][::-1] + \
                [m for m in candidatos if m.group(1).lower() != "json"][::-1]
    ultimo_error = None
    for m in ordenados:
        try:
            datos = json_tolerante(m.group(2))
        except ValueError as e:
            ultimo_error = str(e)
            continue
        if isinstance(datos, dict):
            datos = normalizar_claves(datos)
            if "producto" in datos or "ofertas" in datos or "nombre_comercial" in datos:
                return datos, m.start(), m.end(), None
    if ultimo_error:
        return None, -1, -1, f"el bloque JSON no se pudo leer ({ultimo_error})"
    return None, -1, -1, "no se encontró el bloque ```json de «Datos estructurados»"


def partir_secciones(texto):
    """Devuelve una lista de secciones H2: {titulo, norm, lineas:[(n_linea, texto)]}."""
    secciones = []
    actual = {"titulo": "(inicio)", "norm": "(inicio)", "lineas": []}
    dentro_codigo = False
    for n, linea in enumerate(texto.splitlines(), start=1):
        if linea.strip().startswith("```"):
            dentro_codigo = not dentro_codigo
        m = None if dentro_codigo else re.match(r"^##\s+(?!#)(.*)", linea)
        if m:
            secciones.append(actual)
            titulo = limpiar_md(m.group(1))
            actual = {"titulo": titulo, "norm": norm(titulo), "lineas": []}
        else:
            actual["lineas"].append((n, linea))
    secciones.append(actual)
    return secciones


def buscar_seccion(secciones, *claves):
    """Primera sección cuyo título contiene alguna de las claves (sin tildes)."""
    for s in secciones:
        if any(norm(c) in s["norm"] for c in claves):
            return s
    return None


def texto_de(seccion):
    if not seccion:
        return ""
    return "\n".join(l for _, l in seccion["lineas"]).strip()


def partir_en_bloques(texto):
    """Parte un texto en bloques etiquetados: '### X', '**X:**' o 'X:' en una línea corta.
    Devuelve [(etiqueta, contenido)]. Lo que va antes de la primera etiqueta queda con etiqueta ''."""
    bloques = []
    etiqueta, contenido = "", []
    for linea in texto.splitlines():
        s = linea.strip()
        m = (re.match(r"^#{3,6}\s+(.*)$", s)
             or re.match(r"^\*\*([^*]{2,60}?):?\*\*:?\s*(.*)$", s)
             or re.match(r"^([A-ZÁÉÍÓÚÑ¿][^:]{1,50}):\s*$", s))
        if m:
            bloques.append((etiqueta, "\n".join(contenido).strip()))
            etiqueta = limpiar_md(m.group(1)).rstrip(":")
            resto = m.group(2).strip() if m.lastindex and m.lastindex >= 2 else ""
            contenido = [resto] if resto else []
        else:
            contenido.append(linea)
    bloques.append((etiqueta, "\n".join(contenido).strip()))
    return [(e, c) for e, c in bloques if e or c]


# Tipos de bloque de la página de venta y las palabras que los reconocen (el orden importa).
TIPOS = [
    ("subtitular", ["subtitular", "subtitulo", "bajada"]),
    ("titulares", ["titular", "titulo", "headline"]),
    ("hero", ["hero", "encabezado", "portada"]),
    ("confianza", ["confianza"]),
    ("prueba", ["prueba social", "testimonio"]),
    ("comparativa", ["comparativa", "comparacion", " vs"]),
    ("faq", ["preguntas", "faq"]),
    ("formulario", ["formulario"]),
    ("problema", ["problema", "dolor"]),
    ("agitacion", ["agitacion", "consecuencia"]),
    ("solucion", ["solucion", "mecanismo"]),
    ("beneficios", ["beneficio"]),
    ("uso", ["como se usa", "modo de uso", "pasos", "uso"]),
    ("oferta", ["oferta", "combo", "precio"]),
    ("garantia", ["garantia", "politica"]),
    ("cta", ["cta", "boton", "llamado"]),
]


def tipo_de(etiqueta):
    e = " " + norm(etiqueta)
    for tipo, claves in TIPOS:
        if any(c in e for c in claves):
            return tipo
    return None


def leer_copy_base(seccion):
    """Copy base del brief -> {tipo: texto}."""
    resultado = {}
    for etiqueta, contenido in partir_en_bloques(texto_de(seccion)):
        tipo = tipo_de(etiqueta) if etiqueta else None
        if tipo and contenido:
            resultado[tipo] = (resultado.get(tipo, "") + "\n" + contenido).strip()
    return resultado


# Frases de la plantilla del SKILL: si la estructura solo las repite, no son copy.
ECO_PLANTILLA = {norm(x) for x in [
    "titular, subtitular, CTA, qué imagen/video mostrar", "envío, contra entrega, garantía",
    "dolores en palabras del cliente", "beneficio → característica que lo respalda",
    "3 pasos", "espacios para testimonios reales; qué tipo de prueba buscar",
    "vs. alternativas que el cliente ya intentó", "retracto 5 días hábiles, cambios de talla si aplica",
    "cada objeción con su respuesta", "", "agitación / consecuencia",
]}


def leer_estructura(seccion):
    """Lista numerada de 'Estructura de la página' -> {tipo: texto} (respaldo si falta copy)."""
    items, actual = [], None
    for linea in texto_de(seccion).splitlines():
        m = re.match(r"^\s*\d+[.)]\s+(.*)$", linea)
        if m:
            actual = [m.group(1)]
            items.append(actual)
        elif actual is not None and linea.strip():
            actual.append(linea.strip())
    resultado = {}
    for item in items:
        primera = limpiar_md(item[0])
        partes = re.split(r"\s*[:—–]\s*|\s+-\s+", primera, maxsplit=1)
        etiqueta = partes[0]
        resto = partes[1] if len(partes) > 1 else ""
        contenido = "\n".join([resto] + item[1:]).strip()
        contenido_limpio = re.sub(r"^\((.*)\)$", r"\1", contenido.strip())
        tipo = tipo_de(etiqueta)
        if not tipo or norm(contenido_limpio) in ECO_PLANTILLA:
            continue
        resultado[tipo] = contenido
    return resultado


# Frases que son instrucciones para la IA (no copy para el cliente). Se comparan sin tildes.
MARCAS_INSTRUCCION = ["sin tecnicismos", "no usar", "no uses", "evitar", "evita ", "promesas de",
                      "usar frases", "no medico", "(no medico", "no pongas", "no inventes", "sin inventar",
                      "en palabras del cliente", "la ia ", "recomienda la", "sin estrellas",
                      "hasta tenerlos", "no alarmista", "pasos visuales", "tono:"]
RE_INSTRUCCION = re.compile(r"\btono\b|\bimagen\b|\bvideo\b|\bfoto\b|\bgif\b|\bmostrar\b|\bmuestra\b"
                            r"|\bvisuales\b|\bdestacar\b")
# "fotos" es instrucción solo al empezar la frase o detrás de un verbo de diseño
# ("Fotos reales de oficina", "usa fotos del proveedor"); "te ves encorvado en las fotos" es copy.
RE_FOTOS_INSTRUCCION = re.compile(r"^\W*fotos\b|\b(usa|usar|incluye|incluir|agrega|agregar|pon|poner|sube|subir|"
                                  r"anade|anadir|con|muestra|mostrar)\s+(\w+\s+){0,2}fotos\b")


def es_instruccion(frase):
    n = " " + norm(frase) + " "
    return (any(m in n for m in MARCAS_INSTRUCCION) or bool(RE_INSTRUCCION.search(n))
            or bool(RE_FOTOS_INSTRUCCION.search(norm(frase).strip())))


def normalizar_frase(frase):
    """Mayúscula inicial y punto final: 'te encorvas…;' -> 'Te encorvas….'"""
    f = frase.strip().rstrip(";,: ").strip()
    if not f:
        return ""
    m = re.match(r"^([«\"“¿¡(\[]*)(.)(.*)$", f, re.S)
    f = m.group(1) + m.group(2).upper() + m.group(3)
    if not re.search(r"[.!?»\"”…]$", f):
        f += "."
    return f


def filtrar_copy(texto):
    """Copy base: quita, dentro de cada línea, las frases que son instrucciones."""
    salida = []
    for linea in str(texto).splitlines():
        m = re.match(r"^(\s*(?:[-*•]|\d+[.)])\s+)?(.*)$", linea)
        prefijo, cuerpo = m.group(1) or "", m.group(2)
        trozos = re.split(r"(?<=[.!?;])\s+", cuerpo)
        limpio = " ".join(t for t in trozos if t.strip() and not es_instruccion(t)).strip()
        if limpio or not cuerpo.strip():
            salida.append(prefijo + limpio)
    return "\n".join(salida).strip()


def quitar_indicaciones_visuales(texto):
    """Respaldo de 'Estructura': parte en frases, quita órdenes de diseño e instrucciones,
    normaliza cada frase (mayúscula y punto) y convierte '(1) …' y 'a · b · c' en listas."""
    lineas = []
    for trozo in re.split(r"\n|(?<=[.;!?])\s+|;\s*", texto):
        trozo = trozo.strip()
        if not trozo:
            continue
        partes = [p for p in re.split(r"\s+·\s+", trozo) if p.strip()]
        es_lista = len(partes) > 1
        for p in partes:
            p = p.strip()
            m = re.match(r"^\(?\d+[).]\s*(.*)$", p)
            if m:
                p, es_item = m.group(1), True
            else:
                es_item = es_lista
            if not p or es_instruccion(p):
                continue
            p = normalizar_frase(p)
            lineas.append(("- " if es_item else "") + p)
    return "\n".join(lineas).strip()


def items_de_lista(texto):
    """Ítems de una lista markdown (- x, * x, 1. x)."""
    return [limpiar_md(m.group(1)) for m in re.finditer(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+(.+)$", texto)]


# =====================================================================================
# ESTUDIO (opcional)
# =====================================================================================

CLAVES_ESTUDIO = [
    ("veredicto", ["veredicto"]),
    ("confianza", ["confianza"]),
    ("precio_recomendado", ["precio recomendado"]),
    ("cpa_equilibrio", ["cpa de equilibrio", "cpa equilibrio"]),
    ("margen", ["margen"]),
    ("anuncios_activos", ["anuncios activos"]),
    ("saturacion", ["saturacion"]),
]


def leer_estudio(texto):
    """Saca la tabla 'Veredicto en 30 segundos' del estudio. Devuelve (dict, aviso o None)."""
    lineas = texto.splitlines()
    inicio = None
    for i, l in enumerate(lineas):
        if l.lstrip().startswith("#") and "veredicto en 30 segundos" in norm(l):
            inicio = i
            break
    if inicio is None:
        return {}, "el estudio no tiene la sección «Veredicto en 30 segundos»"
    resumen = {}
    for l in lineas[inicio + 1:]:
        if l.lstrip().startswith("#"):
            break
        if not l.strip().startswith("|"):
            continue
        celdas = [limpiar_md(c) for c in l.strip().strip("|").split("|")]
        if len(celdas) < 2 or not celdas[0] or set(celdas[0]) <= set("-: "):
            continue
        clave_n = norm(celdas[0])
        for clave, patrones in CLAVES_ESTUDIO:
            if clave not in resumen and any(clave_n.startswith(p) for p in patrones):
                resumen[clave] = " | ".join(celdas[1:]).strip()
                break
    faltan = [c for c, _ in CLAVES_ESTUDIO if c not in resumen]
    aviso = f"del estudio no se pudo leer: {', '.join(faltan)}" if faltan else None
    return resumen, aviso


def margen_porcentaje(texto):
    """'22% (escenario base)' -> 22.0 · '−5 %' -> -5.0 · sin porcentaje -> None."""
    m = re.search(r"([-−–]?)\s*(\d+(?:[.,]\d+)?)\s*%", str(texto or ""))
    if not m:
        return None
    valor = float(m.group(2).replace(",", "."))
    return -valor if m.group(1) else valor


def clase_veredicto(texto):
    """Clasifica el veredicto del estudio: 'no-recomendado', 'precaucion', 'probar' o 'desconocido'."""
    t = norm(texto or "").strip().upper()
    if not t:
        return "desconocido"
    if t.startswith("NO ") or t == "NO" or "NO RECOMEND" in t or "DESCART" in t or "NO PROBAR" in t:
        return "no-recomendado"
    if "PRECAUC" in t or "CUIDADO" in t or "CAUTELA" in t or "DUDOS" in t:
        return "precaucion"
    if "PROBAR" in t or "RECOMENDABLE" in t or "VENDER" in t or t.startswith("SI"):
        return "probar"
    return "desconocido"


def decidir_riesgo(resumen_estudio, codigo_descuento):
    """El puente decide (no el modelo): descuento, etiquetas de riesgo y advertencia.
    Devuelve (discount o None, etiquetas_extra, advertencia o None, avisos)."""
    avisos, etiquetas, advertencia = [], [], None
    if resumen_estudio is None:
        avisos.append("Sin estudio (--estudio): no se puede comprobar margen ni veredicto, así que no se propone descuento.")
        return None, etiquetas, advertencia, avisos
    clase = clase_veredicto(resumen_estudio.get("veredicto"))
    margen = margen_porcentaje(resumen_estudio.get("margen"))
    if clase == "no-recomendado":
        etiquetas.append("no-recomendado")
        advertencia = ("El estudio dice NO RECOMENDABLE. El producto queda en borrador, con la etiqueta "
                       "no-recomendado y sin descuento. No lo publiques sin releer el estudio.")
    elif clase == "precaucion":
        etiquetas.append("precaucion")
    if margen is None:
        avisos.append("No se pudo leer el margen del estudio: no se propone descuento.")
    elif margen < MARGEN_MINIMO_DESCUENTO:
        avisos.append(f"Margen base {margen:g} % (< {MARGEN_MINIMO_DESCUENTO:g} %): no se propone descuento, "
                      f"se comería la ganancia.")
        if "precaucion" not in etiquetas and "no-recomendado" not in etiquetas:
            etiquetas.append("precaucion")
    if clase in ("no-recomendado", "precaucion"):
        avisos.append(f"Veredicto «{resumen_estudio.get('veredicto')}»: sin descuento y con etiqueta {etiquetas[0]}.")
    permitido = clase not in ("no-recomendado", "precaucion") and margen is not None and margen >= MARGEN_MINIMO_DESCUENTO
    if permitido and not str(codigo_descuento or "").strip():
        avisos.append("La configuración no trae código de descuento: no se propone ninguno.")
    if not permitido or not str(codigo_descuento or "").strip():
        return None, etiquetas, advertencia, avisos
    discount = {
        "sugerencia": True,
        "code": re.sub(r"[^A-Z0-9_-]", "", str(codigo_descuento).upper())[:30],
        "percentage": DESCUENTO_PORCENTAJE,
        "minimumQuantity": DESCUENTO_MINIMO_UNIDADES,
        "motivo": f"Margen base {margen:g} % y veredicto «{resumen_estudio.get('veredicto')}».",
        "nota": "Propuesta: el orquestador la crea en Shopify solo si el usuario la aprueba.",
    }
    return discount, etiquetas, advertencia, avisos


# =====================================================================================
# VALIDACIÓN
# =====================================================================================

RE_ESTRELLAS = re.compile(r"[★⭐✩✪]|\b[1-5](?:[.,]\d)?\s*/\s*5\b(?![/\d])|\b[1-5]\s+estrellas\b", re.I)
RE_CONTEO_RESENAS = re.compile(
    r"\b\d[\d.,]*\s*\+?\s*(?:reseñas|resenas|opiniones|valoraciones|calificaciones|"
    r"clientes\s+(?:satisfechos|felices|contentos))\b", re.I)
RE_CITA_CON_NOMBRE = re.compile(r"[\"“«][^\"”»]{8,}[\"”»]\s*[-–—]\s*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)")
RE_NOMBRE_CON_INICIAL = re.compile(r"[-–—]\s*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\s+[A-ZÁÉÍÓÚÑ]\.(?=[\s,]|$)")
RE_ETIQUETA_TESTIMONIO = re.compile(r"\b(?:testimonio|reseña|opinión)\s*(?:\d+|de\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\s*:", re.I)

RE_DESCUENTO = [
    (re.compile(r"\bantes\s*:?\s*\$?\s*\d{2,3}[.,]\d{3}"), "«antes $X»"),
    (re.compile(r"\bprecio\s+(?:normal|regular|original|de\s+lista)\s*:?\s*\$?\s*\d"), "«precio normal $X»"),
    (re.compile(r"~~[^~]*\d[^~]*~~"), "precio tachado (~~)"),
    (re.compile(r"<\s*(?:s|del|strike)\s*>"), "precio tachado (<s>/<del>)"),
    (re.compile(r"\b\d{1,2}\s*%\s*(?:de\s+)?(?:descuento|dto|dcto|off)\b"), "porcentaje de descuento"),
    (re.compile(r"\b(?:descuento|dto|dcto)\s+(?:del?\s+)?\d{1,2}\s*%"), "porcentaje de descuento"),
    (re.compile(r"\bcompare_?at_?price\b"), "compareAtPrice"),
]


def es_metatexto(linea):
    n = norm(linea)
    return any(m in n for m in MARCAS_METATEXTO)


def buscar_testimonios(linea):
    """Devuelve el motivo si la línea parece un testimonio o reseña inventada; si no, None."""
    if MARCADOR_TESTIMONIO.lower() in linea.lower():
        return None
    if RE_ESTRELLAS.search(linea):
        return "estrellas o calificación"
    if RE_CONTEO_RESENAS.search(linea):
        return "conteo de reseñas o clientes"
    for regex in (RE_CITA_CON_NOMBRE, RE_NOMBRE_CON_INICIAL):
        for m in regex.finditer(linea):
            if norm(m.group(1)) not in NO_SON_NOMBRES:
                return f"cita atribuida a «{m.group(1)}»"
    if RE_ETIQUETA_TESTIMONIO.search(linea):
        return "testimonio etiquetado sin marcar como pendiente"
    return None


def buscar_claims(linea):
    """Nombres de las promesas prohibidas que aparecen en la línea (sin contar avisos legales permitidos)."""
    return [nombre for nombre, _ in buscar_claims_con_tipo(linea)]


def buscar_claims_con_tipo(linea):
    n = norm(linea)
    for permitida in FRASES_PERMITIDAS:
        n = re.sub(permitida, " ", n)
    salida = []
    for regex, nombre, tipo in CLAIMS_PROHIBIDOS:
        if re.search(regex, n) and (nombre, tipo) not in salida:
            salida.append((nombre, tipo))
    return salida


def sin_instrucciones(linea):
    """Quita de una línea las frases que son instrucciones para la IA (no copy) antes de escanearla."""
    trozos = re.split(r"(?<=[.!?;])\s+", str(linea))
    return " ".join(t for t in trozos if t.strip() and not es_instruccion(t))


# -------------------------------------------------------------------------------------
# Datos por confirmar y frases que dependen de la configuración
# -------------------------------------------------------------------------------------

def marcadores(texto):
    """[CONFIRMAR…], [POR CONFIRMAR…], [… PENDIENTE] que hay en un texto (no cuenta el de testimonios)."""
    return [m.group(0) for m in re.finditer(r"\[[^\]\[]*\b(?:confirmar|pendiente)\b[^\]\[]*\]", str(texto), re.I)
            if m.group(0).strip().upper() != MARCADOR_TESTIMONIO]


# Temas que, si el brief los marca por confirmar en CUALQUIER lugar, no se publican en NINGÚN lugar
# (el JSON a veces trae el dato sin la marca). (nombre, cómo se reconoce el tema en la línea marcada,
# qué fragmentos se quitan de lo publicable).
TEMAS_POR_CONFIRMAR = [
    # Ojo: "5 días hábiles de retracto" NO es un plazo de entrega y no se toca.
    ("días de entrega", r"entrega|llega|transportadora|despacho|envio",
     r"\b\d+\s*(a|-|–)\s*\d+\s*dias|(entrega|llega|demora|tarda|despacha|recibes)\D{0,25}\d+\s*dias"
     r"|entrega\s+estimada"),
    ("contenido de la caja o manual", r"\bcaja\b|\bmanual\b|\bincluye\b",
     r"\bmanual\b|en\s+la\s+caja|la\s+caja\s+(trae|incluye)|que\s+incluye"),
    ("autonomía de la batería", r"bateria|autonomia",
     r"\bautonomia\b|\bdura(n)?\s+(hasta\s+)?\d+\s*(horas|dias|h)\b"),
]


def temas_marcados(texto):
    """Qué temas sensibles están marcados por confirmar en el brief."""
    temas = []
    for linea in str(texto).splitlines():
        if not marcadores(linea):
            continue
        n = norm(linea)
        for nombre, detecta, quita in TEMAS_POR_CONFIRMAR:
            if re.search(detecta, n) and (nombre, quita) not in temas:
                temas.append((nombre, quita))
    return temas


def _partir_fragmentos(linea):
    """Parte una línea en fragmentos (frases, ';' y listas con ' · ') conservando los separadores."""
    piezas = re.split(r"((?<=[.!?;])\s+|\s+·\s+)", linea)
    pares = []
    for i in range(0, len(piezas), 2):
        pares.append((piezas[i], piezas[i + 1] if i + 1 < len(piezas) else ""))
    return pares


def sanear_texto(texto, reglas):
    """Quita de un texto los fragmentos que no se pueden publicar. reglas = [(motivo, regex sobre texto normalizado)].
    Devuelve (texto_limpio, [(motivo, fragmento quitado)])."""
    if not isinstance(texto, str) or not texto.strip():
        return texto, []
    quitados = []
    # 1) Paréntesis con un marcador: se quita solo el paréntesis.
    def _par(m):
        if marcadores(m.group(0)):
            quitados.append(("dato por confirmar", m.group(0).strip()))
            return ""
        return m.group(0)
    texto = re.sub(r"\s*\([^()]*\)", _par, texto)
    salida = []
    for linea in texto.splitlines():
        m = re.match(r"^(\s*(?:[-*•]|\d+[.)])\s+)?(.*)$", linea)
        prefijo, cuerpo = m.group(1) or "", m.group(2)
        conservar = []
        for frag, sep in _partir_fragmentos(cuerpo):
            motivo = None
            if marcadores(frag):
                motivo = "dato por confirmar"
            else:
                n = norm(frag)
                for nombre, regex in reglas:
                    if re.search(regex, n):
                        motivo = nombre
                        break
            if motivo and frag.strip():
                quitados.append((motivo, frag.strip()))
            else:
                conservar.append((frag, sep))
        limpio = "".join(f + s for f, s in conservar).strip().rstrip("·;,").strip()
        # Si se quitó el final de una frase, se cierra con punto ("…con la espalda recta; el manual…" -> "…recta.").
        if limpio and len(conservar) < len(_partir_fragmentos(cuerpo)) and not re.search(r"[.!?…»\"”)]$", limpio):
            limpio += "."
        if limpio or not cuerpo.strip():
            salida.append(prefijo + limpio)
    return "\n".join(salida).strip(), quitados


def reglas_publicables(temas, contra_entrega):
    """Reglas de saneo: temas marcados por confirmar + pago contra entrega si la tienda no lo tiene."""
    reglas = [(f"{nombre} por confirmar", quita) for nombre, quita in temas]
    if not contra_entrega:
        reglas.append(("pago contra entrega desactivado en la configuración", RE_CONTRA_ENTREGA.pattern))
    return reglas


def sanear_datos(datos, copy, estructura, reglas):
    """Aplica el saneo a todo lo que puede llegar a la página o al SEO. Devuelve copias limpias y la lista de quitados."""
    quitados = []
    d = json.loads(json.dumps(datos, ensure_ascii=False))
    for campo in ("envio", "pago", "garantia", "bonus", "promesa", "cta", "angulo"):
        if isinstance(d.get(campo), str):
            d[campo], q = sanear_texto(d[campo], reglas)
            quitados += q
    if isinstance(d.get("dolores"), list):
        nuevos = []
        for x in textos_lista(d["dolores"]):
            t, q = sanear_texto(x, reglas)
            quitados += q
            if t:
                nuevos.append(t)
        d["dolores"] = nuevos
    if isinstance(d.get("objeciones"), list):
        nuevas = []
        for o in leer_objeciones(d["objeciones"]):
            p, qp = sanear_texto(o["objecion"], reglas)
            r, qr = sanear_texto(o["respuesta"], reglas)
            if qp or not p or not r:  # pregunta tocada o respuesta vacía: la pregunta entera no se publica
                quitados.append(("pregunta frecuente retirada", o["objecion"]))
                continue
            quitados += qr
            nuevas.append({"objecion": p, "respuesta": r})
        d["objeciones"] = nuevas
    c, e = {}, {}
    for origen, destino in ((copy, c), (estructura, e)):
        for k, v in origen.items():
            destino[k], q = sanear_texto(v, reglas)
            quitados += q
    return d, c, e, quitados


def buscar_descuentos(linea):
    n = norm(linea)
    return [nombre for regex, nombre in RE_DESCUENTO if regex.search(n)]


def lineas_a_escanear(texto, secciones, json_ini, json_fin):
    """Líneas del brief que son copy o datos (fuera de instrucciones, del JSON y de lo 'a evitar')."""
    # Rango de líneas del bloque JSON (se escanea aparte, por valores).
    linea_ini = texto.count("\n", 0, json_ini) + 1 if json_ini >= 0 else -1
    linea_fin = texto.count("\n", 0, json_fin) + 1 if json_fin >= 0 else -1
    salida = []
    for s in secciones:
        if any(c in s["norm"] for c in SECCIONES_SIN_ESCANEO):
            continue
        modo_evitar = False
        es_palabras = "palabras" in s["norm"] or "frases" in s["norm"]
        for n, linea in s["lineas"]:
            if linea_ini <= n <= linea_fin:
                continue
            if es_palabras:
                corta = norm(limpiar_md(linea)).strip("#: -")
                if "evitar" in corta or "prohib" in corta:
                    modo_evitar = True
                    continue
                if len(corta) <= 40 and re.search(r"\busar\b", corta):
                    modo_evitar = False
                    continue
                if modo_evitar:
                    continue
            if es_metatexto(linea):
                continue
            if s["titulo"] == "(inicio)" and linea.lstrip().startswith(">"):
                continue  # nota del encabezado del brief (no es copy; el HTML final igual se escanea)
            limpia = sin_instrucciones(linea)  # las instrucciones para la IA no son copy
            if limpia.strip():
                salida.append((f"línea {n}", limpia))
    return salida


def valores_json(obj, ruta="json"):
    """Todos los textos del JSON con su ruta, para escanearlos."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if "evitar" in k or "prohib" in k:
                continue
            yield from valores_json(v, f"{ruta}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from valores_json(v, f"{ruta}[{i}]")
    elif isinstance(obj, str):
        yield ruta, obj


def normalizar_pais(valor):
    if not valor:
        return None
    v = norm(valor).strip()
    if v.upper() in MONEDA_POR_PAIS:
        return v.upper()
    return NOMBRE_A_PAIS.get(v)


def textos_lista(valor, claves=("dolor", "texto", "frase")):
    """Lista de textos aunque vengan como dicts o como texto suelto."""
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, list):
        return []
    salida = []
    for v in valor:
        if isinstance(v, str) and v.strip():
            salida.append(v.strip())
        elif isinstance(v, dict):
            for c in claves:
                if isinstance(v.get(c), str) and v[c].strip():
                    salida.append(v[c].strip())
                    break
    return salida


def leer_objeciones(valor):
    """[{objecion, respuesta}] tolerante a 'pregunta', 'duda', textos sueltos."""
    if not isinstance(valor, list):
        return []
    salida = []
    for v in valor:
        if isinstance(v, dict):
            o = v.get("objecion") or v.get("pregunta") or v.get("duda") or ""
            r = v.get("respuesta") or v.get("solucion") or ""
            if str(o).strip():
                salida.append({"objecion": str(o).strip(), "respuesta": str(r).strip()})
        elif isinstance(v, str) and v.strip():
            salida.append({"objecion": v.strip(), "respuesta": ""})
    return salida


def precio_anterior_valido(nodo):
    """Un precio anterior cuenta solo si es numérico y trae fuente o 'verificado: true'."""
    if not isinstance(nodo, dict) or "precio_anterior" not in nodo:
        return None, None
    valor = a_numero(nodo.get("precio_anterior"))
    fuente = nodo.get("precio_anterior_fuente")
    verificado = nodo.get("precio_anterior_verificado") is True or (isinstance(fuente, str) and fuente.strip() != "")
    return valor, verificado


def validar(datos, texto, secciones, json_ini, json_fin):
    """Aplica las reglas fijas. Devuelve (errores, avisos, ofertas_limpias, pais, precios_anteriores)."""
    errores, avisos = [], []

    # --- Identidad del producto ---
    for campo in ("producto", "nombre_comercial"):
        if not isinstance(datos.get(campo), str) or not datos.get(campo).strip():
            errores.append(f"Falta «{campo}» en el bloque JSON.")

    # --- País y moneda ---
    pais = normalizar_pais(datos.get("pais"))
    if not datos.get("pais"):
        pais = "CO"
        avisos.append("El JSON no trae «pais»; se asume Colombia (CO).")
    elif pais is None:
        avisos.append(f"País «{datos.get('pais')}» no reconocido; no se pudo comprobar la moneda.")
    moneda = str(datos.get("moneda") or "").strip().upper()
    if pais in MONEDA_POR_PAIS:
        esperada = MONEDA_POR_PAIS[pais]
        if moneda != esperada:
            errores.append(f"Moneda «{moneda or '(vacía)'}» no corresponde al país {pais}: debe ser {esperada}.")

    # --- Ofertas ---
    ofertas_crudas = datos.get("ofertas")
    ofertas = []
    if not isinstance(ofertas_crudas, list) or len(ofertas_crudas) < 1:
        errores.append("No hay ofertas: se necesita al menos 1 (unidades + precio).")
        ofertas_crudas = []
    for i, o in enumerate(ofertas_crudas, start=1):
        if not isinstance(o, dict):
            errores.append(f"Oferta {i}: no tiene el formato {{unidades, precio}}.")
            continue
        unidades = a_numero(o.get("unidades", o.get("cantidad", o.get("und"))))
        precio_bruto = o.get("precio", o.get("precio_cop", o.get("valor")))
        precio = a_numero(precio_bruto)
        if unidades is None or unidades < 1 or unidades != int(unidades):
            errores.append(f"Oferta {i}: «unidades» debe ser un entero mayor o igual a 1 (llegó {o.get('unidades')!r}).")
            continue
        if precio is None:
            errores.append(f"Oferta {i} ({int(unidades)} und): precio no numérico ({precio_bruto!r}).")
            continue
        if precio <= 0:
            errores.append(f"Oferta {i} ({int(unidades)} und): precio debe ser mayor que 0 (llegó {precio_bruto!r}).")
            continue
        if isinstance(precio_bruto, str):
            avisos.append(f"Oferta {i}: el precio venía como texto ({precio_bruto!r}); se leyó como {int(precio)}.")
        ofertas.append({"unidades": int(unidades), "precio": precio, "crudo": o})

    vistos = set()
    for o in ofertas:
        if o["unidades"] in vistos:
            errores.append(f"Hay dos ofertas de {o['unidades']} unidades.")
        vistos.add(o["unidades"])
    ofertas.sort(key=lambda x: x["unidades"])

    # Precio por unidad estrictamente decreciente al subir el combo.
    for a, b in zip(ofertas, ofertas[1:]):
        pu_a, pu_b = a["precio"] / a["unidades"], b["precio"] / b["unidades"]
        if pu_b >= pu_a:
            errores.append(
                f"Combos mal escalonados: {b['unidades']} und sale a {pesos(pu_b)} por unidad, "
                f"que no es menor que {pesos(pu_a)} por unidad de {a['unidades']} und.")

    if pais == "CO" or moneda == "COP":
        for o in ofertas:
            if int(round(o["precio"])) % 1000 != 900:
                avisos.append(f"Precio de {o['unidades']} und ({pesos(o['precio'])}) no termina en 900.")

    # --- Precio anterior (compareAtPrice) ---
    precios_anteriores = {}  # unidades -> valor verificado
    nodos = [(1, datos)] + [(o["unidades"], o["crudo"]) for o in ofertas]
    for unidades, nodo in nodos:
        valor, verificado = precio_anterior_valido(nodo)
        if valor is None and verificado is None:
            continue
        precio_oferta = next((o["precio"] for o in ofertas if o["unidades"] == unidades), None)
        if valor is None:
            errores.append(f"«precio_anterior» de {unidades} und no es numérico.")
        elif not verificado:
            errores.append(f"«precio_anterior» de {unidades} und sin fuente verificada "
                           f"(falta «precio_anterior_fuente»): no se permite precio tachado.")
        elif precio_oferta is not None and valor <= precio_oferta:
            errores.append(f"«precio_anterior» de {unidades} und ({pesos(valor)}) no es mayor que el precio actual.")
        else:
            precios_anteriores[unidades] = valor

    # --- Escaneo de texto: testimonios, claims médicos, descuentos ---
    lineas = lineas_a_escanear(texto, secciones, json_ini, json_fin) + list(valores_json(datos))
    for donde, linea in lineas:
        extracto = recortar(linea.strip(), 90)
        motivo = buscar_testimonios(linea)
        if motivo:
            errores.append(f"Testimonio o reseña sin marcar {MARCADOR_TESTIMONIO} ({motivo}) en {donde}: «{extracto}»")
        for claim, tipo in buscar_claims_con_tipo(linea):
            errores.append(f"Claim {tipo} prohibido «{claim}» en {donde}: «{extracto}»")
        if not precios_anteriores:
            for tipo in buscar_descuentos(linea):
                errores.append(f"Descuento o precio tachado sin precio anterior verificado ({tipo}) en {donde}: «{extracto}»")

    # --- Avisos de contenido ---
    if not leer_objeciones(datos.get("objeciones")):
        avisos.append("Faltan objeciones: la página saldrá sin preguntas frecuentes.")
    if not textos_lista(datos.get("dolores")):
        avisos.append("Faltan dolores en el JSON.")
    promesa = str(datos.get("promesa") or "")
    if len(promesa) > MAX_PROMESA:
        avisos.append(f"La promesa tiene {len(promesa)} caracteres (recomendado ≤ {MAX_PROMESA}).")
    nombre = str(datos.get("nombre_comercial") or "")
    if len(nombre) > MAX_TITULO_SEO:
        avisos.append(f"El nombre comercial tiene {len(nombre)} caracteres (> {MAX_TITULO_SEO} para SEO); "
                      f"se usará un título corto.")
    return errores, avisos, ofertas, pais or "CO", precios_anteriores


# =====================================================================================
# GENERACIÓN DEL HTML (página de venta)
# =====================================================================================


def inline(texto):
    """Escapa HTML y convierte **negrita** en <strong>."""
    t = html.escape(limpiar_comillas_md(texto), quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)


def limpiar_comillas_md(texto):
    return str(texto).replace("`", "")


def bloque_html(texto):
    """Markdown sencillo -> <p> y <ul>. Subtítulos ### pasan a <p><strong>."""
    partes, lista = [], []

    def cerrar_lista():
        if lista:
            partes.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in lista) + "</ul>")
            lista.clear()

    for linea in str(texto).splitlines():
        s = linea.strip()
        if not s:
            cerrar_lista()
            continue
        m = re.match(r"^(?:[-*•]|\d+[.)])\s+(.+)$", s)
        if m:
            lista.append(m.group(1))
            continue
        cerrar_lista()
        h = re.match(r"^#{1,6}\s+(.+)$", s)
        if h:
            partes.append(f"<p><strong>{inline(limpiar_md(h.group(1)))}</strong></p>")
        else:
            partes.append(f"<p>{inline(s)}</p>")
    cerrar_lista()
    return "\n".join(partes)


def primer_texto(*opciones):
    for o in opciones:
        if o and str(o).strip():
            return str(o).strip()
    return ""


def armar_html(datos, copy, estructura, ofertas, pais):
    """Arma la página de venta en el orden de 'Estructura de la página' del SKILL.
    Solo usa el contenido del brief; si una sección no tiene contenido, se omite."""
    h = []
    respaldo = {k: quitar_indicaciones_visuales(v) for k, v in estructura.items()}
    copy = {k: filtrar_copy(v) for k, v in copy.items()}

    # 1. Hero (sin las comillas «» que trae el brief alrededor del titular)
    titulares = items_de_lista(copy.get("titulares", "")) or [l for l in copy.get("titulares", "").splitlines() if l.strip()]
    titulares = [re.sub(r"^[«\"“](.*)[»\"”]$", r"\1", t.strip()) for t in titulares]
    citas_hero = re.findall(r"[«\"“]([^»\"”]{6,})[»\"”]", estructura.get("hero", ""))
    titular = primer_texto(titulares[0] if titulares else "", citas_hero[0] if citas_hero else "",
                           datos.get("nombre_comercial"))
    subtitular = primer_texto(limpiar_md(copy.get("subtitular", "")).replace("\n", " "),
                              citas_hero[1] if len(citas_hero) > 1 else "", datos.get("promesa"))
    ctas = items_de_lista(copy.get("cta", "")) or [l for l in copy.get("cta", "").splitlines() if l.strip()]
    cta = primer_texto(datos.get("cta"), ctas[0] if ctas else "", "Pídelo hoy")
    h.append('<div style="text-align:center">')
    h.append(f"<h2>{inline(limpiar_md(titular))}</h2>")
    if subtitular:
        h.append(f"<p>{inline(subtitular)}</p>")
    if cta:
        h.append(f"<p><strong>{inline(limpiar_md(cta))}</strong></p>")
    h.append("</div>")

    # 2. Barra de confianza (solo con datos del JSON)
    confianza = []
    if datos.get("envio"):
        confianza.append(f"<strong>Envío:</strong> {inline(datos['envio'])}")
    if datos.get("pago"):
        confianza.append(f"<strong>Pago:</strong> {inline(datos['pago'])}")
    if datos.get("garantia"):
        confianza.append(f"<strong>Garantía:</strong> {inline(datos['garantia'])}")
    if confianza:
        h.append('<p style="text-align:center;padding:8px;border:1px solid #ddd;border-radius:6px">'
                 + " · ".join(confianza) + "</p>")

    # 3. Problema (copy + dolores del cliente)
    problema = primer_texto(copy.get("problema"), respaldo.get("problema"))
    dolores = textos_lista(datos.get("dolores"))
    if problema or dolores:
        h.append("<h2>¿Te pasa esto?</h2>")
        if problema:
            h.append(bloque_html(problema))
        if dolores and not problema:
            h.append("<ul>" + "".join(f"<li>{inline(normalizar_frase(d))}</li>" for d in dolores) + "</ul>")

    # 4. Agitación
    agitacion = primer_texto(copy.get("agitacion"), respaldo.get("agitacion"))
    if agitacion:
        h.append(bloque_html(agitacion))

    # 5. Solución y mecanismo
    solucion = primer_texto(copy.get("solucion"), respaldo.get("solucion"))
    if solucion:
        h.append("<h2>La solución</h2>")
        h.append(bloque_html(solucion))

    # 6. Beneficios
    beneficios = primer_texto(copy.get("beneficios"), respaldo.get("beneficios"))
    if beneficios:
        h.append("<h2>Beneficios</h2>")
        h.append(bloque_html(beneficios))

    # 7. Cómo se usa
    uso = primer_texto(copy.get("uso"), respaldo.get("uso"))
    if uso:
        h.append("<h2>Cómo se usa</h2>")
        h.append(bloque_html(uso))

    # 8. Prueba social: siempre el marcador, nunca testimonios inventados.
    h.append("<h2>Lo que dicen nuestros clientes</h2>")
    h.append(f"<p>{MARCADOR_TESTIMONIO}</p>")

    # 9. Comparativa (solo si el brief trae datos)
    comparativa = primer_texto(copy.get("comparativa"), respaldo.get("comparativa"))
    if comparativa:
        h.append("<h2>Compáralo</h2>")
        h.append(bloque_html(comparativa))

    # 10. Oferta con combos y precio por unidad
    if ofertas:
        h.append("<h2>Elige tu oferta</h2>")
        filas = []
        for o in ofertas:
            nombre = nombre_variante(o["unidades"])
            texto = f"<strong>{nombre}:</strong> {pesos(o['precio'])}"
            if o["unidades"] > 1:
                texto += f" ({pesos(o['precio'] / o['unidades'])} por unidad)"
            filas.append(f"<li>{texto}</li>")
        h.append("<ul>" + "".join(filas) + "</ul>")
        if datos.get("bonus"):
            h.append(f"<p><strong>Bonus:</strong> {inline(str(datos['bonus']))}</p>")

    # 11. Garantía y retracto
    garantia = primer_texto(datos.get("garantia"), copy.get("garantia"))
    if garantia or pais == "CO":
        h.append("<h2>Garantía y devoluciones</h2>")
        if garantia:
            h.append(f"<p>{inline(garantia)}</p>")
        # El texto legal del retracto va una sola vez: si la garantía ya lo explica, no se repite.
        if pais == "CO" and "retracto" not in norm(garantia):
            h.append("<p>Tienes derecho de retracto: puedes devolver tu compra dentro de los 5 días hábiles "
                     "siguientes a la entrega (Ley 1480 de 2011, Estatuto del Consumidor).</p>")

    # 12. Preguntas frecuentes (objeciones con respuesta)
    objeciones = [o for o in leer_objeciones(datos.get("objeciones")) if o["respuesta"]]
    if objeciones:
        h.append("<h2>Preguntas frecuentes</h2>")
        for o in objeciones:
            h.append(f"<p><strong>{inline(o['objecion'])}</strong></p>")
            h.append(f"<p>{inline(o['respuesta'])}</p>")

    # 14. CTA final
    if cta:
        h.append(f'<p style="text-align:center"><strong>{inline(limpiar_md(cta))}</strong></p>')
    return "\n".join(x for x in h if x)


def nombre_variante(unidades):
    return "1 unidad" if unidades == 1 else f"{unidades} unidades"


def texto_plano_html(fragmento):
    return html.unescape(re.sub(r"<[^>]+>", "\n", fragmento))


# =====================================================================================
# PAQUETE PARA SHOPIFY
# =====================================================================================


def nombre_corto(nombre):
    """Si el nombre comercial es largo (> 40), se queda con la parte antes de ':' o ' - '."""
    nombre = re.sub(r"\s+", " ", str(nombre)).strip()
    if len(nombre) <= 40:
        return nombre
    return recortar(re.split(r"\s+[-–—|]\s+|[:|]", nombre)[0].strip(), 40)


def genericos(producto, nombre):
    """Genéricos cortos del producto, del más largo (5 palabras) al más corto, que no repitan el nombre."""
    vistos = []
    for n in range(5, 0, -1):
        g = generico_corto(producto, n)
        if g and g not in vistos and norm(g) not in norm(nombre):
            vistos.append(g)
    return vistos


def armar_titulo(nombre, producto):
    """'<nombre> · <genérico corto>' ≤ 70. Ej.: 'Alineo · Corrector de postura con sensor'."""
    corto = nombre_corto(nombre)
    for g in genericos(producto, corto):
        t = f"{corto} · {g}"
        if len(t) <= MAX_TITULO_SEO:
            return t, corto, g
    return recortar(corto, MAX_TITULO_SEO), corto, ""


def armar_seo_titulo(corto, producto, contra_entrega):
    """'<nombre>: <genérico> | Pago contra entrega' ≤ 70 (el sufijo solo si el JSON dice contra entrega)."""
    sufijo = " | Pago contra entrega" if contra_entrega else ""
    for g in genericos(producto, corto):
        t = f"{corto}: {g}{sufijo}"
        if len(t) <= MAX_TITULO_SEO:
            return t
    for t in (f"{corto}{sufijo}", corto):
        if len(t) <= MAX_TITULO_SEO:
            return t
    return recortar(corto, MAX_TITULO_SEO)


def armar_seo_descripcion(base, envio, pago):
    """Promesa + envío + pago, ≤ 160. Se recorta la promesa, nunca el dato de envío o pago."""
    extras = []
    primera = recortar(re.split(r"(?<=[.!?])\s", str(envio or "").strip())[0].rstrip("."), 70)
    if primera:
        if norm(primera).startswith("gratis"):
            extras.append(f"Envío {primera[0].lower()}{primera[1:]}.")
        else:
            extras.append(f"Envío: {primera}.")
    if "contra" in norm(pago or ""):
        extras.append("Pago contra entrega.")
    elif pago:
        extras.append(f"Pago: {recortar(pago, 40)}.")
    sufijo = " ".join(extras)
    if not sufijo:
        return recortar(base, MAX_DESCRIPCION_SEO)
    espacio = MAX_DESCRIPCION_SEO - len(sufijo) - 1
    cuerpo = recortar(base, max(espacio, 0)).rstrip(" .") if espacio > 20 else ""
    return (f"{cuerpo}. {sufijo}" if cuerpo else sufijo)[:MAX_DESCRIPCION_SEO]


def buscar_linea(seccion, *claves):
    """Valor de una línea 'Clave: valor' dentro de una sección."""
    for _, linea in (seccion or {}).get("lineas", []):
        s = limpiar_md(linea).lstrip("-• ").strip()
        if ":" in s:
            k, v = s.split(":", 1)
            if any(norm(c) in norm(k) for c in claves) and v.strip():
                return v.strip()
    return ""


def primera_frase(texto, maximo=220):
    plano = " ".join(limpiar_md(l).lstrip("-• ") for l in str(texto).splitlines() if l.strip())
    frase = re.split(r"(?<=[.!?])\s", plano, maxsplit=1)[0]
    return recortar(frase, maximo)


def armar_prompts(datos, secciones, pais):
    """4 prompts en inglés para las imágenes (estación 3)."""
    sec_producto = buscar_seccion(secciones, "producto")
    nombre_en = primer_texto(datos.get("nombre_ingles"), datos.get("nombre_en"),
                             buscar_linea(sec_producto, "ingles", "english"))
    objeto = f"a {nombre_en}" if nombre_en else f"the product described in Spanish as \"{datos.get('producto', '')}\""
    estilo = recortar(" ".join(limpiar_md(l).lstrip("-• ") for l in texto_de(buscar_seccion(secciones, "estilo")).splitlines() if l.strip()), 300)
    nota_estilo = f" Visual style from the brief (in Spanish): \"{estilo.rstrip('.')}.\"" if estilo else ""
    avatar = primera_frase(texto_de(buscar_seccion(secciones, "publico", "público", "avatar")))
    gentilicio = GENTILICIO_EN.get(pais, "Latin American")
    nota_avatar = f" Target customer (in Spanish): \"{avatar.rstrip('.')}.\"" if avatar else ""
    sin_texto = " No text, no letters, no logos, no badges, no watermarks."
    return [
        f"Professional e-commerce hero photo of {objeto}, centered on a pure white background, "
        f"soft studio lighting, sharp focus, true-to-life proportions and materials.{sin_texto}{nota_estilo}",
        f"Lifestyle photo of a {gentilicio} adult wearing or using {objeto} in a realistic everyday setting "
        f"in {'Colombia' if pais == 'CO' else 'Latin America'} (home or office desk), natural light, "
        f"authentic and unposed, product clearly visible.{nota_avatar}{sin_texto}{nota_estilo}",
        f"Clean benefits infographic layout for {objeto}: the product in the center with 3 or 4 simple line icons "
        f"around it representing its key features, light neutral background, generous white space. "
        f"Icons only, no written words, no numbers, no claims.{sin_texto}{nota_estilo}",
        f"Product bundle photo showing a set of 2 units and a set of 3 units of {objeto}, arranged side by side "
        f"on a white background, identical lighting, clearly countable units, no price tags.{sin_texto}{nota_estilo}",
    ]


def armar_payload(datos, secciones, copy, estructura, ofertas, pais, precios_anteriores, resumen_estudio, ruta_brief,
                  opciones=None):
    opciones = opciones or opciones_por_defecto()
    producto = str(datos.get("producto") or "").strip()
    nombre = str(datos.get("nombre_comercial") or producto).strip()
    categoria = primer_texto(datos.get("categoria"), buscar_linea(buscar_seccion(secciones, "producto"), "categoria"), producto)
    titulo, corto, generico = armar_titulo(nombre, producto)
    # SKU: RADAR-<NOMBRE en mayúsculas, sin tildes ni espacios, máx. 12>-<n>U
    codigo = re.sub(r"[^A-Z0-9]", "", norm(corto).upper())[:12] or "PRODUCTO"

    variantes = []
    for o in ofertas:
        v = {
            "optionValues": [{"optionName": "Oferta", "name": nombre_variante(o["unidades"])}],
            "price": str(int(round(o["precio"]))),
            "sku": f"RADAR-{codigo}-{o['unidades']}U",
        }
        if o["unidades"] in precios_anteriores:  # solo con precio anterior verificado
            v["compareAtPrice"] = str(int(round(precios_anteriores[o["unidades"]])))
        variantes.append(v)

    base_seo = primer_texto(datos.get("promesa"), limpiar_md(copy.get("subtitular", "")), nombre)
    pago = str(datos.get("pago") or "")
    contra_entrega = bool(opciones["pago_contra_entrega"]) and "contra" in norm(pago)
    descripcion_seo = armar_seo_descripcion(base_seo, datos.get("envio"), pago)
    titulo_seo = armar_seo_titulo(corto, producto, contra_entrega)

    discount, etiquetas_riesgo, advertencia, avisos_riesgo = decidir_riesgo(resumen_estudio, opciones["codigo_descuento"])
    coleccion_handle = slug(opciones["coleccion"], 60) or "radar"
    tags = []
    for t in [slug(opciones["etiqueta_prueba"], 40), coleccion_handle, slug_palabras(categoria, 4),
              slug_palabras(producto, 4)] + etiquetas_riesgo:
        if t and t not in tags:
            tags.append(t)

    payload = {
        "title": titulo,
        # handle: '<nombre> <genérico corto>' sin conectores -> 'alineo-corrector-postura-sensor'
        "handle": slug_palabras(f"{corto} {generico}", 10, quitar_conectores=True) or slug(titulo, 80),
        "productType": recortar(categoria[:1].upper() + categoria[1:], 255) if categoria else "",
        "vendor": str(opciones["vendedor"]).strip() or "Radar",
        "tags": tags,
        "status": "DRAFT",  # siempre borrador: publicar lo decide la persona
        "options": ["Oferta"],
        "variants": variantes,
        "descriptionHtml": armar_html(datos, copy, estructura, ofertas, pais),
        "seo": {"title": titulo_seo, "description": descripcion_seo},
        "collection": {"handle": coleccion_handle,
                       "title": str(opciones["coleccion"]).strip()[:1].upper() + str(opciones["coleccion"]).strip()[1:]},
        "discount": discount,
        "image_prompts": armar_prompts(datos, secciones, pais),
        "_origen": {
            "generado_por": "puente.py (radar-tienda, estación 2)",
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "brief": os.path.abspath(ruta_brief),
            "pago_contra_entrega": contra_entrega,
        },
    }
    if advertencia:
        payload["advertencia"] = advertencia
    if resumen_estudio is not None:
        payload["resumen_estudio"] = resumen_estudio
    payload["_avisos_riesgo"] = avisos_riesgo
    return payload


# =====================================================================================
# OPCIONES (configuración del usuario)
# =====================================================================================


def opciones_por_defecto():
    base = entorno.DEFAULTS if entorno else {
        "pais": "CO", "coleccion": "radar", "vendedor": "Radar", "etiqueta_prueba": "radar-prueba",
        "codigo_descuento": "", "pago_contra_entrega": False}
    return {k: base[k] for k in ("coleccion", "vendedor", "etiqueta_prueba", "codigo_descuento", "pago_contra_entrega")}


def leer_opciones(args):
    """CLI > config.json > valores por defecto. Nunca falla por la configuración (fail-open)."""
    opciones = opciones_por_defecto()
    origen = "valores por defecto"
    if entorno:
        try:
            cfg = entorno.leer_config(args.config) if args.config else entorno.leer_config()
            for k in opciones:
                if k in cfg:
                    opciones[k] = cfg[k]
            origen = cfg.get("_origen", origen)
        except Exception as e:  # pragma: no cover
            origen = f"valores por defecto (no se pudo leer la configuración: {e})"
    for k, attr in (("vendedor", "vendedor"), ("etiqueta_prueba", "etiqueta_prueba"),
                    ("coleccion", "coleccion"), ("codigo_descuento", "codigo_descuento")):
        v = getattr(args, attr, None)
        if v is not None:
            opciones[k] = v
    if args.pago_contra_entrega is not None:
        opciones["pago_contra_entrega"] = str(args.pago_contra_entrega).strip().lower() in (
            "si", "sí", "true", "1", "yes", "s")
    elif not isinstance(opciones["pago_contra_entrega"], bool):
        opciones["pago_contra_entrega"] = str(opciones["pago_contra_entrega"]).strip().lower() in (
            "si", "sí", "true", "1", "yes", "s")
    return opciones, origen


# =====================================================================================
# CSV DE IMPORTACIÓN DE SHOPIFY
# =====================================================================================

# Columnas del formato actual de importación de productos de Shopify (verificado el 2026-10-16 en
# https://help.shopify.com/en/manual/products/import-export/using-csv). Para productos nuevos solo
# "Title" es obligatoria; con variantes hace falta "URL handle". Las filas de variante repiten el
# handle y dejan en blanco Title, Description, Vendor y Tags. "Status" con valor draft = borrador.
CSV_COLUMNAS = ["Title", "URL handle", "Description", "Vendor", "Type", "Tags", "Published on online store",
                "Status", "SKU", "Option1 name", "Option1 value", "Price", "Compare-at price",
                "Requires shipping", "Product image URL", "Image position", "Image alt text",
                "SEO title", "SEO description"]


def filas_csv(payload, imagenes=()):
    """Filas del CSV: una por variante (la primera con todos los datos) + filas extra para imágenes."""
    filas = []
    alt = payload["title"]
    for i, v in enumerate(payload["variants"]):
        f = {c: "" for c in CSV_COLUMNAS}
        f["URL handle"] = payload["handle"]
        f["SKU"] = v.get("sku", "")
        f["Option1 name"] = "Oferta"
        f["Option1 value"] = v["optionValues"][0]["name"]
        f["Price"] = v["price"]
        f["Compare-at price"] = v.get("compareAtPrice", "")
        f["Requires shipping"] = "TRUE"
        if i == 0:
            f.update({
                "Title": payload["title"], "Description": payload["descriptionHtml"],
                "Vendor": payload["vendor"], "Type": payload["productType"],
                "Tags": ", ".join(payload["tags"]), "Published on online store": "FALSE",
                "Status": "draft", "SEO title": payload["seo"]["title"],
                "SEO description": payload["seo"]["description"],
            })
        filas.append(f)
    for n, url in enumerate(imagenes, start=1):
        if n <= len(filas):
            destino = filas[n - 1]
        else:
            destino = {c: "" for c in CSV_COLUMNAS}
            destino["URL handle"] = payload["handle"]
            filas.append(destino)
        destino["Product image URL"] = url
        destino["Image position"] = str(n)
        destino["Image alt text"] = f"{alt} · imagen {n}"
    # Shopify pide un valor en Status si la columna existe: las filas de variante repiten "draft".
    for f in filas[1:]:
        f["Status"] = "draft"
    return filas


def escribir_csv(ruta, payload, imagenes=()):
    with open(ruta, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNAS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for f in filas_csv(payload, imagenes):
            w.writerow(f)


# =====================================================================================
# REPORTE
# =====================================================================================


def escribir_validacion(ruta, ruta_brief, ruta_estudio, errores, avisos, payload, archivo_payload, nota_anterior,
                        lista_marcadores=(), origen_opciones="", archivo_csv=None):
    aprobado = not errores
    l = [f"# Validación del puente · {datetime.now().strftime('%Y-%m-%d %H:%M')}", "",
         f"- Brief: `{os.path.abspath(ruta_brief)}`"]
    if ruta_estudio:
        l.append(f"- Estudio: `{os.path.abspath(ruta_estudio)}`")
    if origen_opciones:
        l.append(f"- Configuración usada: {origen_opciones}")
    l += [f"- Resultado: **{'APROBADO' if aprobado else 'RECHAZADO'}** "
          f"({len(errores)} errores, {len(avisos)} avisos)", ""]
    if payload and payload.get("advertencia"):
        l += [f"> **ADVERTENCIA:** {payload['advertencia']}", ""]
    l += ["## Errores (bloquean)", ""]
    l += [f"- {e}" for e in errores] or ["- Ninguno."]
    l += ["", "## Avisos (no bloquean)", ""]
    l += [f"- {a}" for a in avisos] or ["- Ninguno."]
    l += ["", "## Datos por confirmar en el brief", ""]
    l += [f"- {d}: {m}" for d, m in lista_marcadores] or ["- Ninguno."]
    if lista_marcadores:
        l.append("- Ninguno de estos datos se publica: se quitaron de la página, del título y del SEO.")
    l += ["", "## Qué se generó", ""]
    if aprobado and payload:
        l.append(f"- `{archivo_payload}`")
        if archivo_csv:
            l.append(f"- `{archivo_csv}` (importación en Shopify: Productos → Importar)")
        l.append(f"- Título: {payload['title']} · handle `{payload['handle']}` · estado {payload['status']}")
        l.append(f"- Vendedor: {payload['vendor']} · etiquetas: {', '.join(payload['tags'])}")
        for v in payload["variants"]:
            extra = f" (antes {pesos(float(v['compareAtPrice']))}, verificado)" if "compareAtPrice" in v else ""
            l.append(f"- Variante «{v['optionValues'][0]['name']}»: {pesos(float(v['price']))}{extra} · SKU `{v['sku']}`")
        l.append(f"- SEO: título {len(payload['seo']['title'])} car. · descripción {len(payload['seo']['description'])} car.")
        l.append(f"- Página de venta: {len(payload['descriptionHtml'])} caracteres de HTML")
        l.append(f"- Prompts de imagen: {len(payload['image_prompts'])}")
        if payload.get("discount"):
            l.append(f"- Descuento propuesto: {payload['discount']['code']} ({payload['discount']['percentage']} %, "
                     f"desde {payload['discount']['minimumQuantity']} unidades)")
        else:
            l.append("- Descuento: ninguno (decisión del puente, ver avisos).")
        if "resumen_estudio" in payload:
            l += ["", "## Resumen del estudio", ""]
            l += [f"- {k}: {v}" for k, v in payload["resumen_estudio"].items()] or ["- (vacío)"]
    else:
        l.append("- Nada: con errores no se escribe `shopify_payload.json` ni el CSV (para que la tienda no use datos malos).")
    if nota_anterior:
        l += ["", f"Nota: {nota_anterior}"]
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(l) + "\n")


# =====================================================================================
# MODO ANUNCIO (--anuncio): el copy del anuncio pasa por los mismos filtros
# =====================================================================================


def validar_anuncio(texto):
    """Errores y avisos del anuncio. Ignora la sección de frases prohibidas (habla de lo prohibido, no lo afirma)."""
    errores, avisos = [], []
    ignorar = False
    nivel_ignorado = 0
    dentro_codigo = False
    for n, linea in enumerate(texto.splitlines(), start=1):
        if linea.strip().startswith("```"):
            dentro_codigo = not dentro_codigo
        m = None if dentro_codigo else re.match(r"^(#{1,6})\s+(.*)$", linea)
        if m:
            nivel = len(m.group(1))
            titulo = norm(limpiar_md(m.group(2)))
            if ignorar and nivel <= nivel_ignorado:
                ignorar = False
            if "prohibid" in titulo or "a evitar" in titulo or titulo.startswith("evitar") or "no usar" in titulo:
                ignorar, nivel_ignorado = True, nivel
            continue
        if ignorar or not linea.strip() or es_metatexto(linea):
            continue
        extracto = recortar(linea.strip(), 90)
        for claim, tipo in buscar_claims_con_tipo(linea):
            errores.append(f"Claim {tipo} prohibido «{claim}» en línea {n}: «{extracto}»")
        motivo = buscar_testimonios(linea)
        if motivo:
            errores.append(f"Testimonio o reseña sin marcar ({motivo}) en línea {n}: «{extracto}»")
        for marca in marcadores(linea):
            errores.append(f"Dato por confirmar {marca} en línea {n}: no se publica un anuncio con datos sin confirmar.")
        for tipo in buscar_descuentos(linea):
            avisos.append(f"Descuento en el anuncio ({tipo}) en línea {n}: confirma que el descuento existe de verdad.")
    return errores, avisos


def modo_anuncio(ruta, salida):
    try:
        texto = leer_archivo(ruta)
    except (OSError, UnicodeDecodeError) as e:
        print(f"ERROR: no se pudo leer el anuncio «{ruta}»: {e}")
        return 2
    errores, avisos = validar_anuncio(texto)
    carpeta = salida or os.path.dirname(os.path.abspath(ruta))
    os.makedirs(carpeta, exist_ok=True)
    reporte = os.path.join(carpeta, "validacion-anuncio.md")
    l = [f"# Validación del anuncio · {datetime.now().strftime('%Y-%m-%d %H:%M')}", "",
         f"- Anuncio: `{os.path.abspath(ruta)}`",
         f"- Resultado: **{'APROBADO' if not errores else 'RECHAZADO'}** ({len(errores)} errores, {len(avisos)} avisos)",
         "", "## Errores (bloquean)", ""] + ([f"- {e}" for e in errores] or ["- Ninguno."]) + \
        ["", "## Avisos", ""] + ([f"- {a}" for a in avisos] or ["- Ninguno."])
    with open(reporte, "w", encoding="utf-8") as f:
        f.write("\n".join(l) + "\n")
    print(f"ANUNCIO · {'APROBADO' if not errores else 'RECHAZADO'} · {len(errores)} errores · {len(avisos)} avisos")
    for e in errores:
        print(f"  [ERROR] {e}")
    for a in avisos:
        print(f"  [aviso] {a}")
    print(f"  Reporte: {reporte}")
    return 1 if errores else 0


# =====================================================================================
# MODO RESUMEN (--resumen): tabla para comparar varios estudios
# =====================================================================================

ORDEN_VEREDICTO = {"probar": 0, "desconocido": 1, "precaucion": 2, "no-recomendado": 3}


def nivel_confianza(texto):
    t = norm(texto or "")
    if "media-alta" in t or "media alta" in t:
        return 2
    if "alta" in t:
        return 3
    if "media-baja" in t or "media baja" in t:
        return 0.5
    if "media" in t:
        return 1
    return 0


def resumir_estudios(rutas):
    filas, problemas = [], []
    for ruta in rutas:
        try:
            resumen, aviso = leer_estudio(leer_archivo(ruta))
        except (OSError, UnicodeDecodeError) as e:
            problemas.append(f"no se pudo leer «{ruta}»: {e}")
            continue
        anuncios = resumen.get("anuncios_activos", "")
        m = re.search(r"(\d[\d.]*)\s+anunciantes", norm(anuncios))
        titulo = ""
        try:
            primera = leer_archivo(ruta).splitlines()[0]
            titulo = re.sub(r"^#\s*(estudio de producto\s*:?\s*)?", "", primera, flags=re.I).strip()
        except Exception:
            pass
        clase = clase_veredicto(resumen.get("veredicto"))
        fila = {
            "estudio": os.path.abspath(ruta),
            "producto": titulo,
            "veredicto": resumen.get("veredicto", "no verificable"),
            "clase": clase,
            "confianza": resumen.get("confianza", "no verificable"),
            "margen": resumen.get("margen", "no verificable"),
            "margen_pct": margen_porcentaje(resumen.get("margen")),
            "cpa_equilibrio": resumen.get("cpa_equilibrio", "no verificable"),
            "anuncios": anuncios or "no verificable",
            "anunciantes": int(m.group(1).replace(".", "")) if m else None,
            "precio": resumen.get("precio_recomendado", "no verificable"),
            "aviso": aviso,
        }
        filas.append(fila)
    # Orden determinista: veredicto (probar primero) → confianza → margen.
    filas.sort(key=lambda f: (ORDEN_VEREDICTO.get(f["clase"], 1), -nivel_confianza(f["confianza"]),
                              -(f["margen_pct"] if f["margen_pct"] is not None else -999)))
    ganador = filas[0] if filas and filas[0]["clase"] != "no-recomendado" else None
    return {"filas": filas, "recomendado": ganador["producto"] if ganador else None,
            "regla": "veredicto (PROBAR > sin dato > PRECAUCIÓN > NO RECOMENDABLE), luego confianza, luego margen",
            "problemas": problemas}


# =====================================================================================
# PROGRAMA PRINCIPAL
# =====================================================================================


def leer_archivo(ruta):
    with open(ruta, "r", encoding="utf-8-sig") as f:
        return f.read()


def main(argv=None):
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="Valida el brief del Radar y genera el paquete para Shopify.")
    ap.add_argument("brief", nargs="?", help="Ruta del brief-landing-<producto>.md")
    ap.add_argument("--estudio", help="Ruta del estudio-<producto>-<fecha>.md (decide descuento y etiquetas)")
    ap.add_argument("--salida", help="Carpeta donde se escriben los resultados")
    ap.add_argument("--anuncio", help="Valida un anuncio-meta.md con los mismos filtros")
    ap.add_argument("--resumen", nargs="+", help="Resume y ordena varios estudios (para comparar)")
    ap.add_argument("--vendedor")
    ap.add_argument("--etiqueta-prueba", dest="etiqueta_prueba")
    ap.add_argument("--coleccion")
    ap.add_argument("--codigo-descuento", dest="codigo_descuento")
    ap.add_argument("--pago-contra-entrega", dest="pago_contra_entrega", help="si | no")
    ap.add_argument("--imagen", action="append", default=[], help="URL https de una imagen para el CSV (repetible)")
    ap.add_argument("--config", help="Ruta de un config.json distinto de ~/.radar-tienda/config.json")
    args = ap.parse_args(argv)

    if args.anuncio:
        return modo_anuncio(args.anuncio, args.salida)
    if args.resumen:
        r = resumir_estudios(args.resumen)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["filas"] else 2
    if not args.brief or not args.salida:
        print("ERROR: falta el brief o --salida. Uso: puente.py \"<brief.md>\" --estudio \"<estudio.md>\" --salida \"<carpeta>\"")
        return 2

    opciones, origen_opciones = leer_opciones(args)
    imagenes = [u for u in args.imagen if re.match(r"^https://\S+$", u or "")]

    # --- Leer entradas ---
    try:
        texto = leer_archivo(args.brief)
    except (OSError, UnicodeDecodeError) as e:
        print(f"ERROR: no se pudo leer el brief «{args.brief}»: {e}")
        return 2
    resumen_estudio, aviso_estudio = None, None
    if args.estudio:
        try:
            resumen_estudio, aviso_estudio = leer_estudio(leer_archivo(args.estudio))
        except (OSError, UnicodeDecodeError) as e:
            print(f"ERROR: no se pudo leer el estudio «{args.estudio}»: {e}")
            return 2

    os.makedirs(args.salida, exist_ok=True)
    ruta_payload = os.path.join(args.salida, "shopify_payload.json")
    ruta_csv = os.path.join(args.salida, "shopify_import.csv")
    ruta_validacion = os.path.join(args.salida, "validacion.md")

    # --- Datos por confirmar en todo el brief (aviso con la lista) ---
    lista_marcadores = []
    for n, linea in enumerate(texto.splitlines(), start=1):
        for marca in marcadores(linea):
            lista_marcadores.append((f"línea {n}", f"{marca} · «{recortar(limpiar_md(linea.strip()), 80)}»"))
    temas = temas_marcados(texto)

    # --- Extraer y validar ---
    secciones = partir_secciones(texto)
    datos, j_ini, j_fin, error_json = extraer_json(texto)
    avisos = [aviso_estudio] if aviso_estudio else []
    if lista_marcadores:
        avisos.append(f"El brief trae {len(lista_marcadores)} datos por confirmar (lista abajo): no se publican.")
    payload = None
    if datos is None:
        errores = [f"Bloque JSON: {error_json}."]
    else:
        errores, avisos_v, ofertas, pais, precios_anteriores = validar(datos, texto, secciones, j_ini, j_fin)
        avisos += avisos_v
        copy = leer_copy_base(buscar_seccion(secciones, "copy"))
        estructura = leer_estructura(buscar_seccion(secciones, "estructura"))
        # Saneo: lo que está por confirmar o depende de la configuración no llega a lo publicable.
        reglas = reglas_publicables(temas, opciones["pago_contra_entrega"])
        datos_pub, copy_pub, estructura_pub, quitados = sanear_datos(datos, copy, estructura, reglas)
        vistos = set()
        for motivo, frag in quitados:
            clave = (motivo, frag)
            if clave in vistos:
                continue
            vistos.add(clave)
            avisos.append(f"No se publica ({motivo}): «{recortar(frag, 90)}»")
        if not opciones["pago_contra_entrega"] and RE_CONTRA_ENTREGA.search(json.dumps(datos, ensure_ascii=False)):
            avisos.append("El brief promete pago contra entrega pero la configuración dice que la tienda no lo tiene: "
                          "se quitó de la página, del título y del SEO.")
        payload = armar_payload(datos_pub, secciones, copy_pub, estructura_pub, ofertas, pais,
                                precios_anteriores, resumen_estudio, args.brief, opciones)
        avisos += payload.pop("_avisos_riesgo", [])
        # Red de seguridad: el HTML final se escanea sin excepciones de meta-texto.
        ya = " ".join(errores)
        for linea in texto_plano_html(payload["descriptionHtml"]).splitlines():
            if not linea.strip():
                continue
            for claim, tipo in buscar_claims_con_tipo(linea):
                if f"«{claim}»" not in ya:
                    errores.append(f"El HTML generado contiene el claim {tipo} «{claim}»: «{recortar(linea, 90)}»")
            motivo = buscar_testimonios(linea)
            if motivo and "Testimonio" not in ya:
                errores.append(f"El HTML generado contiene un testimonio sin marcar ({motivo}): «{recortar(linea, 90)}»")
        # Nada por confirmar llega a la página, al título ni al SEO.
        publicables = [("a la página", "La página", texto_plano_html(payload["descriptionHtml"])),
                       ("al título", "El título", payload["title"]),
                       ("al título SEO", "El título SEO", payload["seo"]["title"]),
                       ("a la descripción SEO", "La descripción SEO", payload["seo"]["description"])]
        for donde, nombre_campo, contenido in publicables:
            # También vale un marcador cortado por el recorte del título ("[CONFIRMAR nombre con el").
            sin_testimonio = str(contenido).replace(MARCADOR_TESTIMONIO, "")
            for m in re.finditer(r"\[[^\]\[]*?\b(?:confirmar|pendiente)\b[^\]\[]*\]?", sin_testimonio, re.I):
                errores.append(f"Un dato por confirmar llegó {donde}: {m.group(0)}. Confírmalo o quítalo del brief.")
            if not opciones["pago_contra_entrega"] and RE_CONTRA_ENTREGA.search(norm(contenido)):
                errores.append(f"{nombre_campo} promete pago contra entrega y la configuración dice que no está activo.")
        if not payload["variants"] and not any("oferta" in e.lower() for e in errores):
            errores.append("No quedó ninguna variante válida.")
        for campo in ("title", "handle"):
            if not payload[campo]:
                errores.append(f"El paquete quedó sin «{campo}».")

    # --- Escribir resultados ---
    nota_anterior = None
    if errores:
        for ruta_vieja, nombre in ((ruta_payload, "shopify_payload"), (ruta_csv, "shopify_import")):
            if os.path.exists(ruta_vieja):
                # No se borra: se renombra para que la tienda no tome un paquete viejo.
                ext = os.path.splitext(ruta_vieja)[1]
                renombrado = os.path.join(args.salida, f"{nombre}.anterior-{datetime.now():%Y%m%d-%H%M%S}{ext}")
                os.replace(ruta_vieja, renombrado)
                nota_anterior = (nota_anterior or "") + f"había un paquete anterior; se renombró a `{renombrado}`. "
    else:
        with open(ruta_payload, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        escribir_csv(ruta_csv, payload, imagenes)
    escribir_validacion(ruta_validacion, args.brief, args.estudio, errores, avisos,
                        payload if not errores else None, ruta_payload, nota_anterior,
                        lista_marcadores, origen_opciones, ruta_csv if not errores else None)

    # --- Resumen en consola ---
    print(f"PUENTE · {'APROBADO' if not errores else 'RECHAZADO'} · {len(errores)} errores · {len(avisos)} avisos")
    for e in errores:
        print(f"  [ERROR] {e}")
    for a in avisos:
        print(f"  [aviso] {a}")
    if not errores:
        if payload.get("advertencia"):
            print(f"  [ADVERTENCIA] {payload['advertencia']}")
        print(f"  Paquete: {ruta_payload}")
        print(f"  CSV de importación: {ruta_csv}")
        print(f"  Producto: {payload['title']} · {len(payload['variants'])} variantes · estado {payload['status']}"
              f" · descuento {payload['discount']['code'] if payload.get('discount') else 'ninguno'}")
    print(f"  Reporte: {ruta_validacion}")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
