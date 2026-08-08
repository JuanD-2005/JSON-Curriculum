#!/usr/bin/env python3
"""
Vista previa en vivo, al estilo del panel derecho de FlowCV — pero corriendo
en tu máquina y sobre HTML (no PDF, para que cada guardado se sienta
instantáneo en vez de esperar el render de WeasyPrint en cada tecla).

Qué hace:
  1. Levanta un servidor HTTP local (por defecto http://localhost:8420).
  2. Renderiza content/resume.json -> HTML con el mismo template/CSS del PDF.
  3. Vigila content/, templates/ y styles/ con watchdog.
  4. Al detectar un cambio: re-valida, re-renderiza, y sube un contador de
     versión. La página abierta en el navegador hace polling liviano cada
     600ms a /version y se recarga sola si cambió — sin WebSockets, sin
     dependencias de Node.

Uso:
  pip install -r requirements.txt
  python3 scripts/watch.py               # sirve el primer rol/idioma disponible
  python3 scripts/watch.py --role ia --lang en
  python3 scripts/watch.py --port 9000

Abre la URL que imprime en tu navegador y deja el proceso corriendo mientras
editas content/resume.json, templates/resume.html.j2 o styles/resume.css.
"""
import argparse
import http.server
import pathlib
import re
import socketserver
import sys
import threading
import time

from jinja2 import Environment, FileSystemLoader
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from validate import validate_file, ValidationError, DEFAULT_CONTENT_PATH  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"
STYLES_DIR = ROOT / "styles"

BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")

# Estado compartido entre el watcher (hilo background) y el servidor HTTP.
STATE = {"version": 0, "html": "<p>Generando vista previa…</p>", "error": None}
STATE_LOCK = threading.Lock()

RELOAD_SNIPPET = """
<script>
  let currentVersion = null;
  async function poll() {
    try {
      const res = await fetch('/version');
      const v = await res.text();
      if (currentVersion === null) currentVersion = v;
      else if (v !== currentVersion) location.reload();
    } catch (e) { /* servidor reiniciando, seguimos intentando */ }
    setTimeout(poll, 600);
  }
  poll();
</script>
"""


def bold_filter(text: str) -> str:
    return BOLD_PATTERN.sub(r"<strong>\1</strong>", text)


def render_preview(content_path: pathlib.Path, role: str, lang: str):
    content = validate_file(content_path)  # lanza ValidationError si algo está mal
    role_obj = next(r for r in content["meta"]["roles"] if r["key"] == role)

    css = (STYLES_DIR / "resume.css").read_text(encoding="utf-8")
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["bold"] = bold_filter
    template = env.get_template("resume.html.j2")

    html = template.render(
        content=content, role=role, lang=lang,
        role_label=role_obj["label"][lang], L=content["labels"][lang], css=css,
    )
    # Inyectamos el snippet de auto-reload justo antes de </body>
    return html.replace("</body>", RELOAD_SNIPPET + "</body>")


def rebuild(content_path, role, lang):
    with STATE_LOCK:
        try:
            html = render_preview(content_path, role, lang)
            STATE["html"] = html
            STATE["error"] = None
        except ValidationError as e:
            STATE["error"] = str(e)
        except Exception as e:  # errores de template, etc.
            STATE["error"] = f"Error de render: {e}"
        STATE["version"] += 1
    tag = "✓ vista actualizada" if STATE["error"] is None else "✗ error (ver navegador)"
    print(f"[watch] {tag} (v{STATE['version']})")


class DebouncedHandler(FileSystemEventHandler):
    """Evita re-renderizar 5 veces por un solo guardado (muchos editores
    disparan varios eventos de filesystem seguidos)."""
    def __init__(self, rebuild_fn, debounce_seconds=0.3):
        self.rebuild_fn = rebuild_fn
        self.debounce_seconds = debounce_seconds
        self._timer = None

    def on_any_event(self, event):
        if event.is_directory:
            return
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self.debounce_seconds, self.rebuild_fn)
        self._timer.start()


class PreviewHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silencioso; ya logueamos nosotros en rebuild()

    def do_GET(self):
        if self.path == "/version":
            with STATE_LOCK:
                body = str(STATE["version"]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        with STATE_LOCK:
            if STATE["error"]:
                body = (
                    "<html><body style='font-family:monospace;white-space:pre-wrap;"
                    "padding:2rem;color:#900'>"
                    f"VALIDACIÓN FALLÓ:\n\n{STATE['error']}" + RELOAD_SNIPPET +
                    "</body></html>"
                ).encode("utf-8")
            else:
                body = STATE["html"].encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--content", default=str(DEFAULT_CONTENT_PATH))
    parser.add_argument("--role", default=None, help="Rol a previsualizar (default: el primero en meta.roles)")
    parser.add_argument("--lang", default=None, help="Idioma a previsualizar (default: el primero en meta.languages)")
    parser.add_argument("--port", type=int, default=8420)
    args = parser.parse_args()

    content_path = pathlib.Path(args.content)
    base = validate_file(content_path)
    role = args.role or base["meta"]["roles"][0]["key"]
    lang = args.lang or base["meta"]["languages"][0]

    rebuild_fn = lambda: rebuild(content_path, role, lang)  # noqa: E731
    rebuild_fn()

    handler = DebouncedHandler(rebuild_fn)
    observer = Observer()
    for watched in (content_path.parent, TEMPLATES_DIR, STYLES_DIR):
        observer.schedule(handler, str(watched), recursive=False)
    observer.start()

    with socketserver.TCPServer(("127.0.0.1", args.port), PreviewHandler) as httpd:
        print(f"[watch] Vista previa en vivo: http://127.0.0.1:{args.port}  (rol={role}, lang={lang})")
        print("[watch] Editando content/resume.json, templates/ o styles/ recarga solo. Ctrl+C para salir.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            observer.stop()
            observer.join()


if __name__ == "__main__":
    main()
