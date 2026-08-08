#!/usr/bin/env python3
"""
Valida content/resume.json contra schema/resume.schema.json ANTES de generar
cualquier PDF. Objetivo: que un dato faltante o mal tipeado truene aquí, con
un mensaje claro, en vez de silenciosamente generar un PDF con un hueco o
reventar a medio render.

Dos capas de validación:
  1. JSON Schema (estructura, tipos, campos requeridos, traducciones completas).
  2. Chequeos semánticos que un JSON Schema no puede expresar bien:
     - listas de bullets es/en con distinta cantidad de ítems (probable olvido
       de traducir un bullet nuevo).
     - tags que no son "core" ni coinciden con ningún rol declarado en meta.roles
       (probable typo, ej. "wbe" en vez de "web" → el ítem nunca aparecería
       en ningún CV y nadie se daría cuenta).
     - todo rol en meta.roles tiene su entrada correspondiente en "summary".
     - links (linkedin/github/portfolio) no vacíos tienen forma de dominio válida.

Uso:
  python3 scripts/validate.py                # valida content/resume.json
  python3 scripts/validate.py otro.json       # valida otro archivo
"""
import json
import pathlib
import re
import sys

import jsonschema

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "resume.schema.json"
DEFAULT_CONTENT_PATH = ROOT / "content" / "resume.json"

DOMAIN_PATTERN = re.compile(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$")


class ValidationError(Exception):
    pass


def load_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValidationError(f"{path} no es JSON válido: {e}")


def validate_schema(data, schema):
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        lines = []
        for err in errors:
            loc = " -> ".join(str(p) for p in err.path) or "(raíz)"
            lines.append(f"  - En {loc}: {err.message}")
        raise ValidationError("Errores de schema:\n" + "\n".join(lines))


def validate_semantics(data):
    problems = []
    role_keys = {r["key"] for r in data["meta"]["roles"]}
    langs = data["meta"]["languages"]

    # 1) Cada rol declarado debe tener resumen (summary) en todos los idiomas.
    for role in role_keys:
        if role not in data["summary"]:
            problems.append(f"El rol '{role}' está en meta.roles pero no tiene entrada en 'summary'.")

    # 2) tags de experience/projects deben ser 'core' o un rol conocido.
    known_tags = role_keys | {"core"}
    for section in ("experience", "projects"):
        for i, item in enumerate(data[section]):
            unknown = set(item.get("tags", [])) - known_tags
            if unknown:
                label = item.get("name") or item.get("role", {}).get("es") or f"#{i}"
                problems.append(
                    f"{section}[{label}]: tag(s) desconocido(s) {sorted(unknown)} "
                    f"(¿typo? tags válidos: {sorted(known_tags)})"
                )

    # 3) bullets es/en deben tener la misma cantidad de ítems.
    def check_bullet_parity(section_name, items):
        for i, item in enumerate(items):
            b = item.get("bullets")
            if not b:
                continue
            counts = {lang: len(b.get(lang, [])) for lang in langs}
            if len(set(counts.values())) > 1:
                label = item.get("name") or item.get("role", {}).get("es") or f"#{i}"
                problems.append(
                    f"{section_name}[{label}]: cantidad de bullets distinta entre idiomas {counts} "
                    f"(¿falta traducir un bullet nuevo?)"
                )

    check_bullet_parity("experience", data["experience"])
    check_bullet_parity("projects", data["projects"])
    check_bullet_parity("education", data["education"])

    # 4) links no vacíos deben verse como un dominio real.
    #    portfolio es un dict {rol: url}; linkedin/github son strings planos.
    for key, value in data["basics"]["links"].items():
        if key == "portfolio":
            for role, url in value.items():
                if url and not DOMAIN_PATTERN.match(url):
                    problems.append(
                        f"basics.links.portfolio.{role} = '{url}' no parece un dominio válido "
                        f"(formato esperado: 'dominio.com/ruta', sin 'https://')."
                    )
                if role not in role_keys:
                    problems.append(
                        f"basics.links.portfolio tiene la clave '{role}', que no es un rol "
                        f"declarado en meta.roles (¿typo?)."
                    )
            continue
        if value and not DOMAIN_PATTERN.match(value):
            problems.append(
                f"basics.links.{key} = '{value}' no parece un dominio válido "
                f"(formato esperado: 'dominio.com/ruta', sin 'https://')."
            )

    if problems:
        raise ValidationError("Errores semánticos:\n" + "\n".join(f"  - {p}" for p in problems))


def validate_file(content_path: pathlib.Path):
    schema = load_json(SCHEMA_PATH)
    data = load_json(content_path)
    validate_schema(data, schema)
    validate_semantics(data)
    return data


def main():
    content_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONTENT_PATH
    try:
        validate_file(content_path)
    except ValidationError as e:
        print(f"✗ VALIDACIÓN FALLIDA ({content_path})\n\n{e}\n", file=sys.stderr)
        sys.exit(1)
    print(f"✓ {content_path} es válido.")


if __name__ == "__main__":
    main()
