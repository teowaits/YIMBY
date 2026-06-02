# regional-scout

Identify and rank researchers in a geographic region relevant to Wiley's AI×science journal portfolio — for editorial trip preparation and special-issue author scouting.

Part of the [teowaits](https://github.com/teowaits) OpenAlex tooling suite ([journal-overlap](https://github.com/teowaits/journal-overlap), [journal-profiler](https://github.com/teowaits/journal-profiler), citation-summoner).

| | |
|---|---|
| **Version** | 0.3.0 |
| **Python** | ≥ 3.11 |
| **Data** | [OpenAlex](https://openalex.org) — free API key required |
| **License** | MIT |

---

## Features

- **CLI pipeline** — scope → candidates → works → co-author graph → scoring → `shortlist.json` + offline `shortlist.html`
- **Web UI** — local React app to configure runs, estimate credits, and browse results
- **published-with-us** — enrich shortlists against a target Wiley journal (OpenAlex backend)
- **SQLite cache** — repeat runs are cheaper; all HTTP goes through the cache layer

Scoring combines **relevance**, **productivity** (recency-decayed), **impact** (mean FWCI), **network centrality**, and an optional **Wiley-friendliness** signal.

---

## Quick start

```bash
git clone https://github.com/teowaits/regional-scout.git
cd regional-scout
uv sync
cp config.yaml config.local.yaml
```

Edit `config.local.yaml` and set your OpenAlex API key ([get one free](https://openalex.org/settings/api)).

```bash
# Resolve portfolio source IDs (optional, first time)
uv run regional-scout init-portfolio --config config.local.yaml --write

# Run Italy example (default in config.yaml)
uv run regional-scout run --config config.local.yaml
```

Outputs land in `output/` (or `output/YYYY-MM-DD_HHMMSS/` when timestamped). Open `shortlist.html` in a browser — fully self-contained, no CDN.

---

## Secrets & gitignored files

These files are **not in the repo** — create them locally after clone:

| File | Purpose |
|------|---------|
| `config.local.yaml` | Your OpenAlex **API key** and local overrides (copy from `config.yaml`) |
| `CLAUDE.md` / `CLAUDE.docx` | Internal design notes (optional, local only) |

Never commit `config.local.yaml`. The committed `config.yaml` uses `YOUR_KEY_HERE` as a placeholder.

---

## Web UI

Styled like journal-overlap / journal-profiler (IBM Plex Mono/Sans, dark `#0d111c` palette). The API key stays on the server.

**Development:**

```bash
# Terminal 1
uv run regional-scout serve --config config.local.yaml

# Terminal 2
cd web && npm install && npm run dev
# → http://localhost:5173
```

**Single server** (after `cd web && npm run build`):

```bash
uv run regional-scout serve --config config.local.yaml
# → http://127.0.0.1:8765
```

---

## Commands

| Command | Description |
|---------|-------------|
| `serve` | Local API for the web UI |
| `run` | Full scouting pipeline |
| `estimate` | Credit preflight (no pipeline) |
| `enrich` | Published-with-us checks |
| `report` | Regenerate HTML from JSON |
| `init-portfolio` | Resolve journal OpenAlex source IDs |
| `cache-clear` | Clear SQLite HTTP cache |

```bash
uv run regional-scout estimate --config config.local.yaml
uv run regional-scout run --config config.local.yaml
uv run regional-scout report --input output/latest/shortlist.json
uv run regional-scout enrich --config config.local.yaml \
  --input output/shortlist.json --source-id S4210212817 --years 5
```

---

## Configuration

Copy `config.yaml` → `config.local.yaml`. Key sections:

| Section | Settings |
|---------|----------|
| `openalex` | `api_key`, `max_credits_per_run`, `work_window_years`, `max_candidates` |
| `region` | `country_codes` (ISO 2-letter) or `ror_ids` |
| `scoring` | Weights, `min_in_scope_works`, `scope_author_prefilter` |
| `scope` | Seed DOIs, competitor ISSNs, extra topic IDs |
| `wiley_portfolio` | OpenAlex source IDs per Advanced journal |
| `output` | `shortlist_size`, `timestamp_runs`, `auto_enrich` |

Authors with fewer than `scoring.min_in_scope_works` (default **1**) in-scope works are excluded before scoring.

---

## OpenAlex credits

| Call type | Cost |
|-----------|------|
| List | 10 credits |
| Singleton | 1 credit |
| Free tier | 100,000 credits/day |

The pipeline estimates burn before running and aborts if over `openalex.max_credits_per_run`.

---

## Testing

```bash
uv run pytest
```

---

## Project layout

```
regional_scout/     Python package (CLI, pipeline, OpenAlex client)
web/                React + Vite UI
tests/              pytest suite
config.yaml         Committed template (no secrets)
```

---

## Related tools

- [published-with-us](https://github.com/teowaits/published-with-us) — browser workflow; `enrich` is the Python backend
- [journal-overlap](https://github.com/teowaits/journal-overlap) — authorship overlap between journal sets
- [journal-profiler](https://github.com/teowaits/journal-profiler) — journal topic & citation profiling

---

## License

MIT — see [LICENSE](LICENSE).

Data from [OpenAlex](https://openalex.org) (CC0).
