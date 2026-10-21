# Local Setup Validation Notes

This README documents the local environment validation for `claude-cookbooks/skills`
on Windows (Git Bash). It is supplementary to the upstream `README.md` shipped with
the cookbook.

## TL;DR

- The local environment is **fully validated**: Python 3.13 venv, all
  `requirements.txt` packages, `.env` loading, the `anthropic` SDK, Jupyter
  Notebook, and the API key all work correctly.
- A small `messages.create` smoke test succeeded
  (`'pong'`, 15 input / 5 output tokens, `stop_reason=end_turn`).
- Notebook `notebooks/01_skills_introduction.ipynb` cannot run end-to-end on the
  current Anthropic org tier because cells that load skill bundles
  (`xlsx` / `pptx` / `pdf`) exceed the org's 30,000 input-tokens-per-minute cap
  for `claude-sonnet-4-6`.

The notebook failures are an Anthropic **rate-limit / tier issue**, not a local
setup issue.

## Environment

- OS: Windows
- Shell: Git Bash 5.3.9
- Python: 3.13
- Working directory: `C:\Users\mkhal\claude-cookbooks\skills`
- venv: `skills/venv/` (Windows layout — `venv/Scripts/python.exe`,
  `venv/Scripts/activate`; the Linux-style `venv/bin/activate` does **not**
  exist on Windows)

### Activation

In Git Bash:
```bash
cd /c/Users/mkhal/claude-cookbooks/skills
source venv/Scripts/activate
```

In PowerShell:
```powershell
cd C:\Users\mkhal\claude-cookbooks\skills
venv\Scripts\Activate.ps1
```

In `cmd.exe`:
```cmd
cd C:\Users\mkhal\claude-cookbooks\skills
venv\Scripts\activate.bat
```

### Installed packages (key ones)

Pinned by the upstream `requirements.txt`:

- `anthropic` 0.97.0
- `jupyter` 1.1.1
- `notebook` 7.5.5
- `ipykernel` 7.2.0
- `python-dotenv` 1.2.2
- (plus full transitive set installed by pip resolver)

### `.env` configuration

Located at `skills/.env`. Keys present:

- `ANTHROPIC_API_KEY` — 108-character `sk-ant-api03-…` value (validated by API).
- `ANTHROPIC_MODEL` — `claude-sonnet-4-6` (default from `.env.example`).
- `SKILLS_STORAGE_PATH` — `./custom_skills`
- `OUTPUT_PATH` — `./outputs`

`.env` is already covered by `.gitignore` so the key will not be committed.

### Setup gotchas hit during validation

- **`venv/bin/activate` missing on Windows.** The original copy-pasted setup
  used the Linux activation path, so the venv looked "broken" and packages were
  inadvertently installed into the global Python. Resolution: use
  `venv/Scripts/activate` and reinstall `requirements.txt` into the venv with
  `venv/Scripts/python.exe -m pip install -r requirements.txt`.
- **Bash `read -s` paste corruption.** Pasting a multi-line command into
  `read -s -p "Paste new key: " NEWKEY && sed -i …` caused the prompt text
  to be captured *into* the key value, producing a 122-char `ANTHROPIC_API_KEY`
  ending in `key:` and triggering 401 `invalid x-api-key`. Resolution: edit
  `.env` directly in a text editor (e.g. `notepad .env`) and paste only the
  key value.

## Smoke test

A minimal API call succeeded after the key was correctly written:

```text
[1/4] dotenv loaded: True
[2/4] OK: key looks well-formed: sk-ant-api...ugAA (len=108)
[3/4] Using model: claude-sonnet-4-6
[4/4] OK: API call succeeded. Reply: 'pong'
       usage: input=15, output=5, stop_reason=end_turn
```

## Notebook execution: `notebooks/01_skills_introduction.ipynb`

Executed headlessly with:

```bash
venv/Scripts/jupyter.exe nbconvert --to notebook --execute --allow-errors \
  notebooks/01_skills_introduction.ipynb \
  --output 01_skills_introduction.executed.ipynb \
  --ExecutePreprocessor.timeout=180
```

Per-cell results (9 code cells):

- Cell 1 — `import os` etc. — **OK**
- Cell 2 — small `client.messages.create` — **429** (bucket drained by later
  cells in the same window during the first run)
- Cell 3 — list available skills — **OK** (uses a different endpoint that does
  not count against `messages` input-token quota)
- Cell 4 — `client.beta.messages.create` with `xlsx` skill + `code_execution` — **429**
- Cell 5 — references `excel_response` — **NameError** (cascade from cell 4)
- Cell 6 — `client.beta.messages.create` with `pptx` skill + `code_execution` — **429**
- Cell 7 — references `pptx_response` — **NameError** (cascade from cell 6)
- Cell 8 — `client.beta.messages.create` with `pdf` skill + `code_execution` — **429**
- Cell 9 — references `pdf_response` — **NameError** (cascade from cell 8)

## Rate-limit findings

The 429 responses are not a setup problem. They reflect an organization-level
input-tokens-per-minute cap. The actual rate-limit headers captured from a
follow-up tiny request (`max_tokens=4`, content `'.'`) were:

```text
anthropic-ratelimit-input-tokens-limit:    30000
anthropic-ratelimit-input-tokens-remaining: 0
anthropic-ratelimit-input-tokens-reset:    2026-04-25T23:34:23Z
anthropic-ratelimit-requests-limit:        50
anthropic-ratelimit-requests-remaining:    48
retry-after:                               505   # seconds
x-should-retry:                            true
```

Observations:

- The **input-tokens** bucket was at **0/30000**; the **requests** bucket was
  fine (48/50). The throttle is purely on input-token throughput.
- `retry-after: 505` indicates ~8.5 minutes until the bucket can refill — a
  longer real-time wait than the "per minute" wording in the error message
  would suggest, because the previous skill-bundle calls saturated the bucket
  by a wide margin.
- Even a 1-token follow-up request returns 429 until the reset time.

### Why the skills notebook trips this so easily

Each `beta.messages.create(container={"skills": [...]} , tools=[{"type":
"code_execution_20250825"}])` call attaches the chosen skill bundle
(`xlsx`, `pptx`, `pdf`) as input context. A single skill bundle alone can
exceed 30,000 input tokens, so on a Tier 1 org the very first such call
empties the bucket; the next two skill cells in the same notebook therefore
fail immediately, and small in-between cells fail too until the reset.

## Workarounds

1. **Throttle execution.** Run notebook cells one at a time with sleeps in
   between, keeping each minute's input-token use well under 30,000. (Useful
   for cells 1–3, but cells 4 / 6 / 8 each individually exceed the cap and
   cannot be made to fit.)
2. **Raise the limit.** Increase the org's input-tokens-per-minute tier at
   `https://console.anthropic.com/settings/limits`, or contact sales (the
   429 message links the contact page).
3. **Defer the skill demos.** The basic API + SDK + Jupyter stack is verified
   working. The skill-using cells can be revisited after a tier upgrade.

## Cleanup

Helper scripts created during validation (`test_api_key.py`, `set_api_key.py`)
and the executed notebook artifact have been removed; only this `SETUP_README.md`
remains.

## Security note

An earlier, exposed API key (shared in plain text in chat) was rotated and
must be **revoked** in the Anthropic console
(`https://console.anthropic.com/settings/keys`). Revocation can only be done
in the console UI and cannot be verified by this repository.
