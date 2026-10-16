"""Aplica varias órdenes de estado.py leídas de un archivo de texto.

Uso: <python> lote.py "<carpeta corrida>" "<archivo de órdenes .txt>"
(<python> = py, python3 o python, el que detectó la configuración del plugin)

Una orden por línea, con los campos separados por " | " (así no hay problemas
de comillas en ninguna terminal). Líneas vacías o que empiezan con # se ignoran.
Ejemplos:
  iniciar | --producto | Alineo · corrector | --modo | completo
  estacion | radar | ok | --detalle | PROBAR si costo <= 17.745
  dato | precio_1 | 79900
  log | Corrida arrancada
"""
import subprocess
import sys
from pathlib import Path

ESTADO = Path(__file__).with_name("estado.py")


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    carpeta, archivo = sys.argv[1], Path(sys.argv[2])
    if not archivo.is_file():
        print(f"[lote] no existe: {archivo}", file=sys.stderr)
        return 2
    fallos = 0
    for n, linea in enumerate(archivo.read_text(encoding="utf-8-sig").splitlines(), 1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        args = [p.strip() for p in linea.split(" | ")]
        r = subprocess.run([sys.executable, str(ESTADO), carpeta, *args],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            fallos += 1
            print(f"[lote] línea {n} falló: {linea}\n{r.stderr.strip()}", file=sys.stderr)
    print(f"[lote] listo · {fallos} fallos")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
