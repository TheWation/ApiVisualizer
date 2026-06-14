# API Visualizer

[![made-with-python](http://forthebadge.com/images/badges/made-with-python.svg)](https://www.python.org/)
[![built-with-love](http://forthebadge.com/images/badges/built-with-love.svg)](https://gitHub.com/TheWation/)

API Visualizer converts an exported `swagger.json` or `openapi.json` file, or a remote Swagger/OpenAPI JSON URL, into a portable interactive documentation folder powered by Swagger UI. Each generated API gets its own folder under `output`, with `index.html` and all required static assets copied beside it.

## Features

- Detects Swagger 2.0 and OpenAPI 3.x JSON documents automatically.
- Accepts local JSON files and remote HTTP/HTTPS JSON URLs.
- Embeds the API specification inside the generated HTML file.
- Copies Swagger UI JavaScript, CSS, source maps, licenses, and favicons into each generated output folder.
- Provides Swagger UI features such as endpoint browsing, schema inspection, filtering, deep links, authorization persistence, and `Try it out`.
- Supports overriding the API server URL so interactive requests can target the correct environment.
- Uses only Python's standard library at runtime.

## Requirements

- Python 3.9 or newer.
- Local Swagger UI assets in `static/swagger-ui`.
- Internet access is only needed when using a remote input URL. Generated HTML files do not load Swagger UI assets from a CDN.

## Usage

Generate documentation from an OpenAPI export:

```bash
python ApiVisualizer.py -i openapi.json
```

Generate documentation from a remote Swagger/OpenAPI URL:

```bash
python ApiVisualizer.py -u https://api.example.com/swagger.json --name api-docs.html
```

Generate documentation from a Swagger/OpenAPI export and overwrite an existing output file:

```bash
python ApiVisualizer.py -i swagger.json --overwrite
```

Choose a custom output directory and folder name:

```bash
python ApiVisualizer.py -i openapi.json --output-dir docs --name api-docs
```

Override the server URL used by Swagger UI's `Try it out` requests:

```bash
python ApiVisualizer.py -i openapi.json --server-url https://api.example.com/v1 --overwrite
```

The generated file will be available at:

```text
output/<input-or-url-name>/index.html
```

Each generated folder also contains:

```text
output/<input-or-url-name>/assets/swagger-ui/
```

## Notes

- Remote URLs must return a JSON Swagger/OpenAPI document.
- Use `-i/--input` for local files and `-u/--url` for remote JSON URLs. Exactly one source is required.
- `--name` controls the generated folder name. If you pass `api-docs.html`, the folder will still be named `api-docs`.
- For OpenAPI 3.x documents, `--server-url` replaces the top-level `servers` list with the provided URL.
- For Swagger 2.0 documents, `--server-url` must be an absolute URL such as `https://api.example.com/v1`; it is converted into `schemes`, `host`, and `basePath`.
- If your API requires authentication, use the `Authorize` button in the generated Swagger UI page.
- If `Try it out` fails from a local HTML file, check the API server URL and CORS settings on the API.

## Swagger UI Assets

The project keeps built Swagger UI browser assets in `static/swagger-ui`, so `node_modules` and npm are not required to run the generator. If you ever want to upgrade Swagger UI, download or install a newer `swagger-ui-dist` package separately and replace the files in `static/swagger-ui`.

## Examples Included

This repository includes two real API exports:

- `swagger.json`
- `openapi.json`

You can generate both sample documents with:

```bash
python ApiVisualizer.py -i swagger.json --overwrite
python ApiVisualizer.py -i openapi.json --overwrite
```

## License
`ApiVisualizer` is made with ♥  by [Wation](https://github.com/TheWation) and it's released under the `MIT` license.