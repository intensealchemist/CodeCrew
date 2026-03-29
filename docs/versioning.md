# Versioning and Release

## Documentation Versioning Strategy

Documentation is version-controlled in the same repository as source code, ensuring every release is traceable to exact implementation state.

## Recommended Release Model

- Use semantic versioning for application releases
- Tag repository with release versions, for example `v0.2.0`
- Publish docs per release branch or tag

## Optional Multi-Version Publishing

For multi-version HTML docs, use `mike` with MkDocs.

Install:

```bash
pip install mike
```

Publish versioned docs:

```bash
mike deploy v0.2 latest
mike set-default latest
```

## Build Artifacts

- HTML site output: `site/`
- PDF output: `site/pdf/codecrew-documentation.pdf`

## Release Checklist

1. Update docs for user-facing changes
2. Run backend tests and frontend build
3. Build docs in HTML and PDF modes
4. Create release tag
5. Publish docs artifacts
