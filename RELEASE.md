# Release Process

This repository is prepared for `1.0.0`.

## Pre-Release Checks

1. Ensure working tree is clean: `git status`
2. Validate Python sources compile:
   - `python -m compileall daemon`
3. Validate installer script syntax:
   - `bash -n scripts/install_pi.sh`
4. Verify README and changelog updates are complete.

## Create the Release Tag

1. Confirm `VERSION` matches the intended tag.
2. Create annotated tag:
   - `git tag -a v1.0.0 -m "Release v1.0.0"`
3. Push branch and tag:
   - `git push origin master`
   - `git push origin v1.0.0`

## GitHub Release

1. Create a GitHub release from tag `v1.0.0`.
2. Use `CHANGELOG.md` section `1.0.0` as release notes.
