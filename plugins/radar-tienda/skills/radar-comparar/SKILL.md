---
name: radar-comparar
description: Compara de 2 a 4 productos a la vez y dice cuál lanzar primero. Hace un estudio de mercado exprés de cada uno en paralelo (anuncios activos en Meta, anunciantes, precios de la competencia, margen, CPA de equilibrio, veredicto y confianza) y entrega una tabla lado a lado con la recomendación y el porqué, ordenada con una regla fija (primero el veredicto, luego la confianza, luego el margen). Úsala cuando digan compara estos productos, cuál de estos lanzo, cuál vendo primero, tengo 3 productos y no sé cuál, ponlos a competir, o pasen varias fotos o enlaces pidiendo elegir uno. Al final ofrece montar en la tienda el ganador. No la uses para estudiar un solo producto a fondo, para montar un producto en Shopify sin comparar, ni para la configuración inicial del plugin.
---

# Comparar productos · cuál lanzar primero

Productos pedidos: $ARGUMENTS

`<python>` es el intérprete guardado en `~/.radar-tienda/config.json` (campo `python`). Rutas del plugin en `${CLAUDE_PLUGIN_ROOT}`.

## Reglas de oro

1. **Entre 2 y 4 productos.** Si llegan más, pide que elija 4; si llega uno, ofrece la línea completa de producto a tienda en su lugar.
2. **Mismo método para todos:** estudio exprés con las mismas reglas de evidencia; nada se inventa. Lo que no se pudo verificar dice "no verificable".
3. **La recomendación sale de una regla fija**, no de la intuición: veredicto (PROBAR > sin dato > PRECAUCIÓN > NO RECOMENDABLE) → confianza → margen. Si todos son NO RECOMENDABLE, la respuesta honesta es "ninguno por ahora".
4. **Nada se crea en la tienda** sin que la persona elija el ganador y diga que siga.

## Paso 1 · Arranque

- Comprueba `config.json` con `<python> "${CLAUDE_PLUGIN_ROOT}/scripts/comun/entorno.py" --json`. Si no existe, di "Primero corre /radar-tienda:radar-configurar" y para. (Shopify no hace falta para comparar.)
- Carpeta: `<python> "${CLAUDE_PLUGIN_ROOT}/scripts/comun/entorno.py" --nueva-corrida "comparar"` → `<comparacion>`; dentro, una subcarpeta por producto (`<comparacion>/<n>-<slug>/`).
- Una línea al usuario: cuántos productos y que tarda unos 5 a 10 minutos.

## Paso 2 · Estudios exprés en paralelo

Lanza **un ayudante por producto en el mismo mensaje** (herramienta Agent, `subagent_type: general-purpose`, `model: sonnet`, esfuerzo bajo). Si no hay herramienta Agent, hazlos uno tras otro tú mismo. Encargo de cada ayudante:
- Lee con la herramienta de lectura `${CLAUDE_PLUGIN_ROOT}/skills/radar-producto/SKILL.md` (skill de Carlos Jiménez, no se modifica) y síguela en **modo exprés**: ≤ 25 llamadas, 3 palabras clave, `ads_library_search` (país de la configuración, ACTIVE, limit 50) con 2 palabras clave, 3 o 4 tiendas + un listado de Mercado Libre, costo del usuario o 1 búsqueda de proveedor, fase 6 completa en Python.
- Guarda en su subcarpeta `estudio-<producto>-<fecha>.md` con la tabla "Veredicto en 30 segundos" completa. El brief de landing NO hace falta aquí.
- Plan B: sin Chrome → confianza Baja; sin conector de Meta → conteo "no verificado"; en "Limitaciones" escribe que fue exprés.

## Paso 3 · Tabla y recomendación

- Con Python: `<python> "${CLAUDE_PLUGIN_ROOT}/scripts/puente/puente.py" --resumen "<estudio 1>" "<estudio 2>" ...` → JSON con las filas ya ordenadas por la regla fija y el campo `recomendado`. Sin Python, lee tú la tabla "Veredicto en 30 segundos" de cada estudio y ordena con la misma regla.
- Entrega la tabla:

| # | Producto | Veredicto | Confianza | Margen | CPA de equilibrio | Anunciantes | Precio sugerido |
|---|---|---|---|---|---|---|---|

- Debajo, en 3 a 5 líneas: **cuál lanzar primero y por qué** (con las cifras de la tabla), el mayor riesgo del ganador, y qué haría falta para que el segundo lo supere.
- Guarda la tabla y la recomendación en `<comparacion>/comparacion.md`.

## Paso 4 · Seguir con el ganador (opcional)

Pregunta: "¿Monto en tu tienda el ganador?". Si dice que sí, sigue la línea completa de producto a tienda con ese producto, reutilizando su estudio (no lo repitas); el brief de landing sí se escribe completo en esa línea.

## Qué NUNCA hace

Inventar cifras para desempatar · elegir un ganador con veredicto NO RECOMENDABLE · crear productos, descuentos o campañas sin el sí de la persona.
