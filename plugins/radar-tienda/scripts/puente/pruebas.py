# -*- coding: utf-8 -*-
"""
pruebas.py · Pruebas del puente (estación 2 del plugin radar-tienda).
Uso:  <python> "<plugin>/scripts/puente/pruebas.py"     (<python> = py, python3 o python)

Todo corre en carpetas temporales con espacios en el nombre: no escribe nada dentro del plugin
ni en la configuración real del usuario (usa RADAR_TIENDA_CONFIG_DIR apuntando a una carpeta vacía).

1. Brief bueno, brief malo y brief real (Alineo).
2. Filtro de promesas: las 15 frases que antes pasaban + frases permitidas (falsos positivos).
3. Datos por confirmar, pago contra entrega según la configuración, retracto sin duplicar.
4. El puente decide: margen, veredicto NO RECOMENDABLE y PRECAUCIÓN, código de descuento.
5. Anuncio (--anuncio), CSV de importación de Shopify, resumen para comparar (--resumen).
6. Entradas raras (sin JSON, moneda equivocada, precio 0, archivo inexistente, etc.).
"""

import csv
import json
import os
import re
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
PUENTE = os.path.join(AQUI, "puente.py")
EJEMPLOS = os.path.join(AQUI, "ejemplos")
BUENO = os.path.join(EJEMPLOS, "brief-bueno.md")
MALO = os.path.join(EJEMPLOS, "brief-malo.md")
REAL = os.path.join(EJEMPLOS, "brief-real-alineo.md")
ESTUDIO = os.path.join(EJEMPLOS, "estudio-ejemplo.md")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

resultados = []  # (nombre, pasó, detalle)
RAIZ_TMP = tempfile.mkdtemp(prefix="radar tienda pruebas puente ")
CFG_VACIA = os.path.join(RAIZ_TMP, "config vacia")
os.makedirs(CFG_VACIA, exist_ok=True)
os.environ["RADAR_TIENDA_CONFIG_DIR"] = CFG_VACIA  # también para el import directo de abajo


def tmp(nombre):
    ruta = os.path.join(RAIZ_TMP, nombre)
    os.makedirs(ruta, exist_ok=True)
    return ruta


def correr(*args):
    cmd = [sys.executable, PUENTE] + [str(a) for a in args]
    entorno_proc = dict(os.environ, PYTHONIOENCODING="utf-8", RADAR_TIENDA_CONFIG_DIR=CFG_VACIA)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=entorno_proc)
    return p.returncode, p.stdout + p.stderr


def leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def escribir(ruta, texto):
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    return ruta


def chequear(nombre, condicion, detalle=""):
    resultados.append((nombre, bool(condicion), detalle))


def brief_con_json(texto_base, cambios=None, quitar=(), json_crudo=None, extra_copy=""):
    """Copia del brief bueno con el bloque JSON modificado (y, opcional, un bloque de copy extra)."""
    m = re.search(r"```json\s*\n(.*?)```", texto_base, re.S)
    datos = json.loads(m.group(1))
    for k in quitar:
        datos.pop(k, None)
    datos.update(cambios or {})
    nuevo = json_crudo if json_crudo is not None else json.dumps(datos, ensure_ascii=False)
    texto = texto_base[:m.start(1)] + nuevo + "\n" + texto_base[m.end(1):]
    if extra_copy:
        texto = texto.replace("### CTA", extra_copy + "\n\n### CTA", 1)
    return texto


def estudio(veredicto, margen, confianza="Media", anunciantes=9, titulo="producto de prueba"):
    return (f"# Estudio de producto: {titulo} · Colombia · 2026-10-16\n\n## 0. Veredicto en 30 segundos\n| | |\n|---|---|\n"
            f"| Veredicto | {veredicto} |\n| Confianza de la evidencia | {confianza} |\n"
            f"| Precio recomendado | $89.900 (1 und) |\n| CPA de equilibrio | $31.000 |\n"
            f"| Margen por pedido entregado | {margen} (escenario base) |\n"
            f"| Anuncios activos en Meta | ~300 coincidencias · {anunciantes} anunciantes |\n| Saturación | Media |\n")


base = leer(BUENO)

# ---------------------------------------------------------------- 1. Brief bueno
salida_bueno = tmp("salida bueno")
rc, out = correr(BUENO, "--salida", salida_bueno, "--estudio", ESTUDIO, "--pago-contra-entrega", "si")
print("=== Brief bueno ===\n" + out)
chequear("bueno: código 0", rc == 0, f"código {rc}")
ruta_payload = os.path.join(salida_bueno, "shopify_payload.json")
chequear("bueno: existe shopify_payload.json", os.path.exists(ruta_payload))
p = json.loads(leer(ruta_payload)) if os.path.exists(ruta_payload) else {}
if p:
    claves = ["title", "handle", "productType", "vendor", "tags", "status", "options", "variants",
              "descriptionHtml", "seo", "collection", "image_prompts", "resumen_estudio"]
    faltan = [c for c in claves if c not in p or p[c] in ("", [], {}, None)]
    chequear("bueno: paquete con todas las claves llenas", not faltan, f"faltan {faltan}")
    chequear("bueno: estado DRAFT y vendedor por defecto «Radar»", p["status"] == "DRAFT" and p["vendor"] == "Radar", p["vendor"])
    chequear("bueno: handle ascii", re.fullmatch(r"[a-z0-9-]+", p["handle"]) is not None, p["handle"])
    chequear("bueno: etiquetas de prueba de la configuración", p["tags"][:2] == ["radar-prueba", "radar"], p["tags"])
    chequear("bueno: colección por handle, sin ID fijo", p["collection"] == {"handle": "radar", "title": "Radar"}, p["collection"])
    nombres = [v["optionValues"][0]["name"] for v in p["variants"]]
    chequear("bueno: 3 variantes 1/2/3", nombres == ["1 unidad", "2 unidades", "3 unidades"], nombres)
    precios = [v["price"] for v in p["variants"]]
    chequear("bueno: precios como texto sin decimales", precios == ["89900", "159900", "209900"], precios)
    skus = [v["sku"] for v in p["variants"]]
    chequear("bueno: SKU RADAR-<NOMBRE máx 12>-<n>U", skus == ["RADAR-POSTURAGUARD-1U", "RADAR-POSTURAGUARD-2U", "RADAR-POSTURAGUARD-3U"], skus)
    chequear("bueno: título nombre · genérico", p["title"] == "PosturaGuard Sensor · Corrector de postura con sensor", p["title"])
    chequear("bueno: sin compareAtPrice (no hay precio anterior)", all("compareAtPrice" not in v for v in p["variants"]))
    chequear("bueno: SEO dentro de límites", len(p["seo"]["title"]) <= 70 and len(p["seo"]["description"]) <= 160,
             f"{len(p['seo']['title'])}/{len(p['seo']['description'])}")
    html_ = p["descriptionHtml"]
    chequear("bueno: HTML con marcador de testimonio", "[TESTIMONIO REAL PENDIENTE]" in html_)
    chequear("bueno: HTML con retracto Ley 1480 (una sola vez)", html_.count("Ley 1480") == 1 and "5 días hábiles" in html_)
    chequear("bueno: HTML sin scripts ni hojas externas", not re.search(r"<script|<link|<iframe|<style", html_, re.I))
    orden = ["<h2>Siéntate", "Envío:", "¿Te pasa esto?", "La solución", "Beneficios", "Cómo se usa",
             "Lo que dicen", "Compáralo", "Elige tu oferta", "Garantía y devoluciones", "Preguntas frecuentes"]
    posiciones = [html_.find(x) for x in orden]
    chequear("bueno: secciones en el orden del SKILL", -1 not in posiciones and posiciones == sorted(posiciones), posiciones)
    chequear("bueno: oferta con precio por unidad", "$79.950 por unidad" in html_)
    chequear("bueno: 4 prompts de imagen", len(p["image_prompts"]) == 4)
    chequear("bueno: margen 22 % < 25 % -> sin descuento (lo decide el puente)", p["discount"] is None, p.get("discount"))
    chequear("bueno: margen bajo -> etiqueta precaucion", "precaucion" in p["tags"], p["tags"])
    chequear("bueno: resumen del estudio con veredicto", "PROBAR" in p.get("resumen_estudio", {}).get("veredicto", ""))
    chequear("bueno: 'postura más sana' (adjetivo) no se bloqueó", "postura más sana" in html_)
    chequear("bueno: 'te ves encorvado en las fotos' es copy, no instrucción", "en las fotos y en las videollamadas" in html_)
    chequear("bueno: con contra entrega activo, el SEO lo dice", "contra entrega" in p["seo"]["title"].lower(), p["seo"]["title"])

# ---------------------------------------------------------------- 2. Brief malo
salida_malo = tmp("salida malo")
rc, out = correr(MALO, "--salida", salida_malo)
print("=== Brief malo ===\n" + out)
chequear("malo: código 1", rc == 1, f"código {rc}")
chequear("malo: detecta claim médico", "Claim médico prohibido «elimina el dolor»" in out)
chequear("malo: detecta combos mal escalonados", "Combos mal escalonados" in out)
chequear("malo: detecta testimonio inventado", "Testimonio o reseña sin marcar" in out and "Carolina" in out)
chequear("malo: no escribe shopify_payload.json ni CSV",
         not os.path.exists(os.path.join(salida_malo, "shopify_payload.json"))
         and not os.path.exists(os.path.join(salida_malo, "shopify_import.csv")))
chequear("malo: escribe validacion.md con RECHAZADO", "RECHAZADO" in leer(os.path.join(salida_malo, "validacion.md")))
chequear("malo: «quita la migraña» de la lista a evitar NO cuenta", "quita la migraña" not in out)
chequear("malo: la nota del encabezado («trae un claim médico») no es un falso positivo", "trae un claim" not in out, out)

# ---------------------------------------------------------------- 3. Brief real (corrida 2026-10-16, Alineo)
salida_real = tmp("salida real")
rc, out = correr(REAL, "--salida", salida_real, "--pago-contra-entrega", "si")
print("=== Brief real (Alineo, contra entrega activo) ===\n" + out)
chequear("real: código 0", rc == 0, f"código {rc}")
pr = json.loads(leer(os.path.join(salida_real, "shopify_payload.json"))) if rc == 0 else {}
if pr:
    hr = pr["descriptionHtml"]
    chequear("real 1: title = nombre · genérico corto (≤ 70)",
             pr["title"] == "Alineo · Corrector de postura con sensor" and len(pr["title"]) <= 70, pr["title"])
    chequear("real 2: seo.title = nombre: genérico | Pago contra entrega (≤ 70)",
             pr["seo"]["title"] == "Alineo: Corrector de postura con sensor | Pago contra entrega"
             and len(pr["seo"]["title"]) <= 70, pr["seo"]["title"])
    d = pr["seo"]["description"]
    chequear("real 2: seo.description ≤ 160 con envío y contra entrega",
             len(d) <= 160 and "Envío gratis" in d and "contra entrega" in d, f"{len(d)}: {d}")
    chequear("real 3: handle = slug nombre + genérico", pr["handle"] == "alineo-corrector-postura-sensor", pr["handle"])
    skus = [v["sku"] for v in pr["variants"]]
    chequear("real 4: SKU RADAR-ALINEO-<n>U", skus == ["RADAR-ALINEO-1U", "RADAR-ALINEO-2U", "RADAR-ALINEO-3U"], skus)
    cat = [t for t in pr["tags"] if t not in ("radar-prueba", "radar")]
    conectores = {"de", "del", "con", "para", "y", "en", "a", "la", "el", "sin", "por"}
    chequear("real 5: etiquetas por palabras completas, ≤ 4 palabras, sin preposición final",
             cat and all(len(t.split("-")) <= 4 and t.split("-")[-1] not in conectores for t in cat), pr["tags"])
    chequear("real 6: no se cuela la instrucción «sin tecnicismos médicos»",
             "tecnicismos" not in hr and "promesas de dolor" not in hr)
    chequear("real 6b: no se cuela «pasos visuales»", "pasos visuales" not in hr)
    parrafos = re.findall(r"<(?:p|li)>(.*?)</(?:p|li)>", hr)
    problema = hr.split("¿Te pasa esto?</h2>")[1].split("<h2>")[0]
    frases = re.findall(r"<(?:p|li)>(.*?)</(?:p|li)>", problema)
    chequear("real 7: dolores con mayúscula inicial y punto final",
             frases and all(f[0].isupper() and f.endswith(".") for f in frases), frases)
    chequear("real 7: ningún párrafo termina en «;»", not any(x.rstrip().endswith(";") for x in parrafos))
    chequear("real: titular sin comillas «»", "<h2>Te encorvas y ni cuenta te das. Alineo sí.</h2>" in hr)
    chequear("real: copy legítimo intacto (beneficios y FAQ)",
             "Vibra suavemente cuando te encorvas." in hr and "¿Es seguro pagar contra entrega?" in hr)
    chequear("real: aviso legal permitido intacto («no reemplaza la consulta con un profesional»)",
             "reemplaza la consulta con un profesional" in hr)
    # Datos por confirmar
    chequear("confirmar: ningún [CONFIRMAR…] llega al HTML, título o SEO",
             "CONFIRMAR" not in hr.upper() and "CONFIRMAR" not in pr["title"].upper()
             and "CONFIRMAR" not in json.dumps(pr["seo"]).upper())
    chequear("confirmar: los días de entrega por confirmar no se publican (ni del JSON)",
             "3 a 5 días" not in hr and "3 a 5 días" not in d, d)
    chequear("confirmar: «manual en la caja» por confirmar no se publica", "manual" not in hr.lower())
    chequear("confirmar: el retracto («5 días hábiles») sí se publica", "5 días hábiles de retracto" in hr)
    val_real = leer(os.path.join(salida_real, "validacion.md"))
    chequear("confirmar: validacion.md trae la lista de datos por confirmar",
             "## Datos por confirmar en el brief" in val_real and val_real.count("[CONFIRMAR") >= 5)
    chequear("confirmar: la frase recortada se cierra con punto",
             "Se regula ajustando el tirante y encendiéndolo con la espalda recta.</p>" in hr)
    garantia = hr.split("Garantía y devoluciones</h2>")[1].split("<h2>")[0]
    chequear("retracto: no se duplica cuando la garantía ya lo trae", garantia.lower().count("retracto") == 1, garantia)

# Contra entrega desactivado en la configuración
salida_sin_ce = tmp("salida real sin contra entrega")
rc, out = correr(REAL, "--salida", salida_sin_ce, "--pago-contra-entrega", "no")
p_sin = json.loads(leer(os.path.join(salida_sin_ce, "shopify_payload.json"))) if rc == 0 else {}
todo_pub = (p_sin.get("descriptionHtml", "") + json.dumps(p_sin.get("seo", {}), ensure_ascii=False)).lower() if p_sin else ""
chequear("contra entrega = no: aprobado y sin «contra entrega» ni «al recibir» en página o SEO",
         rc == 0 and "contra entrega" not in todo_pub and "al recibir" not in todo_pub, out)
chequear("contra entrega = no: la pregunta frecuente sobre contra entrega se retira",
         p_sin and "¿Es seguro pagar" not in p_sin["descriptionHtml"])
chequear("contra entrega = no: lo dice en los avisos", "la configuración dice que la tienda no lo tiene" in out)

# El dato por confirmar en el título es ERROR (no se puede publicar sin nombre)
ruta = escribir(os.path.join(tmp("casos confirmar"), "brief nombre por confirmar.md"),
                brief_con_json(base, {"nombre_comercial": "PosturaGuard [CONFIRMAR nombre con el proveedor]"}))
rc, out = correr(ruta, "--salida", tmp("salida nombre por confirmar"))
chequear("confirmar: [CONFIRMAR] en el título -> error código 1", rc == 1 and "Un dato por confirmar llegó al título" in out, out)

# ---------------------------------------------------------------- 4. Filtro de promesas (unidades)
sys.path.insert(0, AQUI)
import puente  # noqa: E402

QUINCE = ["Alivia el dolor de espalda", "Reduce el dolor de cuello", "Desinflama", "Adelgaza sin dieta",
          "Quema grasa", "Elimina las arrugas", "Aprobado por INVIMA", "Clínicamente comprobado",
          "¿Sufres de dolor de espalda?", "Previene la escoliosis", "Terapéutico y ortopédico",
          "Resultados en 7 días", "Quedan pocas unidades", "Últimas unidades", "Solo hoy"]
for frase in QUINCE:
    chequear(f"promesa bloqueada: «{frase}»", puente.buscar_claims(frase), puente.buscar_claims(frase))
otras = ["Científicamente probado", "Aprobado por la FDA", "Recomendado por médicos", "Antes y después en 2 semanas",
         "Stock limitado", "Trata la artritis", "Cura la migraña", "Sana tu espalda", "Corrige la escoliosis",
         "Pierdes peso sin esfuerzo", "Te devuelve la vida sin dolor para siempre"]
for frase in otras:
    chequear(f"promesa bloqueada (extra): «{frase}»", puente.buscar_claims(frase), puente.buscar_claims(frase))
PERMITIDAS = ["Una postura más sana sin pensarlo", "No reemplaza la consulta con un profesional",
              "No reemplaza la consulta médica con un profesional de la salud", "Consulta a tu médico si tienes dudas",
              "No es un dispositivo médico", "Te ves encorvado en las fotos", "Tienes 5 días hábiles de retracto",
              "Pídelo hoy y paga al recibir", "Cojín ortopédico de espuma", "Reduce el ruido de la oficina",
              "Recordatorio suave cada vez que te encorvas", "Tono cercano (no médico, no alarmista)"]
for frase in PERMITIDAS:
    chequear(f"frase permitida (sin falso positivo): «{frase}»", not puente.buscar_claims(frase), puente.buscar_claims(frase))

# Integración: una promesa nueva metida en el copy hace fallar el brief completo
for i, frase in enumerate(["Alivia el dolor de espalda en minutos.", "Aprobado por INVIMA.", "Quedan pocas unidades."]):
    ruta = escribir(os.path.join(tmp("casos promesas"), f"brief promesa {i}.md"),
                    brief_con_json(base, extra_copy=f"### Beneficio extra\n- {frase}"))
    rc, out = correr(ruta, "--salida", tmp(f"salida promesa {i}"))
    chequear(f"brief con «{frase}» -> código 1", rc == 1 and "prohibido" in out, out.splitlines()[:3])

# Filtro de instrucciones en el copy
ins = puente.es_instruccion
chequear("instrucción: detecta y no sobre-filtra",
         ins("sin tecnicismos médicos ni promesas de dolor") and ins("Tono cercano (no médico, no alarmista)")
         and ins("En 3 pasos visuales: te encorvas, vibra, te enderezas") and ins("Fotos reales de oficina")
         and ins("Usa fotos del proveedor") and ins("Destacar el envío gratis") and ins("Mostrar hombre y mujer")
         and ins("Tono: cercano") and ins("Visuales limpios y claros")
         and not ins("Tirantes y banda ajustables, sin apretar de más.")
         and not ins("Te ves encorvado en las fotos y en las videollamadas."))
chequear("unidad: slug_palabras no corta palabras ni deja 'de' al final",
         puente.slug_palabras("Corrector de postura con sensor de vibración", 6) == "corrector-de-postura-con-sensor")
chequear("unidad: genérico corto sin preposición final",
         puente.generico_corto("corrector de postura con sensor de vibración") == "Corrector de postura con sensor")
chequear("unidad: normalizar_frase", puente.normalizar_frase("te encorvas…;") == "Te encorvas…"
         and puente.normalizar_frase("«ojo» con esto,") == "«Ojo» con esto.")
t_largo, _, _ = puente.armar_titulo("Nombre Comercial Muy Largo Que Ocupa Bastante", "x " * 40)
chequear("unidad: título nunca pasa de 70", len(t_largo) <= 70, t_largo)
chequear("unidad: SEO sin contra entrega no promete contra entrega",
         "contra entrega" not in puente.armar_seo_titulo("Alineo", "corrector de postura", False))
chequear("unidad: marcadores ignora [TESTIMONIO REAL PENDIENTE] y ve [POR CONFIRMAR x] y [VIDEO REAL PENDIENTE]",
         puente.marcadores("[TESTIMONIO REAL PENDIENTE]") == []
         and len(puente.marcadores("a [POR CONFIRMAR x] b [VIDEO REAL PENDIENTE]")) == 2)
chequear("unidad: margen_porcentaje", puente.margen_porcentaje("22% (base)") == 22 and puente.margen_porcentaje("−5 %") == -5
         and puente.margen_porcentaje("sin dato") is None)

# ---------------------------------------------------------------- 5. El puente decide (margen y veredicto)
d_casos = tmp("casos decision")
casos_decision = [
    ("PROBAR", "42%", "PRUEBA10", "probar"),
    ("NO RECOMENDABLE", "-5%", "PRUEBA10", "no"),
    ("PRECAUCIÓN", "38%", "PRUEBA10", "precaucion"),
    ("PROBAR", "42%", "", "sin codigo"),
]
for i, (ver, mar, codigo, tipo) in enumerate(casos_decision):
    ruta_e = escribir(os.path.join(d_casos, f"estudio {i}.md"), estudio(ver, mar))
    salida = tmp(f"salida decision {i}")
    rc, out = correr(BUENO, "--estudio", ruta_e, "--salida", salida, "--codigo-descuento", codigo,
                     "--pago-contra-entrega", "si")
    pd = json.loads(leer(os.path.join(salida, "shopify_payload.json"))) if rc == 0 else {}
    if tipo == "probar":
        chequear("decide: PROBAR y margen 42 % -> descuento con el código de la configuración",
                 pd.get("discount") and pd["discount"]["code"] == "PRUEBA10" and pd["discount"]["minimumQuantity"] == 2
                 and "no-recomendado" not in pd["tags"] and "precaucion" not in pd["tags"], pd.get("discount"))
    elif tipo == "no":
        chequear("decide: NO RECOMENDABLE -> sin descuento, etiqueta no-recomendado, DRAFT y advertencia",
                 rc == 0 and pd["discount"] is None and "no-recomendado" in pd["tags"] and pd["status"] == "DRAFT"
                 and "NO RECOMENDABLE" in pd.get("advertencia", ""), out)
        chequear("decide: la advertencia sale en validacion.md y en consola",
                 "ADVERTENCIA" in leer(os.path.join(salida, "validacion.md")) and "[ADVERTENCIA]" in out)
    elif tipo == "precaucion":
        chequear("decide: PRECAUCIÓN -> sin descuento y etiqueta precaucion",
                 pd.get("discount") is None and "precaucion" in pd["tags"] and "advertencia" not in pd, pd.get("tags"))
    else:
        chequear("decide: sin código en la configuración -> no se propone descuento",
                 pd.get("discount") is None and "no trae código de descuento" in out, out)
rc, out = correr(BUENO, "--salida", tmp("salida sin estudio"), "--codigo-descuento", "PRUEBA10")
chequear("decide: sin estudio -> sin descuento", rc == 0 and "descuento ninguno" in out, out)
rc, out = correr(BUENO, "--salida", tmp("salida vendedor"), "--vendedor", "Mi Marca", "--etiqueta-prueba", "demo feria",
                 "--coleccion", "Lanzamientos Octubre")
pv = json.loads(leer(os.path.join(RAIZ_TMP, "salida vendedor", "shopify_payload.json"))) if rc == 0 else {}
chequear("config: vendedor, etiqueta y colección salen de las opciones",
         pv.get("vendor") == "Mi Marca" and pv["tags"][:2] == ["demo-feria", "lanzamientos-octubre"]
         and pv["collection"]["handle"] == "lanzamientos-octubre", pv.get("tags"))
# config.json del usuario (sin pasar opciones por la línea de comandos)
cfg_dir = tmp("config con datos")
escribir(os.path.join(cfg_dir, "config.json"), json.dumps({"vendedor": "Tienda Ana", "coleccion": "novedades",
                                                           "pago_contra_entrega": True}))
rc, out = correr(BUENO, "--salida", tmp("salida config json"), "--config", os.path.join(cfg_dir, "config.json"))
pc = json.loads(leer(os.path.join(RAIZ_TMP, "salida config json", "shopify_payload.json"))) if rc == 0 else {}
chequear("config: lee config.json (vendedor, colección, contra entrega)",
         pc.get("vendor") == "Tienda Ana" and pc["collection"]["handle"] == "novedades"
         and "contra entrega" in pc["seo"]["title"].lower(), pc.get("vendor"))

# ---------------------------------------------------------------- 6. CSV de importación de Shopify
ruta_csv = os.path.join(salida_bueno, "shopify_import.csv")
chequear("csv: se escribe junto al paquete", os.path.exists(ruta_csv))
if os.path.exists(ruta_csv):
    with open(ruta_csv, encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
        f.seek(0)
        cabecera = next(csv.reader(f))
    chequear("csv: columnas del formato oficial de Shopify", cabecera == puente.CSV_COLUMNAS, cabecera)
    chequear("csv: 3 filas (una por variante) con el mismo URL handle",
             len(filas) == 3 and len({x["URL handle"] for x in filas}) == 1, len(filas))
    chequear("csv: primera fila completa, en borrador y sin publicar",
             filas[0]["Title"] == p["title"] and filas[0]["Status"] == "draft"
             and filas[0]["Published on online store"] == "FALSE" and filas[0]["Description"].startswith("<div"))
    chequear("csv: filas de variante sin título y con precio y SKU",
             all(x["Title"] == "" and x["Price"] and x["SKU"] for x in filas[1:]) and filas[1]["Option1 value"] == "2 unidades")
rc, out = correr(BUENO, "--salida", tmp("salida csv imagenes"), "--imagen", "https://cdn.example.com/a.png",
                 "--imagen", "https://cdn.example.com/b.png", "--imagen", "http://inseguro.com/c.png")
with open(os.path.join(RAIZ_TMP, "salida csv imagenes", "shopify_import.csv"), encoding="utf-8", newline="") as f:
    filas_i = list(csv.DictReader(f))
chequear("csv: --imagen llena Product image URL (solo https) con posición y alt",
         filas_i[0]["Product image URL"] == "https://cdn.example.com/a.png" and filas_i[1]["Image position"] == "2"
         and not any("inseguro" in x["Product image URL"] for x in filas_i) and filas_i[0]["Image alt text"])

# ---------------------------------------------------------------- 7. Anuncio (--anuncio)
d_an = tmp("casos anuncio")
anuncio_bueno = """# Anuncio para Meta · Alineo

## Textos principales
1. Te encorvas y ni cuenta te das. Alineo te avisa con una vibración suave.
2. Un recordatorio discreto para sentarte derecho. Envío gratis.

## Titulares
- El aviso que llega cuando te encorvas

## Frases prohibidas (no usar)
- «Alivia el dolor», «cura», «¿Sufres de dolor de espalda?», «Aprobado por INVIMA», «Quedan pocas unidades»

## CTA
Comprar
"""
anuncio_malo = anuncio_bueno.replace("Envío gratis.", "Alivia el dolor de espalda. Quedan pocas unidades.")
anuncio_confirmar = anuncio_bueno.replace("Envío gratis.", "Llega en 3 días [CONFIRMAR CON TRANSPORTADORA].")
rc, out = correr("--anuncio", escribir(os.path.join(d_an, "anuncio bueno.md"), anuncio_bueno))
chequear("anuncio: copy limpio -> código 0 (la sección de frases prohibidas se ignora)", rc == 0, out)
rc, out = correr("--anuncio", escribir(os.path.join(d_an, "anuncio malo.md"), anuncio_malo))
chequear("anuncio: con claims -> código 1", rc == 1 and "«alivia»" in out and "quedan pocas" in out, out)
rc, out = correr("--anuncio", escribir(os.path.join(d_an, "anuncio confirmar.md"), anuncio_confirmar))
chequear("anuncio: con dato por confirmar -> código 1", rc == 1 and "por confirmar" in out, out)
chequear("anuncio: escribe validacion-anuncio.md", os.path.exists(os.path.join(d_an, "validacion-anuncio.md")))
rc, out = correr("--anuncio", os.path.join(d_an, "no existe.md"))
chequear("anuncio: archivo inexistente -> código 2", rc == 2, out)

# ---------------------------------------------------------------- 8. Resumen para comparar (--resumen)
d_res = tmp("casos resumen")
e1 = escribir(os.path.join(d_res, "estudio a.md"), estudio("NO RECOMENDABLE", "-5%", "Alta", 40, "lámpara"))
e2 = escribir(os.path.join(d_res, "estudio b.md"), estudio("PROBAR", "30%", "Media", 9, "corrector"))
e3 = escribir(os.path.join(d_res, "estudio c.md"), estudio("PROBAR", "41%", "Media", 12, "masajeador"))
rc, out = correr("--resumen", e1, e2, e3)
try:
    r = json.loads(out)
except ValueError:
    r = {}
chequear("resumen: ordena PROBAR primero y, a igual confianza, mayor margen",
         rc == 0 and [f["producto"].split(" ·")[0] for f in r.get("filas", [])] == ["masajeador", "corrector", "lámpara"],
         out[:300])
chequear("resumen: recomienda el primero y lee anunciantes", r.get("recomendado", "").startswith("masajeador")
         and r["filas"][0]["anunciantes"] == 12)
rc, out = correr("--resumen", e1)
chequear("resumen: si todo es NO RECOMENDABLE, no recomienda ninguno", rc == 0 and json.loads(out)["recomendado"] is None)

# ---------------------------------------------------------------- 9. Entradas raras
casos = [
    ("raro: sin bloque JSON", re.sub(r"```json.*?```", "", base, flags=re.S), 1, "no se encontró el bloque"),
    ("raro: JSON con coma final y comillas tipográficas (se tolera)",
     brief_con_json(base, json_crudo='{"producto": “corrector de postura con sensor”, "nombre_comercial": "PosturaGuard Sensor", '
                                    '"pais": "CO", "moneda": "COP", "ofertas": [{"unidades": 1, "precio": 89900},], '
                                    '"dolores": ["espalda cargada"], "objeciones": [{"objecion": "¿Se nota?", "respuesta": "No."}],}'),
     0, "APROBADO"),
    ("raro: moneda USD para Colombia", brief_con_json(base, {"moneda": "USD"}), 1, "debe ser COP"),
    ("raro: «antes $149.900» sin precio anterior", brief_con_json(base, extra_copy="### Oferta especial\nAntes $149.900, hoy $89.900"),
     1, "Descuento o precio tachado"),
    ("raro: precio anterior SIN fuente", brief_con_json(base, {"precio_anterior": 119900}), 1, "sin fuente verificada"),
    ("raro: precio 0", brief_con_json(base, {"ofertas": [{"unidades": 1, "precio": 0}]}), 1, "mayor que 0"),
    ("raro: precio no numérico", brief_con_json(base, {"ofertas": [{"unidades": 1, "precio": "a convenir"}]}), 1, "no numérico"),
    ("raro: sin ofertas", brief_con_json(base, {"ofertas": []}), 1, "No hay ofertas"),
    ("raro: sin producto ni nombre", brief_con_json(base, quitar=("producto", "nombre_comercial")), 1, "Falta «producto»"),
    ("raro: precio que no termina en 900 (solo aviso)",
     brief_con_json(base, {"ofertas": [{"unidades": 1, "precio": 89000}, {"unidades": 2, "precio": 159900}]}), 0, "no termina en 900"),
    ("raro: sin objeciones ni dolores (solo aviso)", brief_con_json(base, {"objeciones": [], "dolores": []}), 0, "Faltan objeciones"),
    ("raro: nombre comercial de 90 caracteres (título corto + aviso)",
     brief_con_json(base, {"nombre_comercial": "PosturaGuard Sensor: el corrector inteligente que te recuerda sentarte derecho todo el día"}),
     0, "se usará un título corto"),
    ("raro: testimonio con marcador (se permite)",
     brief_con_json(base, extra_copy="### Prueba social\n[TESTIMONIO REAL PENDIENTE] \"Opinión de cliente real\" — Nombre"), 0, "APROBADO"),
]
d_raros = tmp("casos raros")
for i, (nombre, texto, esperado, debe_decir) in enumerate(casos):
    ruta = escribir(os.path.join(d_raros, f"brief caso {i}.md"), texto)  # con espacios a propósito
    rc, out = correr(ruta, "--salida", os.path.join(d_raros, f"salida {i}"))
    chequear(nombre, rc == esperado and debe_decir in out, f"código {rc}; salida: {out.strip().splitlines()[0:3]}")

ruta = escribir(os.path.join(d_raros, "brief anterior verificado.md"),
                brief_con_json(base, {"precio_anterior": 119900,
                                      "precio_anterior_fuente": "Precio publicado en la tienda hasta el 2026-10-01"}))
salida = os.path.join(d_raros, "salida anterior")
rc, out = correr(ruta, "--salida", salida)
ok = rc == 0 and json.loads(leer(os.path.join(salida, "shopify_payload.json")))["variants"][0].get("compareAtPrice") == "119900"
chequear("raro: precio anterior verificado -> compareAtPrice", ok, f"código {rc}")

p_largo = json.loads(leer(os.path.join(d_raros, "salida 11", "shopify_payload.json")))
chequear("raro: título recortado a <= 70", len(p_largo["title"]) <= 70, p_largo["title"])

salida = os.path.join(d_raros, "salida reuso")
correr(BUENO, "--salida", salida)
rc, out = correr(MALO, "--salida", salida)
chequear("raro: rechazo renombra el paquete y el CSV anteriores (no los borra)",
         rc == 1 and not os.path.exists(os.path.join(salida, "shopify_payload.json"))
         and any(n.startswith("shopify_payload.anterior-") for n in os.listdir(salida))
         and any(n.startswith("shopify_import.anterior-") for n in os.listdir(salida)))

rc, out = correr(os.path.join(d_raros, "no existe.md"), "--salida", os.path.join(d_raros, "salida x"))
chequear("raro: brief inexistente -> código 2", rc == 2, f"código {rc}")
rc, out = correr()
chequear("raro: sin argumentos -> código 2 con mensaje claro", rc == 2 and "falta el brief" in out, out)

# ---------------------------------------------------------------- Resumen
print("=== Resultados ===")
for nombre, ok, detalle in resultados:
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}" + ("" if ok else f"  -> {detalle}"))
fallas = sum(1 for _, ok, _ in resultados if not ok)
print(f"\nCarpeta temporal usada: {RAIZ_TMP}")
print(f"{len(resultados) - fallas}/{len(resultados)} pruebas pasaron.")
sys.exit(1 if fallas else 0)
