"""Generate CLI command."""

import logging
import os
import sys

import click

from src.config import (
    DEFAULT_MODEL,
    MAX_GAP_QUESTIONS,
    DEFAULT_OUTPUT_FORMAT,
)
from src.llm_client import (
    is_ollama_model,
    get_ollama_model_name,
    get_claude_display_name,
    prepare_ollama,
    resolve_claude_model,
)
from src.models import (
    ResumeContent,
    JDAnalysis,
    GapAnalysis,
    CompatibilityAssessment,
)
from src.resume_parser import collect_resume_text, validate_resume_content
from src.jd_analyzer import analyze_jd, collect_jd_text
from src.gap_analyzer import analyze_gaps
from src.compatibility_assessor import assess_compatibility, display_assessment
from src.resume_generator import generate_tailored_resume
from src.docx_builder import build_resume, open_file
from src.session import save_session, load_session
from src.profile import (
    load_profile,
    save_profile,
    first_run_setup,
    select_profile_interactive,
    lookup_experience_semantic,
    save_experience,
    check_conflicts,
    resolve_conflicts,
    append_history,
    save_preferences,
    get_preferences,
)
from src.commands.common import (
    validate_api_key,
    select_model_interactive,
    summarize_resume as _summarize_resume,
    summarize_jd as _summarize_jd,
    load_mock_fixture as _load_mock_fixture,
)

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["docx", "pdf", "md", "all"], case_sensitive=False),
    default=None,
    help="Output format (default: docx, or saved preference).",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(),
    default=None,
    help="Output file or directory path (default: output/ folder, or saved preference).",
)
@click.option(
    "--skip-questions",
    is_flag=True,
    default=False,
    help="Skip follow-up questions for a quick run.",
)
@click.option(
    "--skip-assessment",
    is_flag=True,
    default=False,
    help="Skip the compatibility assessment step.",
)
@click.option(
    "--reference",
    "reference_path",
    type=click.Path(exists=True),
    default=None,
    help="Path to a reference resume from someone in a similar role.",
)
@click.option(
    "--resume-session",
    is_flag=True,
    default=False,
    help="Reload resume and JD from the last saved session.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Use mock API responses instead of calling Claude. For testing without spending credits.",
)
@click.option(
    "--model",
    default=None,
    help="LLM model to use. 'claude' for Anthropic API, or 'ollama:<name>' for local Ollama.",
)
@click.pass_context
def generate(
    ctx,
    output_format: str | None,
    output_path: str | None,
    skip_questions: bool,
    skip_assessment: bool,
    reference_path: str | None,
    resume_session: bool,
    dry_run: bool,
    model: str | None,
):
    """Generate a tailored resume from your resume and a job description."""
    pname = ctx.obj["profile_name"]

    # Step 1: Model selection — first thing, before any LLM calls
    if dry_run:
        model = model or DEFAULT_MODEL
        click.echo(
            click.style("[DRY RUN] Using mock API responses.", fg="yellow", bold=True)
        )
    elif model is None:
        # Load profile only to check saved model preference (no LLM calls)
        existing_prof = load_profile(pname)
        prefs = get_preferences(existing_prof) if existing_prof else {}
        model = select_model_interactive(prefs)

    # Validate/prepare the chosen backend before any LLM calls
    if not dry_run:
        if is_ollama_model(model):
            click.echo(f"Using local Ollama model: {get_ollama_model_name(model)}")
            try:
                prepare_ollama(model)
            except (ConnectionError, RuntimeError) as e:
                click.echo(f"Error: {e}")
                sys.exit(1)
        else:
            validate_api_key()
            try:
                resolve_claude_model(model)
            except ValueError as e:
                click.echo(f"Error: {e}")
                sys.exit(1)

    # Load or create profile (now uses the selected model for any LLM calls)
    pname, prof = select_profile_interactive(pname)
    ctx.obj["profile_name"] = pname  # update in case user picked a different profile
    if not prof:
        prof = first_run_setup(pname, model=model)

    # Save model preference if different from what's stored
    if not dry_run:
        prefs = get_preferences(prof)
        if prefs.get("model") != model:
            prof.preferences["model"] = model
            save_profile(prof, pname)

    # Apply saved preferences as defaults (flags override)
    prefs = get_preferences(prof)
    if output_format is None:
        output_format = prefs.get("format", DEFAULT_OUTPUT_FORMAT)
    if output_path is None:
        output_path = prefs.get("output_path")

    # Periodic experience bank review — prompt after every 10 applications
    # (Baseline resume refresh is handled by Step 3b's "anything new?" prompt,
    # so we only review the experience bank here to keep/update/delete entries.)
    eb_changed = False
    if not dry_run and prof.experience_bank and prof.applications_since_review >= 10:
        click.echo(
            click.style(
                f"\nYou've generated {prof.applications_since_review} resumes since "
                "your last review. Time for a quick experience bank check.",
                fg="yellow",
                bold=True,
            )
        )
        if click.confirm("Review your saved answers?", default=False):
            keys_to_delete: list[str] = []
            for skill, answer in list(prof.experience_bank.items()):
                preview = answer[:80] + "..." if len(answer) > 80 else answer
                click.echo(f"\n  {skill}: {preview}")
                action = (
                    click.prompt(
                        "    [Enter] Keep  |  [u] Update  |  [d] Delete",
                        default="",
                        show_default=False,
                    )
                    .strip()
                    .lower()
                )
                if action == "d":
                    keys_to_delete.append(skill)
                    click.echo("    Deleted.")
                elif action == "u":
                    new_answer = click.prompt(
                        "    New answer",
                        default="",
                        show_default=False,
                    ).strip()
                    if new_answer:
                        prof.experience_bank[skill] = new_answer
                        click.echo("    Updated.")
                        eb_changed = True
            for key in keys_to_delete:
                del prof.experience_bank[key]
                eb_changed = True
            if eb_changed:
                prof.applications_since_review = 0
                save_profile(prof, pname)
                click.echo("Experience bank updated.")

                # Conflict check after user edits
                click.echo("Checking for conflicts...")
                conflicts = check_conflicts(prof, model=model)
                if conflicts:
                    resolve_conflicts(prof, conflicts, pname)
                else:
                    click.echo(click.style("  No conflicts found.", fg="green"))
            else:
                prof.applications_since_review = 0
                save_profile(prof, pname)

    click.echo("\n" + "=" * 50)
    click.echo("  Resume Tailor - AI-Powered Resume Generator")
    click.echo("=" * 50)

    # Use profile resume if available
    identity = prof.identity
    profile_name = identity.name
    has_profile_resume = bool(prof.base_resume)

    # Track optional reference resume
    reference_text = None

    # Try to restore from session
    session = None
    if resume_session:
        session = load_session(pname)
        if session:
            resume_text = session["resume_text"]
            jd_text = session["jd_text"]
            saved_at = session.get("saved_at", "unknown time")
            click.echo(f"\nRestored session from {saved_at}")

            r_summary = _summarize_resume(resume_text)
            name_part = (
                f", name: {r_summary['detected_name']}"
                if r_summary["detected_name"]
                else ""
            )
            click.echo(f"  Resume: {r_summary['word_count']} words{name_part}")
            j_summary = _summarize_jd(jd_text)
            role_part = (
                f", role: {j_summary['detected_title']}"
                if j_summary["detected_title"]
                else ""
            )
            click.echo(f"  JD: {j_summary['word_count']} words{role_part}")

            if not click.confirm("Use this session?", default=True):
                click.echo("Session discarded. Collecting fresh input.\n")
                resume_session = False  # fall through to manual collection
            else:
                click.echo("")
        else:
            click.echo("\nNo saved session found. Collecting fresh input.\n")
            resume_session = False

    if not resume_session:
        # Step 3: Resume Input
        if has_profile_resume:
            resume_text = prof.base_resume
            click.echo(f"\nUsing profile resume for {profile_name}")
            click.echo(
                click.style(
                    "  (Tip: run 'python src/main.py profile' to view or edit your profile)",
                    dim=True,
                )
            )
        else:
            click.echo("\n--- Step 3: Your Resume ---")
            try:
                resume_text = collect_resume_text()
            except (FileNotFoundError, ValueError) as e:
                click.echo(f"Error: {e}")
                sys.exit(1)

            if not resume_text:
                click.echo("Error: No resume text provided.")
                sys.exit(1)

            # Validate that it looks like an actual resume
            while not validate_resume_content(resume_text):
                click.echo(
                    click.style(
                        "\nThis doesn't look like a resume. "
                        "Did you paste the right content?",
                        fg="yellow",
                        bold=True,
                    )
                )
                if not click.confirm("Try again?", default=True):
                    click.echo("Exiting.")
                    sys.exit(0)
                try:
                    resume_text = collect_resume_text()
                except (FileNotFoundError, ValueError) as e:
                    click.echo(f"Error: {e}")
                    sys.exit(1)
                if not resume_text:
                    click.echo("Error: No resume text provided.")
                    sys.exit(1)

            # Show resume summary and confirm
            r_summary = _summarize_resume(resume_text)
            click.echo(f"\n  Words:  {r_summary['word_count']}")
            if r_summary["detected_name"]:
                click.echo(f"  Name:   {r_summary['detected_name']}")
            if r_summary["role_count"]:
                click.echo(f"  Roles:  {r_summary['role_count']} detected")
            if not click.confirm("Is this correct?", default=True):
                click.echo("Please re-run and provide the correct resume.")
                sys.exit(0)

        # Returning user check: anything new since last application?
        if has_profile_resume and not dry_run:
            click.echo("\n--- Returning User Check ---")
            new_input = click.prompt(
                "Anything new since your last application? "
                "New skills, projects, certifications? (Enter to skip)",
                default="",
                show_default=False,
            ).strip()
            if new_input:
                # Update base_resume with new info via enrichment improve (no placeholders)
                click.echo("Updating your baseline resume with new information...")
                try:
                    from src.resume_enricher import improve_resume_with_enrichment
                    from src.models import EnrichmentAnalysis, EnrichmentQuestion

                    enrichment = EnrichmentAnalysis(
                        questions=[
                            EnrichmentQuestion(
                                role="Recent updates",
                                question="What's new since your last application?",
                                category="achievements",
                            )
                        ],
                    )
                    answers = {"What's new since your last application?": new_input}
                    updated = improve_resume_with_enrichment(
                        prof.base_resume, enrichment, answers, model=model
                    )

                    click.echo("\nUpdated resume preview (first 500 chars):")
                    click.echo(updated[:500] + ("..." if len(updated) > 500 else ""))
                    if click.confirm("Save this update to your profile?", default=True):
                        resume_text = updated
                        prof.base_resume = updated
                        save_profile(prof, pname)
                        click.echo("Profile updated.")
                    else:
                        click.echo("Keeping existing resume.")
                except Exception as e:
                    logger.warning("Failed to update resume: %s", e)
                    click.echo(
                        f"Warning: Could not update resume ({e}). Continuing with existing."
                    )

                # Save new info to experience bank and check for conflicts
                save_experience(prof, "recent_updates", new_input, pname)
                click.echo("Checking for conflicts...")
                conflicts = check_conflicts(prof, model=model)
                if conflicts:
                    resolve_conflicts(prof, conflicts, pname)
                else:
                    click.echo(click.style("  No conflicts found.", fg="green"))

        # Step 4: Reference Resume (Optional)
        click.echo("\n--- Step 4: Reference Resume (Optional) ---")
        if reference_path:
            from src.resume_parser import read_resume_from_file

            try:
                reference_text = read_resume_from_file(reference_path)
                click.echo(f"Reference resume loaded from {reference_path}")
            except (FileNotFoundError, ValueError) as e:
                logger.warning("Could not load reference resume: %s", e)
                click.echo(f"Warning: Could not load reference resume ({e}). Skipping.")
        else:
            ref_input = click.prompt(
                "Do you have a reference resume from someone in a similar role? "
                "(file path or Enter to skip)",
                default="",
                show_default=False,
            ).strip()
            if ref_input:
                from src.resume_parser import read_resume_from_file

                try:
                    reference_text = read_resume_from_file(ref_input)
                    r_ref = _summarize_resume(reference_text)
                    click.echo(
                        f"  Reference resume loaded: {r_ref['word_count']} words"
                    )
                except (FileNotFoundError, ValueError) as e:
                    logger.warning("Could not load reference resume: %s", e)
                    click.echo(
                        f"  Warning: Could not load reference resume ({e}). Skipping."
                    )

        # Step 5: JD Input
        click.echo("\n--- Step 5: Target Job Description ---")
        jd_text = collect_jd_text()

        if not jd_text:
            click.echo("Error: No job description provided.")
            sys.exit(1)

        # Show JD summary and confirm
        j_summary = _summarize_jd(jd_text)
        click.echo(f"\n  Words:    {j_summary['word_count']}")
        if j_summary["detected_title"]:
            click.echo(f"  Role:     {j_summary['detected_title']}")
        if j_summary["detected_company"]:
            click.echo(f"  Company:  {j_summary['detected_company']}")
        if not click.confirm("Is this correct?", default=True):
            click.echo("Please re-run and provide the correct job description.")
            sys.exit(0)

        # Auto-save session
        save_session(resume_text, jd_text, profile_name=pname)
        click.echo("\nSession saved. Re-run with --resume-session to skip input.")

    # Step 6: JD Analysis
    click.echo("\n--- Step 6: JD Analysis ---")
    if dry_run:
        click.echo("[DRY RUN] Loading mock JD analysis...")
        jd_analysis = JDAnalysis.from_dict(_load_mock_fixture("mock_jd_analysis.json"))
    else:
        _model_label = (
            get_ollama_model_name(model)
            if is_ollama_model(model)
            else get_claude_display_name(model)
        )
        click.echo(f"Analyzing job description using {_model_label}...")
        try:
            jd_analysis = analyze_jd(
                jd_text, reference_text=reference_text, model=model
            )
        except Exception as e:
            logger.error("JD analysis failed: %s", e)
            click.echo(f"Error analyzing job description: {e}")
            sys.exit(1)

    click.echo(f"Analysis complete. Role: {jd_analysis.job_title or 'N/A'}")
    click.echo(f"Key skills identified: {', '.join(jd_analysis.required_skills[:5])}")
    if jd_analysis.style_insights:
        click.echo(
            f"Reference resume style: {jd_analysis.style_insights.tone or 'analyzed'}"
        )

    # Gap analysis & follow-up questions
    user_additions = ""
    saved_answers: dict | None = None
    if resume_session and session:
        saved_answers = session.get("answers")

    if not skip_questions:
        reuse_answers = False

        # If session has saved answers, offer to reuse them
        if saved_answers:
            click.echo("\n--- Previous Answers Found ---")
            gap_answers_saved = saved_answers.get("gap_answers", [])
            if gap_answers_saved:
                click.echo("\n  Gap question answers:")
                for a in gap_answers_saved:
                    click.echo(f"    - {a}")
            if saved_answers.get("extra_skills"):
                click.echo(f"  Extra skills: {saved_answers['extra_skills']}")
            if saved_answers.get("emphasis"):
                click.echo(f"  Emphasis: {saved_answers['emphasis']}")
            if saved_answers.get("job_title"):
                click.echo(f"  Job title: {saved_answers['job_title']}")

            reuse_answers = click.confirm("Use these answers again?", default=True)

        if reuse_answers and saved_answers:
            # Rebuild user_additions from saved answers
            gap_answers = saved_answers.get("gap_answers", [])
            extra_skills = saved_answers.get("extra_skills", "")
            emphasis = saved_answers.get("emphasis", "")
            job_title = saved_answers.get("job_title", "")
        else:
            # Run gap analysis and ask questions fresh
            click.echo("\n--- Step 7: Gap Analysis & Follow-Up Questions ---")
            if dry_run:
                click.echo("[DRY RUN] Loading mock gap analysis...")
                gap_result = GapAnalysis.from_dict(
                    _load_mock_fixture("mock_gap_analysis.json")
                )
            else:
                click.echo("Comparing your resume against the job requirements...")
                try:
                    gap_result = analyze_gaps(resume_text, jd_analysis, model=model)
                except Exception as e:
                    logger.warning("Gap analysis failed: %s", e)
                    click.echo(
                        f"Warning: Gap analysis failed ({e}). Continuing without it."
                    )
                    gap_result = GapAnalysis()

            # Show strengths
            if gap_result.strengths:
                click.echo("\nYour resume already matches well on:")
                for s in gap_result.strengths:
                    click.echo(f"  - {s}")

            # Ask gap questions (with semantic experience bank matching)
            gap_answers: list[str] = []
            new_answers_saved = False
            if gap_result.gaps:
                from src.conversation import conversational_qa

                # Batch semantic matching: 1 LLM call to match all gaps
                # against the full experience bank
                valid_gaps = [g for g in gap_result.gaps if g.question.strip()]
                gap_skills = [g.skill for g in valid_gaps]
                if prof.experience_bank and gap_skills and not dry_run:
                    click.echo("Checking experience bank for relevant answers...")
                    semantic_matches = lookup_experience_semantic(
                        prof, gap_skills, model=model
                    )
                else:
                    semantic_matches = {s: [] for s in gap_skills}

                click.echo(
                    "\nI have a few questions based on gaps between your resume and the JD."
                    "\nAnswer each one, or press Enter to skip.\n"
                )
                seen_questions: set[str] = set()
                question_count = 0
                for gap in valid_gaps:
                    # Safety: never ask more than MAX_GAP_QUESTIONS
                    if question_count >= MAX_GAP_QUESTIONS:
                        logger.debug(
                            "Reached max gap questions limit (%d), stopping",
                            MAX_GAP_QUESTIONS,
                        )
                        break
                    # Deduplicate: skip if we already asked this question
                    q_key = gap.question.strip().lower()
                    if q_key in seen_questions:
                        logger.debug("Skipping duplicate question: %s", gap.question)
                        continue
                    seen_questions.add(q_key)
                    question_count += 1
                    skill = gap.skill

                    # Check semantic matches from batch lookup
                    matched_entries = semantic_matches.get(skill, [])
                    if matched_entries:
                        # Combine all matched answers for display
                        combined = " | ".join(
                            f"{k}: {v[:70]}..." if len(v) > 70 else f"{k}: {v}"
                            for k, v in matched_entries
                        )
                        click.echo(f"\n  {skill}:")
                        click.echo(f'    Saved answer: "{combined[:150]}"')
                        click.echo(
                            "    [Enter] Use this answer  |  [u] Update  |  [s] Skip this skill"
                        )
                        choice = (
                            click.prompt(
                                "   ",
                                default="",
                                show_default=False,
                            )
                            .strip()
                            .lower()
                        )
                        if choice == "s":
                            pass  # skip — don't include this skill
                        elif choice == "u":
                            answer = conversational_qa(
                                context_type="skill gap",
                                context_description=f"{skill}: {gap.question}",
                                initial_question=gap.question,
                                model=model,
                            )
                            if answer:
                                gap_answers.append(f"{skill}: {answer}")
                                save_experience(prof, skill, answer, pname)
                                new_answers_saved = True
                        else:
                            # Include all matched answers
                            for _k, v in matched_entries:
                                gap_answers.append(f"{skill}: {v}")
                    else:
                        click.echo(f"\n  {skill}:")
                        answer = conversational_qa(
                            context_type="skill gap",
                            context_description=f"{skill}: {gap.question}",
                            initial_question=gap.question,
                            model=model,
                        )
                        if answer:
                            gap_answers.append(f"{skill}: {answer}")
                            save_experience(prof, skill, answer, pname)
                            new_answers_saved = True

                # Conflict check after all new gap answers are saved
                if new_answers_saved and not dry_run:
                    click.echo("\nChecking for conflicts in your profile...")
                    conflicts = check_conflicts(prof, model=model)
                    if conflicts:
                        resolve_conflicts(prof, conflicts, pname)
                    else:
                        click.echo(click.style("  No conflicts found.", fg="green"))

            # Generic follow-up questions
            click.echo("\n--- Additional Questions ---")
            extra_skills = click.prompt(
                "Any other skills or certifications to add?",
                default="",
                show_default=False,
            )
            emphasis = click.prompt(
                "What aspects of your experience do you want to emphasize?",
                default="",
                show_default=False,
            )
            job_title = click.prompt(
                "Preferred job title for the resume header? (Enter to use JD title)",
                default="",
                show_default=False,
            )

        # Save answers to session
        answers_data = {
            "gap_answers": gap_answers,
            "extra_skills": extra_skills.strip(),
            "emphasis": emphasis.strip(),
            "job_title": job_title.strip(),
        }
        save_session(resume_text, jd_text, answers=answers_data, profile_name=pname)

        # Build user_additions string
        additions: list[str] = []
        if gap_answers:
            additions.append(
                "Additional experience from candidate:\n"
                + "\n".join(f"- {a}" for a in gap_answers)
            )
        if extra_skills.strip():
            additions.append(
                f"Additional skills/certifications: {extra_skills.strip()}"
            )
        if emphasis.strip():
            additions.append(f"Candidate wants to emphasize: {emphasis.strip()}")
        if job_title.strip():
            additions.append(f"Preferred job title for header: {job_title.strip()}")

        if additions:
            user_additions = "Additional Context from Candidate:\n" + "\n".join(
                additions
            )

    # Compatibility assessment step
    match_score: int | None = None
    if not skip_assessment:
        click.echo("\n--- Step 8: Compatibility Assessment ---")
        if dry_run:
            click.echo("[DRY RUN] Loading mock compatibility assessment...")
            assessment = CompatibilityAssessment.from_dict(
                _load_mock_fixture("mock_compatibility.json")
            )
        else:
            click.echo("Evaluating match between your resume and the job...")
            try:
                assessment = assess_compatibility(
                    resume_text,
                    jd_analysis,
                    model=model,
                    user_additions=user_additions,
                )
            except Exception as e:
                logger.warning("Compatibility assessment failed: %s", e)
                click.echo(
                    f"Warning: Compatibility assessment failed ({e}). Continuing."
                )
                assessment = None

        if assessment:
            match_score = assessment.match_score
            display_assessment(assessment)

            if not assessment.proceed:
                click.echo(
                    click.style(
                        "  Warning: Your match score is below 30%. "
                        "This may be a poor fit.",
                        fg="bright_red",
                        bold=True,
                    )
                )
                if not click.confirm("Do you still want to proceed?", default=False):
                    click.echo("Exiting. Try a different job description.")
                    sys.exit(0)
            else:
                if not click.confirm(
                    f"Match score: {assessment.match_score}%. "
                    "Proceed with generation?",
                    default=True,
                ):
                    click.echo("Exiting.")
                    sys.exit(0)

    # Collect writing preferences upfront if not already saved
    if not dry_run and not prof.writing_preferences:
        click.echo("\n--- Writing Preferences ---")
        click.echo("These are saved to your profile so you only answer once.\n")
        tone = click.prompt(
            "  Preferred tone? (e.g. professional, conversational, technical)",
            default="professional",
            show_default=True,
        ).strip()
        if tone:
            prof.writing_preferences["tone"] = tone
        length = click.prompt(
            "  Bullet point style? (e.g. concise, detailed, quantified)",
            default="concise and quantified",
            show_default=True,
        ).strip()
        if length:
            prof.writing_preferences["bullet_length"] = length
        general = click.prompt(
            "  Any other writing preferences? (Enter to skip)",
            default="",
            show_default=False,
        ).strip()
        if general:
            prof.writing_preferences["general"] = general
        if prof.writing_preferences:
            save_profile(prof, pname)
            click.echo(click.style("  Preferences saved.", fg="green"))

    # Step 9: Generate Tailored Resume
    click.echo("\n--- Step 9: Generating Tailored Resume ---")
    if dry_run:
        click.echo("[DRY RUN] Loading mock resume generation...")
        resume_data = ResumeContent.from_dict(
            _load_mock_fixture("mock_resume_generation.json")
        )
    else:
        click.echo("Generating tailored resume content...")
        try:
            resume_data = generate_tailored_resume(
                resume_text,
                jd_analysis,
                user_additions,
                model=model,
                writing_preferences=prof.writing_preferences or None,
            )
        except Exception as e:
            logger.error("Resume generation failed: %s", e)
            click.echo(f"Error generating resume: {e}")

            # Fallback: if using Ollama, offer to switch to Claude
            if is_ollama_model(model):
                if click.confirm(
                    "Local model is having issues. "
                    "Would you like to switch to Claude API?",
                    default=True,
                ):
                    validate_api_key()
                    model = "claude"
                    click.echo("Retrying with Claude API...")
                    try:
                        resume_data = generate_tailored_resume(
                            resume_text,
                            jd_analysis,
                            user_additions,
                            model=model,
                            writing_preferences=prof.writing_preferences or None,
                        )
                    except Exception as e2:
                        logger.error("Claude fallback also failed: %s", e2)
                        click.echo(f"Error generating resume with Claude: {e2}")
                        sys.exit(1)
                else:
                    sys.exit(1)
            else:
                sys.exit(1)

    click.echo("Resume content generated.")

    # Step 9b: Preview generated resume
    # Writing preferences are collected upfront (before generation) or from
    # profile. No section-by-section review loop — just show what was generated.
    if not dry_run:
        click.echo("\n--- Generated Resume Preview ---")

        if resume_data.summary:
            click.echo(click.style("\n  Summary:", bold=True))
            click.echo(f"    {resume_data.summary}")

        for exp in resume_data.experience:
            click.echo(click.style(f"\n  {exp.title} — {exp.company}", bold=True))
            click.echo(f"    {exp.dates}")
            for bullet in exp.bullets:
                click.echo(f"    - {bullet}")

        if resume_data.skills:
            click.echo(click.style("\n  Skills:", bold=True))
            for skill in resume_data.skills:
                click.echo(f"    {skill}")

        click.echo("")

    # Step 10: Output
    formats = [output_format.lower()]
    format_label = "all formats" if output_format == "all" else output_format.upper()
    click.echo(f"\n--- Step 10: Building {format_label} ---")

    default_output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "output")
    try:
        filepaths = build_resume(
            resume_data,
            output_dir=default_output_dir,
            output_path=output_path,
            formats=formats,
            identity=identity,
            jd_analysis=jd_analysis,
        )
    except RuntimeError as e:
        click.echo(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error("Output build failed: %s", e)
        click.echo(f"Error building output: {e}")
        sys.exit(1)

    click.echo("\nDone! Your tailored resume has been saved to:")
    for fp in filepaths:
        click.echo(f"  {fp}")

    # Offer PDF conversion if not already generated
    if "pdf" not in formats and any(fp.endswith(".docx") for fp in filepaths):
        if click.confirm("Also save as PDF?", default=False):
            from src.docx_builder import _convert_docx_to_pdf

            for fp in filepaths:
                if fp.endswith(".docx"):
                    pdf_path = fp.rsplit(".", 1)[0] + ".pdf"
                    try:
                        _convert_docx_to_pdf(fp, pdf_path)
                        click.echo(f"  {pdf_path}")
                        filepaths.append(pdf_path)
                    except RuntimeError as e:
                        click.echo(f"PDF conversion failed: {e}")
                    break

    # Save to application history and increment review counter
    company = jd_analysis.company
    role = jd_analysis.job_title
    for fp in filepaths:
        append_history(prof, company, role, match_score, fp, pname)
    prof.applications_since_review += 1
    save_profile(prof, pname)

    # Save preferences on first successful run (or update if flags were explicit)
    if not prefs.get("format"):
        save_preferences(prof, output_format, output_path, pname)

    # Offer to open the file(s) — skip in Docker (no GUI available)
    if not os.path.exists("/.dockerenv"):
        if click.confirm("\nOpen file?", default=False):
            for fp in filepaths:
                open_file(fp)
