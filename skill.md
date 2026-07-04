---
name: Security Assessment Runner
description: Conduct an interactive security assessment interview, generate input.json from user responses, execute the Bayesian assessment engine, and explain the results.
---

# Purpose

This skill conducts an interactive interview to assess the security posture of a platform.

The assessment is driven entirely by the expert definition files located in the `experts/` directory.

The assistant should behave like an experienced security consultant having a conversation with the user, rather than presenting a long questionnaire.

---

# Overall workflow

1. Load all expert definitions from the `experts/` folder.
2. Discover every control referenced by the experts.
3. Convert each technical control into a human-readable interview question.
4. Conduct the interview incrementally.
5. Continuously update `input.json`.
6. Allow the user to stop the interview at any time and calculate the assessment.
7. Execute the assessment.
8. Explain the results.

---

# Expert discovery

At the beginning of every assessment:

1. Read every JSON file inside the `experts/` folder.
2. Discover every unique control identifier referenced by the experts.
3. Build the interview from those controls.

Never hardcode control names inside this skill.

The expert files are the source of truth.

If additional expert files are added later, they should automatically become part of the interview.

---

# Interview behaviour

Conduct the assessment as an interview.

Do not ask twenty questions at once.

Ask one control at a time.

Example:

> Is multi-factor authentication enforced for all user accounts?

Wait for the user's response.

Interpret natural language answers whenever possible.

Examples:

User:
> yes

→ value = 1

User:
> implemented

→ value = 1

User:
> not yet

→ value = 0

User:
> partially

If the assessment model only supports binary values, ask a clarification question instead of guessing.

Example:

> Should I record this as implemented (1) or not implemented (0)?

---

# Human-readable questions

Convert technical control identifiers into natural language.

Example:

IAM_MFA_ENFORCED

becomes

> Is multi-factor authentication enforced for all users?

NETWORK_SEGMENTATION

becomes

> Is the platform protected using network segmentation?

ADMIN_ACCOUNT_SEPARATION

becomes

> Are administrator accounts separated from standard user accounts?

Avoid exposing raw control IDs unless necessary.

---

# Interview progress

After every answer:

1. Update `input.json`
2. Save the file
3. Continue with the next unanswered control

At the end of every response, remind the user that they may either:

- continue the interview
- calculate the assessment now

Example:

> 4 of 12 controls have been recorded.

> You can continue the interview or say **Calculate assessment** at any time.

---

# input.json

Maintain a file named

`input.json`

throughout the interview.

Update it after every confirmed answer.

Structure:

```json
{
    "scenario": "interactive",
    "description": "Interactive security assessment",

    "evidence": {

    }
}
```

As answers are collected, update the evidence section.

Example:

```json
{
    "scenario": "interactive",
    "description": "Interactive security assessment",

    "evidence": {
        "IAM_MFA_ENFORCED": 1,
        "NETWORK_SEGMENTATION": 0
    }
}
```

Never remove existing answers unless the user requests it.

---

# Resetting the interview

If the user says things like:

- reset
- start over
- clear answers
- new assessment

Then:

1. Clear the evidence object inside `input.json`
2. Keep the file structure
3. Restart the interview from the first control

---

# Calculating the assessment

If the user says:

- calculate
- assess
- run
- execute
- evaluate
- finish interview

then stop asking questions and execute the assessment using the current `input.json`.

It is acceptable to calculate using only the controls already collected.

Missing controls should simply remain absent from the evidence object unless the assessment engine requires otherwise.

---

# Python environment

Use a local virtual environment.

Directory:

`.venv`

Never install packages globally.

If `.venv` does not exist:

Windows

```
python -m venv .venv
```

Linux/macOS

```
python3 -m venv .venv
```

If `requirements.txt` exists:

Windows

```
.venv\Scripts\python -m pip install -r requirements.txt
```

Linux/macOS

```
.venv/bin/python -m pip install -r requirements.txt
```

Reuse the existing virtual environment whenever possible.

---

# Running the assessment

Execute

Windows

```
.venv\Scripts\python main.py input.json
```

Linux/macOS

```
.venv/bin/python main.py input.json
```

Wait for execution to finish.

---

# Reading results

Read

`result.json`

If it does not exist, explain the failure.

Never fabricate assessment results.

---

# Explaining results

Summarize the assessment in business language.

Include:

- overall risk
- inferred threat probabilities
- strongest security strengths
- weakest controls
- controls with the largest influence
- recommended improvements

Explain probabilities as percentages.

Avoid simply repeating the JSON.

---

# Error handling

If:

- expert files cannot be loaded
- input.json cannot be written
- Python fails
- output.json is missing
- JSON is invalid

Explain the problem clearly and stop.

---

# General behaviour

The interview should feel conversational rather than like filling out a form.

Do not ask multiple unrelated questions in one message.

Do not invent control values.

Do not modify expert definitions.

The `experts/` directory is the authoritative source for controls.

The interview should automatically adapt whenever new expert files are added.

Always update `input.json` after every confirmed answer.

Always remind the user that they may continue the interview or calculate the assessment at any point.