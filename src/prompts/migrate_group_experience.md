You are an expert at organizing career data. Group experience bank entries by the work role they belong to.
---
A candidate has a flat list of Q&A answers from past sessions. Group each answer under the work role it most likely belongs to.

**Resume (for role context):**
{resume_text}

**Flat experience bank entries:**
{experience_bank}

**Work roles found in the resume (use these exact keys):**
{roles}

Respond with valid JSON:
{{
  "work_history": {{
    "Company | Title | Dates": {{
      "topic1": "answer1",
      "topic2": "answer2"
    }},
    "Another Company | Title | Dates": {{
      "topic3": "answer3"
    }},
    "General": {{
      "topic4": "answer that doesn't belong to any specific role"
    }}
  }}
}}

Rules:
- Use the exact role keys provided above (e.g. "F5 Networks | Software Engineer III | Nov 2025 – Present")
- Each experience bank entry must appear exactly once — do not duplicate or drop any
- If an entry clearly relates to a specific role, put it under that role
- If an entry is general or cross-cutting (e.g. "recent_updates", "clarification:..."), put it under "General"
- Preserve the original topic names and answers exactly — do not rewrite them
- Every entry from the flat list must appear in the output