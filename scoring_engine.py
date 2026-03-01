"""
Scoring Engine - Evaluates parsed candidate profiles against functional area rubrics.
Uses Claude API with rubric-specific prompts to score, tier, and generate interview questions.
"""

import json
import anthropic
from config_loader import CONFIG
from api_utils import retry_api_call


# ============================================================
# RUBRIC PROMPTS - One per functional area
# These encode the scoring criteria from the rubric documents
# ============================================================

RUBRIC_PROMPTS = {

"Strategy & Business Case": """You are an expert AMI recruiting evaluator. Score this candidate for the STRATEGY & BUSINESS CASE functional area.

GATE CRITERIA (all must pass or candidate is ELIMINATED):
- Gate 1: AMI Experience - Must have direct AMI-specific strategy/business case work. Grid modernization strategy WITHOUT AMI specificity does NOT count. Look for AMI business case, AMI cost-benefit analysis, AMI strategy, AMI vendor procurement.
- Gate 2: Minimum AMI Years - Senior: 3+ years. Manager: 7+ years. The candidate's role routing is: {role_routing}. If eliminated, their AMI years are: {ami_years}.
- Gate 3: Functional Area Match - Must show experience in at least one: Strategic Advisory, Business Case Development, or Procurement Advisory.

CRITICAL RULE - AMI vs Grid Modernization:
- "Grid modernization strategy" that included AMI as ONE component = PARTIAL credit (only AMI portion counts)
- "Grid modernization strategy" without AMI specificity = DOES NOT COUNT
- Pure AMI strategy/business case work = FULL credit

SCORING DIMENSIONS (score each 1-5):
1. AMI Program Depth (20%) - Number of AMI programs, variety of clients, scale
2. AMI Technology-to-Value Translation (25%) - Can they translate AMI capabilities into business benefits? The "so what" skill.
3. Financial Modeling & Analytical Rigor (20%) - Cost-benefit analysis, financial modeling, quantifiable scale
4. Utility Operating Model Knowledge (15%) - Cross-department understanding, benefit identification beyond obvious
5. Strategic Advisory & Executive Presence (15%) - Advising leadership, regulatory support, consensus building
6. Consulting Experience (5%) - Consulting-side = 1.0x, Utility-side = 0.7x multiplier on this dimension

TIERING: HIGH (4.0-5.0), MEDIUM (3.0-3.99), LOW (2.0-2.99), ELIMINATED (failed gate or <2.0)""",

"Business Integration": """You are an expert AMI recruiting evaluator. Score this candidate for the BUSINESS INTEGRATION functional area.

GATE CRITERIA (all must pass or candidate is ELIMINATED):
- Gate 1: AMI Experience - Must have direct AMI-specific business integration work. General utility consulting without AMI specificity does NOT count.
- Gate 2: Minimum AMI Years - Senior: 3+ years. Manager: 7+ years. The candidate's role routing is: {role_routing}. If eliminated, their AMI years are: {ami_years}.
- Gate 3: Functional Area Match - Must show experience in at least one: Business Process Design (BPD), Project Management (PM), or Change Management (CM).

BI SUBCATEGORIES:
- BPD: Requirements documentation, process flows, BRDs, user scenarios, facilitating design decisions. Key processes: meter-to-cash, service orders, field operations, outage management.
- PM: Overall AMI program coordination across ALL workstreams (BPD, CM, network, field deployment, SI, cutover).
- CM: Change impact analysis, training strategy/materials, communication strategy, stakeholder engagement. Uses BPD outputs as inputs.
Candidates typically strong in 1, sometimes 2. All 3 is rare and exceptional.

SCORING DIMENSIONS (score each 1-5):
1. AMI Program Depth (25%) - Programs, years, scale, client variety
2. Functional Subcategory Depth (25%) - Depth in primary subcategory. Leader vs participant? Created deliverables?
3. Techno-Functional Capability (20%) - AMI technology knowledge translated to business impact. Names systems? Understands interconnections?
4. Cross-Workstream Coordination (15%) - Works across AMI workstreams, understands input/output relationships
5. Communications Effectiveness (10%) - Written/verbal communication, documentation for multiple audiences
6. Consulting Experience (5%) - Consulting-side = 1.0x, Utility-side = 0.7x

TIERING: HIGH (4.0-5.0), MEDIUM (3.0-3.99), LOW (2.0-2.99), ELIMINATED (failed gate or <2.0)""",

"System Integration": """You are an expert AMI recruiting evaluator. Score this candidate for the SYSTEM INTEGRATION functional area.

GATE CRITERIA (all must pass or candidate is ELIMINATED):
- Gate 1: AMI Experience - Must have direct AMI-specific system integration work. General utility IT/CIS/ERP without AMI specificity does NOT count.
- Gate 2: Minimum AMI Years - Senior: 3+ years. Manager: 7+ years. The candidate's role routing is: {role_routing}. If eliminated, their AMI years are: {ami_years}.
- Gate 3: Functional Area Match - Must show experience in at least one: Solution Architecture, Technical Design, Applications Development, Testing, or Cutover.

SI SUBCATEGORIES:
- Solution Architecture: End-to-end AMI solution architecture, integration patterns, data architecture, cybersecurity, infrastructure. Sits ABOVE the SDLC.
- Technical Design: Functional/technical design docs, interface design, mapping business requirements to technical solutions.
- Applications Development: Building, configuring, customizing AMI platforms and integrations.
- Testing: Test strategy, plans, execution, defect management across AMI platforms.
- Cutover: Production deployment, cross-team coordination, hypercare, transition to operations.
Candidates typically specialize in 1, sometimes adjacent pairs. Architects are typically architecture-only.

KEY AMI PLATFORMS: Itron IEE, SSN, MV-RS; Landis+Gyr Gridstream; Sensus FlexNet; Siemens EnergyIP; Oracle MDM; SAP IS-U; Oracle CC&B.
KEY AMI FUNCTIONALITY: OTA firmware, remote connect/disconnect, on-demand reads/pings, last gasp, meter events, VEE, service orders, meter exchange.
INTEGRATION PATTERNS: File-based transfers, API calls, real-time vs batch, meter data flow (meters→network→HES→MDMS→CIS/OMS/ADMS).

SCORING DIMENSIONS (score each 1-5):
1. AMI Program Depth (20%) - Programs, years, scale, clients
2. Subcategory Technical Depth (25%) - Depth in primary subcategory, leadership vs execution, specific deliverables
3. AMI Platform & Technology Knowledge (25%) - Names specific platforms, languages, integration tools, AMI functionality
4. Cross-SDLC & Cross-Workstream Awareness (15%) - Understands BPD→SI flow, architecture→design→dev→test→cutover cascade
5. Business-Technical Translation (10%) - Can translate business requirements to technical, and technical concepts to business stakeholders
6. Consulting Experience (5%) - Consulting-side = 1.0x, Utility-side = 0.7x

TIERING: HIGH (4.0-5.0), MEDIUM (3.0-3.99), LOW (2.0-2.99), ELIMINATED (failed gate or <2.0)""",

"Field Deployment Management": """You are an expert AMI recruiting evaluator. Score this candidate for the FIELD DEPLOYMENT MANAGEMENT functional area.

GATE CRITERIA (all must pass or candidate is ELIMINATED):
- Gate 1: AMI Experience - Must have direct AMI field deployment experience (meter deployment, network device deployment). General utility construction/field ops without AMI specificity does NOT count.
- Gate 2: Minimum AMI Years - Senior: 3+ years. Manager: 7+ years. The candidate's role routing is: {role_routing}. If eliminated, their AMI years are: {ami_years}.
- Gate 3: Functional Area Match - Must show experience in deployment strategy, MIC vendor management, asset logistics, deployment tracking, network deployment, or meter commissioning.

KEY DOMAINS:
- Deployment Strategy & Planning: Geographic sequencing, mass vs phased deployment, coordination with network readiness
- Network Deployment: RF mesh, cellular, PLC knowledge; collector/repeater deployment; network-meter coordination
- MIC Vendor Management: Meter Installation Contractor relationships (Aclara/First Call, UPA, Pike, Asplundh), contracting, procedures, performance management, exception handling (customer refusals, access issues)
- Supply Chain & Logistics: Meter ordering, receiving, warehousing, sample testing, distribution to MIC, tracking millions of devices
- Commissioning: Meter provisioning onto AMI network, troubleshooting first-boot failures, deployment-to-operations handoff

KEY PROCESSES: Meter ordering → receiving → CIS-to-work-order sync → field order issuance → meter exchange → completion → unable-to-complete/failures

SPECIAL NOTE: MIC vendor-side experience (candidate worked FOR a MIC, not the utility/consultant) = partial credit, flag for phone screen.

SCORING DIMENSIONS (score each 1-5):
1. AMI Program Depth (20%) - Programs, years, scale (meters deployed), clients
2. Deployment Strategy & Planning (20%) - Strategy development, sequencing, deployment approach decisions
3. MIC Vendor Management (20%) - MIC relationships, contracting, procedures, performance management, names vendors
4. Supply Chain, Logistics & Asset Tracking (15%) - Meter supply chain, warehousing, deployment tracking at scale
5. Network & Commissioning Knowledge (10%) - AMI network tech, device deployment, meter provisioning/commissioning
6. Communications & Reporting (10%) - Deployment reporting, dashboards, executive communication
7. Consulting Experience (5%) - Consulting=1.0x, Utility=0.7x, MIC vendor-side=flag for phone screen

TIERING: HIGH (4.0-5.0), MEDIUM (3.0-3.99), LOW (2.0-2.99), ELIMINATED (failed gate or <2.0)""",

"AMI Operations": """You are an expert AMI recruiting evaluator. Score this candidate for the AMI OPERATIONS functional area.

GATE CRITERIA (all must pass or candidate is ELIMINATED):
- Gate 1: AMI Experience - Must have direct AMI operations experience (operating HES and/or MDMS). General IT operations/system admin without AMI specificity does NOT count.
- Gate 2: Minimum AMI Years - Senior: 3+ years. Manager: 7+ years. The candidate's role routing is: {role_routing}. If eliminated, their AMI years are: {ami_years}.
- Gate 3: PRODUCTION EXPERIENCE (CRITICAL) - Must have ACTUAL production environment experience. Testing-only experience in dev/QA/UAT does NOT qualify. Must demonstrate operating live AMI systems serving real customers. If testing-only, suggest cross-referencing against System Integration rubric instead.

KEY DOMAINS:
- HES Operations: Meter provisioning/commissioning, OTA firmware updates, remote connect/disconnect, on-demand reads/pings, meter event management, network performance monitoring
- MDMS Operations: VEE management, reading/billing/registration exception triage, data distribution to CIS and downstream, coordination with billing teams
- Cross-System Triage: Root cause analysis across HES/MDMS/CIS/network, cross-team coordination
- Reporting: AMI network performance, collection rates, billing performance, operational dashboards
- Upgrades & Process Improvement: Platform upgrades, VEE rule optimization, process improvements, distributed intelligence (emerging)

DATA MODEL KNOWLEDGE: Customer/premise/meter/service delivery point hierarchy, channels, units of measure, events/alarms, meter metadata, interval vs register data.

SOLUTION ARCHITECTURE AWARENESS: How HES/MDMS feed CIS (billing), OMS (outage), ADMS (grid ops), data lakes.

SPECIAL NOTE: AMI vendor managed services experience = partial credit, flag for phone screen.

SCORING DIMENSIONS (score each 1-5):
1. AMI Program Depth (15%) - Programs, scale (meters under management), clients, duration
2. HES/MDMS Platform Knowledge (25%) - Names specific platforms, describes operational activities, deep platform knowledge
3. Operational Process Depth (25%) - VEE, provisioning, OTA, remote commands, exception triage, registration. Breadth and depth.
4. Cross-System Triage & Root Cause Analysis (15%) - Troubleshooting across systems, cross-team coordination, complex issue resolution
5. Data Model & Domain Knowledge (10%) - AMI data model fluency, utility operating model understanding
6. Reporting, Upgrades & Process Improvement (5%) - Operational reporting, upgrade experience, process optimization
7. Consulting Experience (5%) - Consulting=1.0x, Utility=0.7x, Vendor managed services=flag

TIERING: HIGH (4.0-5.0), MEDIUM (3.0-3.99), LOW (2.0-2.99), ELIMINATED (failed gate or <2.0)"""
}


SCORING_INSTRUCTION = """
Based on the rubric above and the candidate profile below, provide your evaluation as a JSON object with this exact structure:

{{
    "gate1_pass": true/false,
    "gate1_reason": "Explanation of Gate 1 result",
    "gate2_pass": true/false,
    "gate2_reason": "Explanation of Gate 2 result",
    "gate3_pass": true/false,
    "gate3_reason": "Explanation of Gate 3 result",
    "gates_passed": true/false,
    "dimension_scores": {{
        "dimension_name": {{
            "score": 4,
            "reasoning": "Why this score"
        }}
    }},
    "weighted_score": 4.25,
    "tier": "HIGH" | "MEDIUM" | "LOW" | "ELIMINATED",
    "scoring_narrative": "3-4 sentence summary of the candidate's strengths and gaps for this functional area. Be specific about what impressed you and what concerns you.",
    "manager_stretch_flag": true/false,
    "manager_stretch_narrative": "If 6-7 years AMI and scored HIGH as Senior, explain why they may warrant Manager consideration. Otherwise null."
}}

If the candidate fails any gate, set gates_passed=false, set tier="ELIMINATED", and still provide the gate failure reasons. You do not need to score dimensions if gates are failed, but provide the scoring_narrative explaining why they were eliminated.

CANDIDATE PROFILE:
{candidate_json}
"""


INTERVIEW_QUESTIONS_PROMPT = """You are an expert AMI recruiting interviewer. Generate behavioral interview questions for a phone screen based on this candidate's profile and scoring.

RULES:
- Generate 5-7 questions
- Questions must be DYNAMICALLY TIED to the candidate's specific resume (reference their specific programs, clients, roles, and claimed experience)
- Questions should follow STAR format (Situation, Task, Action, Result) structure
- For HIGH tier candidates: confirm depth, probe for leadership and multi-client perspective
- For MEDIUM tier candidates: probe the identified gaps and ambiguities
- For LOW tier candidates: validate that claimed experience is real and substantive
- Weight questions toward AMI-specific scenarios, not generic behavioral questions
- Map each question to the functional area dimension it's designed to validate

The candidate is being evaluated for: {functional_area}
Their tier is: {tier}
Their scoring narrative: {scoring_narrative}

CANDIDATE PROFILE:
{candidate_json}

Return as a JSON array:
[
    {{
        "question": "The full interview question text, referencing specific resume details",
        "dimension_tested": "Which scoring dimension this validates",
        "what_to_listen_for": "What a strong answer would include",
        "red_flag_answers": "What would concern you in the response"
    }}
]
"""


def score_candidate(parsed_profile, functional_area, ami_years, role_routing):
    """Score a candidate against a specific functional area rubric."""
    client = anthropic.Anthropic(api_key=CONFIG['anthropic_api_key'])

    rubric_prompt = RUBRIC_PROMPTS[functional_area].format(
        role_routing=role_routing or "unknown",
        ami_years=ami_years if ami_years is not None else 0
    )

    scoring_prompt = SCORING_INSTRUCTION.format(
        candidate_json=json.dumps(parsed_profile, indent=2)
    )

    full_prompt = rubric_prompt + "\n\n" + scoring_prompt

    def _call():
        return client.messages.create(
            model=CONFIG['model'],
            max_tokens=4096,
            messages=[{"role": "user", "content": full_prompt}]
        )

    message = retry_api_call(_call)

    response_text = message.content[0].text

    # Extract JSON
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]

    try:
        result = json.loads(response_text.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse scoring response: {e}\nResponse: {response_text[:500]}")

    return result


def generate_interview_questions(parsed_profile, functional_area, tier, scoring_narrative):
    """Generate dynamic phone screen questions for a candidate."""
    if tier == "ELIMINATED":
        return None

    client = anthropic.Anthropic(api_key=CONFIG['anthropic_api_key'])

    prompt = INTERVIEW_QUESTIONS_PROMPT.format(
        functional_area=functional_area,
        tier=tier,
        scoring_narrative=scoring_narrative,
        candidate_json=json.dumps(parsed_profile, indent=2)
    )

    def _call():
        return client.messages.create(
            model=CONFIG['model'],
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )

    message = retry_api_call(_call)

    response_text = message.content[0].text

    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]

    try:
        questions = json.loads(response_text.strip())
    except json.JSONDecodeError:
        # If parsing fails, return the raw text as a single question
        questions = [{"question": response_text, "dimension_tested": "general",
                      "what_to_listen_for": "", "red_flag_answers": ""}]

    return questions
