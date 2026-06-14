# Contributing to API Visualizer

Thank you for your interest in contributing to API Visualizer. Contributions, bug reports, documentation fixes, and practical feedback are welcome.

## Submitting Issues

If you find a bug, please include:

1. The command you ran.
2. The input type you used, local file or URL.
3. The Python version.
4. The error message or unexpected output.
5. A minimal Swagger/OpenAPI example when possible.

## Contributing Code

Please follow these steps:

1. Fork or clone the repository.
2. Create a focused branch for your change.
3. Keep changes small and related to one purpose.
4. Run the local checks before submitting:

```bash
python -m py_compile ApiVisualizer.py
python ApiVisualizer.py -i swagger.json --overwrite
python ApiVisualizer.py -i openapi.json --overwrite
python ApiVisualizer.py -i openapi.json --params --overwrite
```

5. Submit a pull request with a short explanation of the change and any testing performed.

## Development Notes

- The generator should remain usable with Python's standard library.
- Built Swagger UI assets live in `static/swagger-ui`.
- Generated documentation belongs in `output` and should not be committed.
