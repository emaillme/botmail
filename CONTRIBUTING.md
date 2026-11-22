# Contributing

Thanks for helping improve botmail.

1. Open an issue or comment on an existing one before large changes.
2. Fork the repo, create a branch, and keep commits focused.
3. Install dev dependencies: `pip install -e ".[dev]"`.
4. Run `ruff check src tests` and `pytest -q` before pushing.
5. If you change `infra/botmail.yaml`, run `cfn-lint infra/botmail.yaml`.
6. Open a pull request against `main` with a short description and test notes.

Release mechanics are documented in [`docs/RELEASING.md`](docs/RELEASING.md).

By contributing, you agree your work is licensed under the MIT license in `LICENSE`.