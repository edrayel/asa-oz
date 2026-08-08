# Taste

- Keeps secrets out of version control: when a config needs a credential/PAT, the key must never be committed ("Don't check out the key into VCS"). The mechanism may vary — env-var interpolation (e.g. `${GITHUB_EDRAYEL_PAT}`), a key file outside the repo, or a gitignored config with the token inline (following the projectkreate pattern) — but the agent should verify the file is git-ignored/unstaged before committing and pushing. Confidence: 0.95

- Prefers repo-level (project-scoped) tool configuration (e.g., a `.mcp.json` at the repo root) for per-repo integrations like MCP servers, rather than only global/CLI-wide scope. Confidence: 0.7

- Wants tool integrations kept consistent across the agents/tools they use — e.g., replicating an opencode GitHub MCP server for Command Code in the same repo so both tools have the same capabilities. Confidence: 0.6

- When replicating a tool/config setup, wants the agent to follow the pattern already established in their other repos — e.g., pointing at `/home/edrayel/dev/projectkreate` as the reference for how the Command Code MCP was set up, so conventions stay consistent across projects. Confidence: 0.7

