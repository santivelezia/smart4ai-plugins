# radar-tienda · Radar a Tienda

Le das a Claude la foto o el enlace de un producto y te devuelve el estudio de mercado y el producto montado en tu Shopify, en borrador, con fotos, anuncio y video; si el negocio no da, te lo dice.
Se instala en Claude Code con `/plugin marketplace add santivelezia/smart4ai-plugins` y `/plugin install radar-tienda@smart4ai-plugins`; en claude.ai o Cowork, por Configuración → Personalizar → Plugins (mismo repositorio). Después escribe `/radar-tienda:radar-configurar` (en claude.ai o Cowork, di "configura el radar").
Para actualizar en Claude Code: `claude plugin update radar-tienda@smart4ai-plugins` en una terminal, o `/plugin` → Installed → Update now.
Si algo falla, mira las preguntas frecuentes del manual, escribe `/radar-tienda:radar-ayuda` o escribe a santi@smart4ai.io.

| Skill (Claude Code) | En claude.ai / Cowork dices | Para qué sirve |
|---|---|---|
| `/radar-tienda:radar-configurar` | "configura el radar" | Primer uso: revisa qué tienes, crea la colección, hace una prueba de 1 minuto y te dice tu nivel |
| `/radar-tienda:radar-producto` | "estudia este producto" | Estudio de mercado de un producto (creado por Carlos) |
| `/radar-tienda:radar-a-tienda <foto o enlace> [exprés]` | "monta este producto en mi tienda" | Estudio, validación, fotos con IA, producto en Shopify en borrador, anuncio y video |
| `/radar-tienda:radar-comparar` | "compara estos productos" | Compara 2 a 4 productos (unos 5 a 10 minutos) y te dice cuál lanzar |
| `/radar-tienda:radar-ayuda` | "ayuda con el radar" | Pregúntale qué hacer o por qué algo falló |

Tres niveles: **Completo** (Python + Shopify, con tablero en vivo), **Conectores** (Shopify sin Python) y **Solo estudio** (sin Shopify). Al instalar, el plugin te pregunta 9 datos, todos con valor por defecto (detalle en el manual, sección 3E).

Manual completo: [docs/MANUAL_DE_USUARIO.md](docs/MANUAL_DE_USUARIO.md)

Licencia CC BY-NC 4.0. No es asesoría legal, médica ni financiera. El plugin nunca publica, pauta ni cobra.
