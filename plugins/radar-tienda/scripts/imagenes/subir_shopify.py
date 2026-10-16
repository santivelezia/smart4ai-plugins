# -*- coding: utf-8 -*-
"""
subir_shopify.py · Sube una imagen local a la URL temporal que entrega Shopify (stagedUploadsCreate
con httpMethod PUT). Reemplaza el comando de PowerShell que solo servía en Windows: esto es Python
puro (urllib) y corre igual en Windows y Mac.

Paso a paso (lo hace el orquestador):
  1. Conector de Shopify: stagedUploadsCreate con {filename, mimeType, resource: "IMAGE", httpMethod: "PUT"}
     -> devuelve url, resourceUrl y parameters.
  2. <python> subir_shopify.py --url "<url>" --archivo "<ruta de la imagen>" [--mime image/png]
                               [--parametros-archivo "<parameters.json>"]  (o --parametros '<JSON>')
     En PowerShell 5.1 las comillas dobles dentro de un argumento se pierden: usa --parametros-archivo.
     -> imprime UNA línea JSON {"ok": true, "status": 200, "bytes": ...}
  3. resourceUrl va en "images" de create-product (Shopify copia la imagen a su CDN).

Nunca imprime la URL firmada completa (lleva credenciales temporales): solo su dominio.
Códigos de salida: 0 = subida (HTTP 2xx) · 1 = falló (con mensaje claro) · 2 = argumentos.
Probado en el proyecto original (2026-10-16) con Content-Type igual al mimeType: respondió 200.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MIMES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
TIEMPO_MAXIMO = 120
# Parámetros de Shopify que se convierten en cabeceras de la petición PUT.
# content_type -> Content-Type (probado). acl -> x-goog-acl (no verificado: solo si Shopify lo devuelve).
PARAMETRO_A_CABECERA = {"content_type": "Content-Type", "acl": "x-goog-acl"}


class Fallo(Exception):
    pass


def leer_parametros(texto):
    """Acepta [{"name":..,"value":..}] (forma de Shopify) o {"nombre": "valor"}."""
    if not texto:
        return {}
    try:
        datos = json.loads(texto)
    except ValueError as e:
        raise Fallo(f"--parametros no es JSON válido: {e}")
    if isinstance(datos, dict):
        return {str(k): str(v) for k, v in datos.items()}
    if isinstance(datos, list):
        return {str(x.get("name")): str(x.get("value")) for x in datos if isinstance(x, dict) and x.get("name")}
    raise Fallo("--parametros debe ser una lista [{name, value}] o un objeto {nombre: valor}.")


def armar_peticion(url, ruta_archivo, mime=None, parametros=None):
    """Arma (sin enviar) la petición PUT. Se prueba sin red en las pruebas unitarias."""
    partes = urllib.parse.urlparse(str(url or ""))
    if partes.scheme != "https" or not partes.netloc:
        raise Fallo("La URL de subida debe ser https (la que devuelve stagedUploadsCreate).")
    ruta = Path(ruta_archivo).expanduser()
    if not ruta.is_file():
        raise Fallo(f"No existe el archivo a subir: {ruta}")
    datos = ruta.read_bytes()
    if not datos:
        raise Fallo(f"El archivo está vacío: {ruta}")
    tipo = mime or MIMES.get(ruta.suffix.lower())
    if not tipo:
        raise Fallo(f"No se reconoce el tipo de imagen ({ruta.suffix}). Pasa --mime image/png o image/jpeg.")
    cabeceras = {"Content-Type": tipo, "Content-Length": str(len(datos))}
    for nombre, valor in (parametros or {}).items():
        cab = PARAMETRO_A_CABECERA.get(nombre)
        if cab == "Content-Type" and valor and valor != tipo:
            raise Fallo(f"El mimeType del archivo ({tipo}) no coincide con el que firmó Shopify ({valor}). "
                        "Pide la URL otra vez con el mimeType correcto.")
        if cab and cab != "Content-Type":
            cabeceras[cab] = valor
    return urllib.request.Request(url, data=datos, method="PUT", headers=cabeceras)


def subir(peticion):
    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_MAXIMO) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "replace")[:300] if e.fp else ""
        return e.code, cuerpo
    except urllib.error.URLError as e:
        raise Fallo(f"Error de red subiendo a Shopify ({e.reason}).")
    except TimeoutError:
        raise Fallo(f"Tiempo de espera agotado ({TIEMPO_MAXIMO} s) subiendo a Shopify.")


def main(argv=None):
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--url")
    ap.add_argument("--archivo")
    ap.add_argument("--mime")
    ap.add_argument("--parametros")
    ap.add_argument("--parametros-archivo", dest="parametros_archivo",
                    help="Archivo .json con los parameters (más seguro que --parametros en PowerShell 5.1)")
    ap.add_argument("--ayuda", "-h", "--help", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        print(json.dumps({"ok": False, "error": "Argumentos inválidos. Usa --ayuda."}, ensure_ascii=False))
        return 2
    if a.ayuda:
        print(__doc__)
        return 0
    if not a.url or not a.archivo:
        print(json.dumps({"ok": False, "error": 'Faltan --url "<url de stagedUploadsCreate>" y --archivo "<imagen>".'},
                         ensure_ascii=False))
        return 2
    try:
        texto_parametros = a.parametros
        if a.parametros_archivo:
            try:
                texto_parametros = Path(a.parametros_archivo).expanduser().read_text(encoding="utf-8-sig")
            except OSError as e:
                raise Fallo(f"No se pudo leer --parametros-archivo: {e}")
        pet = armar_peticion(a.url, a.archivo, a.mime, leer_parametros(texto_parametros))
        status, cuerpo = subir(pet)
    except Fallo as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1
    dominio = urllib.parse.urlparse(a.url).netloc
    resultado = {"ok": 200 <= status < 300, "status": status, "bytes": len(pet.data), "destino": dominio,
                 "mime": pet.get_header("Content-type")}
    if not resultado["ok"]:
        resultado["error"] = (f"Shopify rechazó la subida (HTTP {status}). Si es 403, la URL venció o el mimeType no "
                              f"coincide: pide otra con stagedUploadsCreate. Detalle: {cuerpo}")
    print(json.dumps(resultado, ensure_ascii=False))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
