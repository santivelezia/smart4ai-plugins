# -*- coding: utf-8 -*-
"""
qr.py · Codificador QR mínimo en Python puro (sin librerías externas).

Alcance (lo justo para el tablero):
  - Modo byte (UTF-8), corrección de errores nivel M (~15 %).
  - Versiones 1 a 40 (de sobra para URLs de hasta 200 caracteres: caben en la versión 10).
  - Elige la mejor máscara por puntaje de penalización (norma ISO/IEC 18004).
  - Salida: matriz de booleanos (True = módulo oscuro) o un SVG listo para incrustar.

Basado en el algoritmo público de Project Nayuki (QR Code generator, licencia MIT),
reescrito y simplificado. Probado contra la librería `qrcode` en pruebas/test_tablero.py.
"""

# ---------------------------------------------------------------------------
# Tablas del nivel M (índice = versión; la posición 0 no se usa)
# ---------------------------------------------------------------------------
ECC_POR_BLOQUE_M = [-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26,
                    26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28]
BLOQUES_M = [-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14,
             16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49]
BITS_FORMATO_M = 0  # nivel M se codifica como 00 en la información de formato


# ---------------------------------------------------------------------------
# Aritmética en GF(256) y Reed-Solomon
# ---------------------------------------------------------------------------
def _gf_mul(x, y):
    """Multiplica dos bytes en el campo de Galois GF(2^8) con polinomio 0x11D."""
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(grado):
    """Polinomio generador de Reed-Solomon del grado pedido."""
    res = [0] * (grado - 1) + [1]
    raiz = 1
    for _ in range(grado):
        for j in range(len(res)):
            res[j] = _gf_mul(res[j], raiz)
            if j + 1 < len(res):
                res[j] ^= res[j + 1]
        raiz = _gf_mul(raiz, 0x02)
    return res


def _rs_resto(datos, divisor):
    """Bytes de corrección de errores para un bloque de datos."""
    res = [0] * len(divisor)
    for b in datos:
        factor = b ^ res.pop(0)
        res.append(0)
        for i, coef in enumerate(divisor):
            res[i] ^= _gf_mul(coef, factor)
    return res


# ---------------------------------------------------------------------------
# Capacidades
# ---------------------------------------------------------------------------
def _modulos_datos_crudos(ver):
    """Cuántos módulos quedan para datos+corrección en una versión."""
    res = (16 * ver + 128) * ver + 64
    if ver >= 2:
        n = ver // 7 + 2
        res -= (25 * n - 10) * n - 55
        if ver >= 7:
            res -= 36
    return res


def _codewords_datos(ver):
    return _modulos_datos_crudos(ver) // 8 - ECC_POR_BLOQUE_M[ver] * BLOQUES_M[ver]


def _bits_conteo(ver):
    """Bits del contador de caracteres en modo byte."""
    return 8 if ver <= 9 else 16


# ---------------------------------------------------------------------------
# Codificación
# ---------------------------------------------------------------------------
def _codificar_datos(texto, ver_min=1):
    """Devuelve (versión, lista de codewords de datos con relleno)."""
    datos = texto.encode("utf-8")
    ver = None
    for v in range(ver_min, 41):
        if 4 + _bits_conteo(v) + 8 * len(datos) <= _codewords_datos(v) * 8:
            ver = v
            break
    if ver is None:
        raise ValueError("Texto demasiado largo para un QR")

    bits = []

    def poner(valor, n):
        for i in range(n - 1, -1, -1):
            bits.append((valor >> i) & 1)

    poner(0b0100, 4)                      # modo byte
    poner(len(datos), _bits_conteo(ver))  # cuántos bytes
    for b in datos:
        poner(b, 8)
    capacidad = _codewords_datos(ver) * 8
    poner(0, min(4, capacidad - len(bits)))  # terminador
    poner(0, (-len(bits)) % 8)               # completar el byte
    cws = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    relleno = 0xEC
    while len(cws) < _codewords_datos(ver):
        cws.append(relleno)
        relleno ^= 0xEC ^ 0x11
    return ver, cws


def _intercalar(ver, datos):
    """Parte en bloques, agrega corrección a cada uno y los intercala."""
    nbloques = BLOQUES_M[ver]
    ecc = ECC_POR_BLOQUE_M[ver]
    crudos = _modulos_datos_crudos(ver) // 8
    ncortos = nbloques - crudos % nbloques
    largo_corto = crudos // nbloques
    divisor = _rs_divisor(ecc)
    bloques = []
    k = 0
    for i in range(nbloques):
        n = largo_corto - ecc + (0 if i < ncortos else 1)
        dat = datos[k:k + n]
        k += n
        bloq = dat + _rs_resto(dat, divisor)
        if i < ncortos:
            bloq.insert(len(dat), None)  # hueco para alinear con los bloques largos
        bloques.append(bloq)
    res = []
    for i in range(len(bloques[0])):
        for b in bloques:
            if b[i] is not None:
                res.append(b[i])
    return res


class _Matriz:
    def __init__(self, ver):
        self.ver = ver
        self.n = ver * 4 + 17
        self.m = [[False] * self.n for _ in range(self.n)]
        self.fun = [[False] * self.n for _ in range(self.n)]

    def fijar(self, x, y, oscuro):
        self.m[y][x] = bool(oscuro)
        self.fun[y][x] = True

    # -- patrones fijos --
    def patrones(self):
        n = self.n
        for i in range(n):  # líneas de sincronía
            self.fijar(6, i, i % 2 == 0)
            self.fijar(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):  # buscadores
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < n and 0 <= y < n:
                        d = max(abs(dx), abs(dy))
                        self.fijar(x, y, d not in (2, 4))
        pos = self._posiciones_alineacion()
        k = len(pos)
        for i in range(k):
            for j in range(k):
                if (i == 0 and j == 0) or (i == 0 and j == k - 1) or (i == k - 1 and j == 0):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.fijar(pos[i] + dx, pos[j] + dy, max(abs(dx), abs(dy)) != 1)
        self.formato(0)  # reserva el espacio (se reescribe al final)
        self._version()

    def _posiciones_alineacion(self):
        if self.ver == 1:
            return []
        k = self.ver // 7 + 2
        paso = 26 if self.ver == 32 else (self.ver * 4 + k * 2 + 1) // (k * 2 - 2) * 2
        res = [self.n - 7 - i * paso for i in range(k - 1)] + [6]
        return sorted(res)

    def formato(self, mascara):
        dato = (BITS_FORMATO_M << 3) | mascara
        rem = dato
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = ((dato << 10) | rem) ^ 0x5412
        b = lambda i: (bits >> i) & 1
        n = self.n
        for i in range(0, 6):
            self.fijar(8, i, b(i))
        self.fijar(8, 7, b(6))
        self.fijar(8, 8, b(7))
        self.fijar(7, 8, b(8))
        for i in range(9, 15):
            self.fijar(14 - i, 8, b(i))
        for i in range(0, 8):
            self.fijar(n - 1 - i, 8, b(i))
        for i in range(8, 15):
            self.fijar(8, n - 15 + i, b(i))
        self.fijar(8, n - 8, True)  # módulo oscuro fijo

    def _version(self):
        if self.ver < 7:
            return
        rem = self.ver
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = (self.ver << 12) | rem
        for i in range(18):
            bit = (bits >> i) & 1
            a, b = self.n - 11 + i % 3, i // 3
            self.fijar(a, b, bit)
            self.fijar(b, a, bit)

    # -- datos --
    def colocar(self, cws):
        n = self.n
        i = 0
        total = len(cws) * 8
        derecha = n - 1
        while derecha >= 1:
            if derecha == 6:
                derecha = 5
            for vert in range(n):
                for j in range(2):
                    x = derecha - j
                    sube = ((derecha + 1) & 2) == 0
                    y = n - 1 - vert if sube else vert
                    if not self.fun[y][x] and i < total:
                        self.m[y][x] = ((cws[i >> 3] >> (7 - (i & 7))) & 1) == 1
                        i += 1
            derecha -= 2

    def aplicar_mascara(self, k):
        f = [
            lambda x, y: (x + y) % 2 == 0,
            lambda x, y: y % 2 == 0,
            lambda x, y: x % 3 == 0,
            lambda x, y: (x + y) % 3 == 0,
            lambda x, y: (x // 3 + y // 2) % 2 == 0,
            lambda x, y: x * y % 2 + x * y % 3 == 0,
            lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
            lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
        ][k]
        for y in range(self.n):
            for x in range(self.n):
                if not self.fun[y][x] and f(x, y):
                    self.m[y][x] = not self.m[y][x]

    def penalizacion(self):
        """Puntaje de la norma: menor es mejor."""
        n = self.n
        m = self.m
        p = 0
        lineas = [m[y] for y in range(n)] + [[m[y][x] for y in range(n)] for x in range(n)]
        patron_a = [True, False, True, True, True, False, True, False, False, False, False]
        patron_b = patron_a[::-1]
        for fila in lineas:
            # Regla 1: corridas de 5 o más del mismo color
            corrida = 1
            for i in range(1, n):
                if fila[i] == fila[i - 1]:
                    corrida += 1
                else:
                    if corrida >= 5:
                        p += corrida - 2
                    corrida = 1
            if corrida >= 5:
                p += corrida - 2
            # Regla 3: patrón parecido a un buscador
            for i in range(n - 10):
                seg = fila[i:i + 11]
                if seg == patron_a or seg == patron_b:
                    p += 40
        # Regla 2: bloques 2x2 del mismo color
        for y in range(n - 1):
            for x in range(n - 1):
                c = m[y][x]
                if c == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    p += 3
        # Regla 4: equilibrio claro/oscuro
        oscuros = sum(sum(1 for c in fila if c) for fila in m)
        total = n * n
        k = (abs(oscuros * 20 - total * 10) + total - 1) // total - 1
        p += max(k, 0) * 10
        return p


def matriz_qr(texto, mascara=None):
    """
    Devuelve la matriz del QR (lista de listas de bool, True = oscuro).
    `mascara` fuerza una máscara 0-7 (solo para pruebas); si es None se elige la mejor.
    """
    ver, datos = _codificar_datos(texto)
    cws = _intercalar(ver, datos)

    def construir(k):
        q = _Matriz(ver)
        q.patrones()
        q.colocar(cws)
        q.aplicar_mascara(k)
        q.formato(k)
        return q

    if mascara is not None:
        return construir(mascara).m
    mejor = None
    for k in range(8):
        q = construir(k)
        pen = q.penalizacion()
        if mejor is None or pen < mejor[0]:
            mejor = (pen, q)
    return mejor[1].m


def svg_qr(texto, borde=4, color="#000", fondo="#fff"):
    """SVG autocontenido del QR (escalable; el tamaño lo pone el CSS)."""
    m = matriz_qr(texto)
    n = len(m)
    t = n + 2 * borde
    trazos = []
    for y in range(n):
        for x in range(n):
            if m[y][x]:
                trazos.append("M%d,%dh1v1h-1z" % (x + borde, y + borde))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" shape-rendering="crispEdges">'
        '<rect width="100%%" height="100%%" fill="%s"/>'
        '<path d="%s" fill="%s"/></svg>' % (t, t, fondo, "".join(trazos), color)
    )


if __name__ == "__main__":
    import sys
    print(svg_qr(sys.argv[1] if len(sys.argv) > 1 else "https://example.com"))
