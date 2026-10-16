# -*- coding: utf-8 -*-
"""
entorno.py · Detecta el equipo y lee la configuración del plugin radar-tienda.

Lo usan todos los scripts del plugin (puente, imágenes, tablero) y la skill de primer uso.
Solo librería estándar de Python. Funciona igual en Windows, Mac y Linux.

Uso desde la terminal:
    <python> entorno.py                      -> resumen legible (SO, intérprete, carpetas, clave sí/no)
    <python> entorno.py --json               -> lo mismo en JSON (para que la skill lo lea)
    <python> entorno.py --guardar clave=valor [clave=valor ...]   -> actualiza config.json
    <python> entorno.py --nueva-corrida "<nombre del producto>"   -> crea la carpeta de la corrida e imprime su ruta
    <python> entorno.py --abrir "<ruta de un archivo>"            -> lo abre en el navegador (webbrowser)

Dónde vive cada cosa (en la carpeta del usuario, nunca dentro del plugin):
    ~/.radar-tienda/config.json   configuración detectada y elegida (sin secretos)
    ~/.radar-tienda/.env          clave de OpenRouter (línea OPENROUTER_API_KEY=...), opcional
    ~/radar-tienda/corridas/      una carpeta por corrida (se puede cambiar con carpeta_corridas)
    ~/radar-tienda/costos.csv     registro de costos de imágenes

Para pruebas: la variable RADAR_TIENDA_CONFIG_DIR cambia la carpeta ~/.radar-tienda.
La clave NUNCA se imprime: solo se dice si está o no.
"""

import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import unicodedata
import webbrowser
from pathlib import Path

# Valores por defecto (los mismos que declara plugin.json en userConfig).
DEFAULTS = {
    "pais": "CO",
    "coleccion": "radar",
    "vendedor": "Radar",
    "etiqueta_prueba": "radar-prueba",
    "codigo_descuento": "",
    "pago_contra_entrega": False,
    "carpeta_corridas": "~/radar-tienda/corridas",
    "proveedor_imagenes": "conector",
    "titulo_tablero": "Radar a Tienda",
}
PROVEEDORES_IMAGENES = ("conector", "openrouter", "mis-fotos")
CLAVES_BOOLEANAS = {"pago_contra_entrega"}
VERDADERO = {"si", "sí", "true", "1", "yes", "y", "s", "verdadero", "activo"}


def _consola_utf8():
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def a_booleano(valor):
    """'sí', 'true', True, 1 -> True. Todo lo demás -> False."""
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in VERDADERO


def carpeta_config():
    """~/.radar-tienda (o RADAR_TIENDA_CONFIG_DIR en pruebas)."""
    otra = os.environ.get("RADAR_TIENDA_CONFIG_DIR")
    return Path(otra).expanduser() if otra else Path.home() / ".radar-tienda"


def ruta_config():
    return carpeta_config() / "config.json"


def ruta_env():
    return carpeta_config() / ".env"


def leer_config(ruta=None):
    """Configuración = valores por defecto + lo guardado en config.json. Nunca falla:
    si el archivo no existe o está dañado, devuelve los valores por defecto y anota el motivo."""
    cfg = dict(DEFAULTS)
    ruta = Path(ruta) if ruta else ruta_config()
    cfg["_origen"] = "valores por defecto"
    if ruta.is_file():
        try:
            guardado = json.loads(ruta.read_text(encoding="utf-8-sig"))
            if isinstance(guardado, dict):
                cfg.update(guardado)
                cfg["_origen"] = str(ruta)
        except (OSError, ValueError) as e:
            cfg["_origen"] = "valores por defecto (config.json ilegible: %s)" % e
    for k in CLAVES_BOOLEANAS:
        cfg[k] = a_booleano(cfg.get(k))
    if cfg.get("proveedor_imagenes") not in PROVEEDORES_IMAGENES:
        cfg["proveedor_imagenes"] = DEFAULTS["proveedor_imagenes"]
    # Un valor vacío o sin sustituir (por ejemplo "${user_config.vendedor}") vuelve al valor por defecto.
    for k, v in DEFAULTS.items():
        if k == "codigo_descuento":
            continue
        if isinstance(cfg.get(k), str) and (not cfg[k].strip() or "${" in cfg[k]):
            cfg[k] = v
    if isinstance(cfg.get("codigo_descuento"), str) and "${" in cfg["codigo_descuento"]:
        cfg["codigo_descuento"] = ""
    return cfg


def guardar_config(cambios, ruta=None):
    """Mezcla los cambios con lo que ya hay en config.json y lo guarda (sin secretos)."""
    ruta = Path(ruta) if ruta else ruta_config()
    actual = {}
    if ruta.is_file():
        try:
            actual = json.loads(ruta.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            actual = {}
    for k, v in cambios.items():
        if "key" in k.lower() or "clave_api" in k.lower() or "token" in k.lower():
            raise ValueError("config.json no guarda claves ni tokens (%s). La clave va en %s" % (k, ruta_env()))
        actual[k] = a_booleano(v) if k in CLAVES_BOOLEANAS else v
    actual["actualizado"] = dt.datetime.now().isoformat(timespec="seconds")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(actual, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ruta)
    return actual


def leer_clave_openrouter():
    """La clave sale de la variable de entorno OPENROUTER_API_KEY o de ~/.radar-tienda/.env.
    Devuelve (clave o None, de dónde salió). Nunca la imprime."""
    clave = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if clave:
        return clave, "variable de entorno OPENROUTER_API_KEY"
    ruta = ruta_env()
    try:
        for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
            t = linea.strip()
            if not t or t.startswith("#") or "=" not in t:
                continue
            k, v = t.split("=", 1)
            if k.strip() == "OPENROUTER_API_KEY":
                v = v.strip().strip('"').strip("'")
                if v:
                    return v, str(ruta)
    except OSError:
        pass
    return None, None


def sistema():
    s = platform.system()
    return {"Darwin": "macOS", "Windows": "Windows"}.get(s, s or "desconocido")


def _version_de(cmd):
    """Corre '<cmd> --version' con tope de 5 s. Devuelve el texto si es Python 3; si no, None.
    (En Windows, 'python' puede ser un atajo de la Microsoft Store que no es Python de verdad.)"""
    try:
        r = subprocess.run(cmd + ["--version"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    salida = (r.stdout + r.stderr).strip()
    return salida if r.returncode == 0 and salida.startswith("Python 3") else None


def detectar_python():
    """Prueba en orden py -> python3 -> python. Devuelve la lista de los que funcionan y el recomendado."""
    candidatos = [("py", ["py", "-3"]), ("python3", ["python3"]), ("python", ["python"])]
    vistos = []
    for nombre, cmd in candidatos:
        if not shutil.which(cmd[0]):
            continue
        v = _version_de(cmd)
        if v:
            vistos.append({"comando": " ".join(cmd) if nombre == "py" else nombre, "version": v})
    recomendado = vistos[0]["comando"] if vistos else None
    return {"funcionan": vistos, "recomendado": recomendado, "este": sys.executable,
            "version_este": platform.python_version()}


def detectar_node():
    if not shutil.which("node"):
        return None
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def carpeta_corridas(cfg=None):
    cfg = cfg or leer_config()
    return Path(os.path.expandvars(str(cfg.get("carpeta_corridas") or DEFAULTS["carpeta_corridas"]))).expanduser()


def carpeta_datos(cfg=None):
    """Carpeta madre de las corridas (~/radar-tienda): ahí van costos.csv y la demo."""
    return carpeta_corridas(cfg).parent


def slug(texto, maximo=40):
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return (s[:maximo].rstrip("-")) or "producto"


def nueva_corrida(nombre, cfg=None):
    """Crea <carpeta_corridas>/AAAA-MM-DD_HHMM_<slug> (sin pisar una existente) y devuelve la ruta."""
    base = carpeta_corridas(cfg)
    nombre_carpeta = "%s_%s" % (dt.datetime.now().strftime("%Y-%m-%d_%H%M"), slug(nombre))
    ruta = base / nombre_carpeta
    n = 2
    while ruta.exists():
        ruta = base / ("%s-%d" % (nombre_carpeta, n))
        n += 1
    ruta.mkdir(parents=True)
    return ruta


def abrir(ruta):
    """Abre un archivo local en el navegador por defecto (Windows, Mac o Linux)."""
    p = Path(ruta).expanduser().resolve()
    if not p.exists():
        return False, "no existe: %s" % p
    try:
        ok = webbrowser.open(p.as_uri())
        return bool(ok), ("abierto" if ok else "el sistema no tiene navegador registrado; ábrelo a mano: %s" % p)
    except Exception as e:  # nunca frenar la línea por no poder abrir una pestaña
        return False, "no se pudo abrir (%s); ábrelo a mano: %s" % (e, p)


def resumen():
    cfg = leer_config()
    clave, origen = leer_clave_openrouter()
    py = detectar_python()
    return {
        "sistema": sistema(),
        "version_sistema": platform.release(),
        "python": py,
        "python_recomendado": py["recomendado"] or sys.executable,
        "node": detectar_node(),
        "carpeta_config": str(carpeta_config()),
        "config_existe": ruta_config().is_file(),
        "carpeta_corridas": str(carpeta_corridas(cfg)),
        "carpeta_datos": str(carpeta_datos(cfg)),
        "clave_openrouter": "presente" if clave else "no encontrada",
        "clave_openrouter_origen": origen,
        "config": {k: v for k, v in cfg.items()},
    }


def main(argv=None):
    _consola_utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv == ["--json"]:
        r = resumen()
        if argv == ["--json"]:
            print(json.dumps(r, ensure_ascii=False, indent=2))
            return 0
        print("Sistema: %s %s" % (r["sistema"], r["version_sistema"]))
        print("Python que funciona: %s" % (", ".join(x["comando"] for x in r["python"]["funcionan"]) or "(solo este: %s)" % sys.executable))
        print("Intérprete recomendado (<python>): %s" % r["python_recomendado"])
        print("Node: %s" % (r["node"] or "no instalado (no hace falta)"))
        print("Configuración: %s (%s)" % (r["carpeta_config"], "existe" if r["config_existe"] else "aún no existe"))
        print("Carpeta de corridas: %s" % r["carpeta_corridas"])
        print("Clave de OpenRouter: %s" % r["clave_openrouter"])
        return 0
    if argv[0] == "--guardar":
        cambios = {}
        for par in argv[1:]:
            if "=" not in par:
                print("ERROR: usa clave=valor (llegó %r)" % par)
                return 2
            k, v = par.split("=", 1)
            cambios[k.strip()] = v.strip()
        try:
            guardado = guardar_config(cambios)
        except (ValueError, OSError) as e:
            print("ERROR: %s" % e)
            return 2
        print(json.dumps({"ok": True, "config": str(ruta_config()), "guardado": guardado}, ensure_ascii=False))
        return 0
    if argv[0] == "--nueva-corrida" and len(argv) >= 2:
        try:
            print(nueva_corrida(" ".join(argv[1:])))
        except OSError as e:
            print("ERROR: no se pudo crear la carpeta de la corrida: %s" % e)
            return 2
        return 0
    if argv[0] == "--abrir" and len(argv) >= 2:
        ok, msg = abrir(argv[1])
        print(("OK · " if ok else "AVISO · ") + msg)
        return 0  # abrir es adorno: nunca devuelve error
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
