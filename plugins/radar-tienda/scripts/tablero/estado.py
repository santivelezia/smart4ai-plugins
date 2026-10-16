# -*- coding: utf-8 -*-
"""
estado.py · Lleva el estado de una corrida "Del producto a la tienda" y pinta el tablero en vivo.

Uso (desde el orquestador; una orden por cambio; <python> = py, python3 o python):
  <python> estado.py "<carpeta corrida>" iniciar --producto "<nombre>" --modo exprés|completo [--ensayo] [--titulo "<marca>"]
  <python> estado.py "<carpeta corrida>" estacion radar|puente|fotos|tienda|anuncio en_curso|ok|error --detalle "<texto>"
  <python> estado.py "<carpeta corrida>" dato <clave> "<valor>"      (dato advertencia "<texto>" sale en rojo)
  <python> estado.py "<carpeta corrida>" log "<texto>"
  <python> estado.py "<carpeta corrida>" recibo --nivel "<nivel>" [--consultas N] [--proveedor "<vía de imágenes>"] [--nota "<texto>"]
  <python> estado.py "<carpeta corrida>" abrir           (abre el tablero en el navegador, Windows o Mac)
  <python> estado.py "<carpeta corrida>" terminar

Cada orden guarda <carpeta>/estado.json y regenera <carpeta>/tablero.html.
El título del tablero sale de --titulo, o de titulo_tablero en ~/.radar-tienda/config.json
(por defecto "Radar a Tienda").
La corrida se da por terminada sola cuando las 5 estaciones quedan en "ok" (o con la orden terminar):
entonces el tablero deja de refrescarse y el cronómetro se congela.

Diseño a prueba de fallas: si pintar el tablero falla, el estado igual queda guardado,
se avisa por la salida de error y la orden termina con código 0 (no frena al orquestador).
Solo la librería estándar de Python.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "comun"))

TITULO_DEFECTO = "Radar a Tienda"


def titulo_configurado():
    """Título del tablero desde la configuración del usuario (fail-open: el valor por defecto)."""
    try:
        import entorno
        return str(entorno.leer_config().get("titulo_tablero") or TITULO_DEFECTO)
    except Exception:
        return TITULO_DEFECTO

# Consola de Windows: forzar UTF-8 para que tildes y ✔ no rompan la salida
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Catálogo de estaciones (orden = orden de la línea de ensamblaje)
# ---------------------------------------------------------------------------
ESTACIONES = [
    ("radar", "Radar", "Estudio de mercado", "Meta Ads Library · búsqueda web · Python"),
    ("puente", "Puente", "Validación", "Validador Python"),
    ("fotos", "Estudio fotográfico", "Imágenes del producto", "IA de imágenes o tu foto"),
    ("tienda", "Tienda", "Producto en Shopify", "Shopify Admin API"),
    ("anuncio", "Anuncio", "Textos + creativo Meta", "Copy + creativo"),
]
CLAVES_EST = [e[0] for e in ESTACIONES]
ESTADOS_VALIDOS = ["en_curso", "ok", "error"]
NOMBRE_ESTADO = {"pendiente": "Pendiente", "en_curso": "En curso", "ok": "Listo", "error": "Error"}

# Datos que se muestran en lugares fijos del panel; el resto va a "Otros datos"
CLAVES_DINERO = {"precio_1", "precio_2", "precio_3", "cpa_equilibrio", "costo", "margen", "ganancia",
                 "precio_costo", "precio_venta"}
CLAVES_CONTEO = {"anuncios_activos", "anunciantes"}
CLAVES_FIJAS = ({"veredicto", "confianza", "angulo", "dolor_1", "dolor_2", "dolor_3", "url_preview",
                 "url_producto", "tiempo", "advertencia", "recibo"} | CLAVES_DINERO | CLAVES_CONTEO
                | {"imagen_%d" % i for i in range(1, 5)})


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def ahora_ms():
    return int(time.time() * 1000)


def hora_local():
    return dt.datetime.now().strftime("%H:%M:%S")


def esc(t):
    return html.escape("" if t is None else str(t), quote=True)


def miles(n):
    """1234567 -> '1.234.567' (separador colombiano)."""
    return "{:,}".format(int(n)).replace(",", ".")


def a_numero(valor):
    """
    Intenta leer un número escrito como '89900', '$89.900', '89.900', '89,900' o '89900.0'.
    Devuelve int o None si no es un número limpio.
    """
    s = str(valor).strip().replace("$", "").replace("COP", "").replace(" ", "").strip()
    if not s:
        return None
    if re.fullmatch(r"-?\d{1,3}([.,]\d{3})+", s):        # 89.900 / 1.234.567 / 89,900
        return int(re.sub(r"[.,]", "", s))
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+[.,]\d{1,2}", s):              # 89900.5 -> redondea
        return int(round(float(s.replace(",", "."))))
    return None


def formato_valor(clave, valor):
    """Cifras en formato colombiano: dinero -> $89.900; conteos -> 1.234; el resto, tal cual."""
    v = str(valor).strip()
    if clave in CLAVES_DINERO and not v.endswith("%"):
        n = a_numero(v)
        if n is not None:
            return ("-$" if n < 0 else "$") + miles(abs(n))
    if clave in CLAVES_CONTEO:
        n = a_numero(v)
        if n is not None:
            return miles(n)
    return v


def url_segura(u, solo_https=False):
    """Solo deja pasar http(s) (o solo https). Evita javascript: y rutas raras."""
    u = (u or "").strip()
    if solo_https:
        return u if re.match(r"^https://[^\s\"'<>]+$", u, re.I) else None
    return u if re.match(r"^https?://[^\s\"'<>]+$", u, re.I) else None


def escribir_atomico(ruta, texto):
    """Escribe a un temporal y lo reemplaza, para que el navegador nunca lea un archivo a medias."""
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    for intento in range(10):  # en Windows el reemplazo puede chocar con un lector un instante
        try:
            os.replace(tmp, ruta)
            return
        except PermissionError:
            time.sleep(0.1)
    os.replace(tmp, ruta)


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------
def estado_nuevo(producto="(sin nombre)", modo="exprés", ensayo=False, titulo=None):
    return {
        "version": 1,
        "titulo": titulo or TITULO_DEFECTO,
        "producto": producto,
        "modo": modo,
        "ensayo": bool(ensayo),
        "inicio_ms": ahora_ms(),
        "inicio_iso": dt.datetime.now().isoformat(timespec="seconds"),
        "fin_ms": None,
        "terminado": False,
        "estaciones": {k: {"estado": "pendiente", "detalle": "", "actualizado": None} for k in CLAVES_EST},
        "datos": {},
        "log": [],
    }


def cargar(carpeta):
    ruta = os.path.join(carpeta, "estado.json")
    if not os.path.exists(ruta):
        print("Aviso: no había estado.json en la carpeta; se crea uno nuevo (usa 'iniciar' primero).",
              file=sys.stderr)
        return estado_nuevo()
    try:
        with open(ruta, encoding="utf-8") as f:
            est = json.load(f)
    except Exception as e:
        # Archivo dañado: se guarda aparte y se sigue con uno nuevo (no se pierde la evidencia)
        respaldo = ruta + ".danado_%s" % dt.datetime.now().strftime("%H%M%S")
        try:
            os.replace(ruta, respaldo)
        except Exception:
            pass
        print("Aviso: estado.json ilegible (%s); copia en %s y se empieza uno nuevo." % (e, respaldo),
              file=sys.stderr)
        return estado_nuevo()
    # Completar campos que falten (archivos viejos o editados a mano)
    base = estado_nuevo(est.get("producto", "(sin nombre)"), est.get("modo", "exprés"))
    for k, v in base.items():
        est.setdefault(k, v)
    for k in CLAVES_EST:
        est["estaciones"].setdefault(k, {"estado": "pendiente", "detalle": "", "actualizado": None})
    return est


def guardar(carpeta, est):
    os.makedirs(carpeta, exist_ok=True)
    escribir_atomico(os.path.join(carpeta, "estado.json"), json.dumps(est, ensure_ascii=False, indent=2))


def agregar_log(est, texto):
    est["log"].append({"hora": hora_local(), "texto": str(texto)})
    est["log"] = est["log"][-200:]  # tope para que el archivo no crezca sin fin


def revisar_fin(est):
    if not est["terminado"] and all(est["estaciones"][k]["estado"] == "ok" for k in CLAVES_EST):
        est["terminado"] = True
        est["fin_ms"] = ahora_ms()
        agregar_log(est, "Línea completa: del producto a la tienda en %s" % duracion_texto(est))


def duracion_texto(est):
    fin = est["fin_ms"] or ahora_ms()
    s = max(0, (fin - est["inicio_ms"]) // 1000)
    return "%d:%02d" % (s // 60, s % 60)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html{font-size:calc(100vw / 100);background:#0b0f17}
body{font-family:'Inter','Segoe UI',system-ui,sans-serif;color:#e8ecf3;background:radial-gradient(ellipse at 20% 0%,#16213a 0%,#0b0f17 55%);
 height:100vh;overflow:hidden;display:grid;grid-template-rows:auto auto 1fr;gap:1.1rem;padding:1.3rem 1.8rem}
.cab{display:flex;align-items:center;justify-content:space-between;gap:2rem}
.marca{font-size:.95rem;letter-spacing:.25em;text-transform:uppercase;color:#8fa3c7;font-weight:600}
.marca b{color:#f5c26b;font-weight:700}
.prod{font-size:2.3rem;font-weight:800;line-height:1.1;margin-top:.25rem}
.chips{display:flex;gap:.6rem;margin-top:.45rem}
.chip{font-size:.8rem;padding:.2rem .7rem;border-radius:2rem;border:1px solid #2c3a57;color:#b9c6de;text-transform:uppercase;letter-spacing:.08em}
.chip.ensayo{border-color:#f5c26b;color:#f5c26b}
.reloj{text-align:right}
.reloj .t{font-size:3.6rem;font-weight:800;font-variant-numeric:tabular-nums;letter-spacing:.02em;color:#fff}
.reloj .l{font-size:.8rem;color:#8fa3c7;text-transform:uppercase;letter-spacing:.2em}
.reloj.fin .t{color:#4ade80}
.linea{display:grid;grid-template-columns:repeat(5,1fr);gap:1.4rem;position:relative}
.est{position:relative;background:#121a2b;border:2px solid #24304a;border-radius:1rem;padding:.9rem 1rem;min-height:9.2rem;display:flex;flex-direction:column;gap:.3rem}
.est:not(:last-child)::after{content:'';position:absolute;right:-1.4rem;top:50%;width:1.4rem;height:3px;background:#24304a}
.est.ok:not(:last-child)::after{background:#22c55e}
.est .n{font-size:.75rem;color:#6b7c9c;letter-spacing:.15em;text-transform:uppercase;font-weight:700}
.est .nom{font-size:1.35rem;font-weight:800}
.est .sub{font-size:.8rem;color:#8fa3c7}
.est .det{font-size:.85rem;color:#d7deeb;margin-top:auto;min-height:1.2rem;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.est .her{font-size:.68rem;color:#6b7c9c;border-top:1px solid #24304a;padding-top:.35rem}
.est .ico{position:absolute;top:.7rem;right:.8rem;width:2rem;height:2rem;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.1rem;font-weight:800;background:#1b2438;color:#6b7c9c}
.est.pendiente{opacity:.55}
.est.en_curso{border-color:#f5c26b;animation:pulso 1.4s ease-in-out infinite}
.est.en_curso .ico{background:#f5c26b;color:#0b0f17}
.est.ok{border-color:#22c55e;background:linear-gradient(180deg,#10261b,#121a2b)}
.est.ok .ico{background:#22c55e;color:#06210f}
.est.error{border-color:#ef4444;background:linear-gradient(180deg,#2a1215,#121a2b)}
.est.error .ico{background:#ef4444;color:#fff}
@keyframes pulso{0%,100%{box-shadow:0 0 0 0 rgba(245,194,107,.55)}50%{box-shadow:0 0 1.4rem .35rem rgba(245,194,107,.35)}}
.giro{width:1rem;height:1rem;border:.18rem solid #0b0f17;border-top-color:transparent;border-radius:50%;animation:gira .8s linear infinite}
@keyframes gira{to{transform:rotate(360deg)}}
.panel{display:grid;grid-template-columns:1.05fr 1.25fr .95fr;gap:1.2rem;min-height:0}
.caja{background:#111827cc;border:1px solid #22304b;border-radius:1rem;padding:1rem 1.2rem;min-height:0;overflow:hidden;display:flex;flex-direction:column;gap:.7rem}
.tit{font-size:.75rem;color:#8fa3c7;text-transform:uppercase;letter-spacing:.2em;font-weight:700}
.ver{font-size:2.5rem;font-weight:900;line-height:1;padding:.6rem .9rem;border-radius:.7rem;text-align:center;letter-spacing:.03em}
.ver.verde{background:#14532d;color:#86efac;border:2px solid #22c55e}
.ver.ambar{background:#422c06;color:#fcd34d;border:2px solid #f59e0b}
.ver.rojo{background:#450a0a;color:#fca5a5;border:2px solid #ef4444}
.ver.neutro{background:#172554;color:#bfdbfe;border:2px solid #3b82f6}
.ver.vacio{background:#151d2e;color:#475569;border:2px dashed #2c3a57;font-size:1.5rem}
.kpis{display:grid;grid-template-columns:1fr 1fr;gap:.6rem}
.kpi{background:#0d1422;border:1px solid #1f2a40;border-radius:.6rem;padding:.45rem .7rem}
.kpi .k{font-size:.66rem;color:#7d8fb0;text-transform:uppercase;letter-spacing:.1em}
.kpi .v{font-size:1.45rem;font-weight:800}
.kpi .v.vac{color:#334155}
.ofertas{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem}
.of{background:#0d1422;border:1px solid #1f2a40;border-radius:.6rem;padding:.45rem .5rem;text-align:center}
.of .k{font-size:.7rem;color:#7d8fb0}
.of .v{font-size:1.35rem;font-weight:800;color:#f5c26b;font-variant-numeric:tabular-nums}
.of .v.vac{color:#334155}
.angulo{font-size:1.25rem;font-weight:700;line-height:1.3;color:#fff}
.angulo.vac{color:#334155}
.dolores{list-style:none;display:flex;flex-direction:column;gap:.35rem}
.dolores li{font-size:.95rem;padding:.35rem .7rem;background:#0d1422;border-left:.25rem solid #f59e0b;border-radius:.3rem}
.tit.abajo{margin-top:auto}
.imgs{display:grid;grid-template-columns:repeat(4,1fr);gap:.6rem}
.imgs .im{aspect-ratio:1;border-radius:.6rem;background:#0d1422 center/cover no-repeat;border:1px solid #1f2a40;overflow:hidden}
.imgs .im img{width:100%;height:100%;object-fit:cover;display:block}
.tienda{display:flex;gap:1rem;align-items:center}
.qr{width:8.5rem;height:8.5rem;background:#fff;border-radius:.6rem;padding:.3rem;flex:none}
.qr svg{width:100%;height:100%;display:block}
.boton{display:inline-block;background:#22c55e;color:#04210f;font-weight:900;font-size:1.3rem;padding:.7rem 1.1rem;border-radius:.7rem;text-decoration:none}
.url{font-size:.72rem;color:#8fa3c7;word-break:break-all;margin-top:.4rem}
.espera{font-size:1rem;color:#475569}
.log{font-family:'Cascadia Mono',Consolas,monospace;font-size:.78rem;display:flex;flex-direction:column;gap:.25rem;color:#c7d2e6}
.log .h{color:#f5c26b;margin-right:.5rem}
.otros{font-size:.8rem;color:#b9c6de}
.otros b{color:#8fa3c7;font-weight:600}
.adv{background:#450a0a;border:2px solid #ef4444;color:#fecaca;border-radius:.6rem;padding:.5rem .7rem;font-size:.9rem;font-weight:700}
.recibo{font-size:.8rem;color:#d7deeb;background:#0d1422;border:1px solid #1f2a40;border-radius:.6rem;padding:.45rem .7rem}
"""

JS_RELOJ = """
(function(){
  var r=document.getElementById('reloj');var ini=+r.dataset.inicio;var fin=r.dataset.fin?+r.dataset.fin:0;
  function pinta(){var s=Math.max(0,Math.floor(((fin||Date.now())-ini)/1000));
    var m=Math.floor(s/60),x=s%60;r.querySelector('.t').textContent=m+':'+(x<10?'0':'')+x;}
  pinta(); if(!fin){setInterval(pinta,250);}
})();
"""


def clase_veredicto(v):
    t = v.upper()
    for a, b in (("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U")):
        t = t.replace(a, b)
    if t.startswith("NO ") or "NO RECOMEND" in t or "DESCART" in t or t == "NO":
        return "rojo"
    if "PRECAUC" in t or "CUIDADO" in t or "DUDOS" in t or "CAUTELA" in t:
        return "ambar"
    if "PROBAR" in t or "RECOMENDABLE" in t or "VENDER" in t or t.startswith("SI"):
        return "verde"
    return "neutro"


def _kpi(etq, clave, datos):
    if clave in datos and str(datos[clave]).strip():
        return '<div class="kpi"><div class="k">%s</div><div class="v">%s</div></div>' % (
            esc(etq), esc(formato_valor(clave, datos[clave])))
    return '<div class="kpi"><div class="k">%s</div><div class="v vac">—</div></div>' % esc(etq)


def _estacion_html(i, clave, nombre, sub, herramienta, e):
    estado = e.get("estado", "pendiente")
    if estado not in ("pendiente", "en_curso", "ok", "error"):
        estado = "pendiente"
    ico = {"pendiente": str(i), "en_curso": '<div class="giro"></div>', "ok": "✔", "error": "✖"}[estado]
    det = e.get("detalle") or NOMBRE_ESTADO[estado]
    return (
        '<div class="est %s"><div class="ico">%s</div>'
        '<div class="n">Estación %d · %s</div><div class="nom">%s</div><div class="sub">%s</div>'
        '<div class="det">%s</div><div class="her">%s</div></div>'
        % (estado, ico, i, esc(NOMBRE_ESTADO[estado]), esc(nombre), esc(sub), esc(det), esc(herramienta))
    )


def generar_html(est):
    d = est.get("datos", {})
    terminado = bool(est.get("terminado"))

    # --- encabezado ---
    chips = '<span class="chip">Modo %s</span>' % esc(est.get("modo", ""))
    if est.get("ensayo"):
        chips += '<span class="chip ensayo">Ensayo · datos de ejemplo</span>'
    reloj = '<div class="reloj%s" id="reloj" data-inicio="%d"%s><div class="t">%s</div><div class="l">%s</div></div>' % (
        " fin" if terminado else "", est["inicio_ms"],
        (' data-fin="%d"' % est["fin_ms"]) if terminado and est.get("fin_ms") else "",
        duracion_texto(est), "Tiempo total" if terminado else "Tiempo transcurrido")

    # --- línea de estaciones ---
    linea = "".join(_estacion_html(i + 1, c, n, s, h, est["estaciones"].get(c, {}))
                    for i, (c, n, s, h) in enumerate(ESTACIONES))

    # --- columna 1: veredicto y números ---
    if d.get("veredicto"):
        ver = '<div class="ver %s">%s</div>' % (clase_veredicto(str(d["veredicto"])), esc(d["veredicto"]))
    else:
        ver = '<div class="ver vacio">Veredicto en camino…</div>'
    if d.get("advertencia"):  # la pone el puente cuando el estudio dice NO RECOMENDABLE
        ver += '<div class="adv">⚠ %s</div>' % esc(d["advertencia"])
    ofertas = ""
    for i in (1, 2, 3):
        k = "precio_%d" % i
        if k in d and str(d[k]).strip():
            ofertas += '<div class="of"><div class="k">%d unidad%s</div><div class="v">%s</div></div>' % (
                i, "" if i == 1 else "es", esc(formato_valor(k, d[k])))
        else:
            ofertas += '<div class="of"><div class="k">%d unidad%s</div><div class="v vac">—</div></div>' % (
                i, "" if i == 1 else "es")
    col1 = (
        '<div class="caja"><div class="tit">Veredicto del Radar</div>%s'
        '<div class="kpis">%s%s%s%s%s%s</div>'
        '<div class="tit">Oferta por combo</div><div class="ofertas">%s</div></div>'
        % (ver, _kpi("Confianza", "confianza", d), _kpi("Anuncios activos", "anuncios_activos", d),
           _kpi("Anunciantes", "anunciantes", d), _kpi("Margen", "margen", d),
           _kpi("CPA de equilibrio", "cpa_equilibrio", d), _kpi("Costo", "costo", d), ofertas)
    )

    # --- columna 2: ángulo, dolores, imágenes ---
    if d.get("angulo"):
        ang = '<div class="angulo">“%s”</div>' % esc(d["angulo"])
    else:
        ang = '<div class="angulo vac">El ángulo de venta aparece cuando termine el Radar</div>'
    dol = "".join("<li>%s</li>" % esc(d["dolor_%d" % i]) for i in (1, 2, 3) if d.get("dolor_%d" % i))
    dol = '<ul class="dolores">%s</ul>' % dol if dol else '<div class="espera">Dolores del cliente: en camino…</div>'
    imgs = ""
    for i in range(1, 5):
        u = url_segura(d.get("imagen_%d" % i), solo_https=True)
        if u:
            imgs += ('<div class="im"><img src="%s" alt="Imagen %d" '
                     'onerror="this.style.display=\'none\'"></div>' % (esc(u), i))
        else:
            imgs += '<div class="im"></div>'
    col2 = ('<div class="caja"><div class="tit">Ángulo de venta</div>%s'
            '<div class="tit">Lo que le duele al cliente</div>%s'
            '<div class="tit abajo">Estudio fotográfico</div><div class="imgs">%s</div></div>' % (ang, dol, imgs))

    # --- columna 3: tienda (QR) + bitácora ---
    enlace = url_segura(d.get("url_preview")) or url_segura(d.get("url_producto"))
    if enlace:
        try:
            import qr
            svg = qr.svg_qr(enlace) if len(enlace) <= 1000 else ""
        except Exception as e:  # el QR es adorno: si falla, el botón sigue
            print("Aviso: no se pudo generar el QR (%s)" % e, file=sys.stderr)
            svg = ""
        tienda = ('<div class="tienda">%s<div><a class="boton" href="%s" target="_blank" rel="noopener">'
                  'Ver la tienda →</a><div class="url">%s</div></div></div>'
                  % ('<div class="qr">%s</div>' % svg if svg else "", esc(enlace), esc(enlace)))
    else:
        tienda = '<div class="espera">El enlace y el QR de la tienda aparecen al terminar la estación 4.</div>'
    ult = est.get("log", [])[-8:]
    log = "".join('<div><span class="h">%s</span>%s</div>' % (esc(x.get("hora")), esc(x.get("texto")))
                  for x in ult) or '<div class="espera">Sin eventos todavía.</div>'
    otros = [(k, v) for k, v in d.items() if k not in CLAVES_FIJAS and str(v).strip()]
    if d.get("tiempo"):
        otros.insert(0, ("tiempo", d["tiempo"]))
    otros_html = ""
    if otros:
        otros_html = '<div class="otros">%s</div>' % " · ".join(
            "<b>%s:</b> %s" % (esc(k.replace("_", " ")), esc(formato_valor(k, v))) for k, v in otros[:6])
    recibo = ('<div class="tit">Recibo de la corrida</div><div class="recibo">%s</div>' % esc(d["recibo"])
              if d.get("recibo") else "")
    col3 = ('<div class="caja"><div class="tit">Tienda en Shopify</div>%s%s%s'
            '<div class="tit">Bitácora</div><div class="log">%s</div></div>' % (tienda, otros_html, recibo, log))

    refresco = "" if terminado else '<meta http-equiv="refresh" content="3">'
    return """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">%s
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s · %s</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap" media="print" onload="this.media='all'">
<style>%s</style></head>
<body>
<header class="cab"><div><div class="marca">Del producto a la tienda · <b>%s</b></div>
<div class="prod">%s</div><div class="chips">%s</div></div>%s</header>
<section class="linea">%s</section>
<section class="panel">%s%s%s</section>
<script>%s</script>
</body></html>
""" % (refresco, esc(est.get("titulo") or TITULO_DEFECTO), esc(est.get("producto")), CSS,
       esc(est.get("titulo") or TITULO_DEFECTO), esc(est.get("producto")), chips, reloj, linea, col1, col2, col3,
       JS_RELOJ)


def pintar(carpeta, est):
    """Regenera tablero.html. Nunca lanza error hacia afuera (fail-open)."""
    try:
        escribir_atomico(os.path.join(carpeta, "tablero.html"), generar_html(est))
        return True
    except Exception as e:
        print("Aviso: el estado se guardó, pero no se pudo pintar el tablero: %r" % e, file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def leer_imagenes(carpeta):
    """Líneas JSON que dejó generar.py con --registro (imagenes.jsonl). Ignora líneas dañadas."""
    ruta = os.path.join(carpeta, "imagenes.jsonl")
    filas = []
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                try:
                    filas.append(json.loads(linea))
                except ValueError:
                    continue
    return filas


def armar_recibo(carpeta, est, nivel, consultas=None, proveedor="", nota=""):
    """Recibo de la corrida: tiempo, consultas, imágenes y su costo (sumado de generar.py), nivel.
    Devuelve (texto markdown, línea corta para el tablero)."""
    imgs = leer_imagenes(carpeta)
    buenas = [x for x in imgs if x.get("ok")]
    fallidas = [x for x in imgs if not x.get("ok")]
    costos = [x.get("costo_usd") for x in buenas if isinstance(x.get("costo_usd"), (int, float))]
    costo = round(sum(costos), 4)
    sin_costo = len(buenas) - len(costos)
    estimado = any("estimado" in str(x.get("costo_fuente", "")) for x in buenas)
    tiempo = duracion_texto(est)
    l = ["# Recibo de la corrida", "",
         "| Concepto | Valor |", "|---|---|",
         "| Producto | %s |" % est.get("producto", ""),
         "| Fecha | %s |" % est.get("inicio_iso", ""),
         "| Tiempo total | %s min |" % tiempo,
         "| Nivel de funcionamiento | %s |" % (nivel or "no indicado"),
         "| Consultas a herramientas (aprox.) | %s |" % (consultas if consultas is not None else "no contadas"),
         "| Vía de imágenes | %s |" % (proveedor or "no indicada"),
         "| Imágenes generadas con IA | %d%s |" % (len(buenas), (" (%d fallidas)" % len(fallidas)) if fallidas else ""),
         "| Costo de imágenes (US$) | %s%s%s |" % (
             "%.4f" % costo, " (incluye estimados)" if estimado else "",
             (" + %d sin dato de costo" % sin_costo) if sin_costo else ""),
         ]
    saltos = [x.get("aviso_modelo") for x in buenas if x.get("aviso_modelo")]
    if saltos or nota:
        l += ["", "## Notas", ""] + ["- %s" % s for s in saltos] + (["- %s" % nota] if nota else [])
    l += ["", "_El costo sale de lo que reportó OpenRouter por cada imagen (o del precio publicado si no lo reportó). "
          "Las consultas son aproximadas._"]
    corta = "%s min · %s · %d imágenes IA · US$%.4f%s" % (
        tiempo, nivel or "nivel no indicado", len(buenas), costo,
        (" · %s consultas" % consultas) if consultas is not None else "")
    return "\n".join(l) + "\n", corta


def main(argv=None):
    p = argparse.ArgumentParser(description="Estado y tablero en vivo de una corrida de radar-tienda")
    p.add_argument("carpeta", help="Carpeta de la corrida (se crea si no existe)")
    sub = p.add_subparsers(dest="orden", required=True)

    a = sub.add_parser("iniciar")
    a.add_argument("--producto", required=True)
    a.add_argument("--modo", default="exprés", help="exprés | completo")
    a.add_argument("--ensayo", action="store_true", help="Marca la corrida como ensayo con datos de ejemplo")
    a.add_argument("--titulo", help="Marca que se ve arriba del tablero (por defecto, la de la configuración)")

    r = sub.add_parser("recibo")
    r.add_argument("--nivel", default="")
    r.add_argument("--consultas", type=int)
    r.add_argument("--proveedor", default="")
    r.add_argument("--nota", default="")

    sub.add_parser("abrir")

    b = sub.add_parser("estacion")
    b.add_argument("nombre", choices=CLAVES_EST)
    b.add_argument("estado", choices=ESTADOS_VALIDOS)
    b.add_argument("--detalle", default="")

    c = sub.add_parser("dato")
    c.add_argument("clave")
    c.add_argument("valor")

    l = sub.add_parser("log")
    l.add_argument("texto")

    sub.add_parser("terminar")

    args = p.parse_args(argv)
    carpeta = os.path.abspath(args.carpeta)
    os.makedirs(carpeta, exist_ok=True)

    if args.orden == "abrir":
        # Abrir es adorno: nunca devuelve error (fail-open). Funciona en Windows, Mac y Linux.
        ruta = os.path.join(carpeta, "tablero.html")
        if not os.path.exists(ruta):
            print("AVISO · aún no hay tablero en %s (usa 'iniciar' primero)" % carpeta)
            return 0
        try:
            import webbrowser
            from pathlib import Path
            ok = webbrowser.open(Path(ruta).resolve().as_uri())
        except Exception as e:
            ok = False
            print("AVISO · no se pudo abrir (%s)" % e, file=sys.stderr)
        print(("OK · abierto · %s" if ok else "AVISO · ábrelo a mano: %s") % ruta)
        return 0

    if args.orden == "iniciar":
        modo = args.modo.strip().lower()
        modo = "exprés" if modo in ("expres", "exprés", "express") else modo
        est = estado_nuevo(args.producto, modo, args.ensayo, args.titulo or titulo_configurado())
        agregar_log(est, "Arranca la línea: %s (modo %s)" % (args.producto, modo))
    else:
        est = cargar(carpeta)

    if args.orden == "recibo":
        texto, corta = armar_recibo(carpeta, est, args.nivel, args.consultas, args.proveedor, args.nota)
        try:
            escribir_atomico(os.path.join(carpeta, "recibo.md"), texto)
        except OSError as e:
            print("Aviso: no se pudo escribir recibo.md (%s)" % e, file=sys.stderr)
        est["datos"]["recibo"] = corta
        agregar_log(est, "Recibo: " + corta)
        print(texto)

    if args.orden == "estacion":
        e = est["estaciones"][args.nombre]
        e["estado"] = args.estado
        e["detalle"] = args.detalle.strip()[:160]
        e["actualizado"] = hora_local()
        nombre = dict((x[0], x[1]) for x in ESTACIONES)[args.nombre]
        txt = "%s · %s" % (nombre, NOMBRE_ESTADO[args.estado])
        if e["detalle"]:
            txt += " · " + e["detalle"]
        agregar_log(est, txt)
        if args.estado != "ok" and est["terminado"]:  # se reabrió una estación
            est["terminado"], est["fin_ms"] = False, None
        revisar_fin(est)
    elif args.orden == "dato":
        clave = re.sub(r"[^a-z0-9_]", "_", args.clave.strip().lower())
        if not clave:
            p.error("la clave no puede quedar vacía")
        if clave.startswith("imagen_") and not url_segura(args.valor, solo_https=True):
            print("Aviso: %s no es una URL https; se guarda pero no se muestra." % clave, file=sys.stderr)
        est["datos"][clave] = args.valor
    elif args.orden == "log":
        agregar_log(est, args.texto)
    elif args.orden == "terminar":
        if not est["terminado"]:
            est["terminado"] = True
            est["fin_ms"] = ahora_ms()
            agregar_log(est, "Corrida cerrada en %s" % duracion_texto(est))

    guardar(carpeta, est)
    pintar(carpeta, est)
    print("OK · %s · %s" % (args.orden, os.path.join(carpeta, "tablero.html")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
