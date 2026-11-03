# Step-by-Step Build & Deployment Playbook: Antigravity (VS Code) -> Public GitHub (95/95 FDE Assessment) -> GCP (`aecom-demo-uc1`) & Gemini Enterprise

> [!IMPORTANT]
> **What This Guide Covers**:
> 1. **Local Laptop Setup in VS Code with Antigravity (AGY)**
> 2. **Copy-Paste Prompts for Antigravity** (engineered so the generated code hits **all 19 criteria / 95 points** on the *AI in 5 Days Assessment Agent* rubric)
> 3. **Publishing to a Public Root GitHub Repo** and submitting to the automated **FDE Project Evaluator**
> 4. **Connecting to GCP Project `aecom-demo-uc1`**, deploying to **Cloud Run / Vertex AI Agent Engine**, registering in **Gemini Enterprise**, and delivering the **Golden Path Demo**

---

## Part 1: Local Laptop Workspace & Google Cloud (`aecom-demo-uc1`) Setup

Open **VS Code** on your laptop, open the integrated terminal (`Ctrl+\`` or `Cmd+\``), and run:

```bash
# 1. Create the ROOT project directory (CRITICAL: must be the root of your future GitHub repo, NOT a subfolder!)
mkdir -p ~/ask-gbs-agent
cd ~/ask-gbs-agent

# 2. Authenticate with Google Cloud and bind to your project: aecom-demo-uc1
gcloud auth login
gcloud auth application-default login
gcloud config set project aecom-demo-uc1

# 3. Enable the required Google Cloud APIs in aecom-demo-uc1
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  logging.googleapis.com \
  cloudtrace.googleapis.com \
  discoveryengine.googleapis.com \
  dlp.googleapis.com \
  --project=aecom-demo-uc1
```

Next, in VS Code:
1. Click **File > Open Folder...** and open `~/ask-gbs-agent`.
2. Place `ai_gbs_uc1_helpdesk_agent_prd.md` and `gbs_source_of_truth_data.md` inside `~/ask-gbs-agent/` so Antigravity can read them directly from your workspace.

---

## Part 2: Step-by-Step Prompts to Run in Antigravity (AGY) on VS Code

Run the following **3 sequential prompts** inside the **Antigravity (AGY) Agent Panel** in VS Code. Splitting the build into 3 focused prompts ensures Antigravity writes complete, production-grade code for every single rubric item without truncating files.

---

### Prompt 1 of 3: Foundation, Schemas, Observability (20 pts) & Context/Memory (20 pts)
*Copy and paste this into Antigravity in VS Code:*

```markdown
Read `ai_gbs_uc1_helpdesk_agent_prd.md` and `gbs_source_of_truth_data.md` in the workspace root. We are building the `ask-gbs-agent` repository in the root of this workspace to score 95/95 on the AI in 5 Days AgentOps Rubric and run in Gemini Enterprise on GCP project `aecom-demo-uc1`.

Execute Phase 1 of the build now:
1. Create `requirements.txt`, `pyproject.toml`, `.env.example` (pre-configured with `GOOGLE_CLOUD_PROJECT=aecom-demo-uc1`, `GOOGLE_CLOUD_LOCATION=us-central1`, `GEMINI_FLASH_MODEL=gemini-2.5-flash`, `GEMINI_PRO_MODEL=gemini-4-argon`), and `.gitignore`.
2. Copy `gbs_source_of_truth_data.md` into `ask_gbs_agent/data/gbs_source_of_truth_data.md`. Ensure zero internal/confidential names exist anywhere.
3. Implement `ask_gbs_agent/config/settings.py` and `ask_gbs_agent/config/secret_manager.py`:
   - Rubric 5.3 (Secure Secret Management): Use `google.cloud.secretmanager.SecretManagerServiceClient` to resolve secrets from `projects/aecom-demo-uc1/secrets/{secret_id}/versions/latest` with environment variable fallback for local dev and zero hardcoded API keys.
4. Implement `ask_gbs_agent/schemas.py`:
   - Rubric 1.3 (Explicit JSON Schemas) & 1.4 (Guided Error Handling): Define strict Pydantic v2 `BaseModel` (`ConfigDict(extra="forbid")`, `Field(...)`) input and output schemas for all tools (`InvoiceLookupInput`, `InvoiceDiagnosticOutput`, `MissingIdentifierFormInput`, `UrgentPaymentFormInput`, `ServiceNowCaseIntakeInput`, `ServiceNowCaseConfirmInput`, `ServiceNowTicketReceiptOutput`, `KbCanvasInput`, and `GuidedToolErrorResponse` containing `status="RECOVERABLE_ERROR"`, `error_code`, `llm_recovery_instruction`, and `suggested_next_tool`).
5. Implement `ask_gbs_agent/observability/` (Rubric Category 4 — 20/20 pts):
   - `pii_redactor.py` (Rubric 4.4): Implement `PiiRedactionScrubber` that scrubs emails, bank account numbers, routing numbers, phone numbers, and tax IDs via deterministic regex patterns plus optional `google.cloud.dlp_v2.DlpServiceClient` de-identification before any log emission or memory write.
   - `structured_logger.py` (Rubric 4.1): Implement `StructuredJsonLogger` using `python-json-logger` and `google-cloud-logging` with `PiiRedactionScrubber` attached as a `logging.Filter`. Never use `print()`.
   - `intent_outcome_tracker.py` (Rubric 4.2): Implement `IntentOutcomeTracker` with explicit `log_intent(execution_id, agent_name, tool_name, sanitized_args, reason)` before execution and `log_outcome(execution_id, agent_name, tool_name, status, latency_ms, a2ui_surface_id, summary)` after execution.
   - `tracing.py` (Rubric 4.3): Configure OpenTelemetry (`opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-gcp-trace`) with `CloudTraceSpanExporter(project_id="aecom-demo-uc1")` and a clean in-memory/console fallback when running offline tests.
6. Implement `ask_gbs_agent/memory/` (Rubric Category 2 — 20/20 pts):
   - `compaction.py` (Rubric 2.2): Implement `HistoryCompactionManager` that enforces token-based sliding window compaction (summarizing older turns when history exceeds token/turn thresholds and stripping raw `<a2a_datapart_json>` payloads into `[Rendered A2UI Surface: {readable_text}]`) plus a helper for Vertex AI Context Caching (`CachedContent`).
   - `persistent_store.py` (Rubric 2.3): Implement `PersistentGbsMemoryService` backed by a persistent SQLite + FTS5/Cosine-Vector database (`ask_gbs_agent/data/gbs_memory.db`) seeded automatically from `gbs_source_of_truth_data.md`, with optional cloud adapters for `VertexAiSessionService` / `VertexAiMemoryBankService` and Vertex AI Search. All stored session turns pass through `PiiRedactionScrubber`.
   - `async_worker.py` (Rubric 2.4): Implement non-blocking `asyncio.create_task()` background workers (`schedule_async_memory_consolidation`, `consolidate_session_memory_async`) so memory summarization and embedding writes never block the UI response stream.
```

---

### Prompt 2 of 3: A2UI v0.9 Canvas Plugin, 2-Step ServiceNow Case Tools & Multi-Agent Orchestration (40 pts)
*Once Prompt 1 completes, copy and paste Prompt 2 into Antigravity:*

```markdown
Now execute Phase 2 of the build (Tools, A2UI v0.9 Canvas & Card Surfaces, Multi-Agent Orchestration, Model Routing, Guardrails, and HITL Hooks):

1. Implement `ask_gbs_agent/plugins/a2ui_canvas_plugin.py`:
   - Build the Gemini Enterprise A2UI v0.9 wire-format packager (`A2UI_VERSION = "v0.9"`, `GE_COMPOSITE_CATALOG_ID = "https://www.gstatic.com/vertexaisearch/a2ui/v0_9/gemini_enterprise_composite_catalog.json"`, `A2UI_MIME_TYPE = "application/json+a2ui"`, `<a2a_datapart_json>...</a2a_datapart_json>`).
   - Implement builders for all 5 A2UI v0.9 surfaces:
     - Surface A (`build_servicenow_intake_form_card`): Inline `MaterialCard` form with inputs for *GBS Service Area*, *Reference Number*, *Urgency/Priority*, *Requester Email*, *Case Description*, and a `[Submit ServiceNow Case]` button (`confirm_create_servicenow_case`).
     - Surface B (`build_servicenow_receipt_card`): Inline `MaterialCard` displaying the generated mock Case ID (e.g., `CS9940120`), target queue, SLA, and the illustrative demo notice.
     - Surface C (`build_missing_identifier_lookup_card`): Inline `MaterialCard` form when a user omits the Invoice/PO number.
     - Surface D (`build_invoice_payment_status_card`): Inline `MaterialCard` showing Coupa status, Net 30 submission date math (`KB0015901`), Oracle EFT reference, and follow-up action buttons.
     - Surface E (`build_multi_invoice_reconciliation_canvas` & `build_interactive_kb_canvas`): Side-Panel `Canvas` (`id="root"`, `component="Canvas"`, `content="canvas-main-col"`) containing a `RichTable` (`spec: {}`, numeric floats) for `PAY-03` (`23469`, `23104`, `23288`), an AP spend/status breakdown chart, and `MaterialExpansionPanel` accordions (titles <= 62 chars).
   - Wrap in `A2uiCanvasPlugin(BasePlugin)` so queued A2UI parts in `state["pending_a2ui_parts"]` are automatically attached to model responses.

2. Implement `ask_gbs_agent/plugins/policy_plugin.py` (Rubric 3.3 — Guardrails & Policy Plugins):
   - Implement `GbsPolicyGuardrailPlugin(BasePlugin)` and `SelfEvaluationGuardrail`:
     - Enforces read-only ERP posture (blocks any direct Coupa/Oracle write attempt).
     - Computes self-evaluation confidence scores on lookups: for `PAY-05` (`2458874037` / `@veritaslabs-group.example.com` vs `DNU - EnviroLab Analytics Inc`), sets `confidence_score = 62 (< 80)`, masks bank digits (`[REDACTED — SECURITY HOLD]`), and forces escalation to `GBS-Vendor-Management-Security`.

3. Implement `ask_gbs_agent/tools/` (Rubric Category 1 — 20/20 pts & Requirement #3):
   - Every tool MUST have comprehensive Google-style docstrings (Rubric 1.1), descriptive verb-noun names (Rubric 1.2), strict Pydantic schema validation from `schemas.py` (Rubric 1.3), and return `GuidedToolErrorResponse` dicts on invalid/missing inputs instead of crashing (Rubric 1.4):
     - `lookup_coupa_oracle_invoice_record` (`invoice_tools.py`): Resolves all 17 Invoice (`INV-01`..`INV-17`), 5 Payment (`PAY-01`..`PAY-05`), Exemptions Registry, and 8 Teaser (`ACC-01`..`CSP-01`) records from `gbs_source_of_truth_data.md` + `PersistentGbsMemoryService` and queues the appropriate A2UI surface (`Surface D` or `Surface E`). If the query is not found in the Golden Dataset / RAG store, returns a guided response instructing the agent to call `stage_servicenow_case_intake_form`.
     - `request_missing_invoice_identifier_form` (`invoice_tools.py`): Queues `Surface C` when the user asks for invoice/payment help without an identifier.
     - `open_urgent_payment_acceleration_form` (`servicenow_tools.py`): Queues the regional Urgent Payment Intake `MaterialCard` for `PAY-01` (`INV00026056`).
     - `stage_servicenow_case_intake_form` (`servicenow_tools.py`): Step 1 of the illustrative ServiceNow workflow. Pre-populates and queues `Surface A` (`gbs-servicenow-intake-form`) and sets `tool_context.state["hitl_ticket_staged"] = True`.
     - `submit_confirmed_servicenow_case` (`servicenow_tools.py`): Step 2 of the illustrative ServiceNow workflow (protected by the HITL gate). Generates an illustrative Case ID (`CS9940120`), records the ticket in SQLite memory, and queues `Surface B` (`gbs-servicenow-receipt-CS9940120`).
     - `open_interactive_coupa_kb_canvas` (`kb_tools.py`): Queues `Surface E` (`Canvas` KB guide for `KB0015760`–`KB0016050`).

4. Implement `ask_gbs_agent/callbacks.py` (Rubric 3.4 — HITL Hooks & Rubric 2.2/4.2):
   - `before_model_callback`: Runs `HistoryCompactionManager.compact()`, parses synthetic Gemini Enterprise A2UI user button clicks (`confirm_create_servicenow_case` sets `state["hitl_user_confirmed"] = True`), and logs model `INTENT`.
   - `before_tool_callback`: Enforces the hard Human-in-the-Loop code stop (`enforce_hitl_confirmation_gate`) on `submit_confirmed_servicenow_case` if `state.get("hitl_user_confirmed")` is not `True`, and logs tool `INTENT` with OpenTelemetry span start.
   - `after_tool_callback` & `after_model_callback`: Logs `OUTCOME` with latency, attaches queued A2UI parts inside a `try/except` blast-radius guard, and triggers `schedule_async_memory_consolidation()`.

5. Implement `ask_gbs_agent/prompts.py`, `ask_gbs_agent/orchestration/model_router.py`, `ask_gbs_agent/sub_agents/`, and `ask_gbs_agent/agent.py` (Rubric 2.1, 3.1, 3.2):
   - Define `AGENT_CONSTITUTION_PROMPT` in `prompts.py`.
   - Implement `StrategicModelRouter` in `model_router.py` routing routine lookups/KB queries to `gemini-2.5-flash` and complex multi-invoice legal holds (`PAY-03`), security mismatches (`PAY-05`), and escalations to `gemini-4-argon`.
   - Create 3 specialist sub-agents (`invoice_payment_diagnostic_agent`, `procurement_kb_advisory_agent`, and `escalation_hitl_specialist_agent` which includes a `SequentialAgent` reconciliation-to-escalation pipeline) orchestrated by `root_agent = LlmAgent(name="ask_gbs_orchestrator", ...)` in `ask_gbs_agent/agent.py`.
```

---

### Prompt 3 of 3: FastAPI / Cloud Run Server, Terraform IaC, Automated Evaluation Suite & 95-Point Verification
*Once Prompt 2 completes, copy and paste Prompt 3 into Antigravity:*

```markdown
Now execute Phase 3 of the build (FastAPI/Cloud Run Wrapper, Terraform IaC, Automated Golden Dataset Evaluation Suite, CI/CD, and Full Verification):

1. Create `main.py` and `Dockerfile`:
   - In `main.py`, wrap the ADK agent using `google.adk.cli.fast_api.get_fast_api_app` (or FastAPI mounting the ADK runner) so it exposes `/run`, `/run_sse`, `/list-apps`, `/health`, and a `POST /warm` endpoint that pre-warms the SQLite/Vector index and model clients to eliminate cold starts during live Gemini Enterprise demos.
2. Create `terraform/main.tf`, `terraform/variables.tf`, and `terraform/outputs.tf` (Rubric 5.2 — Infrastructure as Code):
   - Default `project_id = "aecom-demo-uc1"` and `region = "us-central1"`.
   - Provision the Artifact Registry repository, GCS staging bucket (`aecom-demo-uc1-ask-gbs-staging`), Secret Manager secrets, least-privilege Service Account (`ask-gbs-agent-sa@aecom-demo-uc1.iam.gserviceaccount.com`), and Google Cloud Run v2 service (`ask-gbs-agent`) with `min_instance_count = 1`.
3. Create `deploy_cloud_run.sh`, `deploy_agent_engine.py`, and `register_gemini_enterprise.sh`:
   - `deploy_cloud_run.sh`: Uses `adk deploy cloud_run --project=aecom-demo-uc1 --region=us-central1 --service_name=ask-gbs-agent --with_ui` (and sets `--min-instances=1`).
   - `deploy_agent_engine.py`: Deploys `root_agent` to Vertex AI Agent Engine (`vertexai.agent_engines.create`) in `aecom-demo-uc1`.
   - `register_gemini_enterprise.sh`: Registers the deployed agent endpoint with Gemini Enterprise via the Discovery Engine v1alpha REST API.
4. Create the Automated Evaluation & Test Harness (Rubric 5.1 — Automated Evaluation Suites):
   - `eval/golden_dataset.json` and `eval/run_adk_evaluation.py`: Static and dynamic evaluation suite covering the sanitized Golden Dataset scenarios (`INV-01`..`INV-17`, `PAY-01`..`PAY-05`, `ACC-01`..`CSP-01`, and out-of-scope ServiceNow ticket creation).
   - `tests/test_a2ui_schema_compliance.py`: Validates every generated A2UI v0.9 payload against all 10 Gemini Enterprise composite catalog rules.
   - `tests/test_golden_dataset_eval.py`: Tests all invoice, payment, exemption, teaser, and 2-step ServiceNow ticket creation tool flows (including verifying that `submit_confirmed_servicenow_case` is blocked by the HITL hook until `hitl_user_confirmed=True`).
   - `tests/test_rubric_agentops.py`: Explicitly tests all 19 rubric criteria (Pydantic validation, GuidedToolErrorResponse recovery, HistoryCompactionManager, PersistentGbsMemoryService, async memory consolidation, StrategicModelRouter Flash vs Pro routing, PiiRedactionScrubber, IntentOutcomeTracker, and OpenTelemetry spans).
   - `.github/workflows/agentops_ci.yml`: GitHub Actions workflow running `pytest` and `python eval/run_adk_evaluation.py`.
5. Create a comprehensive `README.md` documenting:
   - Problem & Solution Statement
   - Architecture Diagram (ADK Agent -> Cloud Run / Agent Runtime -> Gemini Enterprise Chat + Side-Panel A2UI Canvas)
   - Explicit 19-Point Rubric Traceability Table showing the exact file & class for each of the 5 Categories (95/95 points)
   - `adk` CLI usage (`adk web`, `adk api_server`, `adk eval`, `adk deploy cloud_run`, `adk deploy agent_engine`)
   - Step-by-step Gemini Enterprise registration & Golden Path Demo script
6. Run `pytest -v` and `python eval/run_adk_evaluation.py` in a virtual environment and fix any issues until 100% of tests pass.
```

---

## Part 3: Pushing to a Public Root GitHub Repository & Running the Assessment Evaluator

Once Antigravity finishes Phase 3 and `pytest -v` passes 100%, run these commands in your VS Code terminal:

```bash
# 1. Ensure you are in the ROOT of ask-gbs-agent (not a subfolder!)
cd ~/ask-gbs-agent

# 2. Verify no .env or temporary files are staged
git status

# 3. Initialize Git and commit all files at the repository root
git init -b main
git add .
git commit -m "feat: Ask GBS Enterprise Helpdesk ADK Agent with A2UI v0.9 Canvas & 95-pt AgentOps"

# 4. Create a PUBLIC GitHub repository at the root level and push
# (If using GitHub CLI `gh`:)
gh repo create ask-gbs-agent --public --source=. --remote=origin --push

# (Or if you created an empty public repo on github.com manually:)
# git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/ask-gbs-agent.git
# git push -u origin main
```

### Submitting to the AI in 5 Days Assessment Agent
1. Open **[https://fde-project-evaluator-510868799189.us-central1.run.app/login](https://fde-project-evaluator-510868799189.us-central1.run.app/login)** and sign in with your Google account.
2. Paste your public GitHub repository URL (`https://github.com/<YOUR_GITHUB_USERNAME>/ask-gbs-agent`).
3. *(Optional)* Include your public English YouTube walkthrough video URL.
4. Click **Evaluate Project**! Remember you can submit and re-evaluate as many times as you like.

---

## Part 4: Deploying to `aecom-demo-uc1`, Registering in Gemini Enterprise & Delivering the Live Demo

### Step 1: Test Locally in VS Code First (`adk web`)
```bash
source .venv/bin/activate
adk web
```
- Open `http://localhost:8000` in your browser to test the multi-agent routing and tool calls locally.

### Step 2: Deploy to Google Cloud (`aecom-demo-uc1`)
You can deploy to **Cloud Run** (recommended for fast demos with `/warm` endpoint) or **Vertex AI Agent Engine**:

```bash
# Option A: Deploy to Cloud Run in aecom-demo-uc1
chmod +x deploy_cloud_run.sh
./deploy_cloud_run.sh

# Option B: Deploy to Vertex AI Agent Engine in aecom-demo-uc1
python deploy_agent_engine.py --project_id=aecom-demo-uc1 --location=us-central1
```

### Step 3: Register the Agent in Your Internal Gemini Enterprise App
1. Open **[Google Cloud Console > Gemini Enterprise (Agent Builder)](https://console.cloud.google.com/gen-app-builder/engines?project=aecom-demo-uc1)** in project **`aecom-demo-uc1`**.
2. Select your **Gemini Enterprise App** -> click **Agents** in the left navigation pane.
3. Click **Create / Register Agent** -> choose **Custom Agent (ADK / A2A)**.
4. Enter:
   - **Display Name**: `Ask GBS — Enterprise Finance & Procurement Helpdesk`
   - **Description**: `Multi-agent ADK assistant for Supplier Invoice Support, Payment Diagnostics, Coupa KB Guidance, and ServiceNow Case Creation with A2UI Canvas.`
   - **Endpoint URL / Resource**: Paste your Cloud Run Service URL (`https://ask-gbs-agent-...-uc.a.run.app`) or Vertex AI Agent Engine Resource Name (`projects/aecom-demo-uc1/locations/us-central1/reasoningEngines/...`).
5. Configure Service Account authentication (`ask-gbs-agent-sa@aecom-demo-uc1.iam.gserviceaccount.com`) and click **Save & Publish**.

### Step 4: Pre-Warm & Run the "Golden Path" Live Demo
1. **Pre-Warm 2 Minutes Before Presenting**:
   ```bash
   curl -X POST "$(gcloud run services describe ask-gbs-agent --project=aecom-demo-uc1 --region=us-central1 --format='value(status.url)')/warm"
   ```
2. **Open Two Browser Tabs**:
   - **Tab 1**: Your **Gemini Enterprise App UI** with **Ask GBS** selected.
   - **Tab 2**: **Google Cloud Console > Logging & Cloud Trace** (`project=aecom-demo-uc1`) filtered to `ask-gbs-agent`.
3. **Execute the 4-Minute Golden Path Script**:
   - **Demo Step 1 (Missing Info Clarification Card)**: Ask *"I need help with an invoice that hasn't been paid yet."* -> Show the inline **A2UI Quick-Lookup Card (`Surface C`)**.
   - **Demo Step 2 (Cross-System Coupa/Oracle Diagnostic & Net 30 Math)**: Submit `INV00026056` (**FieldSync Ops Ltd**) -> Show the **A2UI Status Tracker Card (`Surface D`)** explaining the `15 Dec 2025` submission date rule (`Due 14 Jan 2026`, EFT `1664447`).
   - **Demo Step 3 (Side-Panel `Canvas` Multi-Invoice Reconciliation)**: Ask *"We received a Second Payment Reminder Notice from BioData Registry Online for invoices 23469, 23104, and 23288 threatening an account freeze."* -> Show the **Gemini Enterprise Side-Panel Canvas (`Surface E`)** rendering the interactive `RichTable` reconciliation matrix.
   - **Demo Step 4 (Illustrative 2-Step ServiceNow Case Creation)**: Ask *"Titan Earthworks billed the wrong amount ($22,772) on approved invoice 2158, or I have a custom tax audit question not in the KB."* -> Show the **A2UI ServiceNow Case Intake Form (`Surface A`)**, click **"Submit ServiceNow Case"**, and show the **A2UI Case Confirmation Receipt Card (`CS9940120`, `Surface B`)**.
   - **Demo Step 5 (Observability & AgentOps Proof)**: Switch to **Tab 2 (Cloud Logging / Cloud Trace)** to show real-time OpenTelemetry spans, `INTENT` vs. `OUTCOME` JSON logs, Flash-to-Pro model routing, and automatic PII redaction!
