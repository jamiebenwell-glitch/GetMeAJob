# Agent System

This repo uses a small set of focused agents. Each agent owns a narrow problem, produces explicit outputs, and hands off to the next agent through stable artifacts.

## Agent Flow
1. `source_compliance` finds acceptable job sources and rejects risky ones.
2. `ats_ingestion` fetches raw jobs from approved feeds.
3. `normalization_quality` converts raw jobs into one schema and rejects low-quality records.
4. `reviewer_assistant` improves CV review logic, markup, and user guidance.
5. `frontend_qa` owns the web experience and release gates.

## Rules
- Agents do not bypass source restrictions.
- Agents must leave artifacts that another agent can validate.
- Parser changes are not complete until tests pass.
- UI changes are not complete until Playwright coverage passes.

## Shared Schema
Normalized job records should contain:
- `company`
- `title`
- `location`
- `department`
- `salary`
- `duration`
- `summary`
- `key_requirements`
- `apply_url`
- `source_provider`
- `source_board`

## Release Gate
A change is release-ready only when:
- `pytest -q` passes
- the live fetch command succeeds for official company feeds
- the web app starts and responds locally
