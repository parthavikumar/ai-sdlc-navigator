# AI SDLC Navigator

A living project dashboard that tracks a software feature's requirements, planning, and development guidance — and automatically recalculates risk and readiness scores as the project's inputs change.

## What it does

- **Requirement analysis** — turns a rough feature idea into a structured requirement (target users, user stories, missing questions, acceptance criteria, edge cases, and more), with a rubric-based quality score.
- **Project planning** — generates a detailed, role-assigned, numbered project plan based on the requirement, team, and timeline.
- **Development guidance** — answers specific technical questions with an architecture breakdown, illustrative code snippets, and open questions.
- **Live Capacity Fit / Dependency Risk scoring** — calculated directly in Python (not AI) so it updates instantly as the team, timeline, or dependencies change.
- **Change tracking** — logs every edit to the project with a word-level diff and an AI-generated summary of its impact.
- **Score trend chart** — visualizes how the project's scores have changed over time.

## Requirements

- Python 3.9 or later
- An OpenAI API key (see below)

## Setup

### 1. Get the code

If you were added as a collaborator on the GitHub repo, clone it:

```
git clone https://github.com/parthavikumar/ai-sdlc-navigator.git
cd ai-sdlc-navigator
```

(If you downloaded a ZIP instead, unzip it and `cd` into the folder.)

### 2. Create a virtual environment

This keeps this project's Python packages separate from anything else on your computer.

**Mac/Linux:**
```
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```
python -m venv venv
venv\Scripts\activate
```

You'll know it worked if your terminal prompt now starts with `(venv)`.

### 3. Install the required packages

```
pip install -r requirements.txt
```

### 4. Add the OpenAI API key

This app uses OpenAI's API to generate the requirement analysis, project plans, and development guidance. The key itself is **not** included in this repository (for security reasons).

In the project folder, create a new file named exactly `.env` (no filename before the dot) with the following contents:

```
OPENAI_API_KEY=paste_the_key_here
OPENAI_MODEL=gpt-4o-mini
```

Paste in the key you were given in place of `paste_the_key_here`. No quotes, no spaces around the `=`.

*(If you'd rather use your own key instead: create one at [platform.openai.com](https://platform.openai.com) under **API keys**, after adding a payment method under **Settings → Billing**. Usage costs are typically small — fractions of a cent to a few cents per request.)*

### 5. Run the app

```
streamlit run app.py
```

This should open a browser tab automatically, or print a local URL (like `http://localhost:8501`) to open manually.

## Project structure

```
ai-sdlc-navigator/
├── app.py                # Main Streamlit app — UI, tabs, scoring, change tracking
├── ai_service.py          # Single entry point for all OpenAI API calls
├── project_storage.py     # Save/load/delete logic for projects (stored as local JSON files)
├── requirements.txt        # Python package dependencies
├── .gitignore
└── saved_projects/         # Created automatically — stores your saved projects locally
```

## Notes

- Projects are saved locally as JSON files in a `saved_projects/` folder, which is created automatically the first time you save a project. This folder is not included in the repository, so each person running the app locally has their own separate set of saved projects.
- The app autosaves as you work, once a project has a name other than "Untitled Project."
- Two of the five scores (Capacity Fit and Dependency Risk) are calculated directly in Python rather than by the AI, so they update instantly as you edit the team, timeline, or dependencies — no need to regenerate anything for those two.
