# -*- coding: utf-8 -*-
"""
generar.py · Imagen de producto con Gemini ("Nano Banana") vía OpenRouter. Python puro (urllib),
sin dependencias: corre igual en Windows y Mac. Es UNA de las tres vías de imágenes del plugin
(las otras: un conector de imágenes de la sesión, o las fotos del usuario).

Uso:
  <python> generar.py --prompt "<texto>" --salida "<ruta .png>" [--ref "<ruta o URL>"]
                      [--aspect 1:1|4:5|9:16|16:9|...] [--model <id>] [--api images|chat]
                      [--registro "<corrida>/imagenes.jsonl"]

Clave: OPENROUTER_API_KEY desde la variable de entorno o desde ~/.radar-tienda/.env
(una línea OPENROUTER_API_KEY=...). La clave NUNCA se imprime ni se escribe en ningún archivo.

API (verificado 2026-10-16 en https://openrouter.ai/docs/guides/overview/multimodal/image-generation.md):
  - Principal: POST /api/v1/images  { model, prompt, aspect_ratio, input_references[] } -> data[i].b64_json
  - Respaldo:  POST /api/v1/chat/completions con modalities ["image","text"] -> message.images[i].image_url.url

Salida en consola: UNA línea JSON. Éxito: {"ok": true, "salida", "bytes", "modelo", "costo_usd", ...}.
Error: {"ok": false, "error": "<mensaje claro en español>"} y código de salida 1.
Registro de costos: ~/radar-tienda/costos.csv (carpeta de datos del usuario, nunca dentro del plugin).
"""

import argparse
import base64
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "comun"))
import entorno  # noqa: E402

BASE_URL = "https://openrouter.ai/api/v1"
TIEMPO_MAXIMO = 180  # segundos: nunca colgar la línea

# Cadena por defecto: se salta al siguiente solo si el proveedor responde 429 (cupo) o 5xx.
CADENA_DEFECTO = ["google/gemini-3.1-flash-lite-image", "google/gemini-nano-banana-2.1", "google/gemini-2.5-flash-image"]

# Precio por token de imagen de salida (USD), de /api/v1/images/models/<id>/endpoints (2026-10-16).
# Solo se usa si la respuesta no trae usage.cost.
PRECIO_TOKEN_SALIDA = {
    "google/gemini-nano-banana-2.1": 0.00003,
    "google/gemini-3.1-flash-lite-image": 0.00003,
    "google/gemini-2.5-flash-image": 0.00003,
    "google/gemini-3.1-flash-image": 0.00006,
    "google/gemini-3.1-flash-image-preview": 0.00006,
    "google/gemini-3-pro-image": 0.00012,
    "google/gemini-3-pro-image-preview": 0.00012,
}
TOKENS_IMG = 1290
ASPECTOS = ["1:1", "4:5", "9:16", "16:9", "3:4", "4:3", "2:3", "3:2", "5:4", "21:9"]
MIMES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
EXT_REAL = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


class Fallo(Exception):
    def __init__(self, mensaje, **extra):
        super().__init__(mensaje)
        self.extra = extra


def limpiar(texto, clave=None):
    """Quita la clave de cualquier texto antes de mostrarlo (defensa extra)."""
    s = str(texto or "")
    if clave and len(clave) > 8:
        s = s.replace(clave, "[CLAVE-OCULTA]")
    return re.sub(r"sk-or-[A-Za-z0-9_-]{10,}", "[CLAVE-OCULTA]", s)[:500]


def mensaje_http(status, cuerpo, clave):
    detalle = limpiar(cuerpo, clave)
    if status == 401:
        return f"401 · La clave de OpenRouter es inválida o fue revocada. Revisa ~/.radar-tienda/.env. Detalle: {detalle}"
    if status == 402:
        return f"402 · Sin créditos en OpenRouter: recarga en https://openrouter.ai/settings/credits. Detalle: {detalle}"
    if status == 429:
        return f"429 · Demasiadas solicitudes o cupo agotado del modelo. Espera un minuto. Detalle: {detalle}"
    if status == 404:
        return f"404 · Modelo o ruta no encontrada (¿ID de modelo correcto?). Detalle: {detalle}"
    return f"HTTP {status} · {detalle}"


def preparar_ref(ref):
    """--ref local -> data URL base64; URL https o data URL -> tal cual."""
    if re.match(r"^https?://", ref, re.I) or re.match(r"^data:image/", ref, re.I):
        return ref
    ruta = Path(ref).expanduser().resolve()
    if not ruta.is_file():
        raise Fallo(f"La imagen de referencia no existe: {ruta}")
    mime = MIMES.get(ruta.suffix.lower())
    if not mime:
        raise Fallo(f"Formato de referencia no soportado ({ruta.suffix}). Usa jpg, png, webp o gif.")
    return f"data:{mime};base64,{base64.b64encode(ruta.read_bytes()).decode('ascii')}"


def post(ruta, cuerpo, clave):
    """POST JSON. Devuelve (status, texto, json o None). Errores de red -> Fallo con mensaje claro."""
    req = urllib.request.Request(
        BASE_URL + ruta, data=json.dumps(cuerpo).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://smart4ai.io/radar-tienda", "X-Title": "radar-tienda"})
    try:
        with urllib.request.urlopen(req, timeout=TIEMPO_MAXIMO) as r:
            texto = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8", "replace") if e.fp else ""
        status = e.code
    except urllib.error.URLError as e:
        raise Fallo(f"Error de red llamando a OpenRouter ({limpiar(e.reason, clave)}). ¿Hay internet?")
    except TimeoutError:
        raise Fallo(f"Tiempo de espera agotado ({TIEMPO_MAXIMO} s) llamando a OpenRouter.")
    try:
        datos = json.loads(texto)
    except ValueError:
        datos = None
    return status, texto, datos


def via_images(modelo, prompt, aspect, ref, clave):
    cuerpo = {"model": modelo, "prompt": prompt, "n": 1, "aspect_ratio": aspect}
    if ref:
        cuerpo["input_references"] = [{"type": "image_url", "image_url": {"url": ref}}]
    status, texto, datos = post("/images", cuerpo, clave)
    if not 200 <= status < 300:
        return {"error": (status, texto)}
    item = ((datos or {}).get("data") or [{}])[0]
    if not item.get("b64_json"):
        return {"sin_imagen": texto}
    return {"b64": item["b64_json"], "mime": item.get("media_type") or "image/png", "usage": (datos or {}).get("usage") or {}}


def via_chat(modelo, prompt, aspect, ref, clave):
    contenido = [{"type": "text", "text": prompt}]
    if ref:
        contenido.append({"type": "image_url", "image_url": {"url": ref}})
    cuerpo = {"model": modelo, "messages": [{"role": "user", "content": contenido}],
              "modalities": ["image", "text"], "usage": {"include": True}, "image_config": {"aspect_ratio": aspect}}
    status, texto, datos = post("/chat/completions", cuerpo, clave)
    if not 200 <= status < 300:
        return {"error": (status, texto)}
    msg = (((datos or {}).get("choices") or [{}])[0]).get("message") or {}
    url = (((msg.get("images") or [{}])[0]).get("image_url") or {}).get("url")
    if not url:
        return {"sin_imagen": msg.get("content") or texto}
    m = re.match(r"^data:([^;]+);base64,(.*)$", url, re.S)
    if not m:
        return {"sin_imagen": "La imagen no vino como data URL base64."}
    return {"b64": m.group(2), "mime": m.group(1), "usage": (datos or {}).get("usage") or {}}


def registrar_costo(fila):
    """Anexa a ~/radar-tienda/costos.csv. Fail-open: si falla, solo avisa por stderr."""
    try:
        ruta = entorno.carpeta_datos() / "costos.csv"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        nuevo = not ruta.exists()
        with open(ruta, "a", encoding="utf-8", newline="") as f:
            if nuevo:
                f.write("fecha,modelo,segundos,costo_usd,salida\n")
            salida = '"%s"' % str(fila["salida"]).replace('"', '""')
            f.write(f"{dt.datetime.now().isoformat(timespec='seconds')},{fila['modelo']},{fila['segundos']},"
                    f"{fila['costo_usd'] if fila['costo_usd'] is not None else ''},{salida}\n")
    except Exception as e:  # la imagen ya está guardada: no se frena por el registro
        print(f"[generar] No se pudo escribir costos.csv: {e}", file=sys.stderr)


def generar(a):
    if not a.prompt or not a.prompt.strip():
        raise Fallo('Falta --prompt "<texto>".')
    if not a.salida or not a.salida.strip():
        raise Fallo('Falta --salida "<ruta del archivo .png>".')
    if a.aspect not in ASPECTOS:
        raise Fallo(f"--aspect inválido ({a.aspect}). Usa uno de: {', '.join(ASPECTOS)}")
    clave, _ = entorno.leer_clave_openrouter()
    if not clave:
        raise Fallo("Falta la clave de OpenRouter (OPENROUTER_API_KEY) en la variable de entorno o en "
                    f"{entorno.ruta_env()}. Corre la configuración del plugin para guardarla sin pegarla en el chat. "
                    "Sin clave, la línea sigue con la foto que diste.", sin_clave=True)
    ref = preparar_ref(a.ref) if a.ref else None
    # Con --model se intenta ese primero; si da 429 o 5xx (p. ej. Gemini Pro sin cupo) se cae a la cadena Lite.
    modelos = [a.model] + [m for m in CADENA_DEFECTO if m != a.model] if a.model else list(CADENA_DEFECTO)
    salida = Path(a.salida).expanduser().resolve()
    t0 = time.time()
    saltados, res, modelo, via = [], None, None, a.api
    for modelo in modelos:
        llamar = via_chat if a.api == "chat" else via_images
        res, via = llamar(modelo, a.prompt, a.aspect, ref, clave), a.api
        if "error" in res and a.api == "images" and res["error"][0] in (404, 405):
            res, via = via_chat(modelo, a.prompt, a.aspect, ref, clave), "chat"
        s = res.get("error", (None,))[0]
        if s == 429 or (s is not None and 500 <= s < 600):
            saltados.append(f"{modelo}:{s}")
            continue
        break
    segundos = round(time.time() - t0, 1)
    extra = {"modelo": modelo, "segundos": segundos}
    if saltados:
        extra["saltados"] = saltados
    if "error" in res:
        raise Fallo(mensaje_http(res["error"][0], res["error"][1], clave), **extra)
    if "sin_imagen" in res:
        raise Fallo(f"La respuesta no trajo imagen (posible filtro de seguridad). Texto: {limpiar(res['sin_imagen'], clave)}", **extra)
    datos = base64.b64decode(res["b64"])
    if len(datos) < 100:
        raise Fallo("La imagen decodificada está vacía o corrupta.", **extra)
    aviso = None
    ext_real = EXT_REAL.get(res["mime"])
    if ext_real and salida.suffix.lower() != ext_real and not (ext_real == ".jpg" and salida.suffix.lower() == ".jpeg"):
        pedida = salida
        salida = salida.with_suffix(ext_real)
        aviso = f"El modelo devolvió {res['mime']}; se guardó como {ext_real} en vez de {pedida.name}."
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_bytes(datos)
    usage = res.get("usage") or {}
    costo, fuente = (usage.get("cost"), "usage.cost") if isinstance(usage.get("cost"), (int, float)) else (None, None)
    if costo is None:
        precio = PRECIO_TOKEN_SALIDA.get(modelo)
        tokens = usage.get("completion_tokens") or TOKENS_IMG
        costo = round(precio * tokens, 6) if precio else None
        fuente = "estimado (precio publicado)" if precio else "desconocido"
    fila = {"ok": True, "salida": str(salida), "bytes": len(datos), "modelo": modelo, "costo_usd": costo,
            "costo_fuente": fuente, "segundos": segundos, "formato": res["mime"], "via": via}
    if aviso:
        fila["aviso"] = aviso
    if saltados:
        fila["saltados"] = saltados
        if a.model and modelo != a.model:
            fila["aviso_modelo"] = f"{a.model} no respondió ({saltados[0].split(':')[-1]}); se usó {modelo}."
    registrar_costo(fila)
    return fila


def main(argv=None):
    entorno._consola_utf8()
    ap = argparse.ArgumentParser(description="Imagen de producto con Gemini vía OpenRouter (radar-tienda).",
                                 add_help=False)
    ap.add_argument("--prompt")
    ap.add_argument("--salida")
    ap.add_argument("--ref")
    ap.add_argument("--aspect", default="1:1")
    ap.add_argument("--model")
    ap.add_argument("--api", choices=["images", "chat"], default="images")
    ap.add_argument("--registro", help="Archivo .jsonl donde se anexa la línea de resultado (para el recibo)")
    ap.add_argument("--ayuda", "-h", "--help", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        print(json.dumps({"ok": False, "error": "Argumentos inválidos. Usa --ayuda para ver el uso."}, ensure_ascii=False))
        return 1
    if a.ayuda:
        print(__doc__)
        return 0
    try:
        resultado = generar(a)
        codigo = 0
    except Fallo as e:
        resultado = {"ok": False, "error": limpiar(str(e)), **e.extra}
        codigo = 1
    except Exception as e:  # nunca un traceback crudo: siempre una línea JSON
        resultado = {"ok": False, "error": f"Error inesperado: {limpiar(e)}"}
        codigo = 1
    linea = json.dumps(resultado, ensure_ascii=False)
    print(linea)
    if a.registro:
        try:
            Path(a.registro).expanduser().parent.mkdir(parents=True, exist_ok=True)
            with open(Path(a.registro).expanduser(), "a", encoding="utf-8") as f:
                f.write(linea + "\n")
        except OSError as e:
            print(f"[generar] No se pudo escribir el registro {a.registro}: {e}", file=sys.stderr)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
