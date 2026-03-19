# AGENTS

Repository guidance for coding agents working in this project.

## Scope

- Raspberry Pi daemon that emulates EV behavior via Annex96 PLC-HAT.
- Runtime entrypoint: `python -m daemon.main`
- Installer: `scripts/install_pi.sh`
- Service name: `annex96-ev-emulator.service`

## Project Rules

- Prefer minimal, direct changes.
- Keep scripts idempotent where possible.
- Do not hardcode a specific local username in install paths unless requested.
- Keep defaults aligned across:
  - `scripts/install_pi.sh`
  - `scripts/annex96-ev-emulator.service`
  - `README.md`

## Documentation Rules

- Keep only one canonical copy for the hardware docs in `documentation/`.
- Use the `.pdf.txt` extracted versions for searchable references.
- Update `README.md` when install/runtime behavior changes.
- Update `CHANGELOG.md` for user-visible changes.

## Validation Before Commit

Run:

```bash
python -m compileall daemon
bash -n scripts/install_pi.sh
```

## Release Hygiene

- Keep `VERSION`, `daemon.__version__`, and changelog in sync.
- Use `RELEASE.md` checklist when cutting a tag.
