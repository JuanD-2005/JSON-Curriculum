# Contexto del proyecto (para retomar en Claude Code)

Este proyecto se construyó de forma iterativa en una conversación con Claude
(chat). Este documento resume las decisiones ya tomadas para que una sesión
nueva de Claude Code no las repita ni las contradiga sin querer.

## Qué es esto

Generador de CV en PDF para Juan Paredes, a partir de `content/resume.json`
(fuente única, multilenguaje, con tags de rol). Ver `README.md` para el uso
diario — este archivo es sobre **por qué** está hecho así.

## Decisiones ya tomadas (no las revisites sin razón nueva)

1. **WeasyPrint, no Puppeteer.** Se evaluó explícitamente. WeasyPrint no
   necesita Chrome/Chromium, es más liviano, y el diseño (1 columna, sin
   grid/flex complejo) no necesita el motor de layout de un navegador
   completo. No migrar a Puppeteer/Playwright sin una razón concreta (ej.
   necesitar CSS Grid avanzado que WeasyPrint no soporte bien).

2. **Schema propio, no JSON Resume (jsonresume.org).** Se consideró y se
   descartó: el estándar no tiene soporte nativo para `tags` de filtrado por
   rol ni para campos multilenguaje `{es, en}`. Adoptarlo hubiera significado
   extenderlo de todas formas, perdiendo el beneficio de "usar un estándar".

3. **Diseño ATS-safe es un requisito, no un detalle estético.** El CV se usa
   para postular a vacantes reales. Reglas que no se deben romper al tocar
   `styles/resume.css`:
   - Una sola columna (multi-columna confunde a los parsers ATS).
   - Sin tablas para layout, sin iconos como glifos, sin imágenes con texto.
   - Todo el texto debe seguir siendo extraíble con `pdftotext -layout`.
   - Verificar esto después de CUALQUIER cambio de CSS/template con:
     ```bash
     pdftotext -layout dist/Juan_Paredes_CV_es_web.pdf -
     ```

4. **1 página por combinación rol×idioma.** Es una restricción deliberada
   (estándar para perfil de estudiante/junior). Si el contenido crece y se
   desborda a 2 páginas, la prioridad es: reducir `line-height`/`font-size`/
   márgenes en `styles/resume.css` ANTES que recortar contenido. Verificar
   con:
     ```bash
     python3 -c "from pdf2image import convert_from_path; print(len(convert_from_path('dist/Juan_Paredes_CV_es_web.pdf')))"
     ```

5. **Los hipervínculos del header son reales (`<a href>`), no texto plano.**
   Se verificó con `pypdf` que WeasyPrint efectivamente embebe anotaciones de
   link (`tel:`, `mailto:`, `https://`). Cualquier cambio al header debe
   preservar esto — verificar con:
     ```python
     from pypdf import PdfReader
     r = PdfReader("dist/Juan_Paredes_CV_es_web.pdf")
     print(r.pages[0].get("/Annots"))
     ```

6. **Orden de `experience` es intencional.** Freelance y Docente Técnico van
   primero porque ambos están "2024 – Presente" (vigentes); BeeLearnStudio va
   último porque su contrato ya cerró (02/2026 – 04/2026). No reordenar por
   fecha de inicio sin más — el criterio es vigencia, no antigüedad.

7. **Negritas dentro de bullets vía `**texto**`** (markdown liviano),
   convertido a `<strong>` por el filtro Jinja2 `bold` en `build.py`/
   `watch.py`. Se usa para resaltar tecnologías clave dentro de un bullet,
   igual que en el CV original hecho en FlowCV. No hardcodear `<strong>`
   directo en el JSON — usar `**...**` para que quede consistente y fácil de
   editar.

## Pendiente conocido

- `basics.links.portfolio` está vacío (no se pudo leer la URL desde la
  imagen del QR original). Cuando el usuario la tenga, va sin `https://`
  (ej. `"miportafolio.dev"`), igual que `linkedin`/`github`.
- El repo del usuario fue creado a partir de un `.zip` exportado desde este
  chat — puede haber una versión ligeramente anterior de estos archivos ahí
  si esta sesión no llegó a sincronizarse. Antes de asumir el estado del
  repo, correr `python3 scripts/validate.py` y `git log --oneline` para
  confirmar qué versión hay realmente en disco.

## Cómo verificar que todo sigue sano (correr esto tras cualquier cambio)

```bash
pip install -r requirements.txt
python3 scripts/validate.py                 # falla rápido si algo está mal
python3 scripts/build.py                     # genera las 4 combinaciones
python3 scripts/build_site.py                # arma site/ para GH Pages

# Chequeos que no debería romper ningún cambio:
for f in dist/*.pdf; do
  echo "=== $f ==="
  python3 -c "from pdf2image import convert_from_path; print(len(convert_from_path('$f')), 'página(s)')"
  pdftotext -layout "$f" - | head -3
done
```
