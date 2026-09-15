#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sincronizar-plugins.py · copia las habilidades desde la fuente de verdad (top5-demo-skill/) a los dos plugins de este
repositorio, en una sola dirección (fuente → plugin). Nunca se edita una habilidad dentro del repositorio.

Uso:  python sincronizar-plugins.py            (desde cualquier carpeta)
      python sincronizar-plugins.py --version 1.0.1   (además escribe esa versión en los plugin.json y en marketplace.json)
"""
import os, shutil, sys, json, argparse
sys.stdout.reconfigure(encoding="utf-8")
AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE = os.path.join(os.path.dirname(AQUI), "top5-demo-skill")
PLUGINS = {
    "smart4ai-habilidades-1-comercial": ["arranque-comercial", "mi-voz", "cotizador", "precio-con-margen"],
    "smart4ai-habilidades-2-contenido": ["arranque-contenido", "post-voz-marca", "imagen-post", "video-post"],
}
IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "Thumbs.db", "*.zip")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--version")
    a = p.parse_args()
    for plugin, habilidades in PLUGINS.items():
        destino = os.path.join(AQUI, "plugins", plugin, "skills")
        os.makedirs(destino, exist_ok=True)
        for h in habilidades:
            src = os.path.join(FUENTE, h)
            dst = os.path.join(destino, h)
            if not os.path.isdir(src):
                print(f"  ✗ no existe la fuente {src}"); continue
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=IGNORAR)
            n = sum(len(f) for _, _, f in os.walk(dst))
            print(f"  ✓ {plugin}/skills/{h} ({n} archivos)")
        if a.version:
            pj = os.path.join(AQUI, "plugins", plugin, ".claude-plugin", "plugin.json")
            d = json.load(open(pj, encoding="utf-8")); d["version"] = a.version
            json.dump(d, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if a.version:
        mj = os.path.join(AQUI, ".claude-plugin", "marketplace.json")
        d = json.load(open(mj, encoding="utf-8"))
        for e in d["plugins"]:
            e["version"] = a.version
        json.dump(d, open(mj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"  versión {a.version} escrita en plugin.json y marketplace.json")
    print("plugins sincronizados desde top5-demo-skill/")


if __name__ == "__main__":
    main()
