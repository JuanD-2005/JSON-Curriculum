#!/usr/bin/env python3
"""
Genera el CV en PDF a partir de content/resume.json (fuente única,
multilenguaje real) + templates/resume.html.j2.

Antes de renderizar, SIEMPRE valida contra schema/resume.schema.json (ver
scripts/validate.py). Si el JSON tiene un campo faltante, una traducción
incompleta, o un tag desconocido, el build se detiene con un error claro
en vez de generar un PDF defectuoso.

Uso:
  python3 scripts/build.py                        # genera TODAS las combinaciones (role x lang)
  python3 scripts/build.py --role ia               # todos los idiomas, solo rol "ia"
  python3 scripts/build.py --role ia --lang es      # una sola combinación
  python3 scripts/build.py --role ia --lang en --out mi_cv.pdf
  python3 scripts/build.py --list-roles             # ver qué roles existen sin generar nada
"""
import argparse
import pathlib
import re
import sys

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from validate import validate_file, ValidationError, DEFAULT_CONTENT_PATH  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"
STYLES_DIR = ROOT / "styles"
DIST_DIR = ROOT / "dist"

BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")


def bold_filter(text: str) -> str:
    """Convierte **texto** (markdown liviano) en <strong>texto</strong>."""
    return BOLD_PATTERN.sub(r"<strong>\1</strong>", text)


def load_content(content_path: pathlib.Path):
    """Valida y carga el JSON. Aborta con mensaje claro si es inválido."""
    try:
        return validate_file(content_path)
    except ValidationError as e:
        sys.exit(f"✗ No se generó ningún PDF — el contenido es inválido.\n\n{e}")


def render_one(content, role: str, lang: str, out_path: pathlib.Path):
    role_obj = next((r for r in content["meta"]["roles"] if r["key"] == role), None)
    if role_obj is None:
        sys.exit(f"Rol desconocido: '{role}'. Roles disponibles: "
                  f"{[r['key'] for r in content['meta']['roles']]}")

    css = (STYLES_DIR / "resume.css").read_text(encoding="utf-8")
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["bold"] = bold_filter
    template = env.get_template("resume.html.j2")

    html_str = template.render(
        content=content,
        role=role,
        lang=lang,
        role_label=role_obj["label"][lang],
        L=content["labels"][lang],
        css=css,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_str, base_url=str(ROOT)).write_pdf(str(out_path))
    print(f"OK  role={role} lang={lang} -> {out_path.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--content", default=str(DEFAULT_CONTENT_PATH), help="Ruta al resume.json (default: content/resume.json)")
    parser.add_argument("--role", help="Generar solo este rol (por defecto: todos los definidos en meta.roles)")
    parser.add_argument("--lang", help="Generar solo este idioma (por defecto: todos los definidos en meta.languages)")
    parser.add_argument("--out", help="Nombre de archivo de salida (solo válido junto con --role y --lang específicos)")
    parser.add_argument("--list-roles", action="store_true", help="Listar los roles disponibles y salir")
    args = parser.parse_args()

    content = load_content(pathlib.Path(args.content))

    available_roles = [r["key"] for r in content["meta"]["roles"]]
    available_langs = content["meta"]["languages"]

    if args.list_roles:
        print("Roles disponibles:")
        for r in content["meta"]["roles"]:
            print(f"  - {r['key']}: {r['label'].get('es', '')}")
        print(f"Idiomas disponibles: {available_langs}")
        return

    if args.role and args.role not in available_roles:
        sys.exit(f"--role '{args.role}' no existe. Disponibles: {available_roles}")
    if args.lang and args.lang not in available_langs:
        sys.exit(f"--lang '{args.lang}' no existe. Disponibles: {available_langs}")

    roles = [args.role] if args.role else available_roles
    langs = [args.lang] if args.lang else available_langs

    if args.out and (len(roles) != 1 or len(langs) != 1):
        sys.exit("--out solo se puede usar junto con --role y --lang específicos (una sola combinación).")

    for role in roles:
        for lang in langs:
            out_path = DIST_DIR / (args.out or f"{content['basics']['name'].replace(' ', '_')}_CV_{lang}_{role}.pdf")
            render_one(content, role, lang, out_path)


if __name__ == "__main__":
    main()
