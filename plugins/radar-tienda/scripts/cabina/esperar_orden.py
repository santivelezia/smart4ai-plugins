# -*- coding: utf-8 -*-
"""
esperar_orden.py · Claude espera aquí la siguiente orden de la Cabina Radar.

Uso (<python> = py, python3 o python):
  <python> esperar_orden.py [--timeout 1500]
      Bloquea hasta que exista orden.json (mira cada 1 s). La pasa a orden_en_curso.json,
      imprime la orden en UNA línea JSON y sale con 0. Si vence el tiempo: imprime SIN_ORDEN y sale con 2.
      Si ya había una orden en curso sin terminar, la devuelve de nuevo (Claude la retoma).
  <python> esperar_orden.py --terminar "<resultado en una frase>" [--veredicto "<veredicto>"] [--producto "<nombre>"]
      Marca la orden en curso como hecha: la registra en historial.jsonl con su tiempo y veredicto
      (si no se da, se lee de la corrida activa) y la archiva en hechas/. Imprime una línea JSON.

Carpeta: ~/radar-tienda/cabina/ (o RADAR_CABINA_DIR). Solo la librería estándar.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import servidor  # noqa: E402  (mismas rutas y utilidades que la página)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def latido():
    """Le avisa a la página que Claude está escuchando (marca de tiempo en escuchando.txt)."""
    try:
        servidor.ruta("escuchando.txt").write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def tomar_orden():
    """Si hay orden.json, la pasa a orden_en_curso.json y la devuelve. Si no, None."""
    p = servidor.ruta("orden.json")
    if not p.exists():
        return None
    orden = servidor.leer_json(p)
    if not isinstance(orden, dict):
        return None  # a medio escribir: se reintenta en el siguiente segundo
    orden["tomada_ms"] = servidor.ahora_ms()
    servidor.escribir_json(servidor.ruta("orden_en_curso.json"), orden)
    try:
        os.remove(p)
    except OSError:
        pass
    return orden


def esperar(timeout, cada=1.0):
    en_curso = servidor.ruta("orden_en_curso.json")
    if en_curso.exists():  # Claude se cortó a mitad: se retoma la misma orden
        o = servidor.leer_json(en_curso)
        if isinstance(o, dict):
            o["retomada"] = True
            return o
    fin = time.time() + max(0, timeout)
    while True:
        latido()
        o = tomar_orden()
        if o:
            return o
        if time.time() >= fin:
            return None
        time.sleep(cada)


def veredicto_de_corrida():
    try:
        est = servidor.leer_estado_corrida() or {}
        return str((est.get("datos") or {}).get("veredicto") or "")
    except Exception:
        return ""


def terminar(resultado, veredicto=None, producto=None):
    p = servidor.ruta("orden_en_curso.json")
    orden = servidor.leer_json(p) if p.exists() else None
    if not isinstance(orden, dict):
        return {"ok": False, "error": "No hay una orden en curso."}
    fin = servidor.ahora_ms()
    ini = orden.get("tomada_ms") or orden.get("creada_ms") or fin
    tipo = orden.get("tipo", "")
    if producto is None:
        if tipo == "correr":
            producto = (orden.get("producto") or {}).get("nombre", "")
        elif tipo == "comparar":
            producto = "Comparación: " + ", ".join(x.get("nombre", "") for x in orden.get("productos") or [])
        else:
            producto = str(orden.get("producto") or "")
    if veredicto is None:
        veredicto = veredicto_de_corrida() if tipo == "correr" else ""
    fila = {"id": orden.get("id"), "tipo": tipo, "modo": orden.get("modo", ""), "producto": producto,
            "inicio_ms": ini, "fin_ms": fin, "segundos": max(0, (fin - ini) // 1000),
            "veredicto": veredicto or "", "resultado": (resultado or "")[:300],
            "hora_fin": dt.datetime.now().strftime("%H:%M")}
    with open(servidor.ruta("historial.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    destino = servidor.carpeta_cabina() / "hechas"
    destino.mkdir(exist_ok=True)
    orden["resultado"] = fila["resultado"]
    servidor.escribir_json(destino / ("%s.json" % (orden.get("id") or fin)), orden)
    try:
        os.remove(p)
    except OSError:
        pass
    return {"ok": True, "registrada": fila}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Espera o termina órdenes de la Cabina Radar")
    ap.add_argument("--timeout", type=float, default=1500, help="Segundos máximos de espera (por defecto 1500)")
    ap.add_argument("--terminar", metavar="RESULTADO")
    ap.add_argument("--veredicto")
    ap.add_argument("--producto")
    a = ap.parse_args(argv)
    if a.terminar is not None:
        r = terminar(a.terminar, a.veredicto, a.producto)
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r.get("ok") else 1
    o = esperar(a.timeout)
    if not o:
        print("SIN_ORDEN")
        return 2
    print(json.dumps(o, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
