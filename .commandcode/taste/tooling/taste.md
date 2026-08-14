# Taste

- Keeps secrets out of version control: when a config needs a credential/PAT, the key must never be committed ("Don't check out the key into VCS"). The mechanism may vary — env-var interpolation (e.g. `${GITHUB_EDRAYEL_PAT}`), a key file outside the repo, or a gitignored config with the token inline (following the projectkreate pattern) — but the agent should verify the file is git-ignored/unstaged before committing and pushing. Confidence: 0.95

- Prefers repo-level (project-scoped) tool configuration (e.g., a `.mcp.json` at the repo root) for per-repo integrations like MCP servers, rather than only global/CLI-wide scope. Confidence: 0.7

- Wants tool integrations kept consistent across the agents/tools they use — e.g., replicating an opencode GitHub MCP server for Command Code in the same repo so both tools have the same capabilities. Confidence: 0.6

- When replicating a tool/config setup, wants the agent to follow the pattern already established in their other repos — e.g., pointing at `/home/edrayel/dev/projectkreate` as the reference for how the Command Code MCP was set up, so conventions stay consistent across projects. Confidence: 0.7

- Treats "commit" and "push" as separate, explicitly-scoped steps — when the user says only "commit all changes" (after being offered "commit and push"), the agent should commit, verify a clean working tree, and stop there without pushing; pushing happens only when explicitly requested. Confidence: 0.6

- Handles authenticated git operations non-interactively by passing the PAT directly in the push URL (`https://user:PAT@github.com/...`) for that single operation, without writing the token to git config, credentials files, or the repo — the established remote/credential-helper auth may be broken or stale, so one-off PAT-in-URL pushes (with the token read from an out-of-repo key file, e.g. `~/.config/opencode/keys/...`) are an accepted workflow. Confidence: 0.7

- Prefers extracting shared/identical code (e.g., the per-page cart JS) into the shared component (shared.js/shared.css) to avoid duplicating the same logic across files, and checks whether logic is truly identical across files before deciding to extract. Confidence: 0.6

- Accepts pushing through an authenticated MCP GitHub connection (which recreates commits via the API rather than a literal `git push`) when the machine's git/gh credentials are broken — explicitly choosing the fastest option that requires no user action over re-authenticating, and letting the agent reconcile local/remote afterward (e.g., fast-forwarding local master to the API-created commit). Confidence: 0.6

