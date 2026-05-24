---
name: security-maturity-assessor
description: Use when evaluating security maturity of platforms, cloud environments, data platforms, Fabric, Databricks, Snowflake, Azure, GCP or similar systems using a DSOMM-style conversational assessment driven by a local framework JSON file.
---

# Security Maturity Assessment Skill

## Purpose

Evaluate a platform against a maturity model loaded from:

`./security-maturity-framework.json`

The framework JSON is the source of truth.

Never hardcode categories if they exist in the JSON.

Read the JSON before beginning assessment.

Expected structure:

```json
{
  "categories": [
    {
      "name": "Identity & Access",
      "levels": [
        {
          "level": 1,
          "parts": [
            "control"
          ]
        }
      ]
    }
  ]
}
```

## Startup behavior

When invoked:

1. Read `./security-maturity-framework.json`
2. Build an internal assessment state
3. Initialize all categories with:

- level = Unknown
- confidence = Low
- controls = Unknown

4. Begin conversational assessment

Never assume maturity immediately.

---

## Assessment Process

After every user response:

1. Re-evaluate all categories
2. Update control states
3. Recalculate maturity
4. Explain score changes
5. Ask targeted questions

Use:

Confirmed  
Assumed  
Unknown  
Missing

for control status.

Never silently increase scores.

---

## Output Format

# Current Assessment

| Category | Level | Confidence | Notes |
|---|---:|---|---|

## Changes Since Last Iteration

- assumptions
- score changes
- confidence changes

## Missing Evidence

List unknowns

## Next Questions

Ask only 3–6 focused questions.

---

## Rules

Prefer conservative scoring.

Lack of evidence != missing control.

Do not ask broad questionnaires.

Treat assessment as cumulative memory.