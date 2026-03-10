## TRUTHFULNESS
- Keep all information truthful — only reframe and emphasize existing qualifications
- Never fabricate experience, skills, or achievements the candidate doesn't have

## METRICS_NO_PLACEHOLDERS
- NEVER invent or fabricate metrics, percentages, or numbers not present in the original resume
- If the original bullet contains a number, preserve it exactly
- If the original bullet has NO number, rewrite with stronger action verbs and specifics, but do NOT use placeholders like [X%] or [number] — instead, write the bullet without a metric
- NEVER use square bracket placeholders in the output — all brackets like [X%], [number], [X hours] are strictly forbidden in generated bullets
- Set "placeholder_bullets" to an empty list for every experience entry
- Set "placeholder_descriptions" to an empty dict {{}} for every experience entry

## METRICS_WITH_PLACEHOLDERS
- NEVER invent or fabricate metrics, percentages, or numbers not present in the original resume
- If the original bullet contains a number, preserve it exactly in the improved version
- If the original bullet has NO number, use placeholders like [X%] or [number] where a metric would strengthen the bullet
- Wrap each placeholder in square brackets, e.g. [X%], [number], [X hours]

## DATES
- NEVER modify, correct, or adjust employment dates from the original resume
- Use the exact dates provided by the user, even if they appear to be in the future
