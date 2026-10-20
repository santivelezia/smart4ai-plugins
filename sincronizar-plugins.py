#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sincronizar-plugins.py · copia las habilidades desde la fuente de verdad (top5-demo-skill/) a los dos plugins de este
repositorio, en una sola dirección (fuente → plugin). Nunca se edita una habilidad dentro del repositorio.

Uso:  python sincronizar-plugins.py            (desde cualquier carpeta)
      python sincronizar-plugins.py --version 1.0.1   (además escribe esa versión en los plugin.json y en marketplace.json)
      python sincronizar-plugins.py --solo radar-tienda   (copia el plugin completo desde proyectos/Feria-Effix/plugin/)

--version solo toca los plugins de las habilidades del curso. radar-tienda lleva su versión en su propio
plugin.json, en la fuente de Feria-Effix, y se copia tal cual.
"""
import os, shutil, sys, json, argparse
sys.stdout.reconfigure(encoding="utf-8")
AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE = os.path.join(os.path.dirname(AQUI), "top5-demo-skill")
# 2026-10-20 (decisión de Santiago): los dos plugins de las habilidades del curso SALIERON de este repo público;
# se entregan dentro de WeMany a los alumnos. No volver a sincronizarlos aquí. Paquete exclusivo:
# proyectos/Embajador-Claude/exclusivo-alumnos/2026-10-20_habilidades-del-curso/
PLUGINS = {}
# Plugins que se copian completos (carpeta entera) desde otro proyecto; solo con --solo <nombre>
PLUGINS_COMPLETOS = {
    "radar-tienda": os.path.join(os.path.dirname(os.path.dirname(AQUI)), "Feria-Effix", "plugin", "radar-tienda"),
}
IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "Thumbs.db", "*.zip")
IGNORAR_COMPLETO = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "Thumbs.db", "*.zip",
                                          ".env", ".env.*", "*.bak*")


def copiar_completo(plugin):
    # Copia la carpeta entera del plugin. Si la fuente no parece un plugin, no borra nada y sale.
    src = PLUGINS_COMPLETOS[plugin]
    if not os.path.isfile(os.path.join(src, ".claude-plugin", "plugin.json")):
        print(f"  ✗ no existe la fuente {src} (o no tiene .claude-plugin/plugin.json); no se tocó nada"); return False
    dst = os.path.join(AQUI, "plugins", plugin)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=IGNORAR_COMPLETO)
    n = sum(len(f) for _, _, f in os.walk(dst))
    print(f"  ✓ plugins/{plugin} completo ({n} archivos)")
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--version")
    p.add_argument("--solo", help="sincroniza solo este plugin: " + ", ".join(list(PLUGINS) + list(PLUGINS_COMPLETOS)))
    a = p.parse_args()
    if a.solo and a.solo not in PLUGINS and a.solo not in PLUGINS_COMPLETOS:
        print(f"  ✗ plugin desconocido: {a.solo}"); sys.exit(2)
    if a.solo in PLUGINS_COMPLETOS:
        if a.version:
            print(f"  aviso: --version no aplica a {a.solo}; su versión está en su propio plugin.json")
        ok = copiar_completo(a.solo)
        sys.exit(0 if ok else 1)
    for plugin, habilidades in PLUGINS.items():
        if a.solo and plugin != a.solo:
            continue
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
            # solo las entradas de las habilidades del curso (y solo la pedida, si hay --solo)
            if e["name"] in PLUGINS and (not a.solo or e["name"] == a.solo):
                e["version"] = a.version
        json.dump(d, open(mj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"  versión {a.version} escrita en plugin.json y marketplace.json")
    print("plugins sincronizados desde top5-demo-skill/")


if __name__ == "__main__":
    main()
