CURRENT_DISCLAIMER_VERSION = "2026-07-06"

DISCLAIMER_TITLE = "Research Prototype Disclaimer"

DISCLAIMER_ACKNOWLEDGEMENT = (
    "I have read and understand the disclaimer. I will use INSIGHT only as "
    "decision support and accept responsibility for all clinical judgments "
    "and actions taken while using the app."
)

DISCLAIMER_HTML = """
<p><strong>INSIGHT</strong> is a research prototype for academic
schizophrenia-care decision support. Please read and confirm this note
before using the app.</p>

<h3 class="mt-4 mb-1 font-semibold text-ink-800 dark:text-ink-100">Clinical scope</h3>
<ul class="list-disc pl-5 space-y-1">
  <li>INSIGHT is intended for academic research and clinical decision-support exploration only.
    It is not a medical device and is not intended for routine clinical diagnosis, treatment,
    prescribing, triage, emergency care, or patient self-management.</li>
  <li>INSIGHT does not autonomously diagnose, prescribe, recommend treatment, determine
    eligibility for care, or replace professional judgment.</li>
  <li>All diagnostic, treatment, risk, medication, referral, admission, discharge, and follow-up
    decisions remain solely with the treating psychiatrist or other appropriately qualified clinician.</li>
  <li>Any model output, guideline view, draft plan, patient education text, or assistant response
    must be independently reviewed against the full clinical context, current standards of care,
    applicable guidelines, local policy, and the psychiatrist's own examination and judgment.</li>
  <li>Do not rely on INSIGHT as the only source for safety-critical decisions, including
    suicidality, violence risk, medication adverse effects, medical comorbidity, substance use risk,
    or other urgent clinical conditions.</li>
</ul>

<h3 class="mt-4 mb-1 font-semibold text-ink-800 dark:text-ink-100">Data, privacy, and security</h3>
<ul class="list-disc pl-5 space-y-1">
  <li>Patient identifiers and clinical information may be stored in an identifiable clinical database
    so psychiatrists can use direct patient lookup and clinically usable records during the research
    prototype.</li>
  <li>Deployment-level safeguards such as access control, audit logging, redaction, encryption,
    backups, and environment security must be configured and verified by the deploying organization
    before use with real patient data.</li>
  <li>Do not enter patient data unless you are authorized to do so, the deployment has been approved
    for that data, and all applicable institutional, ethical, privacy, consent, and legal requirements
    are satisfied.</li>
  <li>If external AI or hosting services are configured, verify what data is sent, whether it is
    redacted, where it is processed, and whether the configuration meets your institution's
    requirements before use.</li>
</ul>

<h3 class="mt-4 mb-1 font-semibold text-ink-800 dark:text-ink-100">Research and software limitations</h3>
<ul class="list-disc pl-5 space-y-1">
  <li>INSIGHT may contain incomplete, outdated, incorrect, biased, or non-generalizable logic,
    content, models, guidelines, calculations, or generated text.</li>
  <li>The app may change over time, and outputs may depend on the active model revision, guideline
    revision, software version, configuration, and available patient information.</li>
  <li>Use of this app does not create a clinician-patient relationship with the software author,
    contributors, maintainers, or hosting providers.</li>
  <li>No warranty is provided. The software is supplied as open-source research software under the
    MIT License.</li>
</ul>

<h3 class="mt-4 mb-1 font-semibold text-ink-800 dark:text-ink-100">Project attribution</h3>
<p>The project is open-sourced under the MIT License and is accessible at
  <code class="font-mono">a-rastin/INSIGHT-Project</code>.</p>
<p class="mt-3 text-ink-600 dark:text-ink-300 italic">
  By continuing, you acknowledge that you have read this disclaimer, understand INSIGHT's
  research-prototype status and limitations, will use it only as decision support, and accept
  responsibility for all clinical judgments and actions taken while using the app.
</p>
""".strip()


def current_disclaimer() -> dict:
    return {
        "version": CURRENT_DISCLAIMER_VERSION,
        "title": DISCLAIMER_TITLE,
        "content_html": DISCLAIMER_HTML,
        "acknowledgement": DISCLAIMER_ACKNOWLEDGEMENT,
    }
