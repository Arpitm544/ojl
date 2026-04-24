import google.generativeai as genai
import json
import re
import time
from datetime import datetime


class GeminiServiceError(Exception):
    """Raised when Gemini request fails after retries/fallbacks."""


DEFAULT_MODELS = ["gemini-2.5-flash", "gemini-1.5-flash"]


# ─────────────────────────────────────────────
# ✅ DATE FORMATTER
# ─────────────────────────────────────────────
def format_date(date_str: str) -> str:
    try:
        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%y"]:
            try:
                parsed = datetime.strptime(date_str, fmt)
                return parsed.strftime("%-d-%-m-%Y")
            except ValueError:
                continue
        return date_str
    except Exception:
        return date_str


# ─────────────────────────────────────────────
# ✅ SAFE GEMINI CALL (handles retries + model fallback)
# ─────────────────────────────────────────────
def call_gemini(api_key: str, prompt: str, retries=3, models=None):
    genai.configure(api_key=api_key)
    model_names = models or DEFAULT_MODELS
    last_error = None

    for model_name in model_names:
        model = genai.GenerativeModel(model_name)

        for attempt in range(retries):
            try:
                response = model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.4,
                        "top_p": 0.9,
                    }
                )

                text = (getattr(response, "text", "") or "").strip()
                if not text:
                    raise ValueError("Gemini returned an empty response")

                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)
                return text

            except Exception as e:
                last_error = e
                msg = str(e).lower()

                transient = any(token in msg for token in [
                    "429", "500", "503", "504", "timeout", "deadline", "resource_exhausted", "temporarily unavailable"
                ])
                model_unavailable = any(token in msg for token in [
                    "404", "not found", "not supported", "unknown model", "unsupported model"
                ])

                if attempt < retries - 1 and transient:
                    time.sleep(min(5 * (attempt + 1), 20))
                    continue

                # Try next model when current model is unavailable
                if model_unavailable:
                    break

                # Non-transient error should stop immediately with clear context
                raise GeminiServiceError(f"Gemini API error ({model_name}): {e}") from e

    raise GeminiServiceError(
        f"Gemini failed after retries/fallback. Last error: {last_error}"
    )


# ─────────────────────────────────────────────
# ✅ SPLIT WORK INTO DAYS (IMPROVED PROMPT)
# ─────────────────────────────────────────────
def split_work_into_days(api_key: str, work_description: str, dates: list, num_days: int) -> list:
    prompt = f"""
You are a professional OJT training supervisor.

Divide the following work into EXACTLY {num_days} day-wise entries.

RULES:
- No HR / meetings / company talk
- Only technical/project work
- Each day must be unique
- Maintain progression:
  understanding → planning → implementation → debugging → improvement
- Each day: 2–4 meaningful sentences
- No generic phrases
- No repetition
- No empty or incomplete entries
- Use college/student-level tools (avoid professional tools like Jira, Azure, enterprise software)

OUTPUT JSON ONLY:
[
  {{ "day": 1, "work": "..." }}
]

WORK:
{work_description}
"""

    text = call_gemini(api_key, prompt)

    try:
        daily_splits = json.loads(text)
    except json.JSONDecodeError as e:
        raise GeminiServiceError("Gemini returned invalid JSON while splitting work into days") from e

    if not isinstance(daily_splits, list):
        raise GeminiServiceError("Gemini returned unexpected format for day-wise work split")

    result = []
    for i in range(num_days):
        item = daily_splits[i] if i < len(daily_splits) else {}
        work_text = ""
        if isinstance(item, dict):
            work_text = str(item.get("work", "")).strip()
        if not work_text:
            work_text = "Worked on assigned internship tasks and documented progress for the day."

        formatted_date = format_date(dates[i]) if i < len(dates) else ""
        result.append({
            "day": i + 1,
            "date": formatted_date,
            "work": work_text
        })

    return result


# ─────────────────────────────────────────────
# ✅ GENERATE ALL JOURNAL ENTRIES IN ONE CALL 🚀
# ─────────────────────────────────────────────
def generate_all_journals(api_key: str, daily_data: list) -> list:
    combined_input = "\n".join([
        f"Day {d['day']} ({d['date']}): {d['work']}"
        for d in daily_data
    ])

    prompt = f"""
Generate professional OJT daily journal entries for college students.

RULES:
- Each day must be unique
- No repetition
- No HR/company content
- Keep concise and realistic
- Avoid professional/enterprise tools (no Jira, Azure, Salesforce, etc.)
- Use college-friendly tools: Python, JavaScript, Git, SQL, VS Code, Linux, React, etc.

For EACH day return:
- my_space: Minimum 4 lines of detailed personal reflection
- tasks_carried_out: List items separated by NEWLINE (NOT array)
- key_learnings: List items separated by NEWLINE (NOT array)
- tools_used: comma-separated list
- special_achievements: 1-2 lines (NEVER "N/A")

OUTPUT JSON (use plain text with newlines for multi-line fields):
[
  {{
    "day": 1,
    "my_space": "reflection text",
    "tasks_carried_out": "Task 1\\nTask 2\\nTask 3",
    "key_learnings": "Learning 1\\nLearning 2",
    "tools_used": "tool1, tool2, tool3",
    "special_achievements": "achievement text"
  }}
]

INPUT:
{combined_input}
"""

    text = call_gemini(api_key, prompt)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise GeminiServiceError("Gemini returned invalid JSON while generating journals") from e

    if not isinstance(parsed, list):
        raise GeminiServiceError("Gemini returned unexpected format for generated journals")

    return parsed


# ─────────────────────────────────────────────
# ✅ FINAL PIPELINE FUNCTION
# ─────────────────────────────────────────────
def generate_full_entries(api_key: str, work_description: str, dates: list):
    num_days = len(dates)

    # Step 1: Split
    daily_split = split_work_into_days(api_key, work_description, dates, num_days)

    # Step 2: Generate ALL entries (1 API call)
    journal_data = generate_all_journals(api_key, daily_split)

    # Merge
    final = []
    for i in range(num_days):
        entry = journal_data[i]
        base = daily_split[i]

        final.append({
            "date_display": base["date"],
            "my_space": entry["my_space"],
            "tasks_carried_out": entry["tasks_carried_out"],
            "key_learnings": entry["key_learnings"],
            "tools_used": entry["tools_used"],
            "special_achievements": entry["special_achievements"],
        })

    return final


# ─────────────────────────────────────────────
# ✅ SINGLE JOURNAL ENTRY (for backward compatibility)
# ─────────────────────────────────────────────
def generate_journal_entry(api_key: str, date: str, work: str) -> dict:
    """Generate structured journal entry for one day using Gemini."""

    # Format date to DD-M-YYYY
    formatted_date = format_date(date)

    prompt = f"""Generate a professional internship daily journal entry for a college student.

Date: {formatted_date}
Work Done: {work}

Return ONLY a valid JSON object (no markdown, no explanation):
{{
  "my_space": "Detailed personal reflection (Minimum 4 sentences/lines)",
  "tasks_carried_out": "Task 1\\nTask 2\\nTask 3\\nTask 4",
  "key_learnings": "Learning 1\\nLearning 2\\nLearning 3",
  "tools_used": "tool1, tool2, tool3",
  "special_achievements": "Achievement description (1-2 sentences)"
}}

IMPORTANT:
- Use college/student-level tools only (Python, JavaScript, Git, VS Code, Linux, React, etc.)
- AVOID professional tools like Jira, Azure, Salesforce, enterprise software
- Use plain newlines (\\n) between items for multi-line fields, NOT JSON arrays
- Each task/learning should be a complete sentence
- Keep it concise, professional, realistic, and non-repetitive"""

    text = call_gemini(api_key, prompt)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise GeminiServiceError("Gemini returned invalid JSON for single entry generation") from e