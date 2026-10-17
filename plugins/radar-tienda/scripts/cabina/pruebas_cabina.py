# -*- coding: utf-8 -*-
"""
Pruebas de la Cabina Radar. Correr con:  <python> pruebas_cabina.py
Levantan el servidor real en un puerto de prueba, con carpetas temporales (con espacios),
sin tocar ~/radar-tienda ni la red (la cola pública se simula).
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import warnings

warnings.simplefilter("ignore", ResourceWarning)  # avisos de urllib al leer errores HTTP: ruido, no fallas
import urllib.error
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="cabina prueba "))
os.environ["RADAR_CABINA_DIR"] = str(TMP / "cabina")
os.environ["RADAR_TIENDA_CONFIG_DIR"] = str(TMP / "config")
(TMP / "config").mkdir()
CORRIDAS = TMP / "corridas con espacio"
(TMP / "config" / "config.json").write_text(json.dumps({"carpeta_corridas": str(CORRIDAS)}), encoding="utf-8")
sys.path.insert(0, str(AQUI))
import servidor  # noqa: E402
import esperar_orden  # noqa: E402

ESPERAR = str(AQUI / "esperar_orden.py")
ESTADO = str(AQUI.parent / "tablero" / "estado.py")


def correr(*args, timeout=30):
    return subprocess.run([sys.executable] + list(args), capture_output=True, text=True, encoding="utf-8",
                          env=dict(os.environ), timeout=timeout)


class Parser(unittest.TestCase):
    """La cola pública: lo que llega de internet es dato y se filtra."""

    def test_json_bueno(self):
        p = servidor.parsear_mensaje_publico('{"enlace":"https://tienda.co/producto/masajeador-cuello","nombre":"Masajeador"}')
        self.assertEqual(p, {"enlace": "https://tienda.co/producto/masajeador-cuello", "nombre": "Masajeador"})

    def test_url_suelta_y_texto_con_url(self):
        self.assertEqual(servidor.parsear_mensaje_publico("https://vm.tiktok.com/ZMabc/")["enlace"], "https://vm.tiktok.com/ZMabc/")
        p = servidor.parsear_mensaje_publico("Mira esto https://vm.tiktok.com/ZMxyz/ está buenísimo")
        self.assertEqual(p["enlace"], "https://vm.tiktok.com/ZMxyz/")
        p = servidor.parsear_mensaje_publico('{"enlace":"Mira esto https://www.mercadolibre.com.co/lampara-led","nombre":""}')
        self.assertEqual(p["enlace"], "https://www.mercadolibre.com.co/lampara-led")
        self.assertEqual(p["nombre"], "lampara led")

    def test_rechazos(self):
        malos = ["", "hola", "javascript:alert(1)", '{"enlace":"javascript:alert(1)"}', "{no es json", "[1,2]",
                 '{"enlace": 5}', "https://example.com/x", '{"enlace":"https://example.com/prueba-cabina"}',
                 '{"enlace":"https://tienda.co/a","nombre":"PRUEBA del equipo"}', "https://tienda.co/prueba-cabina",
                 "x" * 3000]
        for m in malos:
            self.assertIsNone(servidor.parsear_mensaje_publico(m), m)

    def test_nombre_hostil_se_recorta(self):
        p = servidor.parsear_mensaje_publico(json.dumps({"enlace": "https://t.co/a", "nombre": "<script>x</script>\n" * 20}))
        self.assertLessEqual(len(p["nombre"]), servidor.MAX_NOMBRE)
        self.assertNotIn("\n", p["nombre"])

    def test_respuesta_ntfy(self):
        cuerpo = "\n".join([
            json.dumps({"id": "a1", "event": "open"}),
            json.dumps({"id": "a2", "event": "message", "message": '{"enlace":"https://tienda.co/uno","nombre":"Uno"}'}),
            "línea rota {",
            json.dumps({"id": "a3", "event": "message", "message": "sin enlace"}),
            json.dumps({"id": "a4", "event": "keepalive"}),
        ])
        r = servidor.parsear_respuesta_ntfy(cuerpo)
        self.assertEqual([x[0] for x in r], ["a2", "a3"])
        self.assertEqual(r[0][1]["nombre"], "Uno")
        self.assertIsNone(r[1][1])

    def test_validar_pedido(self):
        self.assertEqual(servidor.validar_pedido("Masajeador de cuello")[0], {"enlace": "", "nombre": "Masajeador de cuello"})
        self.assertIsNotNone(servidor.validar_pedido("javascript:alert(1)")[1])
        self.assertIsNotNone(servidor.validar_pedido("")[1])
        self.assertIsNotNone(servidor.validar_pedido("x" * 200)[1])
        self.assertIsNotNone(servidor.validar_pedido("https://" + "a" * 600)[1])
        self.assertEqual(servidor.validar_pedido("Lámpara: solar")[0]["nombre"], "Lámpara: solar")


class Servidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv, cls.puerto = servidor.crear_servidor(18765)
        cls.url = "http://127.0.0.1:%d" % cls.puerto
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        for n in ("cola.json", "orden.json", "orden_en_curso.json", "historial.jsonl"):
            p = servidor.ruta(n)
            if p.exists():
                p.unlink()

    def get(self, camino):
        r = urllib.request.urlopen(self.url + camino, timeout=5)
        return r.status, r.read().decode("utf-8")

    def post(self, camino, datos, headers=None):
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        req = urllib.request.Request(self.url + camino, data=json.dumps(datos).encode("utf-8"), method="POST", headers=h)
        try:
            r = urllib.request.urlopen(req, timeout=5)
            return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_pagina_y_estado(self):
        c, html = self.get("/")
        self.assertEqual(c, 200)
        self.assertIn("Radar a Tienda", html)
        self.assertIn("<svg", html)  # QR del público embebido
        self.assertIn("https://smart4ai.io/radar-cola", html)
        self.assertNotIn("<!--QR_PUBLICO-->", html)
        c, t = self.get("/api/estado")
        j = json.loads(t)
        self.assertTrue(j["ok"])
        self.assertEqual(j["cola"], [])

    def test_puerto_ocupado_salta_al_siguiente(self):
        s2, p2 = servidor.crear_servidor(self.puerto)
        try:
            self.assertGreater(p2, self.puerto)
        finally:
            s2.server_close()

    def test_flujo_completo(self):
        c, j = self.post("/api/pedido", {"enlace": "https://tienda.co/producto/lampara-solar", "nombre": "Lámpara solar"})
        self.assertEqual(c, 200, j)
        id1 = j["item"]["id"]
        c, j = self.post("/api/pedido", {"enlace": "https://tienda.co/producto/lampara-solar/"})
        self.assertEqual(c, 409)  # duplicado
        c, j = self.post("/api/pedido", {"enlace": "javascript:alert(1)"})
        self.assertEqual(c, 400)
        # Lanzar -> orden.json
        c, j = self.post("/api/lanzar", {"id": id1, "modo": "completo"})
        self.assertEqual(c, 200, j)
        orden = json.loads(servidor.ruta("orden.json").read_text(encoding="utf-8"))
        self.assertEqual(orden["tipo"], "correr")
        self.assertEqual(orden["modo"], "completo")
        self.assertEqual(orden["producto"]["nombre"], "Lámpara solar")
        # Segunda orden mientras hay una esperando -> 409 y el producto vuelve a la cola
        c, j = self.post("/api/pedido", {"enlace": "https://tienda.co/otro"})
        id2 = j["item"]["id"]
        c, j = self.post("/api/lanzar", {"id": id2, "modo": "expres"})
        self.assertEqual(c, 409)
        self.assertTrue(any(x["id"] == id2 for x in json.loads(self.get("/api/estado")[1])["cola"]))
        # esperar_orden la toma (proceso aparte, como lo hará Claude)
        r = correr(ESPERAR, "--timeout", "5")
        self.assertEqual(r.returncode, 0, r.stderr)
        tomada = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(tomada["id"], orden["id"])
        self.assertFalse(servidor.ruta("orden.json").exists())
        self.assertTrue(servidor.ruta("orden_en_curso.json").exists())
        est = json.loads(self.get("/api/estado")[1])
        self.assertEqual(est["orden_en_curso"]["id"], orden["id"])
        # Una corrida con veredicto (como la escribe radar-a-tienda)
        carpeta = str(CORRIDAS / "2026-10-16_2245_lampara-solar")
        correr(ESTADO, carpeta, "iniciar", "--producto", "Lámpara solar", "--modo", "completo")
        correr(ESTADO, carpeta, "dato", "veredicto", "PROBAR")
        correr(ESTADO, carpeta, "dato", "url_producto", "https://x.myshopify.com/admin/products/1")
        est = json.loads(self.get("/api/estado")[1])
        self.assertEqual(est["corrida"]["producto"], "Lámpara solar")
        self.assertEqual(est["corrida"]["datos"]["veredicto"], "PROBAR")
        # Terminar -> historial y contador
        time.sleep(1.1)
        r = correr(ESPERAR, "--terminar", "Producto en borrador")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        fila = json.loads(r.stdout)["registrada"]
        self.assertEqual(fila["veredicto"], "PROBAR")
        self.assertGreaterEqual(fila["segundos"], 1)
        est = json.loads(self.get("/api/estado")[1])
        self.assertEqual(len(est["noche"]), 1)
        self.assertEqual(est["noche"][0]["producto"], "Lámpara solar")
        self.assertEqual(est["ultimo_veredicto"], "PROBAR")
        self.assertIsNone(est["orden_en_curso"])
        # Publicar -> orden tipo publicar con la carpeta y el enlace de la corrida
        c, j = self.post("/api/publicar", {"producto": "Lámpara solar"})
        self.assertEqual(c, 200, j)
        self.assertEqual(j["orden"]["tipo"], "publicar")
        self.assertIn("lampara-solar", j["orden"]["corrida"])
        self.assertTrue(j["orden"]["url_producto"].startswith("https://"))
        # Terminar sin orden en curso -> error claro
        r = correr(ESPERAR, "--terminar", "nada")
        self.assertEqual(r.returncode, 1)

    def test_comparar_y_quitar(self):
        ids = [self.post("/api/pedido", {"enlace": "https://tienda.co/p%d" % i})[1]["item"]["id"] for i in range(4)]
        c, j = self.post("/api/comparar", {"ids": ids[:1]})
        self.assertEqual(c, 400)
        c, j = self.post("/api/comparar", {"ids": ids[:3]})
        self.assertEqual(c, 200, j)
        self.assertEqual(len(j["orden"]["productos"]), 3)
        c, j = self.post("/api/quitar", {"id": ids[3]})
        self.assertEqual(j["quitados"], 1)
        self.assertEqual(json.loads(self.get("/api/estado")[1])["cola"], [])
        # destrabar
        c, j = self.post("/api/cancelar", {})
        self.assertEqual(j["canceladas"], ["orden.json"])

    def test_tope_de_cola(self):
        for i in range(servidor.MAX_COLA):
            self.assertEqual(self.post("/api/pedido", {"enlace": "https://t.co/%d" % i})[0], 200)
        self.assertEqual(self.post("/api/pedido", {"enlace": "https://t.co/extra"})[0], 409)

    def test_entradas_raras(self):
        req = urllib.request.Request(self.url + "/api/pedido", data=b"no json", method="POST",
                                     headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(e.exception.code, 400)
        req = urllib.request.Request(self.url + "/api/pedido", data=b"enlace=x", method="POST",
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(e.exception.code, 400)
        c, j = self.post("/api/pedido", {"enlace": "https://t.co/a"}, {"Origin": "https://sitio-malo.com"})
        self.assertEqual(c, 403)
        c, j = self.post("/api/lanzar", {"id": "no-existe"})
        self.assertEqual(c, 404)
        self.assertEqual(self.post("/api/nada", {})[0], 404)
        with self.assertRaises(urllib.error.HTTPError):
            self.get("/api/qr?t=javascript:alert(1)")
        c, svg = self.get("/api/qr?t=https%3A%2F%2Ftienda.co%2Fx")
        self.assertIn("<svg", svg)

    def test_cola_publica_simulada(self):
        servidor.DESDE_PUBLICO["since"] = "1792200000"
        pedidos = []

        def falso(url):
            pedidos.append(url)
            return "\n".join([
                json.dumps({"id": "m1", "event": "message", "message": '{"enlace":"https://tienda.co/pub1","nombre":"Del público"}'}),
                json.dumps({"id": "m2", "event": "message", "message": "Mira esto https://vm.tiktok.com/ZMq/"}),
                json.dumps({"id": "m3", "event": "message", "message": '{"enlace":"https://example.com/prueba-cabina"}'}),
            ])
        self.assertEqual(servidor.consultar_publico_una_vez(falso), 2)
        self.assertIn("since=1792200000", pedidos[0])  # arranca desde la hora de arranque, no 12 h
        self.assertEqual(servidor.consultar_publico_una_vez(falso), 0)  # duplicados no entran
        self.assertIn("since=m3", pedidos[1])  # luego sigue desde el último id visto
        cola = json.loads(self.get("/api/estado")[1])["cola"]
        self.assertEqual([x["origen"] for x in cola], ["público", "público"])

    def test_esperar_vence(self):
        t0 = time.time()
        r = correr(ESPERAR, "--timeout", "1")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout.strip(), "SIN_ORDEN")
        self.assertLess(time.time() - t0, 10)
        self.assertTrue(json.loads(self.get("/api/estado")[1])["claude_escuchando"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
