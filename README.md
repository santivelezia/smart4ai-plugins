# smart4ai-plugins · las habilidades de Smart4AI para Claude

Dos plugins con las habilidades del curso **Arquitectos de IA**, listos para instalar en **Claude Cowork** y **Claude Code**,
con sus conectores declarados. Cada habilidad trabaja con los datos de tu empresa (un perfil que vive en tu Google Drive);
Smart4AI viene adentro solo como ejemplo. Nada se envía ni se publica sin tu aprobación.

| Plugin | Habilidades | Conectores |
|---|---|---|
| [`smart4ai-habilidades-1-comercial`](plugins/smart4ai-habilidades-1-comercial/) | el arranque · mi voz · el cotizador · el precio con margen | Google Drive · Gmail · Google Calendar · Firecrawl |
| [`smart4ai-habilidades-2-contenido`](plugins/smart4ai-habilidades-2-contenido/) | el arranque de contenido · el post con la voz de la marca · la imagen del post · el video del post | Cloudinary · Notion · Google Drive · Clipkit · Descript · Hugging Face |

## Instalar

**Claude Code** (dos comandos, una sola vez):

```
claude plugin marketplace add santivelezia/smart4ai-plugins
claude plugin install smart4ai-habilidades-1-comercial@smart4ai-plugins
```
(y `smart4ai-habilidades-2-contenido@smart4ai-plugins` para el segundo). Después, `/mcp` para autorizar los conectores.

**Claude Cowork:** agrega este marketplace desde su enlace en la configuración de plugins y pulsa Instalar; los
conectores se autorizan con un clic cada uno. Como respaldo, cada plugin también se entrega como archivo `.plugin`.

**claude.ai (el chat):** ahí no hay plugins. Cada habilidad se instala por aparte desde su ZIP
(`Configuración → Personalizar → Habilidades → Agregar → Subir habilidad`). Los ZIP están en las descargas de cada versión.

**Después de instalar, escribe "arranque"** (o "arranque de contenido"): revisa tus conectores, te hace las preguntas de tu
empresa una sola vez y deja todo listo. La guía paso a paso con capturas está en el curso.

## Actualizar

`claude plugin update <plugin>@smart4ai-plugins` (Claude Code) o desde Cowork. Las versiones están en el índice y en
`CHANGELOG.md` de cada habilidad.

## Licencia

Uso personal y de tu empresa, no transferible: ver [`LICENSE`](LICENSE). Smart4AI · Medellín · smart4ai.io
