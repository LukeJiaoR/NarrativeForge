# NarrativeForge

NarrativeForge is a local, agent-first media orchestration lab. It separates narrative
planning, speech, subtitle timing, visual retrieval, composition, and quality assurance
into observable and replaceable stages.

Repository: [github.com/LukeJiaoR/NarrativeForge](https://github.com/LukeJiaoR/NarrativeForge)

This repository is an early refactoring baseline. Its goal is a general media workflow
that can be driven consistently through agents, a CLI, an API, or a WebUI—not a
single-purpose content generator.

## Principles

- Explicit and recoverable agent contracts
- Audio-derived subtitle timing
- Ambiguity-aware visual retrieval
- Traceable media provenance
- Replaceable model and media providers
- Local-first configuration and artifacts

## Quick start

Python 3.11+, FFmpeg, and [uv](https://docs.astral.sh/uv/) are required.

```bash
cp config.example.toml config.toml
uv python install 3.11
uv sync --frozen
sh webui.sh
```

Start the API with:

```bash
uv run python main.py
```

The repository does not bundle font or music binaries. Subtitle rendering uses a
Unicode-capable system font by default; add only music and fonts you are licensed to use.

See [docs/refactor-roadmap.md](docs/refactor-roadmap.md) for the architecture roadmap.

## Project status

This is an independently initialized repository with a fresh Git history. It is not a
GitHub fork. APIs and configuration may change while the architecture is being rebuilt.

## License

MIT. Some components continue from existing MIT-licensed work. The required copyright
notice is retained in [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
