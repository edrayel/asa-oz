# Taste

- Keeps secrets out of version control: when a config needs a credential/PAT, the key must never be committed ("Don't check out the key into VCS"). The mechanism may vary — env-var interpolation (e.g. `${GITHUB_EDRAYEL_PAT}`), a key file outside the repo, or a gitignored config with the token inline (following the projectkreate pattern) — but the agent should verify the file is git-ignored/unstaged before committing and pushing. Confidence: 0.95

- Prefers repo-level (project-scoped) tool configuration (e.g., a `.mcp.json` at the repo root) for per-repo integrations like MCP servers, rather than only global/CLI-wide scope. Especially important when multiple agent instances share the same machine — user-level MCP config that spawns stateful resources (browser processes, devtools ports, user-data-dir locks) causes cross-instance collisions, and the user prefers scoping stateful MCPs to the project/repo so only the instance working in that repo pays the cost. Confidence: 0.8

- Wants tool integrations kept consistent across the agents/tools they use — e.g., replicating an opencode GitHub MCP server for Command Code in the same repo so both tools have the same capabilities. Confidence: 0.6

- When replicating a tool/config setup, wants the agent to follow the pattern already established in their other repos — e.g., pointing at `/home/edrayel/dev/projectkreate` as the reference for how the Command Code MCP was set up, so conventions stay consistent across projects. Confidence: 0.7

- Treats "commit" and "push" as separate, explicitly-scoped steps — when the user says only "commit all changes" (after being offered "commit and push"), the agent should commit, verify a clean working tree, and stop there without pushing; pushing happens only when explicitly requested. Confidence: 0.7

- Prefers a branch-per-initiative workflow: commit the outstanding work first, then create a dedicated branch for a new, distinct initiative rather than continuing on the default branch. Expects the agent to propose a descriptive branch name that encodes the purpose/target (type prefix + goal, e.g. `content/align-rorys-travel-club`) — the "Suggest a name for the branch" asks are an invitation to name it and offer alternatives. Confidence: 0.65

- Handles authenticated git operations non-interactively by passing the PAT directly in the push URL (`https://user:PAT@github.com/...`) for that single operation, without writing the token to git config, credentials files, or the repo — the established remote/credential-helper auth may be broken or stale, so one-off PAT-in-URL pushes (with the token read from an out-of-repo key file, e.g. `~/.config/opencode/keys/...`) are an accepted workflow. Confidence: 0.7

- Prefers extracting shared/identical code (e.g., the per-page cart JS) into the shared component (shared.js/shared.css) to avoid duplicating the same logic across files, and checks whether logic is truly identical across files before deciding to extract. Confidence: 0.6

- Accepts pushing through an authenticated MCP GitHub connection (which recreates commits via the API rather than a literal `git push`) when the machine's git/gh credentials are broken — explicitly choosing the fastest option that requires no user action over re-authenticating, and letting the agent reconcile local/remote afterward (e.g., fast-forwarding local master to the API-created commit). Confidence: 0.6

- Prefers hand-rolled, dependency-light security primitives (CSRF tokens via `hmac.compare_digest` + Flask sessions, URL scheme allow-lists, server-side HTML sanitization with `nh3`) over heavy frameworks like Flask-WTF — wants the implementation to be small enough to read end-to-end and audit, not a black box. Confidence: 0.8

- For service integrations (Google Drive, Stripe, SMTP, etc.), wants structured logging (`app.logger.info/warning`) on every entry point and every error path, plus retry-with-exponential-backoff for transient failures — not silent failures or `try/except: pass`. Confidence: 0.85

- For health check endpoints, prefers real liveness probes that exercise dependencies (DB query, Drive API call) and return 503 with a JSON status report on degradation, over cheap no-op "return ok" endpoints — wants the probe to actually catch outages. Confidence: 0.85

- Prefers the file path `DEPLOY.md` at the repo root as the canonical place for environment-variable documentation: required vs. optional vars, how to generate secrets, security model, and first-time setup steps — keeps deployment knowledge out of scattered comments and in one place maintainers actually read. Confidence: 0.8

- For MCP server integrations, prefers the hosted HTTP endpoint (e.g., `https://mcp.render.com/mcp`) with the API key passed via `Authorization: Bearer ${ENV_VAR}` in the MCP config headers, rather than running a local Docker-based MCP server — the env var interpolation keeps the config safe to commit while avoiding OAuth prompts and Docker dependencies. Confidence: 0.8

- When adding a new MCP server to a repo, places it in `.commandcode/mcp.json` (project-scoped, committed) following the same `mcpServers` shape as `.mcp.json` (which holds tool-agent MCPs), so MCPs live in a separate, tool-specific file rather than mixing with tool-agent MCPs. Confidence: 0.8

- When configuring per-project secrets (API keys, PATs) via env vars, project-prefixes the variable name (e.g., `ASAOZ_RENDER_API_KEY` rather than the generic `RENDER_API_KEY`) to avoid collisions with other accounts/projects the user manages — expects distinct env var names per project. Confidence: 0.85

- Keeps the source of a secret (key file path, secrets-manager reference, etc.) out of committed MCP/config files — the committed config references only the env var, and the user controls how the env var is populated. Don't hardcode absolute paths like `/home/edrayel/.config/opencode/keys/..._api_key` into committed config; document the sourcing approach in DEPLOY.md instead. Confidence: 0.85

- Treats secret API keys as strictly display-redacted in chat — explicitly instructs the agent never to print/log the key value in the conversation, even when troubleshooting the config. Agent may verify the file exists, check length/permissions, and read it into a process or env var, but must not echo the contents. Confidence: 0.95

- When a tool install or dependency (e.g., `pip install pillow`, system package) fails or times out in the sandbox, prefers documenting a ready-to-run snippet in `DEPLOY.md` (or similar) and skipping the step in-session over blocking the entire task — ships the code and the instructions, lets the user run it locally. Confidence: 0.75

- When documenting a third-party service integration (SMTP provider, OAuth library, payment processor, etc.) in `DEPLOY.md` or config, expects the agent to verify the current settings/endpoints by web-fetching the vendor's docs before writing them down — not to paraphrase from memory. Cites the source URL in the doc/PR summary so the values can be re-checked. Confidence: 0.7

- Runs the local dev server themselves in a separate terminal and expects the agent to keep that in mind — don't assume the server is down or broken, and don't kill/restart the user's running instance. When verification would otherwise interfere, work around it (e.g., a second instance on another port, or the Flask test client) and leave the user's server untouched. Confidence: 0.6

- Expects changes verified against the database and site the user is actually running (their real, already-populated content DB), not only an isolated fresh/empty test database — a clean-slate verification creates a blind spot, and the user will come back reporting they still see old content. Reproduce the result on the real database/served instance before declaring done, and check that the user's assumed server is genuinely listening rather than trusting their report of which port it is on. Confidence: 0.65

- When a change has accidentally removed or overwritten existing functionality/design (e.g. a section the agent replaced while adding a new one, wiping the wall-of-moments marquee), expects the agent to consult git history to recover and restore the original implementation verbatim ("Restore it back. Check the git history.") instead of reinventing a replacement. Treats unintentional deletion of shipped work as a regression to be reverted to the previously intended state. Confidence: 0.7

- Maintains secrets as one-file-per-credential under `~/.config/opencode/keys/` (e.g. `render_asa-oz_api_key`) and expects env vars to be populated from those files — e.g. shell rc exports like `export X="$(cat ~/.config/opencode/keys/<name> 2>/dev/null)"` — so rotating a credential is a one-file change instead of editing it in multiple places. Points the agent at the key file path so it can wire the env var up itself. Confidence: 0.7
- Requires absolute links to use the canonical custom domain (`asa-oz.com`) and never the platform default host (`*.onrender.com`), even when `RENDER_EXTERNAL_URL` is available — applies to emailed links, logos, Stripe return URLs, OG tags and sitemaps. Confidence: 0.85

(`*.onrender.com`), even when `RENDER_EXTERNAL_URL` is available — applies to emailed links, logos, Stripe return URLs, OG tags and sitemaps. Confidence: 0.8

