# AMI Recruiting Automation

A system that automatically screens AMI consulting resumes, scores candidates against five functional area rubrics, generates dynamic phone screen questions, and provides a dashboard to manage your recruiting pipeline.

---

## Quick Start (5 minutes)

### Step 1: Install Python

If you don't already have Python installed:

1. Go to **https://www.python.org/downloads/**
2. Click the big yellow **"Download Python 3.x.x"** button
3. Run the installer
4. **CRITICAL:** Check the box that says **"Add Python to PATH"** at the bottom of the installer
5. Click "Install Now"
6. When it finishes, close the installer

### Step 2: Run Setup

1. Open the `ami-recruiter` folder
2. **Double-click `setup.bat`**
3. Wait for it to finish installing packages (about 1 minute)
4. You should see "Setup Complete!"

### Step 3: Get Your Anthropic API Key

1. Go to **https://console.anthropic.com**
2. Create an account (use any email)
3. Once logged in, click **"API Keys"** in the left sidebar
4. Click **"Create Key"**
5. Give it a name like "AMI Recruiter"
6. **Copy the key** (it starts with `sk-ant-...`)
7. Open **`config.yaml`** in Notepad
8. Replace `YOUR_API_KEY_HERE` with your key
9. Save the file

### Step 4: Set Up Gmail Notifications (Optional)

1. Go to **https://myaccount.google.com/security**
2. Make sure **2-Step Verification** is turned ON
3. Go to **https://myaccount.google.com/apppasswords**
4. Select "Mail" and your device, then click "Generate"
5. Copy the 16-character password
6. In **`config.yaml`**, update:
   - `gmail_address`: your Gmail address
   - `gmail_app_password`: the 16-character app password
   - `notification_email`: where to receive alerts (can be the same Gmail)

### Step 5: Launch the System

1. **Double-click `start.bat`**
2. The dashboard will open in your browser at **http://localhost:8501**
3. The processing pipeline will start watching for new resumes

---

## How to Use

### Processing Resumes

1. Download a resume from a LinkedIn DM (PDF or Word)
2. Drop the file into the **`AMI_Candidates_Inbox`** folder
3. The system automatically:
   - Extracts text from the resume
   - Parses it into a structured profile
   - Scores it against all matching functional area rubrics
   - Generates phone screen questions
   - Sends you an email notification
4. The file moves to **`AMI_Candidates_Processed`** when done

For plain-text resumes (someone pasted their experience in a DM):
1. Copy the text
2. Open Notepad, paste it in, and save as a `.txt` file
3. Drop the `.txt` file into the inbox folder

### Using the Dashboard

**Pipeline Overview:** See all candidates with their tiers, scores, and status. Filter by status or functional area.

**Candidate Details:** Click into any candidate to see:
- Full scoring breakdown by functional area
- Gate pass/fail results with explanations
- Dimension-by-dimension scores with reasoning
- Phone screen questions (dynamically generated)
- Manager stretch flags where applicable
- Status history and notes

**Eliminated Review:** Review candidates the system eliminated. You can:
- **Confirm** the elimination (you agree)
- **Override** to Low/Medium/High (you disagree)
- **Flag a rubric issue** with feedback on what the rubric got wrong

**Rubric Feedback:** See accumulated feedback from your elimination reviews. Use this to identify patterns for rubric updates.

**Handoff Email Generator:** For candidates who pass the phone screen, generates a pre-written email with the correct job posting link. Copy/paste into your corporate email.

### Managing Candidate Status

On the Candidate Details page, update status through the pipeline:

| Status | When to Use |
|--------|------------|
| Phone Screen Scheduled | You've set up a phone screen |
| Passed — Senior | Candidate passed screen, route to Senior req |
| Passed — Manager | Candidate passed screen, route to Manager req |
| Phone Screen — Rejected | Candidate did not pass screen |
| Handed Off | You've sent the handoff email |

---

## Functional Areas & Rubrics

The system evaluates candidates against five AMI functional areas:

1. **Strategy & Business Case** — Pre-implementation: strategy, business case, cost-benefit analysis, procurement
2. **Business Integration** — BPD, project management, change management
3. **System Integration** — Architecture, technical design, development, testing, cutover
4. **Field Deployment Management** — Meter deployment strategy, MIC vendor management, logistics
5. **AMI Operations** — Head-end and MDMS operations, VEE management, production support

Candidates are scored against ALL areas where they show relevant experience.

### Role Routing

| AMI Years | Route |
|-----------|-------|
| < 3 years | Eliminated |
| 3-5 years | Senior only |
| 6-7 years | Senior + Manager stretch flag |
| 7+ years | Manager only |

### Tiers

| Tier | Score | Meaning |
|------|-------|---------|
| HIGH | 4.0 - 5.0 | Strong candidate, priority pursuit |
| MEDIUM | 3.0 - 3.99 | Meets threshold, probe gaps in phone screen |
| LOW | 2.0 - 2.99 | Barely qualifies, significant concerns |
| ELIMINATED | Failed gate or < 2.0 | Does not meet minimum requirements |

---

## File Structure

```
ami-recruiter/
├── config.yaml              ← Your settings (API key, Gmail, etc.)
├── setup.bat                ← One-time setup (run first)
├── start.bat                ← Launch the system (run daily)
├── pipeline.py              ← Resume processing engine
├── dashboard.py             ← Web dashboard (Streamlit)
├── database.py              ← Database models
├── resume_parser.py         ← Resume text extraction and parsing
├── scoring_engine.py        ← Rubric-based scoring logic
├── notifications.py         ← Gmail notification system
├── requirements.txt         ← Python package dependencies
├── ami_recruiter.db         ← Database (auto-created)
├── AMI_Candidates_Inbox/    ← Drop resumes here
├── AMI_Candidates_Processed/← Processed resumes move here
└── AMI_Candidates_Failed/   ← Failed/duplicate resumes go here
```

---

## Troubleshooting

**"Python is not installed"** — Run the Python installer and make sure to check "Add Python to PATH."

**"API key not configured"** — Open config.yaml in Notepad and replace YOUR_API_KEY_HERE with your actual key.

**Resume stuck in inbox** — Check the command prompt window for error messages. The file may have an unsupported format.

**Dashboard won't load** — Make sure the start.bat window is still running. Try going to http://localhost:8501 manually.

**Gmail notifications not sending** — Make sure you're using an App Password, not your regular Gmail password. 2-Step Verification must be enabled first.

**"Failed to parse scoring response"** — This occasionally happens with the Claude API. The file will be moved to the Failed folder. You can move it back to the Inbox to retry.

---

## Estimated API Costs

Processing 50-100 resumes:
- Resume parsing: ~$0.05-0.10 per resume
- Scoring (per functional area): ~$0.05-0.10 per area per resume
- Interview questions: ~$0.03-0.05 per functional area

**Estimated total for 100 resumes: $15-30**

Costs depend on resume length and number of functional areas each candidate is scored against.

---

## Support

This system was designed for a specific AMI recruiting workflow. The rubrics embedded in the scoring engine reflect the evaluation criteria developed through detailed knowledge transfer sessions. If the rubrics need updates based on your elimination review feedback, the rubric prompts in `scoring_engine.py` can be modified directly.
