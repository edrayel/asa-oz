# Taste

- Keeps secrets out of version control: when a config needs a credential/PAT, expects the checked-in file to reference it indirectly (env-var interpolation, e.g. `${GITHUB_EDRAYEL_PAT}`, or a key file outside the repo) rather than committing the key itself ("Don't check out the key into VCS"). Confidence: 0.9

- Prefers repo-level (project-scoped) tool configuration (e.g., a `.mcp.json` at the repo root) for per-repo integrations like MCP servers, rather than only global/CLI-wide scope. Confidence: 0.7

- Wants tool integrations kept consistent across the agents/tools they use — e.g., replicating an opencode GitHub MCP server for Command Code in the same repo so both tools have the same capabilities. Confidence: 0.6
