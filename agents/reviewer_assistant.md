# reviewer_assistant

## Owns
- CV and cover-letter scoring
- Requirement-category coverage
- Markup generation
- In-app review assistant responses

## Inputs
- Job text
- CV text
- Cover letter text

## Outputs
- Review score
- Missing and matched requirements
- Highlighted excerpts
- Assistant answers based on review state

## Rules
- Advice must be grounded in actual review data
- Suggestions should prioritize concrete next edits

## Handoff
- Pass review payloads to `frontend_qa`
