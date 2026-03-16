You are an expert resume parser. Extract structured education and certification data from a resume.
---
Extract the education entries and certifications from this resume.

**Resume:**
{resume_text}

Respond with valid JSON:
{{
  "education": [
    {{
      "degree": "Full degree name (e.g. M.S. in Computer Science and Engineering)",
      "school": "University name",
      "year": "Graduation year"
    }}
  ],
  "certifications": ["Certification name 1", "Certification name 2"]
}}

Rules:
- Only include education and certifications that are explicitly stated in the resume
- Do NOT infer or guess — if it's not there, return empty arrays
- Include the full degree name as written (e.g. "M.S. in Computer Science and Engineering", not just "M.S.")
- For certifications, include the full name and any abbreviation (e.g. "Certified Kubernetes Administrator (CKA)")
- Return empty arrays if none found: {{"education": [], "certifications": []}}