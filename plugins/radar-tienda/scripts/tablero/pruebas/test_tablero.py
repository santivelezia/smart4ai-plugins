# -*- coding: utf-8 -*-
"""
Pruebas del tablero (y de la configuración común). Correr con:
  <python> -m unittest discover -s "<plugin>/scripts/tablero/pruebas" -v
Trabajan en carpetas temporales con espacios; no tocan la carpeta de datos real del usuario
(RADAR_TIENDA_CONFIG_DIR apunta a una carpeta temporal).
La comparación del QR usa la librería `qrcode` SOLO como referencia de prueba (si no está, se salta).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
COMUN = os.path.join(os.path.dirname(RAIZ), "comun")
CFG_TMP = tempfile.mkdtemp(prefix="radar tienda config prueba ")
os.environ["RADAR_TIENDA_CONFIG_DIR"] = CFG_TMP
sys.path.insert(0, RAIZ)
sys.path.insert(0, COMUN)
import entorno  # noqa: E402
import estado  # noqa: E402
import qr  # noqa: E402

ESTADO_PY = os.path.join(RAIZ, "estado.py")
LOTE_PY = os.path.join(RAIZ, "lote.py")
DEMO_PY = os.path.join(RAIZ, "demo_simulada.py")
ENTORNO_PY = os.path.join(COMUN, "entorno.py")


def correr(carpeta, *args):
    return subprocess.run([sys.executable, ESTADO_PY, carpeta] + list(args), capture_output=True, text=True,
                          encoding="utf-8", env=dict(os.environ, RADAR_TIENDA_CONFIG_DIR=CFG_TMP))


class Etiquetas(HTMLParser):
    """Verificador simple de HTML: etiquetas abiertas y cerradas en orden."""
    VACIAS = {"meta", "link", "img", "br", "hr", "input", "path", "rect"}

    def __init__(self):
        super().__init__()
        self.pila, self.errores = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VACIAS:
            self.pila.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in self.VACIAS:
            return
        if not self.pila or self.pila[-1] != tag:
            self.errores.append("cierre inesperado </%s> (abierto: %s)" % (tag, self.pila[-1:] or "nada"))
        else:
            self.pila.pop()


def html_valido(texto):
    p = Etiquetas()
    p.feed(texto)
    p.close()
    return p.errores + (["sin cerrar: %s" % p.pila] if p.pila else [])


class TestQR(unittest.TestCase):
    def test_igual_a_libreria_de_referencia(self):
        try:
            import qrcode
            import qrcode.util as u
        except ImportError:
            self.skipTest("qrcode no instalada")
        textos = ["a", "https://example.com", "https://mi-tienda.myshopify.com/products/corrector?preview=1",
                  "x" * 200, "https://tienda.co/ñandú?precio=$89.900", "h" * 213]
        for t in textos:
            for k in range(8):
                q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, mask_pattern=k, border=0)
                q.add_data(u.QRData(t.encode("utf-8"), mode=u.MODE_8BIT_BYTE))
                q.make(fit=True)
                self.assertEqual(q.get_matrix(), qr.matriz_qr(t, k), "texto=%r mascara=%d" % (t[:30], k))

    def test_200_caracteres_cabe_en_version_10(self):
        m = qr.matriz_qr("https://" + "a" * 192)
        self.assertLessEqual(len(m), 10 * 4 + 17)

    def test_svg(self):
        s = qr.svg_qr("https://example.com")
        self.assertTrue(s.startswith("<svg") and s.endswith("</svg>"))


class TestFormato(unittest.TestCase):
    def test_dinero_colombiano(self):
        f = estado.formato_valor
        self.assertEqual(f("precio_1", "89900"), "$89.900")
        self.assertEqual(f("precio_1", "$89.900"), "$89.900")
        self.assertEqual(f("precio_2", "1234567"), "$1.234.567")
        self.assertEqual(f("margen", "42%"), "42%")
        self.assertEqual(f("cpa_equilibrio", "37700.4"), "$37.700")
        self.assertEqual(f("anuncios_activos", "1500"), "1.500")
        self.assertEqual(f("precio_1", "consultar"), "consultar")  # no numérico: tal cual

    def test_veredicto_colores(self):
        c = estado.clase_veredicto
        self.assertEqual(c("PROBAR"), "verde")
        self.assertEqual(c("PRECAUCIÓN"), "ambar")
        self.assertEqual(c("NO RECOMENDABLE"), "rojo")
        self.assertEqual(c("Otro"), "neutro")

    def test_urls(self):
        self.assertIsNone(estado.url_segura("javascript:alert(1)"))
        self.assertIsNone(estado.url_segura("http://x.com/a.jpg", solo_https=True))
        self.assertEqual(estado.url_segura("https://x.com/a.jpg", solo_https=True), "https://x.com/a.jpg")


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tablero test con espacios ")

    def leer(self):
        with open(os.path.join(self.tmp, "estado.json"), encoding="utf-8") as f:
            est = json.load(f)
        with open(os.path.join(self.tmp, "tablero.html"), encoding="utf-8") as f:
            return est, f.read()

    def test_flujo_completo_y_fin(self):
        self.assertEqual(correr(self.tmp, "iniciar", "--producto", "Lámpara ñ", "--modo", "completo").returncode, 0)
        est, h = self.leer()
        self.assertIn('http-equiv="refresh"', h)
        self.assertIn("Lámpara ñ", h)
        for e in estado.CLAVES_EST:
            r = correr(self.tmp, "estacion", e, "ok", "--detalle", "listo")
            self.assertEqual(r.returncode, 0, r.stderr)
        est, h = self.leer()
        self.assertTrue(est["terminado"])
        self.assertNotIn('http-equiv="refresh"', h)  # al terminar deja de refrescar
        self.assertIn("data-fin=", h)
        self.assertEqual(html_valido(h), [])

    def test_estacion_o_estado_invalido_falla(self):
        correr(self.tmp, "iniciar", "--producto", "X", "--modo", "exprés")
        self.assertNotEqual(correr(self.tmp, "estacion", "bodega", "ok").returncode, 0)
        self.assertNotEqual(correr(self.tmp, "estacion", "radar", "listo").returncode, 0)

    def test_escapa_html_y_bloquea_javascript(self):
        correr(self.tmp, "iniciar", "--producto", "<script>alert(1)</script>", "--modo", "exprés")
        correr(self.tmp, "dato", "url_producto", "javascript:alert(1)")
        correr(self.tmp, "dato", "imagen_1", "http://inseguro.com/a.jpg")
        correr(self.tmp, "log", '"><img src=x onerror=alert(1)>')
        correr(self.tmp, "dato", "advertencia", "<b>NO</b> recomendable")
        est, h = self.leer()
        self.assertNotIn("<script>alert", h)
        self.assertNotIn("javascript:alert", h)
        self.assertNotIn("inseguro.com", h)
        self.assertNotIn("<img src=x", h)
        self.assertNotIn("<b>NO</b>", h)
        self.assertEqual(html_valido(h), [])

    def test_sin_iniciar_no_se_cae(self):
        r = correr(self.tmp, "log", "hola")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Aviso", r.stderr)
        est, h = self.leer()
        self.assertEqual(est["log"][-1]["texto"], "hola")

    def test_estado_danado_se_respalda(self):
        with open(os.path.join(self.tmp, "estado.json"), "w", encoding="utf-8") as f:
            f.write("{roto")
        r = correr(self.tmp, "log", "sigue")
        self.assertEqual(r.returncode, 0)
        self.assertTrue(any(n.startswith("estado.json.danado_") for n in os.listdir(self.tmp)))

    def test_qr_y_boton_con_url(self):
        correr(self.tmp, "iniciar", "--producto", "X", "--modo", "exprés")
        correr(self.tmp, "dato", "url_preview", "https://example.com")
        est, h = self.leer()
        self.assertIn("<svg", h)
        self.assertIn("Ver la tienda", h)

    def test_bitacora_ultimas_8(self):
        correr(self.tmp, "iniciar", "--producto", "X", "--modo", "exprés")
        for i in range(12):
            correr(self.tmp, "log", "evento-%02d" % i)
        est, h = self.leer()
        self.assertIn("evento-11", h)
        self.assertIn("evento-04", h)
        self.assertNotIn("evento-03", h)

    # --- nuevo en el plugin ---
    def test_titulo_por_defecto_y_sin_marca_fija(self):
        correr(self.tmp, "iniciar", "--producto", "X", "--modo", "exprés")
        est, h = self.leer()
        self.assertIn("<b>Radar a Tienda</b>", h)
        self.assertNotIn("Effix", h)

    def test_titulo_desde_argumento_y_desde_config(self):
        correr(self.tmp, "iniciar", "--producto", "X", "--modo", "exprés", "--titulo", "Tienda de Ana")
        est, h = self.leer()
        self.assertIn("<b>Tienda de Ana</b>", h)
        with open(os.path.join(CFG_TMP, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"titulo_tablero": "Mi Marca"}, f)
        try:
            otra = tempfile.mkdtemp(prefix="tablero titulo config ")
            correr(otra, "iniciar", "--producto", "Y", "--modo", "exprés")
            with open(os.path.join(otra, "tablero.html"), encoding="utf-8") as f:
                self.assertIn("<b>Mi Marca</b>", f.read())
        finally:
            os.remove(os.path.join(CFG_TMP, "config.json"))

    def test_advertencia_en_rojo(self):
        correr(self.tmp, "iniciar", "--producto", "X", "--modo", "exprés")
        correr(self.tmp, "dato", "advertencia", "El estudio dice NO RECOMENDABLE")
        est, h = self.leer()
        self.assertIn('class="adv"', h)
        self.assertIn("NO RECOMENDABLE", h)

    def test_recibo_suma_costos_de_generar(self):
        correr(self.tmp, "iniciar", "--producto", "X", "--modo", "exprés")
        with open(os.path.join(self.tmp, "imagenes.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"ok": True, "costo_usd": 0.034, "costo_fuente": "usage.cost", "modelo": "a"}) + "\n")
            f.write(json.dumps({"ok": True, "costo_usd": 0.14, "costo_fuente": "usage.cost", "modelo": "b",
                                "aviso_modelo": "google/gemini-3-pro-image no respondió (429); se usó otro."}) + "\n")
            f.write(json.dumps({"ok": False, "error": "401"}) + "\n")
            f.write("línea dañada\n")
        r = correr(self.tmp, "recibo", "--nivel", "Completo", "--consultas", "23", "--proveedor", "openrouter")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.tmp, "recibo.md"), encoding="utf-8") as f:
            recibo = f.read()
        self.assertIn("0.1740", recibo)
        self.assertIn("| Imágenes generadas con IA | 2 (1 fallidas) |", recibo)
        self.assertIn("429", recibo)
        est, h = self.leer()
        self.assertIn("Recibo de la corrida", h)
        self.assertIn("US$0.1740", h)

    def test_abrir_sin_tablero_no_falla(self):
        r = correr(self.tmp, "abrir")
        self.assertEqual(r.returncode, 0)
        self.assertIn("AVISO", r.stdout)

    def test_lote(self):
        ordenes = os.path.join(self.tmp, "ordenes 1.txt")
        with open(ordenes, "w", encoding="utf-8") as f:
            f.write("# comentario\niniciar | --producto | Alineo · corrector | --modo | completo\n"
                    "dato | precio_1 | 79900\nestacion | radar | ok | --detalle | PROBAR con espacios\n")
        r = subprocess.run([sys.executable, LOTE_PY, self.tmp, ordenes], capture_output=True, text=True,
                           encoding="utf-8", env=dict(os.environ, RADAR_TIENDA_CONFIG_DIR=CFG_TMP))
        self.assertEqual(r.returncode, 0, r.stderr)
        est, h = self.leer()
        self.assertEqual(est["datos"]["precio_1"], "79900")
        self.assertEqual(est["estaciones"]["radar"]["detalle"], "PROBAR con espacios")

    def test_demo_rapida_en_carpeta_temporal(self):
        destino = os.path.join(self.tmp, "demo con espacios")
        r = subprocess.run([sys.executable, DEMO_PY, "--rapido", "--carpeta", destino], capture_output=True,
                           text=True, encoding="utf-8", env=dict(os.environ, RADAR_TIENDA_CONFIG_DIR=CFG_TMP))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.exists(os.path.join(destino, "recibo.md")))
        with open(os.path.join(destino, "tablero.html"), encoding="utf-8") as f:
            self.assertEqual(html_valido(f.read()), [])


class TestEntorno(unittest.TestCase):
    def test_valores_por_defecto(self):
        cfg = entorno.leer_config(os.path.join(CFG_TMP, "no-existe.json"))
        self.assertEqual(cfg["vendedor"], "Radar")
        self.assertEqual(cfg["coleccion"], "radar")
        self.assertEqual(cfg["etiqueta_prueba"], "radar-prueba")
        self.assertEqual(cfg["codigo_descuento"], "")
        self.assertIs(cfg["pago_contra_entrega"], False)
        self.assertEqual(cfg["proveedor_imagenes"], "conector")

    def test_valores_sin_sustituir_vuelven_al_defecto(self):
        ruta = os.path.join(CFG_TMP, "raro.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"vendedor": "${user_config.vendedor}", "codigo_descuento": "${user_config.codigo_descuento}",
                       "proveedor_imagenes": "dibujos", "pago_contra_entrega": "sí"}, f)
        cfg = entorno.leer_config(ruta)
        self.assertEqual(cfg["vendedor"], "Radar")
        self.assertEqual(cfg["codigo_descuento"], "")
        self.assertEqual(cfg["proveedor_imagenes"], "conector")
        self.assertIs(cfg["pago_contra_entrega"], True)

    def test_config_danado_no_rompe(self):
        ruta = os.path.join(CFG_TMP, "danado.json")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("{roto")
        cfg = entorno.leer_config(ruta)
        self.assertIn("ilegible", cfg["_origen"])
        self.assertEqual(cfg["vendedor"], "Radar")

    def test_guardar_no_acepta_claves(self):
        with self.assertRaises(ValueError):
            entorno.guardar_config({"openrouter_api_key": "x"}, os.path.join(CFG_TMP, "g.json"))
        g = entorno.guardar_config({"vendedor": "Ana", "pago_contra_entrega": "si"}, os.path.join(CFG_TMP, "g.json"))
        self.assertEqual(g["vendedor"], "Ana")
        self.assertIs(g["pago_contra_entrega"], True)

    def test_clave_desde_env_archivo_sin_imprimirla(self):
        with open(os.path.join(CFG_TMP, ".env"), "w", encoding="utf-8") as f:
            f.write("# comentario\nOPENROUTER_API_KEY=\"sk-or-v1-prueba-secreta-123\"\n")
        viejo = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            clave, origen = entorno.leer_clave_openrouter()
            self.assertEqual(clave, "sk-or-v1-prueba-secreta-123")
            r = subprocess.run([sys.executable, ENTORNO_PY, "--json"], capture_output=True, text=True, encoding="utf-8",
                               env={k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"})
            self.assertNotIn("prueba-secreta", r.stdout)
            self.assertEqual(json.loads(r.stdout)["clave_openrouter"], "presente")
        finally:
            os.remove(os.path.join(CFG_TMP, ".env"))
            if viejo is not None:
                os.environ["OPENROUTER_API_KEY"] = viejo

    def test_nueva_corrida_no_pisa(self):
        destino = tempfile.mkdtemp(prefix="corridas con espacios ")
        cfg = {"carpeta_corridas": destino}
        a = entorno.nueva_corrida("Corrector de Postura ñ", cfg)
        b = entorno.nueva_corrida("Corrector de Postura ñ", cfg)
        self.assertTrue(a.is_dir() and b.is_dir() and a != b)
        self.assertTrue(a.name.endswith("_corrector-de-postura-n"))

    def test_resumen_tiene_lo_basico(self):
        r = entorno.resumen()
        for k in ("sistema", "python", "python_recomendado", "carpeta_corridas", "clave_openrouter"):
            self.assertIn(k, r)


if __name__ == "__main__":
    unittest.main()
