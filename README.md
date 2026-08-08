# CV Automation — Juan Paredes

Generador de CV en PDF a partir de **un único** archivo de datos, con:

- Filtrado por rol/tags (como pedirle al compilador "dame el CV para X vacante").
- Multilenguaje real desde un solo origen (sin archivos duplicados por idioma).
- Validación estricta antes de generar cualquier PDF.
- Vista previa en vivo mientras editas (sin depender de FlowCV).
- CI/CD: cada `git push` valida, genera los PDFs y los publica en GitHub Pages.

## Arquitectura

```
content/resume.json        ← ÚNICA fuente de verdad (multilenguaje, con tags)
schema/resume.schema.json  ← contrato de datos (JSON Schema)
templates/resume.html.j2   ← un solo template, reutilizado para todo rol/idioma
styles/resume.css          ← diseño ATS-safe (1 columna, sin iconos, sin tablas)
scripts/
  validate.py   ← valida resume.json (schema + reglas semánticas)
  build.py      ← genera dist/*.pdf (valida primero, siempre)
  build_site.py ← arma site/ (PDFs + index.html) para GitHub Pages
  watch.py      ← servidor local con recarga automática (vista previa en vivo)
.github/workflows/build-resume.yml  ← CI: valida → genera → publica
```

### Por qué un solo `resume.json` y no un archivo por idioma

Antes teníamos `resume.es.json` y `resume.en.json` duplicados. El riesgo real:
agregar una experiencia nueva y olvidar replicarla en el otro idioma, y no
enterarte hasta que alguien lee el CV en inglés con un hueco. Ahora cada campo
de texto es un objeto `{ "es": "...", "en": "..." }` dentro del mismo nodo, y
`validate.py` **falla el build** si a un bullet le falta una traducción o si
las listas de bullets es/en tienen distinta cantidad de ítems.

### Cómo funciona el filtrado por rol (la ventaja real sobre FlowCV)

Cada ítem de `experience`/`projects` tiene un array `"tags"`:

- `"core"` → aparece en **todos** los roles.
- cualquier otro tag (`"web"`, `"ia"`, ...) → aparece solo cuando ese tag
  coincide con el rol que estás generando.

Los roles disponibles se declaran en `meta.roles` — agregar un rol nuevo
(ej. para adaptar el CV a una vacante puntual) es 100% edición de datos, cero
código:

```json
{ "key": "backend", "label": { "es": "Backend Engineer", "en": "Backend Engineer" } }
```

y luego etiquetar los ítems relevantes con `"backend"` en su `tags`.

## Uso local

```bash
pip install -r requirements.txt

# Valida el JSON contra el schema + reglas semánticas
python3 scripts/validate.py

# Genera TODAS las combinaciones rol x idioma en dist/
python3 scripts/build.py

# Solo una combinación (para una vacante puntual)
python3 scripts/build.py --role ia --lang es

# Nombre de archivo custom
python3 scripts/build.py --role ia --lang en --out mi_cv.pdf

# Ver qué roles/idiomas existen sin generar nada
python3 scripts/build.py --list-roles
```

### Vista previa en vivo (equivalente al panel de FlowCV)

```bash
python3 scripts/watch.py --role web --lang es
```

Abre `http://127.0.0.1:8420` en el navegador y déjalo corriendo. Cada vez que
guardes `content/resume.json`, `templates/resume.html.j2` o
`styles/resume.css`, la página se re-renderiza y se recarga sola (polling
liviano, sin WebSockets ni Node). Si el JSON queda inválido a mitad de una
edición, el navegador muestra el error de validación en vez de una página
rota — así sabes al instante qué corregir.

> Nota: esto sirve **HTML**, no PDF, para que la recarga sea instantánea. Usa
> el mismo `resume.css`, así que el parecido con el PDF final es prácticamente
> 1:1. Para el PDF real, corre `build.py`.

## CI/CD (GitHub Actions → GitHub Pages)

En cada `git push` a `main` que toque `content/`, `templates/`, `styles/`,
`schema/` o `scripts/`, el workflow:

1. **Valida** `content/resume.json`. Si falla, el workflow se detiene ahí —
   nunca se llega a publicar un PDF roto.
2. Genera los PDFs (`scripts/build.py`).
3. Arma `site/` (`scripts/build_site.py`): copia los PDFs + genera un
   `index.html` con un link de descarga por cada rol/idioma.
4. Sube los PDFs como *artifact* de la ejecución (descargable desde la pestaña
   Actions).
5. Comitea los PDFs de vuelta a `dist/` en el repo (link permanente tipo
   `.../raw/main/dist/Juan_Paredes_CV_es_ia.pdf`).
6. Publica `site/` en **GitHub Pages** — link estable con todos los CVs.

**Para activarlo la primera vez:** en el repo de GitHub, ve a
`Settings → Pages → Source` y selecciona **GitHub Actions** (no "Deploy from
a branch"). Después de eso, cada push despliega solo.

## Stack y por qué

| Decisión | Alternativa considerada | Por qué esta y no la otra |
|---|---|---|
| Jinja2 + WeasyPrint | Puppeteer/Playwright + Chrome headless | WeasyPrint no depende de un navegador (menos dependencias, más rápido, corre en cualquier CI sin instalar Chrome). El diseño es deliberadamente simple (1 columna) así que no necesitamos el motor de layout completo de Chrome. |
| Schema propio | Estándar [JSON Resume](https://jsonresume.org/) | JSON Resume no tiene soporte nativo para `tags` de filtrado ni campos multilenguaje — tendríamos que extenderlo igual, perdiendo la limpieza del schema. |
| `http.server` + polling | WebSockets / LiveReload / Vite | Cero dependencias de Node, ~150 líneas, y el caso de uso (recargar una pestaña) no necesita nada más sofisticado. |

## Para agregar contenido nuevo

- **Un logro/proyecto nuevo:** agrégalo en `content/resume.json` con su
  `tags`, y con `{ "es": ..., "en": ... }` en cada campo de texto.
  `validate.py` te avisa si te falta una traducción.
- **Un rol nuevo:** agrégalo en `meta.roles`, agrega su entrada en `summary`,
  y etiqueta los ítems relevantes.
- **Un idioma nuevo:** agrégalo en `meta.languages` y agrega la clave
  correspondiente en cada campo `{ "es", "en", ... }` del JSON — el schema
  actual exige `es` y `en`; si sumas `"fr"` hay que actualizar
  `schema/resume.schema.json` (los `required: ["es","en"]` de las
  definiciones `localized*`) para que también lo exija.

## Pendiente / a tu criterio

- `basics.links.portfolio` sigue vacío — no hay forma de leer la URL desde el
  QR de la imagen original. Complétalo (sin `https://`, ej.
  `"tuportafolio.com"`) y sale como quinto link clicable automáticamente.
- El diseño prioriza compatibilidad ATS (sin columnas, sin iconos). Si en
  algún momento quieres una versión más visual para enviar directo a una
  persona, se puede sumar `styles/resume-visual.css` sin tocar el contenido
  ni el resto del pipeline.
