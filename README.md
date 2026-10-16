# smart4ai-plugins · las habilidades de Smart4AI para Claude

Dos plugins con las habilidades del curso **Arquitectos de IA**, listos para instalar en **claude.ai**, **Claude Cowork** y
**Claude Code**, con sus conectores declarados. Cada habilidad trabaja con los datos de tu empresa (un perfil que vive en tu Google Drive);
Smart4AI viene adentro solo como ejemplo. Nada se envía ni se publica sin tu aprobación.

| Plugin | Habilidades | Conectores |
|---|---|---|
| [`smart4ai-habilidades-1-comercial`](plugins/smart4ai-habilidades-1-comercial/) | el arranque · mi voz · el cotizador · el precio con margen | Google Drive · Gmail · Google Calendar · Firecrawl |
| [`smart4ai-habilidades-2-contenido`](plugins/smart4ai-habilidades-2-contenido/) | el arranque de contenido · el post con la voz de la marca · la imagen del post · el video del post | Cloudinary · Notion · Google Drive · Clipkit · Descript · Hugging Face |

Y un plugin aparte, de la Feria Effix:

- [`radar-tienda`](plugins/radar-tienda/) · **Del producto a la tienda**: estudio de mercado de un producto (skill de Carlos Jiménez), imágenes, producto en borrador en tu Shopify, anuncio para Meta revisado y tablero en vivo con recibo de costos; nunca publica. Instálalo en Claude Code con `/plugin marketplace add santivelezia/smart4ai-plugins` y `/plugin install radar-tienda@smart4ai-plugins`.

## Instalar

**claude.ai y Claude Cowork** (sin instalar nada en el computador): **Configuración → Personalizar → Plugins → Agregar →
Agregar marketplace → Agregar desde un repositorio**, escribe `santivelezia/smart4ai-plugins`, pulsa **Sincronizar** y, en la
pestaña **Descubrir**, **Agregar** en el plugin que quieras. En la ficha del plugin, la pestaña **Conectores** muestra cada uno
con su botón **Conectar**. Como respaldo, cada plugin también se entrega como archivo `.plugin` (**Agregar → Subir plugin**).

**Claude Code** (dos comandos, una sola vez):

```
claude plugin marketplace add santivelezia/smart4ai-plugins
claude plugin install smart4ai-habilidades-1-comercial@smart4ai-plugins
```
(y `smart4ai-habilidades-2-contenido@smart4ai-plugins` para el segundo). Después, `/mcp` para autorizar los conectores.

**Habilidad por habilidad (sin plugin):** cada una viene también como ZIP en las descargas de cada versión, para
`Configuración → Personalizar → Habilidades → Agregar → Subir habilidad`.

**Después de instalar, escribe "arranque"** (o "arranque de contenido"): revisa tus conectores, te hace las preguntas de tu
empresa una sola vez y deja todo listo. La guía paso a paso con capturas está en el curso.

## Actualizar

En claude.ai y Cowork, con **Sincronizar automáticamente** encendido, las mejoras llegan solas. En Claude Code:
`claude plugin update <plugin>@smart4ai-plugins`. Las versiones están en el índice y en el `CHANGELOG.md` de cada habilidad.

## Licencia

Uso personal y de tu empresa, no transferible: ver [`LICENSE`](LICENSE). Smart4AI · Medellín · smart4ai.io
