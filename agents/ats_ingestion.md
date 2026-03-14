# ats_ingestion

## Owns
- Feed fetchers
- Retry and timeout handling
- Provider-specific parsing entrypoints

## Inputs
- Approved source inventory

## Outputs
- Raw provider payloads
- Fetch commands
- Smoke tests for each provider

## Current Providers
- `Lever`
- `Greenhouse`

## Handoff
- Pass raw payloads and source metadata to `normalization_quality`
