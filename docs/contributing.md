# Contributing

Thank you for contributing to CodeCrew.

## Contribution Workflow

1. Fork the repository
2. Create a feature branch
3. Implement focused changes
4. Add or update tests
5. Run validation commands
6. Open a pull request with clear context

## Branch Naming

- `feature/<short-description>`
- `fix/<short-description>`
- `docs/<short-description>`
- `refactor/<short-description>`

## Pull Request Requirements

- Clear summary of what changed and why
- Linked issue or context
- Validation evidence:
  - Backend tests passing
  - Frontend build status
  - Docs build status when docs change
- No secrets or credentials in code or docs

## Local Validation Checklist

```bash
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
cd ..
mkdocs build
```

## Code Quality Principles

- Keep changes minimal and coherent
- Follow existing project conventions and patterns
- Prefer explicit, readable code over clever shortcuts
- Handle error states explicitly in API and runtime flows

## Security and Secret Management

- Never commit `.env` secrets
- Rotate any accidentally exposed keys immediately
- Avoid logging provider credentials in command output

## Documentation Standards

- Update docs with every externally visible behavior change
- Add API examples for new endpoints
- Keep troubleshooting entries action-oriented and testable
