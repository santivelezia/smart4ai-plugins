# -*- coding: utf-8 -*-
"""
demo_simulada.py · Ensayo de pantalla: simula una corrida completa llamando a estado.py
igual que lo hace el orquestador. Los datos son DE EJEMPLO (la corrida queda marcada "Ensayo").

  <python> demo_simulada.py                      -> ~60 s, para ensayar frente al proyector
  <python> demo_simulada.py --rapido             -> ~5 s, para probar que todo funciona
  <python> demo_simulada.py --abrir              -> además abre el tablero en el navegador (Windows o Mac)
  <python> demo_simulada.py --carpeta "<ruta>"   -> escribe en otra carpeta

Por defecto escribe en la carpeta de datos del usuario (~/radar-tienda/demo), nunca dentro del plugin.
Después de cada paso verifica que estado.json se lea y que tablero.html exista y esté completo;
si algo falla, para y dice en qué paso.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

AQUI = os.path.dirname(os.path.abspath(__file__))
ESTADO = os.path.join(AQUI, "estado.py")
sys.path.insert(0, os.path.join(AQUI, "..", "comun"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Imágenes de ejemplo: URL https que no existen a propósito (el tablero oculta la imagen que no carga).
IMG = "https://example.com/radar-tienda-demo/imagen-de-ejemplo.jpg"

# (segundos de espera ANTES del paso, argumentos para estado.py)
GUION = [
    (0, ["iniciar", "--producto", "Corrector de postura con sensor", "--modo", "exprés", "--ensayo"]),
    (2, ["estacion", "radar", "en_curso", "--detalle", "Buscando anuncios activos en Meta Ads Library"]),
    (4, ["log", "Meta Ads Library: consultando anuncios en Colombia"]),
    (4, ["dato", "anuncios_activos", "143"]),
    (1, ["dato", "anunciantes", "27"]),
    (3, ["log", "Competencia: 6 tiendas revisadas, precios entre 79.900 y 119.900"]),
    (3, ["dato", "dolor_1", "Dolor de espalda tras 8 horas frente al computador"]),
    (1, ["dato", "dolor_2", "Fajas incómodas que se notan bajo la ropa"]),
    (1, ["dato", "dolor_3", "Olvidar corregir la postura durante el día"]),
    (2, ["dato", "angulo", "Vibra cuando te encorvas: un recordatorio, no una faja"]),
    (2, ["dato", "precio_1", "89900"]),
    (0.5, ["dato", "precio_2", "159900"]),
    (0.5, ["dato", "precio_3", "209900"]),
    (1, ["dato", "margen", "42%"]),
    (0.5, ["dato", "cpa_equilibrio", "37700"]),
    (0.5, ["dato", "costo", "28000"]),
    (1.5, ["dato", "confianza", "Media-alta"]),
    (0.5, ["dato", "veredicto", "PROBAR"]),
    (0, ["estacion", "radar", "ok", "--detalle", "Veredicto: PROBAR · 143 anuncios activos"]),
    (1.5, ["estacion", "puente", "en_curso", "--detalle", "Revisando precios .900, combos y promesas"]),
    (3, ["estacion", "puente", "ok", "--detalle", "Brief válido: 0 errores"]),
    (1, ["estacion", "fotos", "en_curso", "--detalle", "Generando imagen principal"]),
    (3, ["dato", "imagen_1", IMG]),
    (2, ["dato", "imagen_2", IMG]),
    (0, ["estacion", "fotos", "ok", "--detalle", "2 imágenes listas"]),
    (1, ["estacion", "tienda", "en_curso", "--detalle", "Creando producto con variantes 1/2/3 en borrador"]),
    (4, ["log", "Shopify: producto creado en borrador con etiqueta de prueba"]),
    (2, ["dato", "url_preview", "https://example.com"]),
    (0, ["estacion", "tienda", "ok", "--detalle", "Producto en borrador · colección de la configuración"]),
    (1, ["estacion", "anuncio", "en_curso", "--detalle", "Escribiendo 3 textos con el ángulo ganador"]),
    (4, ["log", "Anuncio: 3 textos listos y validados (sin publicar)"]),
    (1, ["estacion", "anuncio", "ok", "--detalle", "3 textos, sin publicar"]),
    (0, ["recibo", "--nivel", "Completo", "--consultas", "24", "--proveedor", "ensayo (sin imágenes reales)"]),
]


def carpeta_por_defecto():
    try:
        import entorno
        return str(entorno.carpeta_datos() / "demo")
    except Exception:
        return str(Path.home() / "radar-tienda" / "demo")


def verificar(carpeta, paso, args):
    """Comprueba que el paso dejó estado.json legible y tablero.html completo."""
    with open(os.path.join(carpeta, "estado.json"), encoding="utf-8") as f:
        est = json.load(f)
    with open(os.path.join(carpeta, "tablero.html"), encoding="utf-8") as f:
        h = f.read()
    errores = []
    if not h.rstrip().endswith("</html>"):
        errores.append("tablero.html incompleto")
    if est["producto"] not in h:
        errores.append("el producto no aparece en el tablero")
    if args[0] == "estacion" and est["estaciones"][args[1]]["estado"] != args[2]:
        errores.append("la estación no quedó en %s" % args[2])
    if args[0] == "dato" and est["datos"].get(args[1]) != args[2]:
        errores.append("el dato %s no quedó guardado" % args[1])
    if args[0] == "recibo" and not os.path.exists(os.path.join(carpeta, "recibo.md")):
        errores.append("no se escribió recibo.md")
    if errores:
        raise RuntimeError("Paso %d (%s): %s" % (paso, " ".join(args[:3]), "; ".join(errores)))
    return est


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rapido", action="store_true", help="Divide los tiempos por 12 (~5 s en total)")
    p.add_argument("--abrir", action="store_true", help="Abre el tablero en el navegador al empezar")
    p.add_argument("--carpeta", help="Dónde escribir la demo (por defecto ~/radar-tienda/demo)")
    a = p.parse_args()
    carpeta = os.path.abspath(os.path.expanduser(a.carpeta or carpeta_por_defecto()))
    factor = 1 / 12 if a.rapido else 1.0
    os.makedirs(carpeta, exist_ok=True)
    t0 = time.time()
    est = {}
    for i, (espera, args) in enumerate(GUION, 1):
        time.sleep(espera * factor)
        r = subprocess.run([sys.executable, ESTADO, carpeta] + args, capture_output=True, text=True,
                           encoding="utf-8")
        if r.returncode != 0 or r.stderr.strip():
            print("FALLA en el paso %d: %s\n%s%s" % (i, args, r.stdout, r.stderr))
            return 1
        est = verificar(carpeta, i, args)
        print("[%5.1fs] paso %2d/%d OK · %s" % (time.time() - t0, i, len(GUION), " ".join(args[:3])))
        if i == 1 and a.abrir:
            try:
                webbrowser.open(Path(carpeta, "tablero.html").resolve().as_uri())
            except Exception as e:  # abrir es adorno
                print("Aviso: no se pudo abrir el navegador (%s)" % e)
    print("Corrida simulada completa en %.1f s · terminado=%s" % (time.time() - t0, est.get("terminado")))
    print("Tablero: %s" % os.path.join(carpeta, "tablero.html"))
    return 0 if est.get("terminado") else 1


if __name__ == "__main__":
    sys.exit(main())
