#!/usr/bin/env python3
"""Generate a Swagger UI HTML page from a Swagger/OpenAPI JSON export."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
DEFAULT_URL_TIMEOUT = 30
PROJECT_ROOT = Path(__file__).resolve().parent
STATIC_ASSETS_DIR = PROJECT_ROOT / "static" / "swagger-ui"
OUTPUT_ASSETS_DIRNAME = "assets"
SWAGGER_UI_ASSETS_DIRNAME = "swagger-ui"


def logo() -> str:
    """Return the CLI banner."""
    return r'''
 __     __     ______     ______   __     ______     __   __    
/\ \  _ \ \   /\  __ \   /\__  _\ /\ \   /\  __ \   /\ "-.\ \   
\ \ \/ ".\ \  \ \  __ \  \/_/\ \/ \ \ \  \ \ \/\ \  \ \ \-.  \  
 \ \__/".~\_\  \ \_\ \_\    \ \_\  \ \_\  \ \_____\  \ \_\\"\_\ 
  \/_/   \/_/   \/_/\/_/     \/_/   \/_/   \/_____/   \/_/ \/_/ 

                          ApiVisualizer v1.0                                       
'''


class CustomArgumentParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        return logo() + "\n" + super().format_help()

    def error(self, message: str) -> None:
        self.exit(2, f"{logo()}\n{self.format_usage()}{self.prog}: error: {message}\n")


def load_spec(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Input file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Input path is not a file: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            spec = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(spec, dict):
        raise ValueError("The API document must be a JSON object.")
    if "paths" not in spec or not isinstance(spec["paths"], dict):
        raise ValueError("The API document must contain a top-level 'paths' object.")

    return spec


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def parse_spec_json(raw_json: str, source: str) -> dict[str, Any]:
    try:
        spec = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from {source}: {exc}") from exc

    if not isinstance(spec, dict):
        raise ValueError("The API document must be a JSON object.")
    if "paths" not in spec or not isinstance(spec["paths"], dict):
        raise ValueError("The API document must contain a top-level 'paths' object.")

    return spec


def download_spec(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json, application/vnd.oai.openapi+json;q=0.9, */*;q=0.1",
            "User-Agent": "ApiVisualizer/1.0",
        },
    )

    try:
        with urlopen(request, timeout=DEFAULT_URL_TIMEOUT) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            raw_json = response.read().decode(charset)
    except HTTPError as exc:
        raise ValueError(f"Could not download {url}: HTTP {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise ValueError(f"Could not download {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ValueError(f"Timed out while downloading {url}") from exc

    return parse_spec_json(raw_json, url)


def load_spec_from_source(source: str) -> tuple[dict[str, Any], str]:
    if is_url(source):
        return download_spec(source), source

    path = Path(source).resolve()
    return load_spec(path), path.name


def resolve_source(args: argparse.Namespace) -> tuple[dict[str, Any], str, str]:
    if args.input_file:
        path = Path(args.input_file).resolve()
        return load_spec(path), path.name, str(path)

    if not is_url(args.url):
        raise ValueError("URL input must be an HTTP or HTTPS URL.")
    return download_spec(args.url), args.url, args.url


def detect_document_type(spec: dict[str, Any]) -> tuple[str, str]:
    if isinstance(spec.get("openapi"), str):
        return "OpenAPI", spec["openapi"]
    if isinstance(spec.get("swagger"), str):
        return "Swagger", spec["swagger"]
    raise ValueError("Could not detect document type. Expected top-level 'openapi' or 'swagger'.")


def summarize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    paths = spec.get("paths", {})
    operations = 0
    tags: set[str] = set()

    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operations += 1
            for tag in operation.get("tags", []):
                if isinstance(tag, str):
                    tags.add(tag)

    return {
        "path_count": len(paths),
        "operation_count": operations,
        "tag_count": len(tags),
    }


def json_for_script(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (
        payload.replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def apply_server_url(spec: dict[str, Any], server_url: str | None) -> None:
    if not server_url:
        return

    if "openapi" in spec:
        spec["servers"] = [{"url": server_url}]
        return

    if "swagger" in spec:
        match = re.match(r"^(https?)://([^/]+)(/.*)?$", server_url.rstrip("/"))
        if not match:
            raise ValueError("Swagger 2.0 server URL must be absolute, for example: https://api.example.com/v1")
        scheme, host, base_path = match.groups()
        spec["schemes"] = [scheme]
        spec["host"] = host
        spec["basePath"] = base_path or "/"


def safe_stem(value: str) -> str:
    if is_url(value):
        parsed = urlparse(value)
        name = Path(unquote(parsed.path)).stem or parsed.netloc
    else:
        name = Path(value).stem

    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return name or "api-docs"


def make_output_folder_name(source: str, output_name: str | None) -> str:
    if output_name:
        candidate = Path(output_name).stem
    else:
        candidate = safe_stem(source)

    candidate = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate).strip(".-")
    return candidate or "api-docs"


def build_html(spec: dict[str, Any], input_name: str, doc_type: str, version: str) -> str:
    info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
    title = str(info.get("title") or input_name)
    spec_json = json_for_script(spec)

    page_title = f"{title} API Docs"
    escaped_page_title = html.escape(page_title)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_page_title}</title>
  <link rel="icon" sizes="16x16" href="assets/swagger-ui/favicon-16x16.png">
  <link rel="icon" sizes="32x32" href="assets/swagger-ui/favicon-32x32.png">
  <link rel="stylesheet" href="assets/swagger-ui/swagger-ui.css">
  <style>
    :root {{
      --page-bg: #f4f7f9;
      --ink: #162033;
      --muted: #667085;
      --line: #d8e0ea;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-soft: #dff6f2;
      --code-bg: #101828;
    }}

    body {{
      margin: 0;
      background:
        linear-gradient(180deg, rgba(15, 118, 110, 0.08), rgba(244, 247, 249, 0) 260px),
        var(--page-bg);
      color: var(--ink);
    }}

    .topbar,
    .topbar-wrapper img,
    .topbar-wrapper span {{
      display: none;
    }}

    #swagger-ui {{
      max-width: 1380px;
      margin: 0 auto;
      padding: 26px 18px 56px;
    }}

    .swagger-ui {{
      color: var(--ink);
      font-family: "Segoe UI", Tahoma, sans-serif;
    }}

    .swagger-ui .wrapper {{
      padding: 0;
    }}

    .swagger-ui .info {{
      margin: 0 0 18px;
      padding: 22px 24px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.86);
      box-shadow: 0 18px 45px rgba(16, 24, 40, 0.06);
    }}

    .swagger-ui .info .title {{
      color: var(--ink);
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(1.8rem, 3vw, 2.75rem);
      line-height: 1.08;
      letter-spacing: 0;
    }}

    .swagger-ui .info .title small {{
      top: -4px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: #0b625b;
      font-size: 11px;
    }}

    .swagger-ui .info p,
    .swagger-ui .info li,
    .swagger-ui .info table {{
      color: var(--muted);
      line-height: 1.65;
    }}

    .swagger-ui .scheme-container {{
      margin: 0 0 18px;
      padding: 18px 20px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.9);
      box-shadow: 0 10px 28px rgba(16, 24, 40, 0.05);
    }}

    .swagger-ui .scheme-container .schemes {{
      align-items: center;
      gap: 10px;
    }}

    .swagger-ui .filter-container {{
      margin: 0 0 18px;
      padding: 0;
    }}

    .swagger-ui .filter-container input {{
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: none;
      color: var(--ink);
    }}

    .swagger-ui .opblock-tag {{
      margin: 18px 0 10px;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.78);
      color: var(--ink);
      font-size: 20px;
    }}

    .swagger-ui .opblock {{
      overflow: hidden;
      border-radius: 8px;
      box-shadow: 0 12px 28px rgba(16, 24, 40, 0.06);
    }}

    .swagger-ui .opblock .opblock-summary {{
      min-height: 54px;
      padding: 8px 12px;
    }}

    .swagger-ui .opblock .opblock-summary-method {{
      min-width: 78px;
      border-radius: 6px;
      font-size: 12px;
      letter-spacing: 0;
    }}

    .swagger-ui .opblock .opblock-summary-path {{
      color: var(--ink);
      font-size: 15px;
      word-break: break-word;
    }}

    .swagger-ui .btn {{
      border-radius: 6px;
      box-shadow: none;
    }}

    .swagger-ui .btn.authorize {{
      border-color: var(--accent);
      color: var(--accent);
    }}

    .swagger-ui textarea,
    .swagger-ui input,
    .swagger-ui select {{
      border-radius: 6px;
    }}

    .swagger-ui .highlight-code,
    .swagger-ui .microlight {{
      background: var(--code-bg) !important;
    }}

    @media (max-width: 680px) {{
      #swagger-ui {{
        padding-inline: 8px;
      }}

      .swagger-ui .info,
      .swagger-ui .scheme-container {{
        padding: 16px;
      }}

      .swagger-ui .opblock .opblock-summary-method {{
        min-width: 66px;
      }}
    }}
  </style>
</head>
<body>
  <main id="swagger-ui"></main>

  <script src="assets/swagger-ui/swagger-ui-bundle.js"></script>
  <script src="assets/swagger-ui/swagger-ui-standalone-preset.js"></script>
  <script>
    window.__API_SPEC__ = {spec_json};
    window.addEventListener("load", function () {{
      window.ui = SwaggerUIBundle({{
        spec: window.__API_SPEC__,
        dom_id: "#swagger-ui",
        deepLinking: true,
        displayOperationId: true,
        filter: true,
        showExtensions: true,
        showCommonExtensions: true,
        tryItOutEnabled: true,
        persistAuthorization: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        plugins: [
          SwaggerUIBundle.plugins.DownloadUrl
        ],
        layout: "BaseLayout"
      }});
    }});
  </script>
</body>
</html>
"""


def copy_static_assets(output_folder: Path) -> None:
    if not STATIC_ASSETS_DIR.exists():
        raise FileNotFoundError(
            f"Swagger UI assets were not found at {STATIC_ASSETS_DIR}. "
            "Place built swagger-ui-dist assets in static/swagger-ui."
        )

    target = output_folder / OUTPUT_ASSETS_DIRNAME / SWAGGER_UI_ASSETS_DIRNAME
    target.mkdir(parents=True, exist_ok=True)
    for asset in STATIC_ASSETS_DIR.iterdir():
        if asset.is_file():
            shutil.copy2(asset, target / asset.name)


def write_output(html_content: str, output_folder: Path, overwrite: bool) -> Path:
    index_path = output_folder / "index.html"
    if index_path.exists() and not overwrite:
        raise FileExistsError(f"Output file already exists: {index_path}. Use --overwrite to replace it.")

    output_folder.mkdir(parents=True, exist_ok=True)
    copy_static_assets(output_folder)
    index_path.write_text(html_content, encoding="utf-8")
    return index_path


def parse_args() -> argparse.Namespace:
    parser = CustomArgumentParser(
        description="Convert an exported Swagger/OpenAPI JSON file into an interactive Swagger UI HTML page."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("-i", "--input", dest="input_file", help="Path to swagger.json/openapi.json")
    source.add_argument("-u", "--url", help="HTTP/HTTPS URL to swagger.json/openapi.json")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("output"), help="Directory for generated HTML")
    parser.add_argument("-n", "--name", help="Output folder name. Defaults to the input filename or URL filename")
    parser.add_argument(
        "--server-url",
        help="Override the API server/base URL used by Try it out, for example https://api.example.com/v1",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace the output file if it already exists")
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        spec, source_name, source_value = resolve_source(args)
        doc_type, version = detect_document_type(spec)
        apply_server_url(spec, args.server_url)

        output_name = make_output_folder_name(source_value, args.name)
        output_folder = (args.output_dir / output_name).resolve()
        html_content = build_html(spec, source_name, doc_type, version)
        index_path = write_output(html_content, output_folder, args.overwrite)

        summary = summarize_spec(spec)
        print(logo())
        print(f"Generated {doc_type} {version} documentation: {index_path}")
        print(f"Included {summary['path_count']} paths, {summary['operation_count']} operations, {summary['tag_count']} tags.")
        return 0
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(logo())
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
