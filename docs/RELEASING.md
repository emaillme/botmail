# Releasing botmail-cli to PyPI

Publishing uses **PyPI Trusted Publishing (OIDC)**. No API tokens are stored in GitHub.

## One-time setup

### 1. PyPI projects

Create (or claim) the **`botmail-cli`** project on:

- [test.pypi.org](https://test.pypi.org/) (recommended first)
- [pypi.org](https://pypi.org/)

### 2. Trusted Publisher on TestPyPI

1. Log in to TestPyPI as owner **`emaillme`**.
2. Open project **botmail-cli** → **Publishing** → **Add a new pending publisher**.
3. Set:
   - **PyPI project name:** `botmail-cli`
   - **Owner:** `emaillme`
   - **Repository name:** `botmail`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `testpypi`

### 3. Trusted Publisher on PyPI (production)

Repeat on **pypi.org** with the same owner and repository, workflow **`publish.yml`**, environment **`pypi`**.

### 4. GitHub environments

In [github.com/emaillme/botmail/settings/environments](https://github.com/emaillme/botmail/settings/environments):

| Environment | Purpose | Suggested protection |
| --- | --- | --- |
| `testpypi` | Manual TestPyPI uploads via **workflow_dispatch** | Optional reviewers |
| `pypi` | Production publish on **GitHub Release published** | Required reviewers recommended |

Trusted Publishing ties each environment to the matching publisher entry on TestPyPI or PyPI.

## Versioning

- Single source of truth: `__version__` in `src/botmail/__init__.py`
- Update `CHANGELOG.md` before each release
- Tag format: `v0.1.0` (must match the package version without the `v`)

## Test publish (TestPyPI)

1. Actions → **Publish** → **Run workflow**
2. Branch: `main`
3. **target:** `testpypi` (default)
4. Confirm the run uses environment `testpypi` and succeeds

Install from TestPyPI:

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ botmail-cli
```

(`--extra-index-url` pulls normal dependencies like boto3 from production PyPI.)

## Production release

1. Bump `src/botmail/__init__.py` `__version__` and add a `CHANGELOG.md` section.
2. Merge to `main`.
3. GitHub → **Releases** → **Draft a new release**
   - Choose tag `vX.Y.Z` (create new tag on `main`)
   - Title `vX.Y.Z`
   - Paste the changelog section for that version
4. **Publish release** (not draft). This triggers `publish.yml`, which:
   - Builds sdist and wheel
   - Runs `twine check`
   - Publishes to **pypi** via OIDC

Do not publish wheels manually from a laptop unless debugging; prefer the workflow.

## Workflow reference

File: [`.github/workflows/publish.yml`](../.github/workflows/publish.yml)

| Trigger | Environment | Index |
| --- | --- | --- |
| `release` published | `pypi` | pypi.org |
| `workflow_dispatch` → `testpypi` | `testpypi` | test.pypi.org |
| `workflow_dispatch` → `pypi` | `pypi` | pypi.org |

CI on every PR also builds the package, runs `twine check`, and smoke-tests `botmail --help` after installing the wheel.