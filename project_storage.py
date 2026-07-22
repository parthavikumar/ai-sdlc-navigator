import json
import os

SAVE_DIR = "saved_projects"


def save_project(project):
    os.makedirs(SAVE_DIR, exist_ok=True)
    filename = project["project_name"].strip().replace(" ", "_").lower() + ".json"
    path = os.path.join(SAVE_DIR, filename)

    with open(path, "w") as f:
        json.dump(project, f, indent=2)

    return filename


DEFAULT_PROJECT = {
    "project_name": "Untitled Project",
    "team": "",
    "timeline": "",
    "dependencies": "",
    "requirement": "",
    "business_goal": "",
    "constraints": "",
    "requirement_output": "",
    "planning_output": "",
    "dev_guidance_output": "",
    "scores": {
        "requirement_quality": 0,
        "planning_confidence": 0,
        "capacity_fit": "Not assessed",
        "dependency_risk": "Not assessed",
        "development_readiness": 0,
    },
    "change_log": [],
    "score_history": [],
}


def load_project(filename):
    path = os.path.join(SAVE_DIR, filename)

    with open(path, "r") as f:
        loaded = json.load(f)

    # Fill in any fields that are missing from older saved files
    merged = dict(DEFAULT_PROJECT)
    merged.update(loaded)

    if "scores" in loaded:
        merged_scores = dict(DEFAULT_PROJECT["scores"])
        merged_scores.update(loaded["scores"])
        merged["scores"] = merged_scores

    return merged


def list_saved_projects():
    os.makedirs(SAVE_DIR, exist_ok=True)
    return sorted(f for f in os.listdir(SAVE_DIR) if f.endswith(".json"))

def delete_project(filename):
    path = os.path.join(SAVE_DIR, filename)
    if os.path.exists(path):
        os.remove(path)