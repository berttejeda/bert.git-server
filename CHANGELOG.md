# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.3.0] - 2026-09-22

### Fixed

- Pushes larger than git's `http.postBuffer` (1 MiB by default) no longer fail
  with `ValueError: subsection not found`. For large pushes, git first sends a
  probe request whose body is only a flush packet (`0000`), and the
  receive-pack handler assumed every request body contained a `PACK`.
  Delete-only pushes, which also carry no pack, work as well.
- Gzip-compressed request bodies (`Content-Encoding: gzip`), which git sends
  for larger fetch negotiations, are now decompressed before being handed to
  `git-upload-pack`.
- Repos created on demand no longer have a HEAD that points at a missing
  branch. They are initialized with `HEAD -> refs/heads/master`, so after a
  first push of e.g. `main`, clones warned
  `remote HEAD refers to nonexistent ref` and checked nothing out. After each
  push, a missing HEAD target is now repointed at an existing branch
  (`main`, then `master`, then the first branch alphabetically). Non-bare repos
  also get their working tree checked out, so `updateInstead` accepts later
  pushes.
- Creating an on-demand repo no longer crashes its error handler with
  `UnboundLocalError` when directory creation fails. The failure now returns
  HTTP 500 (previously 501).
- `info/refs` requests without a `?service=` parameter return HTTP 400
  instead of crashing with `TypeError`.
- The server now starts on Python environments with setuptools 81 or later,
  which removed `pkg_resources`. gunicorn 20.x imported `pkg_resources` and
  failed with `ModuleNotFoundError`.

### Security

- `info/refs` accepts only the `git-upload-pack` and `git-receive-pack`
  services. It used to run any executable whose name started with `git-`.
- Org and project names in request paths are validated: letters, digits,
  `.`, `_` and `-` only, and a name may not start with `.`. Names such as `..`
  (including URL-encoded `%2e%2e`) are rejected with HTTP 400, which prevents
  repos from being created or served outside the configured search paths.
- Repos are created on demand only for pushes (`git-receive-pack`). Cloning
  or fetching a repo that doesn't exist returns 404 and creates nothing.

### Changed

- Missing repos on `git-receive-pack` / `git-upload-pack` now return
  HTTP 404 instead of 501.
- The received pack is parsed for commit logging only when debug logging is
  enabled, and a parse failure can no longer abort a push.
- Subprocess I/O with `git-receive-pack` / `git-upload-pack` uses
  `Popen.communicate(input=...)`, which avoids possible pipe deadlocks.
- Bumped the `gunicorn` requirement from `>=20.1.0,<21.0.0` to
  `>=23.0.0,<24.0.0`.

### Removed

- Python 2 `StringIO` code paths.

## [3.2.0] - 2026-01-30

### Changed

- Updated `PackStreamReader` usage for the newer dulwich API (explicit `sha1`
  and read callables).
- Existing repos are set to `receive.denyCurrentBranch=updateInstead` on
  access, so pushes to their checked-out branch update the working tree.
