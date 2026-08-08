# Taste

- When a code review surfaces concrete issues, expects the findings to be acted on immediately ("Proceed with fixes") rather than stopping at a recommendations report. Confidence: 0.7

- Wants shared, reusable components (header, footer, etc.) instead of duplicated static markup repeated across pages — "it doesn't make sense for these to be static and raw." Explicitly requires the shared header/footer to render identically across ALL pages (only the active nav link may differ) and to come from a single shared source (shared.js + shared.css) rather than per-page markup or CSS. Confidence: 0.98

- When a queue of previously identified follow-up/pending items exists, expects them all to be completed in the same pass once approved ("Yes, build a shared header/footer. Then fix all pending queued items.") rather than left dangling for a later session. Confidence: 0.7

- Wants the agent to debug reported issues independently and verify with its own evidence ("Debug and see for yourself") rather than asking the user to explain or re-check — expects the agent to trace the served output vs. local files and pinpoint root causes itself. Confidence: 0.7

- Drives multi-part work with terse one-word nudges ("Continue") — when a session resumes mid-task (e.g., after an investigation-heavy turn that ended without finishing the edits), the user expects the agent to proceed straight through implementation and verification without re-confirming scope, re-reading instructions, or re-asking what to do. Confidence: 0.6
