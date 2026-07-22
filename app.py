import streamlit as st
from ai_service import call_ai
import json
import difflib
import datetime
from project_storage import save_project, load_project, list_saved_projects, delete_project
import re
import hashlib

def get_plan_inputs_hash(project):
    relevant = f"{project['requirement']}|{project['team']}|{project['timeline']}|{project['dependencies']}|{project['requirement_output']}"
    return hashlib.md5(relevant.encode()).hexdigest()

def calculate_capacity_and_dependency_risk(project, num_steps):
    team_text = project["team"].lower()
    timeline_text = project["timeline"].lower()
    dependencies_text = project["dependencies"].strip().lower()

    # --- Capacity Fit ---
    has_backend = "backend" in team_text
    has_frontend = "frontend" in team_text
    has_qa = bool(re.search(r'\bqa\b|quality assurance', team_text))
    has_design = "design" in team_text

    # Count people: sum each number that appears directly before a role word,
    # rather than summing every number in the text (avoids picking up stray numbers)
    role_pattern = r'(\d+)\s*(backend|frontend|qa|quality assurance|design(?:er)?|developer)'
    matches = re.findall(role_pattern, team_text)
    people_count = sum(int(n) for n, _ in matches)

    # Part-time mentions count as half a person for capacity purposes
    part_time_mentions = len(re.findall(r'part[\s-]?time', team_text))
    people_count = max(people_count - (part_time_mentions * 0.5), 0.5) if people_count else 1

    # Fallback: if no role-prefixed numbers were found at all, count any numbers as a rough estimate
    if not matches:
        any_numbers = re.findall(r'\d+', team_text)
        people_count = sum(int(n) for n in any_numbers) if any_numbers else 1

    # --- Timeline, converted to days ---
    timeline_numbers = re.findall(r'\d+', timeline_text)
    timeline_value = int(timeline_numbers[0]) if timeline_numbers else 0

    if "month" in timeline_text:
        timeline_days = timeline_value * 30
    elif "week" in timeline_text:
        timeline_days = timeline_value * 7
    elif "day" in timeline_text:
        timeline_days = timeline_value
    else:
        # No unit mentioned — assume weeks, since that's the most common way people describe project timelines
        timeline_days = timeline_value * 7

    days_per_step = (timeline_days / num_steps) if num_steps else 0

    if people_count < 2 or not (has_backend and has_frontend):
        capacity_fit = "High Risk"
        capacity_reasoning = f"~{people_count:.1f} person/people mentioned, or a required role (backend/frontend) is missing."
    elif timeline_days < num_steps * 3:
        capacity_fit = "High Risk"
        capacity_reasoning = f"{num_steps} steps but only {timeline_days} days available (~{days_per_step:.1f} days/step) — too tight."
    elif has_backend and has_frontend and has_qa and days_per_step >= 5:
        capacity_fit = "Low Risk"
        capacity_reasoning = f"~{people_count:.1f} people covering backend, frontend, and QA, with ~{days_per_step:.1f} days/step."
    else:
        capacity_fit = "Medium Risk"
        capacity_reasoning = f"~{people_count:.1f} people, {num_steps} steps, ~{days_per_step:.1f} days/step — workable but with limited slack."

    # --- Dependency Risk ---
    uncertainty_words = ["not sure", "tbd", "unclear", "unknown", "need to confirm", "unsure"]

    if not dependencies_text or dependencies_text in ("none", "n/a", "na"):
        dependency_risk = "Low Risk"
        dependency_reasoning = "No external dependencies mentioned."
    elif any(word in dependencies_text for word in uncertainty_words):
        dependency_risk = "High Risk"
        dependency_reasoning = f"Dependency mentioned with uncertain language: \"{project['dependencies']}\""
    elif dependencies_text.count(",") >= 1 or " and " in dependencies_text:
        dependency_risk = "High Risk"
        dependency_reasoning = f"Multiple external dependencies mentioned: \"{project['dependencies']}\""
    else:
        dependency_risk = "Medium Risk"
        dependency_reasoning = f"One external dependency mentioned: \"{project['dependencies']}\""

    return capacity_fit, capacity_reasoning, dependency_risk, dependency_reasoning

def highlight_word_diff(before, after):
    before_words = before.split()
    after_words = after.split()
    matcher = difflib.SequenceMatcher(None, before_words, after_words)

    result = []
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            result.append(" ".join(after_words[j1:j2]))
        elif opcode == "insert":
            added = " ".join(after_words[j1:j2])
            result.append(f":green[{added}]")
        elif opcode == "replace":
            added = " ".join(after_words[j1:j2])
            result.append(f":green[{added}]")
        # "delete" opcode is skipped entirely — we're only showing the new/after text,
        # so removed words just disappear rather than showing strikethrough

    return " ".join(result)

def normalize(value):
    if isinstance(value, str):
        text = value.strip()
        # Normalize smart quotes and dashes to their plain equivalents
        replacements = {
            "\u2018": "'", "\u2019": "'",   # smart single quotes
            "\u201c": '"', "\u201d": '"',   # smart double quotes
            "\u2013": "-", "\u2014": "-",   # en dash, em dash
        }
        for smart, plain in replacements.items():
            text = text.replace(smart, plain)
        return text
    return value

def diff_project(old, new):
    changes = {}
    fields_to_check = ["project_name", "team", "timeline", "dependencies", "requirement", "business_goal", "constraints"]
    for field in fields_to_check:
        old_value = normalize(old.get(field))
        new_value = normalize(new.get(field))
        if old_value != new_value:
            changes[field] = {"before": old.get(field), "after": new.get(field)}
    return changes

def record_score_snapshot(project, label):
    sequence_number = len(project["score_history"]) + 1
    project["score_history"].append({
        "sequence": sequence_number,
        "timestamp": datetime.datetime.now().strftime("%I:%M:%S %p"),
        "label": f"{sequence_number}. {label}",
        "requirement_quality": project["scores"]["requirement_quality"] if isinstance(project["scores"]["requirement_quality"], (int, float)) else 0,
        "planning_confidence": project["scores"]["planning_confidence"] if isinstance(project["scores"]["planning_confidence"], (int, float)) else 0,
        "development_readiness": project["scores"]["development_readiness"] if isinstance(project["scores"]["development_readiness"], (int, float)) else 0,
    })

def get_role_color(role_text):
        role_lower = role_text.lower()
        if "backend" in role_lower:
            return "blue"
        elif "frontend" in role_lower:
            return "green"
        elif "qa" in role_lower or "quality" in role_lower:
            return "orange"
        elif "design" in role_lower:
            return "violet"
        elif "product" in role_lower or "pm" in role_lower:
            return "red"
        else:
            return "gray"


def colorize_roles(assigned_to_text):
    # assigned_to_text may list multiple roles separated by commas or "and"
    parts = re.split(r',| and ', assigned_to_text)
    colored_parts = []
    for part in parts:
        part = part.strip()
        if part:
            color = get_role_color(part)
            colored_parts.append(f":{color}[{part}]")
    return ", ".join(colored_parts)


st.set_page_config(page_title="AI SDLC Navigator", layout="wide")

# -----------------------------
# Initialize project state
# -----------------------------
if "project" not in st.session_state:
    st.session_state.project = {
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
    }

project = st.session_state.project
project.setdefault("score_history", [])

# -----------------------------
# Header
# -----------------------------
st.title("AI SDLC Navigator")
st.caption("Living project dashboard for requirements, planning, and development guidance")

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.header("Project Setup")

    def handle_project_switch():
        selected = st.session_state.project_selector
        if selected == "+ New Project":
            st.session_state.project = {
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
        else:
            st.session_state.project = load_project(selected)
        st.session_state.last_snapshot = dict(st.session_state.project)

    saved_files = list_saved_projects()
    dropdown_options = ["+ New Project"] + saved_files

    current_filename = (
        project["project_name"].strip().replace(" ", "_").lower() + ".json"
        if project["project_name"].strip() else "+ New Project"
    )

    if "project_selector" not in st.session_state:
        st.session_state.project_selector = current_filename if current_filename in dropdown_options else "+ New Project"

    st.selectbox("Project", dropdown_options, key="project_selector", on_change=handle_project_switch)

    project["project_name"] = st.text_input("Project Name", value=project["project_name"])
    project["team"] = st.text_area("Team", value=project["team"], placeholder="e.g. 1 backend, 1 frontend, 1 QA")
    project["timeline"] = st.text_input("Timeline", value=project["timeline"], placeholder="e.g. 4 weeks")
    project["dependencies"] = st.text_area("Known Dependencies", value=project["dependencies"])

    if project["project_name"].strip() and project["project_name"] != "Untitled Project":
        save_project(project)
        st.caption(f"Autosaved at {datetime.datetime.now().strftime('%I:%M:%S %p')}")

    st.divider()
    st.header("Log a Change")

    if "last_snapshot" not in st.session_state:
        st.session_state.last_snapshot = dict(project)

    pending_changes = diff_project(st.session_state.last_snapshot, project)

    if pending_changes:
        st.caption(f"{len(pending_changes)} field(s) edited since last log.")
    else:
        st.caption("No changes made since last log.")

    if st.button("Record Change", disabled=not pending_changes):
        changes = pending_changes
        change_summary_text = "\n".join(
            f"- {field} changed from '{v['before']}' to '{v['after']}'"
            for field, v in changes.items()
        )

        prompt = f"""
        You are a technical project lead reviewing a change that was just made to an active project.

        Here is exactly what changed:
        {change_summary_text}

        Instructions:
        - Base your analysis ONLY on the specific change shown above — do not speculate about unrelated aspects of the project.
        - Be concrete: name the actual new work, risk, or consideration this change introduces, not a generic statement like "this may increase scope."
        - If the change is minor or low-impact (e.g. a small wording clarification), say so plainly rather than manufacturing significance.
        - Do not repeat the raw before/after text back verbatim — synthesize what it means.

        In 2-3 sentences, explain the practical impact of this change: what new work it likely creates,
        what risk it introduces or changes, and anything the team should double-check as a result.
        """

        with st.spinner("Analyzing change impact..."):
            impact_summary = call_ai(prompt)

        project["change_log"].append({
            "changes": changes,
            "impact_summary": impact_summary
        })
        st.session_state.last_snapshot = dict(project)
        st.success(f"Recorded {len(changes)} change(s).")
        st.rerun()
        
    st.divider()
    if current_filename != "+ New Project" and current_filename in saved_files:
        with st.expander("Delete this project"):
            st.markdown(":red[This permanently deletes the saved project file. This cannot be undone.]")
            confirm_delete = st.checkbox("Yes, I'm sure")
            if st.button("Delete Project", disabled=not confirm_delete, type="primary"):
                delete_project(current_filename)
                st.session_state.project = {
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
                st.session_state.last_snapshot = dict(st.session_state.project)
                del st.session_state["project_selector"]
                st.success("Project deleted.")
                st.rerun()
        
# -----------------------------
# Live recalculation of Capacity Fit / Dependency Risk
# (runs every time the page reruns, so it reflects the current team/timeline/dependencies immediately)
# -----------------------------
project.setdefault("num_plan_steps", 5)  # reasonable default before any plan has been generated

live_capacity_fit, live_capacity_reasoning, live_dependency_risk, live_dependency_reasoning = (
    calculate_capacity_and_dependency_risk(project, project["num_plan_steps"])
)
project["scores"]["capacity_fit"] = live_capacity_fit
project["scores"]["dependency_risk"] = live_dependency_risk

# -----------------------------
# Health score cards
# -----------------------------
st.subheader("Project Health")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Requirement Quality", project["scores"]["requirement_quality"])
col2.metric("Planning Confidence", project["scores"]["planning_confidence"])
col3.metric("Capacity Fit", project["scores"]["capacity_fit"])
col4.metric("Dependency Risk", project["scores"]["dependency_risk"])
col5.metric("Dev Readiness", project["scores"]["development_readiness"])

# -----------------------------
# Tabs
# -----------------------------
overview_tab, req_tab, plan_tab, dev_tab, log_tab = st.tabs(
    ["Overview", "Requirement", "Planning", "Dev Guidance", "Change Log"]
)

with overview_tab:
    st.header("Project Overview")

    st.write(f"**Project:** {project['project_name']}")
    st.write(f"**Team:** {project['team'] or 'Not provided'}")
    st.write(f"**Timeline:** {project['timeline'] or 'Not provided'}")
    st.write(f"**Dependencies:** {project['dependencies'] or 'Not provided'}")

    st.divider()

    st.subheader("Most Recent Change")
    if project["change_log"]:
        latest = project["change_log"][-1]
        if "impact_summary" in latest:
            st.markdown(latest["impact_summary"])
        for field, values in latest["changes"].items():
            st.markdown(f"- **{field}** was updated")
    else:
        st.info("No changes recorded yet.")

    st.divider()

    st.subheader("Score Trend")
    if len(project["score_history"]) >= 2:
        import pandas as pd
        import altair as alt

        df = pd.DataFrame(project["score_history"])
        df["order"] = range(len(df))
        df = df.sort_values("order")

        # Reshape into long format so Altair can plot multiple lines with a legend
        long_df = df.melt(
            id_vars=["order", "label"],
            value_vars=["requirement_quality", "planning_confidence", "development_readiness"],
            var_name="metric",
            value_name="score"
        )

        chart = alt.Chart(long_df).mark_line(point=True).encode(
            x=alt.X("order:O", axis=alt.Axis(labelExpr="datum.value", title=None), sort=None),
            y=alt.Y("score:Q", scale=alt.Scale(domain=[0, 100]), title="Score (0-100)"),
            color=alt.Color("metric:N", title="Metric"),
            tooltip=["label", "metric", "score"]
        ).properties(height=350)

        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Generate at least two updates (Requirement, Planning, or Dev Guidance) to see a score trend chart.")
        
with req_tab:
    st.header("Requirement Gathering")

    with st.form("requirement_form"):
        requirement = st.text_area(
            "Feature idea / requirement",
            value=project["requirement"],
            placeholder="Example: Build a customer dashboard that shows monthly data usage."
        )
        business_goal = st.text_area(
            "Business goal",
            value=project["business_goal"],
            placeholder="Example: Reduce support calls by giving users visibility into usage."
        )
        constraints = st.text_area(
            "Known constraints",
            value=project["constraints"],
            placeholder="Example: Usage data comes from an existing backend service."
        )
        submitted = st.form_submit_button("Analyze Requirement")

    if submitted:
        project["requirement"] = requirement
        project["business_goal"] = business_goal
        project["constraints"] = constraints

        prompt = f"""
        You are a senior product manager conducting a thorough requirements review before this goes to engineering.
        Be precise, specific, and critical — do not soften your assessment to be encouraging, and do not invent
        details, users, or constraints that were not stated below.

        REQUIREMENT: {requirement}
        BUSINESS GOAL: {business_goal}
        KNOWN CONSTRAINTS: {constraints}

        Provide a deep analysis with all of the following sections. Every item must be specific to THIS requirement —
        never a generic, could-apply-to-anything statement.

        1. SUMMARY: One or two sentences describing what is being built, in your own words, at a level of detail
           someone unfamiliar with the request could understand.

        2. TARGET USERS: Identify the specific user type(s) who would use this feature. If multiple distinct user
           types are implied (e.g. "customers" and "internal support agents"), list each separately. If the
           requirement genuinely does not specify who this is for, say so explicitly rather than guessing.

        3. USER STORIES: Write 3-5 user stories in the standard format "As a [user type], I want [capability] so that
           [benefit]." These should cover the core functionality implied by the requirement, not just restate it once.

        4. MISSING QUESTIONS: 3-5 genuinely important questions that are NOT answered by the requirement, business
           goal, or constraints above. Each must be specific to this feature — do not include generic checklist
           questions (like "what is the deadline") unless truly relevant. For each question, briefly note WHY it
           matters (what decision or risk depends on the answer).

        5. ACCEPTANCE CRITERIA: 4-6 testable criteria a QA person could actually verify pass/fail on. Avoid vague
           statements like "works well" — each criterion must describe an observable, checkable behavior.

        6. EDGE CASES: 3-5 specific edge cases or unusual scenarios this feature needs to handle (e.g. what happens
           with no data yet, conflicting inputs, extreme values, permission boundaries). These must be plausible
           for THIS specific feature, not generic software edge cases.

        7. OUT OF SCOPE: 2-4 things that seem plausible to assume are included, but should explicitly NOT be built
           in this version, based on what's implied by the requirement and constraints. This prevents scope creep.

        8. DEPENDENCIES: Any other systems, teams, APIs, or data sources this requirement would depend on, based on
           what's stated or reasonably implied. If genuinely none, say so.

        Score the requirement quality (0-100) by checking these five criteria. Each is worth up to 20 points:

        1. Target user clarity (0-20): Is it clear WHO this is for? (0 = no user mentioned, 20 = specific user type clearly defined)
        2. Problem/goal clarity (0-20): Is it clear WHY this is being built / what problem it solves? (0 = no goal stated, 20 = clear, specific goal)
        3. Scope clarity (0-20): Is it clear WHAT is included and excluded? (0 = totally open-ended, 20 = specific, bounded functionality described)
        4. Constraints defined (0-20): Are technical, business, or resource constraints stated? (0 = none mentioned, 20 = specific constraints listed)
        5. Success criteria (0-20): Is there any way to know when this is "done" or working? (0 = no way to tell, 20 = clear, testable criteria)

        Add the five criteria for the final quality_score. Do not round up generously — if a criterion is missing
        or vague, score it low. Use the full 0-100 range; a requirement missing 2+ criteria entirely should score below 40.

        Return ONLY valid JSON, with no markdown formatting and no extra commentary, in exactly this shape:

        {{
          "quality_score": <integer 0-100>,
          "summary": "<one to two sentence summary>",
          "target_users": ["<user type 1>", "<user type 2>"],
          "user_stories": ["<story 1>", "<story 2>", "<story 3>"],
          "missing_questions": [
            {{"question": "<question 1>", "why_it_matters": "<brief reason>"}},
            {{"question": "<question 2>", "why_it_matters": "<brief reason>"}}
          ],
          "acceptance_criteria": ["<criterion 1>", "<criterion 2>", "<criterion 3>"],
          "edge_cases": ["<edge case 1>", "<edge case 2>"],
          "out_of_scope": ["<item 1>", "<item 2>"],
          "dependencies": ["<dependency 1>"]
        }}
        """

        with st.spinner("Analyzing requirement..."):
            result = call_ai(prompt)

        try:
            parsed = json.loads(result)
            project["scores"]["requirement_quality"] = parsed["quality_score"]
            record_score_snapshot(project, "Requirement updated")

            users_text = "\n".join(f"- {u}" for u in parsed["target_users"])
            stories_text = "\n".join(f"- {s}" for s in parsed["user_stories"])
            questions_text = "\n".join(
                f"- **{q['question']}** — {q['why_it_matters']}" for q in parsed["missing_questions"]
            )
            criteria_text = "\n".join(f"- {c}" for c in parsed["acceptance_criteria"])
            edge_cases_text = "\n".join(f"- {e}" for e in parsed["edge_cases"])
            out_of_scope_text = "\n".join(f"- {o}" for o in parsed["out_of_scope"])
            dependencies_text = "\n".join(f"- {d}" for d in parsed["dependencies"]) or "- None identified"

            project["requirement_output"] = (
                f"**Summary:** {parsed['summary']}\n\n"
                f"**Target Users:**\n{users_text}\n\n"
                f"**User Stories:**\n{stories_text}\n\n"
                f"**Missing Questions:**\n{questions_text}\n\n"
                f"**Acceptance Criteria:**\n{criteria_text}\n\n"
                f"**Edge Cases:**\n{edge_cases_text}\n\n"
                f"**Out of Scope:**\n{out_of_scope_text}\n\n"
                f"**Dependencies:**\n{dependencies_text}"
            )
        except (json.JSONDecodeError, KeyError):
            project["requirement_output"] = result
            st.warning("Got a response, but couldn't parse the score. Showing raw output instead.")

        st.success("Requirement analyzed!")
        st.rerun()

    if project["requirement_output"]:
        st.subheader("Requirement Analysis")
        st.write(project["requirement_output"])


with plan_tab:
    st.header("Project Planning")

    st.write("This uses your requirement, team, and timeline to generate a project plan.")

    st.subheader("Capacity & Dependency Assessment (live)")
    st.write(f"**Capacity Fit:** {live_capacity_fit} — {live_capacity_reasoning}")
    st.write(f"**Dependency Risk:** {live_dependency_risk} — {live_dependency_reasoning}")
    st.divider()

    if not project["requirement_output"]:
        st.info("Fill out and analyze the Requirement tab first — planning works best once the requirement is clearer.")
    else:
        current_hash = get_plan_inputs_hash(project)
        is_stale = project.get("last_plan_hash") != current_hash
        has_existing_plan = bool(project["planning_output"])

        if is_stale and has_existing_plan:
            button_label = "Regenerate Project Plan"

            last_inputs = project.get("last_plan_inputs", {})
            current_inputs = {
                "requirement": project["requirement"],
                "team": project["team"],
                "timeline": project["timeline"],
                "dependencies": project["dependencies"],
            }
            changed_fields = [
                field for field in current_inputs
                if normalize(last_inputs.get(field, "")) != normalize(current_inputs[field])
            ]

            if changed_fields:
                field_list = ", ".join(f"**{f}**" for f in changed_fields)
                st.info(f"Done editing? {field_list} changed since this plan was generated.")
            else:
                st.info("Done editing? Something used by this plan changed.")
        elif has_existing_plan:
            button_label = "Regenerate Anyway"
            st.caption("Plan is up to date with current inputs.")
        else:
            button_label = "Generate Project Plan"

        if st.button(button_label):
            prompt = f"""
            You are helping create a detailed, actionable project plan for a software feature.

            Requirement: {project["requirement"]}
            Requirement analysis: {project["requirement_output"]}
            TEAM (the ONLY people available to assign work to): {project["team"]}
            Timeline: {project["timeline"]}
            Known dependencies: {project["dependencies"]}

            Break the work into 5-8 major numbered steps, in the exact order they should be executed.
            Order strictly by technical dependency: data model/schema before backend logic, backend/API before frontend
            integration, core functionality before edge-case handling, implementation before QA/testing steps.

            For EACH step, provide all of the following, with no field left vague or generic:

            1. TITLE: Name the actual component, screen, endpoint, or system involved. Never use a generic title
               like "Backend work" or "Frontend work" — instead something like "Build usage-data retrieval endpoint"
               or "Build daily usage breakdown UI component."

            2. ASSIGNED_TO: Assign exactly which team member(s) from TEAM own this step.
               - Use ONLY roles/people that literally appear in TEAM. Never invent a role not mentioned
                 (e.g. do not assign to "Designer" if no designer is listed).
               - If TEAM lists multiple people in the same role (e.g. "2 backend developers"), refer to them as
                 "Backend developer 1" and "Backend developer 2" ONLY when splitting their work meaningfully improves
                 parallelization — otherwise just say "Backend developer(s)."
               - If a step genuinely requires more than one role working together (e.g. wiring frontend to a new API),
                 list all relevant roles, separated by commas.
               - Be consistent: if you refer to "Backend developer 1" in one step, use that same exact label
                 consistently in any other step assigned to that same person.

            3. SUBTASKS: 2-4 specific actions. Each subtask must describe an actual action taken on the actual
               feature — never a restatement of the title in different words, and never a placeholder like
               "implement the necessary logic." For EACH subtask, also specify the SINGLE role (from TEAM) who
               is actually the one doing that specific action — even if the step as a whole involves multiple
               roles, each individual subtask should map to just one responsible role.

            4. GUIDANCE: One or two sentences of practical direction on HOW or WHERE to approach this step
               (e.g. "coordinate with the billing API team to confirm rate limits before building the retry logic,"
               or "reuse the existing authentication middleware rather than building new session handling").
               Do NOT include specific URLs, fabricated documentation links, or made-up internal tool names.

            5. RISK: One specific risk unique to this step, if one genuinely exists (e.g. "billing API's 24-hour
               refresh delay may cause the dashboard to show outdated numbers right after a purchase"). Use an
               empty string if there is truly no notable risk for this particular step — do not force a risk that
               doesn't apply just to fill the field.

            Score the planning confidence (0-100) by checking these five criteria. Each is worth up to 20 points:

            1. Task clarity (0-20): Can the work be broken into concrete tasks? (0 = too vague to break down, 20 = clear discrete tasks)
            2. Team fit (0-20): Does the described team have the right skills for this work? (0 = obvious skill gap, 20 = team clearly covers what's needed)
            3. Timeline realism (0-20): Is the timeline plausible given the scope and team size? (0 = clearly unrealistic, 20 = reasonable given the work)
            4. Dependency risk (0-20): Are external dependencies identified and manageable? (0 = unknown or blocking dependencies, 20 = dependencies known and low-risk)
            5. Risk awareness (0-20): Are meaningful risks identified rather than glossed over? (0 = no real risks named, 20 = specific, relevant risks identified)

            Add up the five criteria for the final confidence_score. Do not round up generously — if a criterion is weak, score it low.

            Return ONLY valid JSON, with no markdown formatting and no extra commentary, in exactly this shape:

            {{
              "confidence_score": <integer 0-100>,
              "steps": [
                {{
                  "title": "<specific step title>",
                  "assigned_to": "<role(s) from the team responsible for this step>",
                  "subtasks": [
                    {{"text": "<specific subtask 1>", "role": "<single role from TEAM responsible for this exact subtask>"}},
                    {{"text": "<specific subtask 2>", "role": "<single role from TEAM responsible for this exact subtask>"}}
                  ],
                  "guidance": "<practical how/where guidance, no links>",
                  "risk": "<specific risk for this step, or empty string if none>"
                }}
              ],
              "overall_risks": ["<project-level risk 1>", "<project-level risk 2>"],
              "realism_assessment": "<one sentence assessment of whether the team/timeline seems realistic>"
            }}
            """

            with st.spinner("Generating project plan..."):
                result = call_ai(prompt)

            try:
                parsed = json.loads(result)
                project["scores"]["planning_confidence"] = parsed["confidence_score"]

                project["num_plan_steps"] = len(parsed["steps"])
                record_score_snapshot(project, "Planning updated")

                steps_text = ""
                for i, step in enumerate(parsed["steps"], start=1):
                    steps_text += f"\n**{i}. {step['title']}**\n"
                    if step.get("assigned_to"):
                        colored_owner = colorize_roles(step["assigned_to"])
                        steps_text += f"   - 👤 *Owner:* {colored_owner}\n"
                    for sub in step["subtasks"]:
                        # Support both old (plain string) and new (dict with role) formats, just in case
                        if isinstance(sub, dict):
                            sub_color = get_role_color(sub.get("role", ""))
                            steps_text += f"   - :{sub_color}[{sub['text']}]\n"
                        else:
                            steps_text += f"   - {sub}\n"
                    if step.get("guidance"):
                        steps_text += f"   - *Guidance:* {step['guidance']}\n"
                    if step.get("risk"):
                        steps_text += f"   - ⚠️ *Risk:* {step['risk']}\n"
                risks_text = "\n".join(f"- {r}" for r in parsed["overall_risks"])

                project["planning_output"] = (
                    f"**Task Breakdown (in order):**\n{steps_text}\n\n"
                    f"**Overall Risks:**\n{risks_text}\n\n"
                    f"**Realism Assessment:** {parsed['realism_assessment']}"
                )
                project["last_plan_hash"] = get_plan_inputs_hash(project)
                project["last_plan_inputs"] = {
                    "requirement": project["requirement"],
                    "team": project["team"],
                    "timeline": project["timeline"],
                    "dependencies": project["dependencies"],
                }
            except (json.JSONDecodeError, KeyError):
                project["planning_output"] = result
                st.warning("Got a response, but couldn't parse the score. Showing raw output instead.")

            st.success("Project plan generated!")
            st.rerun()

        if project["planning_output"]:
            st.subheader("Project Plan")
            st.write(project["planning_output"])

with dev_tab:
    st.header("Development Guidance")

    if not project["planning_output"]:
        st.info("Generate a Project Plan first — development guidance works best once there's a plan to build against.")
    else:
        technical_question = st.text_area(
            "Technical question",
            placeholder="Example: What API design should we use for fetching and displaying usage data?"
        )

        if st.button("Generate Development Guidance"):
            prompt = f"""
            You are a senior engineer giving detailed, actionable technical guidance for a software feature.

            Requirement: {project["requirement"]}
            Requirement analysis: {project["requirement_output"]}
            Project plan: {project["planning_output"]}
            Team: {project["team"]}

            Technical question: {technical_question}

            Provide a detailed technical breakdown with 3-6 numbered architecture steps, in the order they should be
            implemented (e.g. data model before API, API before frontend integration).

            For EACH step, provide:
            - A clear, specific title (name the actual component, endpoint, or layer involved)
            - 2-3 concrete implementation details
            - A short illustrative code snippet where it would genuinely help (pseudocode or a real language is fine —
              use Python or JavaScript depending on what fits the step; keep snippets under 10 lines, illustrative only,
              not full production code)

            Also include:
            - 2-3 edge cases or failure modes to watch out for
            - 2-3 security or data-handling considerations if relevant (empty list if truly not relevant)
            - 1-2 open questions that still need a human decision

            Do NOT include specific URLs or links — general guidance only, since exact links may not be accurate.

            Score the development readiness (0-100) by checking these five criteria. Each is worth up to 20 points:

            1. Technical approach clarity (0-20): Is there a specific, actionable technical direction? (0 = no clear approach, 20 = specific approach with reasoning)
            2. Edge case coverage (0-20): Are meaningful edge cases or failure modes addressed? (0 = none considered, 20 = key edge cases identified)
            3. Security/privacy consideration (0-20): Are relevant security or data-handling concerns addressed? (0 = not mentioned, 20 = explicitly addressed if relevant)
            4. Integration clarity (0-20): Is it clear how this fits with existing systems/APIs? (0 = unclear, 20 = clearly explained)
            5. Open question resolution (0-20): How much is still unresolved? (0 = major unknowns remain, 20 = few or no unresolved questions)

            Add up the five criteria for the final readiness_score. Do not round up generously — if a criterion is weak, score it low.

            Return ONLY valid JSON, with no markdown formatting outside string values, and no extra commentary, in exactly this shape:

            {{
              "readiness_score": <integer 0-100>,
              "steps": [
                {{
                  "title": "<specific step title>",
                  "details": ["<detail 1>", "<detail 2>"],
                  "code_snippet": "<short illustrative code, or empty string if not useful for this step>",
                  "language": "<python, javascript, etc, or empty string if no snippet>"
                }}
              ],
              "watch_outs": ["<edge case or failure mode 1>", "<edge case or failure mode 2>"],
              "security_considerations": ["<consideration 1>"],
              "open_questions": ["<open question 1>"]
            }}
            """
            with st.spinner("Generating development guidance..."):
                result = call_ai(prompt)

            try:
                parsed = json.loads(result)
                project["scores"]["development_readiness"] = parsed["readiness_score"]
                record_score_snapshot(project, "Dev guidance updated")

                steps_text = ""
                for i, step in enumerate(parsed["steps"], start=1):
                    steps_text += f"\n**{i}. {step['title']}**\n"
                    for d in step["details"]:
                        steps_text += f"   - {d}\n"
                    if step.get("code_snippet"):
                        lang = step.get("language", "")
                        steps_text += f"\n```{lang}\n{step['code_snippet']}\n```\n"

                watch_outs_text = "\n".join(f"- {w}" for w in parsed["watch_outs"])
                security_text = "\n".join(f"- {s}" for s in parsed["security_considerations"]) or "- None identified"
                questions_text = "\n".join(f"- {q}" for q in parsed["open_questions"])

                project["dev_guidance_output"] = (
                    f"**Technical Approach (in order):**\n{steps_text}\n\n"
                    f"**Watch Out For:**\n{watch_outs_text}\n\n"
                    f"**Security / Data Considerations:**\n{security_text}\n\n"
                    f"**Open Questions:**\n{questions_text}"
                )
            except (json.JSONDecodeError, KeyError):
                project["dev_guidance_output"] = result
                st.warning("Got a response, but couldn't parse the score. Showing raw output instead.")

            st.success("Development guidance generated!")
            st.rerun()

        if project["dev_guidance_output"]:
            st.subheader("Development Guidance")
            st.write(project["dev_guidance_output"])

with log_tab:
    st.header("Change Log")

    if not project["change_log"]:
        st.info("No changes recorded yet. Use 'Log a Change' in the sidebar after editing something.")
    else:
        for i, entry in enumerate(reversed(project["change_log"]), start=1):
            version_number = len(project["change_log"]) - i + 1
            with st.expander(f"Change #{version_number}", expanded=(i == 1)):
                if "impact_summary" in entry:
                    st.markdown(f"**Impact:** {entry['impact_summary']}")
                    st.divider()

                st.markdown("**What changed:**")
                for field, values in entry["changes"].items():
                    diffed = highlight_word_diff(values["before"], values["after"])
                    st.markdown(f"**{field}**")
                    st.markdown(f":gray[Before: {values['before']}]")
                    st.markdown(f"After: {diffed}")
                    st.markdown("")  # small spacing between fields
                    if project["change_log"]:
                        last_entry = project["change_log"][-1]
                    


