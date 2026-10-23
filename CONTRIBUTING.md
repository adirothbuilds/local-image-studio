# Contributing

Open an issue to discuss a larger change before implementing it. Keep changes focused and include a practical verification of the changed behavior.

```bash
./studio.sh setup
./studio.sh test
```

Do not commit `.env`, credentials, model weights, generated images, reference photos, logs, caches or machine-specific files. Use generic fixtures and synthetic images in tests. CI runs without the model or GPU; local generation changes also need manual Apple Silicon verification.

Only the repository owner can approve changes for inclusion in `main`. CODEOWNERS applies to every file, including repository policy. Stale approvals are dismissed when new changes arrive. Public forks and proposed pull requests do not grant permission to merge. Contributions are provided under the repository's MIT license; third-party material must retain its applicable notices.
