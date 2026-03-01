"""
Processing Pipeline - Orchestrates the end-to-end resume processing workflow.
Watches the inbox folder, processes new resumes, and triggers scoring.
"""

import os
import sys
import time
import shutil
import traceback
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add project directory to path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from config_loader import CONFIG
from logger_config import setup_logging

logger = setup_logging()

from database import (
    create_candidate, update_candidate, update_candidate_status,
    check_duplicate, save_functional_score, log_processing
)
from resume_parser import (
    extract_text_from_file, parse_resume, determine_role_routing,
    get_matching_functional_areas
)
from scoring_engine import score_candidate, generate_interview_questions
from notifications import send_notification, send_error_notification

# Setup folders
INBOX = os.path.join(PROJECT_DIR, CONFIG['inbox_folder'])
PROCESSED = os.path.join(PROJECT_DIR, CONFIG['processed_folder'])
FAILED = os.path.join(PROJECT_DIR, CONFIG['failed_folder'])

for folder in [INBOX, PROCESSED, FAILED]:
    os.makedirs(folder, exist_ok=True)

VALID_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt'}


def process_resume(filepath):
    """Process a single resume through the full pipeline."""
    filename = os.path.basename(filepath)
    logger.info("")
    logger.info("=" * 60)
    logger.info("Processing: %s", filename)
    logger.info("=" * 60)

    candidate_id = None

    try:
        # --- Step 1: Extract Text ---
        logger.info("  [1/5] Extracting text from %s...", filename)
        resume_text = extract_text_from_file(filepath)

        if not resume_text or len(resume_text.strip()) < 100:
            logger.error("  [ERROR] Resume text too short or empty. Skipping.")
            _move_to_failed(filepath, "Empty or unreadable file")
            return

        # --- Step 2: Check for Duplicates ---
        logger.info("  [2/5] Checking for duplicates...")
        if check_duplicate(filename, resume_text):
            logger.info("  [SKIP] Duplicate resume detected. Skipping.")
            _move_to_failed(filepath, "Duplicate resume")
            return

        # --- Step 3: Parse Resume ---
        logger.info("  [3/5] Parsing resume with Claude API...")
        parsed_profile = parse_resume(resume_text)

        candidate_name = parsed_profile.get('name', 'Unknown')
        ami_years = parsed_profile.get('total_ami_years', 0)
        role_routing = determine_role_routing(ami_years)

        logger.info("         Name: %s", candidate_name)
        logger.info("         AMI Years: %s", ami_years)
        logger.info("         Role Routing: %s", role_routing)

        # Create candidate in database
        candidate_id = create_candidate(
            name=candidate_name,
            resume_filename=filename,
            resume_text=resume_text,
            email=parsed_profile.get('email'),
            phone=parsed_profile.get('phone'),
            linkedin_url=parsed_profile.get('linkedin_url')
        )

        update_candidate(candidate_id,
                         parsed_profile=parsed_profile,
                         total_ami_years=ami_years,
                         role_routing=role_routing)

        log_processing(candidate_id, 'parse', 'success', f'Parsed: {candidate_name}, {ami_years} AMI years')

        # --- Step 4: Score Against Matching Functional Areas ---
        logger.info("  [4/5] Scoring candidate...")

        # Check if eliminated at routing level
        if role_routing == "eliminated":
            logger.info("         ELIMINATED: Less than 3 years AMI experience (%s years)", ami_years)
            update_candidate_status(candidate_id, 'eliminated_pending_review', 'system',
                                    f'Eliminated: {ami_years} AMI years (minimum 3 required)')

            # Still save a score record for each potential functional area
            matching_areas = get_matching_functional_areas(parsed_profile)
            if not matching_areas:
                matching_areas = ['Business Integration']  # Default for tracking

            for area in matching_areas:
                save_functional_score(
                    candidate_id=candidate_id,
                    functional_area=area,
                    gate_results={
                        'gate1_pass': True,
                        'gate1_reason': 'Has some AMI experience',
                        'gate2_pass': False,
                        'gate2_reason': f'Only {ami_years} years AMI experience (minimum 3 required)',
                        'gates_passed': False
                    },
                    dimension_scores=None,
                    weighted_score=0,
                    tier='ELIMINATED',
                    scoring_narrative=f'Candidate has {ami_years} years of AMI experience, which is below the 3-year minimum for the Senior role.',
                    phone_screen_questions=None
                )

            log_processing(candidate_id, 'score', 'eliminated', f'AMI years below minimum: {ami_years}')
            _move_to_processed(filepath)
            logger.info("  [DONE] %s — ELIMINATED (insufficient AMI years)", candidate_name)
            return

        # Get matching functional areas
        matching_areas = get_matching_functional_areas(parsed_profile)

        if not matching_areas:
            logger.info("         No matching functional areas identified. Scoring against all areas.")
            matching_areas = [
                'Strategy & Business Case', 'Business Integration',
                'System Integration', 'Field Deployment Management', 'AMI Operations'
            ]

        logger.info("         Matching functional areas: %s", ', '.join(matching_areas))

        highest_tier = 'ELIMINATED'
        tier_priority = {'HIGH': 4, 'MEDIUM': 3, 'LOW': 2, 'ELIMINATED': 1}
        all_scores = []

        for area in matching_areas:
            logger.info("         Scoring for: %s...", area)

            try:
                score_result = score_candidate(parsed_profile, area, ami_years, role_routing)

                tier = score_result.get('tier', 'ELIMINATED')
                weighted_score = score_result.get('weighted_score', 0)
                scoring_narrative = score_result.get('scoring_narrative', '')

                logger.info("           -> %s: %s (%.2f)", area, tier, weighted_score)

                # Generate interview questions if not eliminated
                questions = None
                if tier != 'ELIMINATED':
                    logger.info("           -> Generating phone screen questions...")
                    questions = generate_interview_questions(
                        parsed_profile, area, tier, scoring_narrative
                    )

                # Save to database
                save_functional_score(
                    candidate_id=candidate_id,
                    functional_area=area,
                    gate_results={
                        'gate1_pass': score_result.get('gate1_pass'),
                        'gate1_reason': score_result.get('gate1_reason'),
                        'gate2_pass': score_result.get('gate2_pass'),
                        'gate2_reason': score_result.get('gate2_reason'),
                        'gate3_pass': score_result.get('gate3_pass'),
                        'gate3_reason': score_result.get('gate3_reason'),
                        'gates_passed': score_result.get('gates_passed')
                    },
                    dimension_scores=score_result.get('dimension_scores'),
                    weighted_score=weighted_score,
                    tier=tier,
                    scoring_narrative=scoring_narrative,
                    manager_stretch_flag=score_result.get('manager_stretch_flag', False),
                    manager_stretch_narrative=score_result.get('manager_stretch_narrative'),
                    phone_screen_questions=questions
                )

                all_scores.append({
                    'area': area,
                    'score': weighted_score,
                    'tier': tier
                })

                if tier_priority.get(tier, 0) > tier_priority.get(highest_tier, 0):
                    highest_tier = tier

            except Exception as e:
                logger.error("           [ERROR] Scoring failed for %s: %s", area, e)
                log_processing(candidate_id, 'score', 'error', f'{area}: {str(e)}')

        # --- Step 5: Update Status & Notify ---
        logger.info("  [5/5] Finalizing...")

        if highest_tier == 'ELIMINATED':
            new_status = 'eliminated_pending_review'
        else:
            new_status = f'scored_{highest_tier.lower()}'

        update_candidate_status(candidate_id, new_status, 'system',
                                f'Highest tier: {highest_tier}')

        # Send notification
        if highest_tier != 'ELIMINATED':
            send_notification(candidate_name, highest_tier, all_scores, role_routing)

        _move_to_processed(filepath)

        log_processing(candidate_id, 'complete', 'success',
                        f'Highest tier: {highest_tier}, Areas scored: {len(all_scores)}')

        logger.info("  [DONE] %s — %s", candidate_name, highest_tier)
        scores_summary = ', '.join([f"{s['area']}: {s['tier']} ({s['score']:.2f})" for s in all_scores])
        logger.info("         Scores: %s", scores_summary)

    except Exception as e:
        logger.error("  [ERROR] Failed to process %s: %s", filename, e)
        logger.debug(traceback.format_exc())
        if candidate_id:
            update_candidate_status(candidate_id, 'error', 'system', str(e))
            log_processing(candidate_id, 'pipeline', 'error', str(e))
        _move_to_failed(filepath, str(e))

        # Send error notification email
        try:
            send_error_notification("Resume Processing Failed", traceback.format_exc(), filename)
        except Exception:
            pass  # Don't let notification failure mask the original error


def _move_to_processed(filepath):
    """Move a processed file to the processed folder."""
    try:
        dest = os.path.join(PROCESSED, os.path.basename(filepath))
        # Handle filename conflicts
        if os.path.exists(dest):
            base, ext = os.path.splitext(os.path.basename(filepath))
            counter = 1
            while os.path.exists(dest):
                dest = os.path.join(PROCESSED, f"{base}_{counter}{ext}")
                counter += 1
        shutil.move(filepath, dest)
    except Exception as e:
        logger.warning("  [WARN] Could not move file to processed: %s", e)


def _move_to_failed(filepath, reason="Unknown"):
    """Move a failed file to the failed folder."""
    try:
        dest = os.path.join(FAILED, os.path.basename(filepath))
        if os.path.exists(dest):
            base, ext = os.path.splitext(os.path.basename(filepath))
            counter = 1
            while os.path.exists(dest):
                dest = os.path.join(FAILED, f"{base}_{counter}{ext}")
                counter += 1
        shutil.move(filepath, dest)
        # Write reason file
        reason_file = dest + ".reason.txt"
        with open(reason_file, 'w') as f:
            f.write(reason)
    except Exception as e:
        logger.warning("  [WARN] Could not move file to failed: %s", e)


def _get_retry_count(reason_file_path):
    """Read the retry count from a reason file. Returns 0 if not found."""
    try:
        if os.path.exists(reason_file_path):
            with open(reason_file_path, 'r') as f:
                content = f.read()
            for line in content.split('\n'):
                if line.startswith('RETRIES:'):
                    return int(line.split(':')[1].strip())
    except Exception:
        pass
    return 0


def _set_retry_count(reason_file_path, count, original_reason):
    """Update the retry count in a reason file."""
    try:
        with open(reason_file_path, 'w') as f:
            f.write(f"{original_reason}\nRETRIES:{count}")
    except Exception:
        pass


def retry_failed_resumes():
    """Check the Failed folder for resumes eligible for retry and move them back to inbox."""
    max_retries = CONFIG.get('failed_max_retries', 3)

    for filename in os.listdir(FAILED):
        filepath = os.path.join(FAILED, filename)

        # Skip reason files and non-resume files
        if filename.endswith('.reason.txt') or not os.path.isfile(filepath):
            continue
        ext = Path(filepath).suffix.lower()
        if ext not in VALID_EXTENSIONS:
            continue

        reason_file = filepath + ".reason.txt"

        # Skip duplicates — they will always be duplicates
        if os.path.exists(reason_file):
            with open(reason_file, 'r') as f:
                reason_text = f.read()
            if 'Duplicate resume' in reason_text:
                continue
            original_reason = reason_text.split('\n')[0]
        else:
            original_reason = "Unknown"

        retry_count = _get_retry_count(reason_file)

        if retry_count >= max_retries:
            continue  # Max retries exceeded

        # Move back to inbox for reprocessing
        logger.info("  [RETRY] Moving %s back to inbox (attempt %d/%d)", filename, retry_count + 1, max_retries)
        try:
            dest = os.path.join(INBOX, filename)
            if os.path.exists(dest):
                base, ext_str = os.path.splitext(filename)
                dest = os.path.join(INBOX, f"{base}_retry{retry_count + 1}{ext_str}")
            shutil.move(filepath, dest)
            _set_retry_count(reason_file, retry_count + 1, original_reason)
        except Exception as e:
            logger.warning("  [RETRY] Failed to move %s: %s", filename, e)


class ResumeHandler(FileSystemEventHandler):
    """Watches the inbox folder for new resume files."""

    def __init__(self):
        self.processing = set()

    def on_created(self, event):
        if event.is_directory:
            return
        filepath = event.src_path
        ext = Path(filepath).suffix.lower()
        if ext not in VALID_EXTENSIONS:
            return
        if filepath in self.processing:
            return

        # Wait for file to finish writing (longer for OneDrive-synced folders)
        time.sleep(3)

        # Verify file still exists (may have been moved by a prior event)
        if not os.path.exists(filepath):
            return

        self.processing.add(filepath)
        try:
            process_resume(filepath)
        finally:
            self.processing.discard(filepath)


def process_existing_files():
    """Process any files already in the inbox folder."""
    for filename in os.listdir(INBOX):
        filepath = os.path.join(INBOX, filename)
        if os.path.isfile(filepath):
            ext = Path(filepath).suffix.lower()
            if ext in VALID_EXTENSIONS:
                process_resume(filepath)


def main():
    """Main entry point - start watching for resumes."""
    api_configured = not CONFIG['anthropic_api_key'].startswith('YOUR_') and not CONFIG['anthropic_api_key'].startswith('SET_IN')
    gmail_configured = not CONFIG['gmail_address'].startswith('YOUR_') and not CONFIG['gmail_address'].startswith('SET_IN')

    logger.info("=" * 60)
    logger.info("  AMI Recruiting Automation — Processing Pipeline")
    logger.info("=" * 60)
    logger.info("  Inbox folder:     %s", INBOX)
    logger.info("  Processed folder: %s", PROCESSED)
    logger.info("  Failed folder:    %s", FAILED)
    logger.info("  Model:            %s", CONFIG['model'])
    logger.info("  API Key:          %s", 'Configured' if api_configured else 'NOT CONFIGURED')
    logger.info("  Gmail:            %s", 'Configured' if gmail_configured else 'NOT CONFIGURED')
    logger.info("=" * 60)

    if not api_configured:
        logger.error("\n  [ERROR] Anthropic API key not configured!")
        logger.error("  Edit config.yaml or .env file and add your API key.")
        logger.error("  Get one at: https://console.anthropic.com")
        sys.exit(1)

    # Process any existing files first
    logger.info("\nChecking for existing files in inbox...")
    process_existing_files()

    # Start watching for new files
    logger.info("Watching for new resumes in: %s", INBOX)
    logger.info("Drop PDF, DOCX, or TXT files into the inbox folder to process them.")
    logger.info("Press Ctrl+C to stop.\n")

    event_handler = ResumeHandler()
    observer = Observer()
    observer.schedule(event_handler, INBOX, recursive=False)
    observer.start()

    try:
        retry_interval = CONFIG.get('failed_retry_interval_minutes', 60) * 60
        last_retry_check = time.time()
        while True:
            time.sleep(1)
            # Periodically retry failed resumes
            now = time.time()
            if now - last_retry_check > retry_interval:
                retry_failed_resumes()
                last_retry_check = now
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
