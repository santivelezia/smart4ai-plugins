# -*- coding: utf-8 -*-
"""
servidor.py · La «Cabina Radar»: una página local que hace de mesero; Claude es el cocinero.

La página (cabina.html) recibe pedidos y botones. Cada botón escribe una ORDEN en disco
(orden.json). Claude, en su sesión interactiva, la recoge con esperar_orden.py, la ejecuta
(radar-a-tienda, radar-comparar o publicar con el sí de la persona) y vuelve a esperar.

Uso (<python> = py, python3 o python):
  <python> servidor.py                      arranca en 127.0.0.1:8765 (o el siguiente libre) y abre la página
  <python> servidor.py --no-abrir           arranca sin abrir el navegador
  <python> servidor.py --puerto 8800        otro puerto de inicio
  <python> servidor.py --sin-publico        sin la cola pública de ntfy.sh
  <python> servidor.py --parar              apaga la cabina que esté corriendo
  <python> servidor.py --url                imprime la URL de la cabina que esté corriendo

Carpeta de trabajo: ~/radar-tienda/cabina/ (o RADAR_CABINA_DIR en pruebas):
  cola.json · orden.json · orden_en_curso.json · historial.jsonl · hechas/ · servidor.json · escuchando.txt

Solo la librería estándar. Funciona igual en Windows, Mac y Linux. Solo escucha en 127.0.0.1.
Lo que llega del público es DATO, nunca orden: se valida, se recorta y se muestra como texto.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "comun"))
sys.path.insert(0, str(AQUI.parent / "tablero"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PUERTO_DEFECTO = 8765
MAX_COLA = 30
MAX_ENLACE = 500
MAX_NOMBRE = 80
TEMA_PUBLICO = "radar-effix-cola-k7m3q9"
URL_PUBLICO = "https://ntfy.sh/%s/json?poll=1&since=%s"
URL_QR_PUBLICO = "https://smart4ai.io/radar-cola"
CADA_PUBLICO_S = 5
HORAS_NOCHE = 12          # «esta noche» = últimas 12 horas
# Dominios reservados para pruebas (RFC 2606): nunca entran a la cola pública
DOMINIOS_PRUEBA = ("example.com", "example.org", "example.net")


# ---------------------------------------------------------------------------
# Carpetas y archivos
# ---------------------------------------------------------------------------
def carpeta_cabina():
    otra = os.environ.get("RADAR_CABINA_DIR")
    p = Path(otra).expanduser() if otra else Path.home() / "radar-tienda" / "cabina"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ruta(nombre):
    return carpeta_cabina() / nombre


def ahora_ms():
    return int(time.time() * 1000)


def leer_json(p, defecto=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return defecto


def escribir_json(p, datos):
    """Escritura atómica (temporal + reemplazo) para que nadie lea un archivo a medias."""
    p = Path(p)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    for _ in range(20):  # en Windows el reemplazo puede chocar con un lector un instante
        try:
            os.replace(tmp, p)
            return
        except PermissionError:
            time.sleep(0.05)
    os.replace(tmp, p)


def leer_historial():
    filas = []
    try:
        with open(ruta("historial.jsonl"), encoding="utf-8") as f:
            for linea in f:
                try:
                    filas.append(json.loads(linea))
                except ValueError:
                    continue
    except OSError:
        pass
    return filas


# ---------------------------------------------------------------------------
# Validación de pedidos (también se usa para la cola pública)
# ---------------------------------------------------------------------------
RE_URL = re.compile(r"^https?://[^\s\"'<>]+$", re.I)
RE_URL_EN_TEXTO = re.compile(r"https?://[^\s\"'<>]+", re.I)


def limpiar_texto(t, maximo):
    t = re.sub(r"[\x00-\x1f\x7f]+", " ", str(t or "")).strip()
    return re.sub(r"\s+", " ", t)[:maximo].strip()


def es_url(t):
    return bool(t) and len(t) <= MAX_ENLACE and bool(RE_URL.match(t))


def es_dominio_prueba(url):
    try:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return True
    return any(host == d or host.endswith("." + d) for d in DOMINIOS_PRUEBA)


def validar_pedido(enlace, nombre=None):
    """Devuelve (pedido, None) o (None, motivo). Acepta una URL http(s) o un texto corto (nombre del producto)."""
    enlace = limpiar_texto(enlace, MAX_ENLACE + 1)
    nombre = limpiar_texto(nombre, MAX_NOMBRE)
    if not enlace and not nombre:
        return None, "Pega un enlace o escribe el nombre del producto."
    if enlace and not es_url(enlace):
        if enlace.lower().startswith(("http://", "https://")):
            return None, "El enlace no es válido (o es demasiado largo)."
        if len(enlace) > MAX_NOMBRE:
            return None, "Eso no parece un enlace y es muy largo para ser un nombre (máximo %d letras)." % MAX_NOMBRE
        if re.match(r"^[a-z][a-z0-9+.-]*:", enlace, re.I) and not re.match(r"^\w+:\s", enlace):
            return None, "Solo se aceptan enlaces http o https."
        nombre, enlace = (nombre or enlace), ""
    if not nombre and enlace:
        nombre = nombre_desde_url(enlace)
    return {"enlace": enlace, "nombre": nombre}, None


def nombre_desde_url(url):
    """Un nombre legible a partir del enlace (último tramo de la ruta, o el dominio)."""
    try:
        partes = urllib.parse.urlsplit(url)
        tramos = [x for x in partes.path.split("/") if x and not x.isdigit()]
        base = urllib.parse.unquote(tramos[-1]) if tramos else (partes.hostname or url)
    except ValueError:
        base = url
    base = re.sub(r"\.(html?|php|aspx?)$", "", base, flags=re.I)
    base = re.sub(r"[-_+]+", " ", base)
    return limpiar_texto(base, MAX_NOMBRE) or "producto"


def clave_duplicado(p):
    if p.get("enlace"):
        return "u:" + p["enlace"].lower().rstrip("/")
    return "n:" + re.sub(r"\s+", " ", p.get("nombre", "").lower())


def parsear_mensaje_publico(texto):
    """Mensaje de ntfy -> pedido o None. Acepta JSON {"enlace","nombre"} o un URL suelto (o un texto que lo contenga).
    Ignora dominios de prueba y todo lo que no sea un enlace http(s) válido."""
    if not isinstance(texto, str) or not texto.strip() or len(texto) > 2000:
        return None
    t = texto.strip()
    enlace, nombre = "", ""
    if t.startswith("{"):
        try:
            d = json.loads(t)
        except ValueError:
            return None
        if not isinstance(d, dict):
            return None
        enlace = d.get("enlace") or d.get("url") or ""
        nombre = d.get("nombre") or ""
        if not isinstance(enlace, str) or not isinstance(nombre, str):
            return None
    else:
        enlace = t
    # Si el enlace viene dentro de un texto («Mira esto https://vm.tiktok.com/...»), se toma el primer http(s)
    m = RE_URL_EN_TEXTO.search(enlace)
    if not m:
        return None
    enlace = limpiar_texto(m.group(0).rstrip(".,;)"), MAX_ENLACE + 1)
    if not es_url(enlace) or es_dominio_prueba(enlace):
        return None
    # Mensajes de prueba del equipo: nunca entran a la cola
    if "prueba" in enlace.lower() or "prueba" in nombre.lower():
        return None
    pedido, error = validar_pedido(enlace, nombre)
    return None if error else pedido


def parsear_respuesta_ntfy(cuerpo):
    """Texto de /json?poll=1 (una línea JSON por mensaje) -> lista de (id, pedido o None)."""
    salida = []
    for linea in (cuerpo or "").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            ev = json.loads(linea)
        except ValueError:
            continue
        if not isinstance(ev, dict) or ev.get("event") != "message" or not ev.get("id"):
            continue
        salida.append((str(ev["id"]), parsear_mensaje_publico(ev.get("message"))))
    return salida


# ---------------------------------------------------------------------------
# La cola (protegida con un candado: el servidor atiende varias peticiones a la vez)
# ---------------------------------------------------------------------------
CANDADO = threading.Lock()


def leer_cola():
    c = leer_json(ruta("cola.json"), [])
    return c if isinstance(c, list) else []


def agregar_a_cola(pedido, origen="local"):
    """Devuelve (item, None) o (None, motivo). Sin duplicados y con tope."""
    with CANDADO:
        cola = leer_cola()
        clave = clave_duplicado(pedido)
        if any(clave_duplicado(x) == clave for x in cola):
            return None, "Ese producto ya está en la cola."
        if len(cola) >= MAX_COLA:
            return None, "La cola está llena (máximo %d)." % MAX_COLA
        item = {"id": "p%d" % ahora_ms(), "enlace": pedido["enlace"], "nombre": pedido["nombre"],
                "origen": origen, "hora": dt.datetime.now().strftime("%H:%M")}
        while any(x["id"] == item["id"] for x in cola):
            item["id"] += "x"
        cola.append(item)
        escribir_json(ruta("cola.json"), cola)
        return item, None


def sacar_de_cola(ids):
    """Quita de la cola los ids pedidos y los devuelve en el orden pedido (los que no existan, se ignoran)."""
    with CANDADO:
        cola = leer_cola()
        por_id = {x["id"]: x for x in cola}
        sacados = [por_id[i] for i in ids if i in por_id]
        if sacados:
            quedan = [x for x in cola if x["id"] not in set(ids)]
            escribir_json(ruta("cola.json"), quedan)
        return sacados


def devolver_a_cola(items):
    with CANDADO:
        cola = leer_cola()
        escribir_json(ruta("cola.json"), items + cola)


# ---------------------------------------------------------------------------
# Órdenes para Claude
# ---------------------------------------------------------------------------
def escribir_orden(orden):
    """Escribe orden.json si no hay otra esperando. Devuelve (orden, None) o (None, motivo)."""
    with CANDADO:
        if ruta("orden.json").exists():
            pend = leer_json(ruta("orden.json"), {}) or {}
            return None, "Ya hay una orden esperando a Claude (%s). Espera a que la tome." % pend.get("resumen", "")
        orden.setdefault("id", "o%d" % ahora_ms())
        orden["creada_ms"] = ahora_ms()
        orden["creada"] = dt.datetime.now().isoformat(timespec="seconds")
        escribir_json(ruta("orden.json"), orden)
        return orden, None


# ---------------------------------------------------------------------------
# Corrida activa (la más reciente con estado.json en la carpeta de corridas)
# ---------------------------------------------------------------------------
def carpeta_corridas():
    try:
        import entorno
        return entorno.carpeta_corridas()
    except Exception:
        return Path.home() / "radar-tienda" / "corridas"


def corrida_activa():
    base = carpeta_corridas()
    mejor, t_mejor = None, -1
    try:
        for d in base.iterdir():
            e = d / "estado.json"
            if d.is_dir() and e.is_file():
                t = e.stat().st_mtime
                if t > t_mejor:
                    mejor, t_mejor = d, t
    except OSError:
        return None
    return mejor


def extracto_anuncio(carpeta, maximo=700):
    """Primer bloque útil de anuncio-meta.md (sin la sección de frases prohibidas)."""
    try:
        t = (carpeta / "anuncio-meta.md").read_text(encoding="utf-8-sig")
    except OSError:
        return ""
    t = re.split(r"(?im)^##\s*frases prohibidas", t)[0]
    t = re.sub(r"(?m)^#+\s*", "", t).strip()
    return t[:maximo] + ("…" if len(t) > maximo else "")


def leer_estado_corrida():
    c = corrida_activa()
    if not c:
        return None
    est = leer_json(c / "estado.json")
    if not isinstance(est, dict):
        return None
    est["_carpeta"] = str(c)
    est["_anuncio"] = extracto_anuncio(c)
    est["_tiene_tablero"] = (c / "tablero.html").is_file()
    return est


def contador_noche():
    limite = ahora_ms() - HORAS_NOCHE * 3600 * 1000
    filas = [f for f in leer_historial() if (f.get("fin_ms") or 0) >= limite and f.get("tipo") in ("correr", "comparar")]
    return [{"producto": f.get("producto", ""), "segundos": f.get("segundos"), "veredicto": f.get("veredicto", ""),
             "tipo": f.get("tipo"), "modo": f.get("modo", ""), "hora": f.get("hora_fin", "")} for f in filas]


def claude_escuchando():
    try:
        return time.time() - ruta("escuchando.txt").stat().st_mtime < 5
    except OSError:
        return False


def estado_api():
    hist = leer_historial()
    ultimo = next((f.get("veredicto") for f in reversed(hist) if f.get("veredicto")), "")
    return {
        "ok": True,
        "ahora_ms": ahora_ms(),
        "cola": leer_cola(),
        "orden_pendiente": leer_json(ruta("orden.json")) if ruta("orden.json").exists() else None,
        "orden_en_curso": leer_json(ruta("orden_en_curso.json")) if ruta("orden_en_curso.json").exists() else None,
        "claude_escuchando": claude_escuchando(),
        "corrida": leer_estado_corrida(),
        "noche": contador_noche(),
        "ultimo_veredicto": ultimo,
        "publico": dict(ESTADO_PUBLICO),
        "max_cola": MAX_COLA,
    }


# ---------------------------------------------------------------------------
# Cola pública (ntfy.sh). Si no hay internet, la cabina sigue igual.
# ---------------------------------------------------------------------------
ESTADO_PUBLICO = {"activo": False, "ultimo_ok": None, "error": "", "recibidos": 0}
# Solo lo nuevo desde que arranca el servidor: primero la hora de arranque (unix), luego el id del último mensaje visto
DESDE_PUBLICO = {"since": str(int(time.time()))}


def consultar_publico_una_vez(abrir_url=None):
    """Una consulta a ntfy. abrir_url se puede reemplazar en pruebas. Devuelve cuántos entraron a la cola."""
    abrir_url = abrir_url or (lambda u: urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "radar-tienda-cabina/1.1"}), timeout=8).read().decode("utf-8", "replace"))
    desde = DESDE_PUBLICO["since"]
    if not re.fullmatch(r"[A-Za-z0-9]{1,40}", desde or ""):
        desde = str(int(time.time()))
    cuerpo = abrir_url(URL_PUBLICO % (TEMA_PUBLICO, desde))
    entraron = 0
    ultimo = None
    for mid, pedido in parsear_respuesta_ntfy(cuerpo):
        ultimo = mid
        if pedido:
            item, _ = agregar_a_cola(pedido, origen="público")
            if item:
                entraron += 1
    if ultimo:
        DESDE_PUBLICO["since"] = ultimo
    ESTADO_PUBLICO.update(ultimo_ok=dt.datetime.now().strftime("%H:%M:%S"), error="")
    ESTADO_PUBLICO["recibidos"] += entraron
    return entraron


def hilo_publico(parar):
    ESTADO_PUBLICO["activo"] = True
    while not parar.is_set():
        try:
            consultar_publico_una_vez()
        except Exception as e:  # sin internet o ntfy caído: se anota y se sigue
            ESTADO_PUBLICO["error"] = ("%s" % e)[:120]
        parar.wait(CADA_PUBLICO_S)


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------
def svg_qr(texto):
    try:
        import qr
        return qr.svg_qr(texto)
    except Exception as e:  # el QR es adorno
        print("Aviso: no se pudo generar el QR (%s)" % e, file=sys.stderr)
        return ""


def pagina_html():
    html = (AQUI / "cabina.html").read_text(encoding="utf-8")
    return html.replace("<!--QR_PUBLICO-->", svg_qr(URL_QR_PUBLICO)).replace("{{URL_QR_PUBLICO}}", URL_QR_PUBLICO)


class Manejador(BaseHTTPRequestHandler):
    server_version = "CabinaRadar/1.1"

    def log_message(self, fmt, *args):  # silencio: la consola es de Claude
        pass

    def _responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
        datos = cuerpo if isinstance(cuerpo, bytes) else (
            cuerpo.encode("utf-8") if isinstance(cuerpo, str) else json.dumps(cuerpo, ensure_ascii=False).encode("utf-8"))
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(datos)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _error(self, codigo, msg):
        self._responder(codigo, {"ok": False, "error": msg})

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        try:
            if u.path in ("/", "/index.html"):
                return self._responder(200, pagina_html(), "text/html; charset=utf-8")
            if u.path == "/api/estado":
                return self._responder(200, estado_api())
            if u.path == "/api/qr":
                t = (urllib.parse.parse_qs(u.query).get("t") or [""])[0]
                if not es_url(t):
                    return self._error(400, "QR solo para enlaces http(s).")
                return self._responder(200, svg_qr(t) or "<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml")
            if u.path == "/tablero":
                c = corrida_activa()
                if c and (c / "tablero.html").is_file():
                    return self._responder(200, (c / "tablero.html").read_bytes(), "text/html; charset=utf-8")
                return self._error(404, "Aún no hay tablero.")
            return self._error(404, "No existe.")
        except Exception as e:  # nunca tumbar el servidor por una petición
            return self._error(500, "Error interno: %s" % e)

    def _leer_cuerpo(self):
        # Defensa contra páginas ajenas: solo JSON y, si el navegador manda Origin, que sea esta misma cabina.
        origen = self.headers.get("Origin")
        if origen and urllib.parse.urlsplit(origen).netloc != self.headers.get("Host", ""):
            raise PermissionError("Origen no permitido.")
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            raise ValueError("Se espera JSON.")
        n = int(self.headers.get("Content-Length") or 0)
        if n > 20000:
            raise ValueError("Pedido demasiado grande.")
        d = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        if not isinstance(d, dict):
            raise ValueError("Se espera un objeto JSON.")
        return d

    def do_POST(self):
        u = urllib.parse.urlsplit(self.path)
        try:
            d = self._leer_cuerpo()
        except PermissionError as e:
            return self._error(403, str(e))
        except (ValueError, UnicodeDecodeError) as e:
            return self._error(400, "Pedido inválido: %s" % e)
        try:
            return self._post(u.path, d)
        except Exception as e:
            return self._error(500, "Error interno: %s" % e)

    def _post(self, camino, d):
        if camino == "/api/pedido":
            pedido, err = validar_pedido(d.get("enlace"), d.get("nombre"))
            if err:
                return self._error(400, err)
            item, err = agregar_a_cola(pedido, "local")
            return self._error(409, err) if err else self._responder(200, {"ok": True, "item": item})

        if camino == "/api/quitar":
            sac = sacar_de_cola([str(d.get("id", ""))])
            return self._responder(200, {"ok": True, "quitados": len(sac)})

        if camino == "/api/lanzar":
            modo = "completo" if str(d.get("modo", "")).lower() == "completo" else "expres"
            items = sacar_de_cola([str(d.get("id", ""))])
            if not items:
                return self._error(404, "Ese producto ya no está en la cola.")
            it = items[0]
            orden, err = escribir_orden({"tipo": "correr", "modo": modo, "producto": it,
                                         "resumen": "%s · %s" % (it["nombre"], modo)})
            if err:
                devolver_a_cola(items)
                return self._error(409, err)
            return self._responder(200, {"ok": True, "orden": orden})

        if camino == "/api/comparar":
            ids = [str(x) for x in (d.get("ids") or []) if isinstance(x, (str, int))][:4]
            if len(ids) < 2:
                return self._error(400, "Para comparar hacen falta de 2 a 4 productos.")
            items = sacar_de_cola(ids)
            if len(items) < 2:
                devolver_a_cola(items)
                return self._error(404, "Faltan productos en la cola para comparar.")
            orden, err = escribir_orden({"tipo": "comparar", "productos": items,
                                         "resumen": "comparar %d productos" % len(items)})
            if err:
                devolver_a_cola(items)
                return self._error(409, err)
            return self._responder(200, {"ok": True, "orden": orden})

        if camino == "/api/publicar":
            est = leer_estado_corrida() or {}
            producto = limpiar_texto(d.get("producto") or est.get("producto"), 120)
            if not producto:
                return self._error(400, "No hay producto para publicar.")
            datos = est.get("datos") or {}
            orden, err = escribir_orden({"tipo": "publicar", "producto": producto, "corrida": est.get("_carpeta", ""),
                                         "url_producto": datos.get("url_producto", ""),
                                         "advertencia": datos.get("advertencia", ""),
                                         "resumen": "publicar %s (pide el sí en el chat)" % producto})
            return self._error(409, err) if err else self._responder(200, {"ok": True, "orden": orden})

        if camino == "/api/cancelar":
            # Destraba la cabina si Claude se cayó a mitad de una orden. No toca la tienda ni las corridas.
            hechas = []
            for nombre in ("orden.json", "orden_en_curso.json"):
                p = ruta(nombre)
                if p.exists():
                    o = leer_json(p, {}) or {}
                    destino = carpeta_cabina() / "hechas"
                    destino.mkdir(exist_ok=True)
                    os.replace(p, destino / ("%s_cancelada.json" % (o.get("id") or ahora_ms())))
                    hechas.append(nombre)
            return self._responder(200, {"ok": True, "canceladas": hechas})

        if camino == "/api/apagar":
            self._responder(200, {"ok": True, "mensaje": "Cabina apagada."})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return None

        return self._error(404, "No existe.")


# ---------------------------------------------------------------------------
# Arranque
# ---------------------------------------------------------------------------
class ServidorCabina(ThreadingHTTPServer):
    # En Windows, SO_REUSEADDR deja que DOS servidores tomen el mismo puerto sin error.
    # Se apaga para que un puerto ocupado falle de verdad y se pase al siguiente.
    allow_reuse_address = False
    allow_reuse_port = False
    daemon_threads = True


def crear_servidor(puerto_inicial=PUERTO_DEFECTO, intentos=20):
    ultimo_error = None
    for p in range(puerto_inicial, puerto_inicial + intentos):
        try:
            return ServidorCabina(("127.0.0.1", p), Manejador), p
        except OSError as e:
            ultimo_error = e
    raise OSError("No hay puerto libre entre %d y %d (%s)" % (puerto_inicial, puerto_inicial + intentos - 1, ultimo_error))


def _post_local(url, camino):
    req = urllib.request.Request(url.rstrip("/") + camino, data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=5).read().decode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cabina Radar · servidor local")
    ap.add_argument("--puerto", type=int, default=PUERTO_DEFECTO)
    ap.add_argument("--no-abrir", action="store_true")
    ap.add_argument("--sin-publico", action="store_true")
    ap.add_argument("--parar", action="store_true")
    ap.add_argument("--url", action="store_true")
    a = ap.parse_args(argv)

    info = leer_json(ruta("servidor.json"), {}) or {}
    if a.url or a.parar:
        if not info.get("url"):
            print("SIN_CABINA · no hay una cabina registrada en %s" % carpeta_cabina())
            return 1
        try:
            if a.parar:
                _post_local(info["url"], "/api/apagar")
                print("OK · cabina apagada · %s" % info["url"])
            else:
                urllib.request.urlopen(info["url"].rstrip("/") + "/api/estado", timeout=3).read()
                print(info["url"])
            return 0
        except Exception as e:
            print("SIN_CABINA · la cabina registrada (%s) no responde: %s" % (info["url"], e))
            return 1

    try:
        srv, puerto = crear_servidor(a.puerto)
    except OSError as e:
        print("ERROR · %s" % e)
        return 2
    url = "http://127.0.0.1:%d/" % puerto
    escribir_json(ruta("servidor.json"), {"url": url, "puerto": puerto, "pid": os.getpid(),
                                          "inicio": dt.datetime.now().isoformat(timespec="seconds")})
    parar = threading.Event()
    if not a.sin_publico:
        threading.Thread(target=hilo_publico, args=(parar,), daemon=True).start()
    print("CABINA · %s · carpeta %s · cola pública %s" % (url, carpeta_cabina(), "apagada" if a.sin_publico else "ntfy.sh/" + TEMA_PUBLICO),
          flush=True)
    if not a.no_abrir:
        try:
            webbrowser.open(url)
        except Exception:
            print("AVISO · ábrela a mano: %s" % url, flush=True)
    try:
        srv.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        parar.set()
        srv.server_close()
    print("CABINA · apagada", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
