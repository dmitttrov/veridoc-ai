# Publication Dry-Run (Phase 5A)

> **NOTHING here has been executed.** These are the exact commands and
> inclusion/exclusion lists for a future public release, pending **explicit
> owner approval**. Do not run without approval, a real `SEC_USER_AGENT`, and a
> Hugging Face token with write scope.

## ⚠️ Pre-publication blocker: Git history contains a personal email

The SEC User-Agent was hardcoded as a personal email in 3 historical commits
(`9b2f2f2`, `a277034`, `c682c39`). It is now env-configurable in the working
tree, **but forward commits do not remove it from history.** Choose one before a
public GitHub push:

- **Option A (recommended): publish a clean snapshot** — new repo, no history:
  ```bash
  # from a clean checkout of the approved commit
  rm -rf .git && git init && git add -A
  git commit -m "Veridoc AI — initial public release (experimental)"
  ```
- **Option B: rewrite history** to scrub the email, then push. Put the mapping
  in a local, untracked `replacements.txt` (one line: `<owner-email>==>redacted@example.com`)
  so the address itself is not committed:
  ```bash
  pipx run git-filter-repo --replace-text replacements.txt   # replacements.txt stays untracked
  ```
- **Option C:** owner explicitly accepts publishing their own contact email.

## GitHub source release

**Include:** all tracked files (code, `docs/`, `infra/`, `training/` code,
`LICENSE`, `README.md`, `CONTRIBUTING.md`). **Exclude (already git-ignored):**
`data/`, `artifacts/`, `**/.venv`, `**/.env`, `node_modules/`, model weights,
`*.jsonl`. No base weights, datasets, server config, or secrets are tracked.

```bash
# verify no excluded material is tracked (expect empty)
git ls-files | grep -E '\.safetensors$|\.jsonl$|/data/|/artifacts/|\.env$' || echo clean

# after resolving the history blocker above, with approval:
gh repo create <org>/veridoc-ai --public --source=. --remote=origin --disable-wiki
git push -u origin main
```

## Hugging Face — adapter-only release

**Upload ONLY the adapter** (base weights are NOT ours to redistribute). The
adapter-v2 artifact lives on the GPU server at
`~/veridoc-phase4b/training/artifacts/adapter-v2` (checksum
`165518747f28…b58497`).

**Include:** `adapter_model.safetensors`, `adapter_config.json`, tokenizer files
(`tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`,
`vocab.json`, `merges.txt`, `added_tokens.json`), `chat_template.jinja`, and
`README.md` (= `training/MODEL_CARD.md`). **Exclude:** `checkpoint-*/`,
`optimizer.pt`, `training_args.bin`, any `data/`, and the base model weights.

Explicit include list (verified present in `artifacts/adapter-v2/`):
`adapter_config.json`, `adapter_model.safetensors`, `tokenizer.json`,
`tokenizer_config.json`, `special_tokens_map.json`, `added_tokens.json`,
`vocab.json`, `merges.txt`, `chat_template.jinja`, and `README.md` (replaced by
the model card). Explicit exclude: `training_args.bin`, `training_metrics.json`,
`checkpoint-*/` (optimizer/scheduler/rng/trainer state), any base weights, `data/`.

```bash
# target id: <org>/veridoc-extract-qwen3-0.6b-lora   (experimental)
export HF_TOKEN=***                      # write scope; never commit
python - <<'PY'
from huggingface_hub import HfApi
api = HfApi()
repo = "<org>/veridoc-extract-qwen3-0.6b-lora"
api.create_repo(repo, repo_type="model", private=True, exist_ok=True)   # start PRIVATE
# Model card as README (overrides the training-saved README.md).
api.upload_file(path_or_fileobj="training/MODEL_CARD.md", path_in_repo="README.md", repo_id=repo)
api.upload_folder(
    repo_id=repo, folder_path="artifacts/adapter-v2",
    allow_patterns=[
        "adapter_config.json", "adapter_model.safetensors",
        "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
        "added_tokens.json", "vocab.json", "merges.txt", "chat_template.jinja",
    ],
    ignore_patterns=[
        "checkpoint-*", "training_args.bin", "training_metrics.json",
        "optimizer.pt", "README.md", "**/data/**",
    ],
)
PY
```

Flip the repo to public only after the owner reviews the uploaded card and files.
The card must retain the experimental disclaimers (adapter not from scratch;
templated-evidence caveat; frozen-benchmark-targeted-v2 caveat; authentic
filing-text untested; not financial advice).

## Must-not-do

- Do **not** upload Qwen3-0.6B base weights.
- Do **not** upload `data/` (synthetic or SEC-derived) or `artifacts/` run logs.
- Do **not** include server hostnames/IPs, SSH keys, tokens, or `.env` files.
- Do **not** expose any inference endpoint.
