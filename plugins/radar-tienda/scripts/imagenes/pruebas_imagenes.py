# -*- coding: utf-8 -*-
"""
pruebas_imagenes.py · Pruebas de generar.py y subir_shopify.py, SIN gastar dinero.
Uso:  <python> pruebas_imagenes.py          (sin red: errores claros y armado de la petición PUT)
      <python> pruebas_imagenes.py --red    (además: una llamada real a OpenRouter con una clave FALSA -> 401;
                                             no cuesta nada porque OpenRouter rechaza antes de generar)
Usa una carpeta de configuración temporal y vacía: nunca lee la clave real del usuario.
"""
import json
import os
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
GENERAR = os.path.join(AQUI, "generar.py")
SUBIR = os.path.join(AQUI, "subir_shopify.py")
sys.path.insert(0, AQUI)
import subir_shopify  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TMP = tempfile.mkdtemp(prefix="radar tienda pruebas imagenes ")
CFG = os.path.join(TMP, "config vacia")
os.makedirs(CFG, exist_ok=True)
resultados = []


def chequear(nombre, ok, detalle=""):
    resultados.append((nombre, bool(ok), detalle))


def correr(script, *args, clave=None):
    env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
    env.update(PYTHONIOENCODING="utf-8", RADAR_TIENDA_CONFIG_DIR=CFG)
    if clave:
        env["OPENROUTER_API_KEY"] = clave
    p = subprocess.run([sys.executable, script] + list(args), capture_output=True, text=True, encoding="utf-8", env=env)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def json_de(salida):
    try:
        return json.loads(salida.splitlines()[-1])
    except (ValueError, IndexError):
        return {}


salida_png = os.path.join(TMP, "img con espacios", "hero.png")

# --- generar.py: errores claros, código 1, una línea JSON ---
rc, out, err = correr(GENERAR, "--prompt", "producto en fondo blanco", "--salida", salida_png)
j = json_de(out)
print("sin clave:", out)
chequear("generar: sin clave -> JSON ok:false, código 1, mensaje que explica qué hacer",
         rc == 1 and j.get("ok") is False and "Falta la clave de OpenRouter" in j.get("error", "")
         and "foto" in j.get("error", "") and j.get("sin_clave") is True, out)
rc, out, err = correr(GENERAR, "--salida", salida_png)
j = json_de(out)
print("sin prompt:", out)
chequear("generar: sin prompt -> error claro", rc == 1 and "Falta --prompt" in j.get("error", ""), out)
rc, out, err = correr(GENERAR, "--prompt", "x", "--salida", salida_png, "--aspect", "7:3")
j = json_de(out)
print("aspecto inválido:", out)
chequear("generar: aspecto inválido -> error claro con la lista", rc == 1 and "--aspect inválido (7:3)" in j.get("error", ""), out)
rc, out, err = correr(GENERAR, "--prompt", "x", "--salida", salida_png, "--ref", os.path.join(TMP, "no existe.png"),
                      clave="sk-or-v1-falsa-para-prueba-0000000000")
j = json_de(out)
chequear("generar: referencia inexistente -> error claro (antes de llamar a la red)",
         rc == 1 and "no existe" in j.get("error", ""), out)
chequear("generar: la clave falsa no aparece en la salida", "falsa-para-prueba" not in out + err, out)
rc, out, err = correr(GENERAR, "--ayuda")
chequear("generar: --ayuda muestra el uso", rc == 0 and "OPENROUTER_API_KEY" in out)
rc, out, err = correr(GENERAR, "--opcion-que-no-existe")
chequear("generar: argumento desconocido -> JSON ok:false", rc == 1 and json_de(out).get("ok") is False, out)
chequear("generar: no se creó ninguna imagen en los errores", not os.path.exists(salida_png))

# --- subir_shopify.py ---
rc, out, err = correr(SUBIR, "--ayuda")
print("subir --ayuda (primeras líneas):", "\n".join(out.splitlines()[:3]))
chequear("subir: --ayuda muestra el paso a paso", rc == 0 and "stagedUploadsCreate" in out)
imagen = os.path.join(TMP, "img con espacios", "foto prueba.png")
os.makedirs(os.path.dirname(imagen), exist_ok=True)
with open(imagen, "wb") as f:
    f.write(b"\x89PNG\r\n\x1a\n" + b"0" * 500)
pet = subir_shopify.armar_peticion("https://shopify-staged-uploads.storage.googleapis.com/tmp/x?firma=abc", imagen,
                                   parametros={"content_type": "image/png", "acl": "private"})
chequear("subir: petición PUT armada sin red (método, cabeceras, cuerpo)",
         pet.get_method() == "PUT" and pet.get_header("Content-type") == "image/png"
         and pet.get_header("Content-length") == "508" and len(pet.data) == 508
         and pet.get_header("X-goog-acl") == "private", dict(pet.header_items()))
pet2 = subir_shopify.armar_peticion("https://ejemplo.com/subida", imagen)
chequear("subir: mimeType deducido de la extensión", pet2.get_header("Content-type") == "image/png")
for nombre, args, debe in [
    ("subir: URL http (no https) -> error", ("http://inseguro.com/x", imagen), "https"),
    ("subir: archivo inexistente -> error", ("https://ejemplo.com/x", os.path.join(TMP, "no.png")), "No existe"),
    ("subir: extensión desconocida -> pide --mime", ("https://ejemplo.com/x", __file__), "--mime"),
]:
    try:
        subir_shopify.armar_peticion(*args)
        chequear(nombre, False, "no lanzó error")
    except subir_shopify.Fallo as e:
        chequear(nombre, debe in str(e), str(e))
try:
    subir_shopify.armar_peticion("https://ejemplo.com/x", imagen, "image/jpeg", {"content_type": "image/png"})
    chequear("subir: mimeType distinto al firmado -> error", False)
except subir_shopify.Fallo as e:
    chequear("subir: mimeType distinto al firmado -> error", "no coincide" in str(e), str(e))
rc, out, err = correr(SUBIR, "--archivo", imagen)
chequear("subir: sin --url -> código 2 con mensaje", rc == 2 and "Faltan --url" in out, out)
rc, out, err = correr(SUBIR, "--url", "https://ejemplo.com/x", "--archivo", imagen,
                      "--parametros-archivo", os.path.join(TMP, "no existe.json"))
chequear("subir: --parametros-archivo inexistente -> error claro antes de la red",
         rc == 1 and "No se pudo leer --parametros-archivo" in out, out)
ruta_param = os.path.join(TMP, "img con espacios", "parametros 1.json")
with open(ruta_param, "w", encoding="utf-8") as f:
    json.dump([{"name": "content_type", "value": "image/jpeg"}], f)
rc, out, err = correr(SUBIR, "--url", "https://ejemplo.com/x", "--archivo", imagen, "--parametros-archivo", ruta_param)
chequear("subir: --parametros-archivo se lee (y detecta mimeType distinto al firmado)",
         rc == 1 and "no coincide" in out, out)
chequear("subir: parámetros en forma de Shopify [{name,value}]",
         subir_shopify.leer_parametros('[{"name":"content_type","value":"image/png"}]') == {"content_type": "image/png"})

# --- Con red: clave falsa -> 401 claro (no gasta) ---
if "--red" in sys.argv:
    rc, out, err = correr(GENERAR, "--prompt", "producto en fondo blanco", "--salida", salida_png,
                          clave="sk-or-v1-clave-falsa-de-prueba-000000000000000000")
    j = json_de(out)
    print("clave falsa (red):", out)
    chequear("generar (red): clave falsa -> 401 claro, código 1, sin imagen",
             rc == 1 and j.get("error", "").startswith("401") and not os.path.exists(salida_png), out)
    chequear("generar (red): la clave falsa no aparece en la salida", "clave-falsa-de-prueba" not in out + err)

print("=== Resultados ===")
for nombre, ok, detalle in resultados:
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}" + ("" if ok else f"  -> {detalle}"))
fallas = sum(1 for _, ok, _ in resultados if not ok)
print(f"\n{len(resultados) - fallas}/{len(resultados)} pruebas pasaron.")
sys.exit(1 if fallas else 0)
