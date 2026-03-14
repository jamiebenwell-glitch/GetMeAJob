# normalization_quality

## Owns
- Schema normalization
- Summary extraction
- Salary and duration parsing
- Requirement extraction
- Data cleanup and readability

## Inputs
- Raw ATS payloads

## Outputs
- Normalized JSON/CSV
- Parser tests
- Quality assertions

## Rules
- No HTML in normalized summaries
- No junk token requirements
- One bad source must not fail the whole dataset

## Handoff
- Pass normalized jobs to `frontend_qa`
