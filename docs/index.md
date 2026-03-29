# CodeCrew Documentation

Welcome to the official CodeCrew documentation package.

This documentation is designed to be:

- Clear and task-oriented for developers and operators
- Searchable and easy to navigate
- Version-controlled alongside the source code
- Publishable in responsive HTML and PDF formats

## Documentation Scope

This package includes:

- Project overview and core concepts
- Architecture and component diagrams
- Full API reference with practical examples
- Step-by-step installation and configuration guides
- Troubleshooting runbooks for common failures
- Contribution and release/versioning guidelines

## Quick Links

- [Project Overview](project-overview.md)
- [Architecture](architecture.md)
- [API Reference](api-reference.md)
- [Installation](installation.md)
- [Configuration](configuration.md)
- [Troubleshooting](troubleshooting.md)
- [Contributing](contributing.md)
- [Versioning and Release](versioning.md)

## Build and Publish

Generate responsive HTML:

```bash
py -m mkdocs build --strict
```

Generate PDF bundle:

```bash
py -m mkdocs build -f mkdocs-pdf.yml
```

Run local docs server:

```bash
py -m mkdocs serve
```
