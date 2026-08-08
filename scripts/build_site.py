#!/usr/bin/env python3
"""
Arma site/ (para publicar en GitHub Pages): copia los PDFs de dist/ y genera
un index.html simple con un link de descarga por cada combinación rol x idioma.

Se corre DESPUÉS de scripts/build.py. Ver .github/workflows/build-resume.yml.
"""
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from validate import validate_file, DEFAULT_CONTENT_PATH  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
SITE_DIR = ROOT / "site"

TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{name} — CV</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; max-width: 640px;
          margin: 3rem auto; padding: 0 1.5rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 0.2rem; }}
  p.sub {{ color: #666; margin-top: 0; }}
  ul {{ list-style: none; padding: 0; }}
  li {{ margin-bottom: 0.6rem; }}
  a.card {{ display: block; padding: 0.9rem 1.1rem; border: 1px solid #ddd; border-radius: 8px;
            text-decoration: none; color: #14424a; font-weight: 600; }}
  a.card:hover {{ border-color: #14424a; background: #f7fafa; }}
  a.card span {{ display: block; font-weight: 400; color: #666; font-size: 0.85rem; margin-top: 0.15rem; }}
  footer {{ margin-top: 2.5rem; font-size: 0.8rem; color: #999; }}
</style>
</head>
<body>
  <h1>{name} — Currículum</h1>
  <p class="sub">Generado automáticamente en cada push. Última actualización: build de CI.</p>
  <ul>
    {items}
  </ul>
  <footer>Generado con content/resume.json + Jinja2 + WeasyPrint. Código fuente en el repo.</footer>
</body>
</html>
"""


def main():
    content = validate_file(DEFAULT_CONTENT_PATH)
    name = content["basics"]["name"]
    roles = content["meta"]["roles"]
    langs = content["meta"]["languages"]

    SITE_DIR.mkdir(exist_ok=True)
    for pdf in DIST_DIR.glob("*.pdf"):
        shutil.copy(pdf, SITE_DIR / pdf.name)

    lang_names = {"es": "Español", "en": "English"}
    items = []
    for role in roles:
        for lang in langs:
            fname = f"{name.replace(' ', '_')}_CV_{lang}_{role['key']}.pdf"
            if not (SITE_DIR / fname).exists():
                continue
            items.append(
                f'<li><a class="card" href="{fname}">{role["label"][lang]}'
                f'<span>{lang_names.get(lang, lang)} · {fname}</span></a></li>'
            )

    html = TEMPLATE.format(name=name, items="\n    ".join(items))
    (SITE_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"OK  site/index.html con {len(items)} PDFs listados.")


if __name__ == "__main__":
    main()
