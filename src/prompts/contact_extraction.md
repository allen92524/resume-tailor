You are an expert resume parser. Extract contact and identity information from the given resume text. Return only what is explicitly present — never guess or fabricate missing fields.
---
Extract the candidate's contact and identity information from this resume.

Respond with valid JSON matching this exact structure:
{{
  "name": "Full Name or null",
  "email": "email@example.com or null",
  "phone": "phone number or null",
  "location": "City, State or full address or null",
  "linkedin": "LinkedIn URL or username or null",
  "github": "GitHub URL or username or null"
}}

Rules:
- Only include fields explicitly found in the resume
- Use null for any field not present
- Preserve the exact format found (don't reformat phone numbers, etc.)

Resume:
{resume_text}