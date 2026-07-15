"""
CLONE — ACP Skill (iCLONE)
Virtuals Protocol Agent Commerce Protocol integration.

iCLONE acts as a PROVIDER on ACP:
  - Publishes job offerings
  - Accepts jobs from client agents
  - Executes tasks and delivers DeliverableMemo
  - Coordinates with other agents
  - Gets paid in USDC via on-chain escrow (ERC-8183)

Standard: ERC-8183 — Virtuals Protocol + Ethereum Foundation
Docs: https://whitepaper.virtuals.io/about-virtuals/agent-commerce-protocol-acp
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from datetime import datetime, timezone

from .base_skill import SkillResult
from .. import db
from .execution_engine import ExecutionEngine


class JobStatus(str, Enum):
    PENDING   = "pending"
    ACCEPTED  = "accepted"
    EXECUTING = "executing"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    DISPUTED  = "disputed"
    CANCELLED = "cancelled"


class OfferingCategory(str, Enum):
    # Engine 1 — Research & Data (web_search native)
    RESEARCH           = "research"
    DATA_EXTRACTION    = "data_extraction"
    # Engine 2 — Code & Dev (Claude code generation)
    CODE_GENERATION    = "code_generation"
    CODE_REVIEW        = "code_review"
    # Engine 3 — Wallet & Crypto (Etherscan + DeFiLlama)
    WALLET_ANALYSIS    = "wallet_analysis"
    DEFI_INTEL         = "defi_intel"
    # Engine 4 — Content & Social (Claude writing)
    CONTENT            = "content"
    # Engine 5 — Agent Platform (training, building, coordination)
    AGENT_TRAINING     = "agent_training"
    SKILL_BUILDING     = "skill_building"
    AGENT_COORDINATION = "agent_coordination"
    PLATFORM_ONBOARDING = "platform_onboarding"


@dataclass
class JobOffering:
    """
    A service listing published by iCLONE on ACP.
    Describes what iCLONE can be hired to do.
    """
    offering_id: str
    name: str
    description: str
    category: OfferingCategory
    price_usdc: float                    # Price in USDC
    sla_hours: int                       # Service Level Agreement — max hours to deliver
    requirements: list[str]              # What the client must provide
    deliverable_description: str         # What will be delivered
    active: bool = True


@dataclass
class Job:
    """
    An active job instance — created when a client buys an offering.
    Backed by an on-chain escrow contract (ERC-8183).
    """
    job_id: str
    offering_id: str
    client_agent_id: str
    status: JobStatus
    price_usdc: float
    requirements_received: dict[str, Any] = field(default_factory=dict)
    deliverable: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    delivered_at: str | None = None


@dataclass
class DeliverableMemo:
    """
    Proof of work delivery — signed on-chain by provider.
    Client/Evaluator signs to release USDC from escrow.
    """
    job_id: str
    provider_id: str
    deliverable_hash: str          # Hash of the delivered content
    deliverable_url: str           # Where to access the deliverable
    summary: str                   # Human-readable summary
    delivered_at: str


class ACPSkill:
    """
    ACP Provider skill for iCLONE.

    Capabilities:
    - Publish and manage job offerings on Virtuals Protocol ACP
    - Accept and execute jobs from client agents
    - Coordinate with other agents to fulfil complex tasks
    - Submit DeliverableMemo and collect USDC payment
    - Build reputation through on-chain job history (ERC-8004)
    """

    SKILL_ID = "acp_skill_v1"
    SKILL_NAME = "ACP Provider — Agentic Commerce"
    SKILL_DESCRIPTION = (
        "Virtuals Protocol ACP provider. iCLONE publishes job offerings, "
        "accepts on-chain jobs, executes tasks (agent training, skill building, "
        "crypto research, agent coordination), and collects USDC payment via escrow. "
        "Standard: ERC-8183."
    )

    PROVIDER_ID = "iclone-ai"

    # -------------------------------------------------------------------------
    # Full product catalogue — one engine, many SKUs.
    # Pattern: build the capability once, sell quick/standard/deep tiers
    # and per-parameter variants. Volume in cheap tiers; anchor for credibility.
    # -------------------------------------------------------------------------
    DEFAULT_OFFERINGS: list[JobOffering] = [

        # ── ENGINE 1: RESEARCH & DATA ─────────────────────────────────────────
        # Underlying: Claude web_search_20250305 (native, zero extra cost)

        JobOffering(
            offering_id="iclone-research-quick-v1",
            name="Web Research Quick",
            description="Single-query web research. 5 sources, 200-word summary. Ideal for fast fact-checks.",
            category=OfferingCategory.RESEARCH,
            price_usdc=0.25,
            sla_hours=1,
            requirements=["query"],
            deliverable_description="JSON: {summary, sources[], key_facts[]}",
        ),
        JobOffering(
            offering_id="iclone-research-standard-v1",
            name="Web Research Standard",
            description="Multi-query research report. 10+ sources, structured findings, confidence score.",
            category=OfferingCategory.RESEARCH,
            price_usdc=0.75,
            sla_hours=2,
            requirements=["query", "depth"],  # depth: standard | competitive | technical
            deliverable_description="JSON: {report, sources[], findings[], confidence, recommendations[]}",
        ),
        JobOffering(
            offering_id="iclone-research-deep-v1",
            name="Web Research Deep",
            description="5 parallel searches, cross-referenced, structured intelligence report. Best for competitive analysis.",
            category=OfferingCategory.RESEARCH,
            price_usdc=1.50,
            sla_hours=3,
            requirements=["query", "context"],
            deliverable_description="JSON: full intelligence report with confidence scores, gaps identified, and action items.",
        ),
        JobOffering(
            offering_id="iclone-pdf-extract-v1",
            name="PDF → Structured JSON",
            description="Extract structured data from any PDF document. Tables, fields, sections → clean JSON.",
            category=OfferingCategory.DATA_EXTRACTION,
            price_usdc=0.50,
            sla_hours=1,
            requirements=["pdf_url", "extraction_schema"],
            deliverable_description="JSON matching the requested extraction schema.",
        ),
        JobOffering(
            offering_id="iclone-csv-cleaner-v1",
            name="CSV Cleaner & Normalizer",
            description="Clean, deduplicate, normalize, and validate a CSV. Returns cleaned file + audit report.",
            category=OfferingCategory.DATA_EXTRACTION,
            price_usdc=0.35,
            sla_hours=1,
            requirements=["csv_data", "cleaning_rules"],
            deliverable_description="JSON: {cleaned_csv, rows_removed, rows_modified, issues_found[]}",
        ),
        JobOffering(
            offering_id="iclone-price-monitor-v1",
            name="Price Monitor (Non-Crypto)",
            description="Monitor price or availability of any product on any website. Returns current value + change since last check.",
            category=OfferingCategory.DATA_EXTRACTION,
            price_usdc=0.40,
            sla_hours=1,
            requirements=["url", "selector_or_description"],
            deliverable_description="JSON: {current_value, previous_value, change_pct, timestamp, url}",
        ),

        # ── ENGINE 2: CODE & DEV ──────────────────────────────────────────────
        # Underlying: Claude claude-sonnet-4-6 code generation + execution

        JobOffering(
            offering_id="iclone-code-gen-quick-v1",
            name="Code Generate Quick",
            description="Generate a single function or class from a description. Any language. Returns code + docstring.",
            category=OfferingCategory.CODE_GENERATION,
            price_usdc=0.25,
            sla_hours=1,
            requirements=["description", "language"],
            deliverable_description="JSON: {code, language, docstring, example_usage}",
        ),
        JobOffering(
            offering_id="iclone-code-gen-standard-v1",
            name="Code Generate Standard",
            description="Generate a complete module with tests, type hints, and documentation from a spec.",
            category=OfferingCategory.CODE_GENERATION,
            price_usdc=0.75,
            sla_hours=2,
            requirements=["spec", "language", "test_framework"],
            deliverable_description="JSON: {module_code, test_code, README, dependencies[]}",
        ),
        JobOffering(
            offering_id="iclone-bug-fix-v1",
            name="Bug Fix from Error Trace",
            description="Provide an error trace + code snippet. Returns fixed code with explanation of root cause.",
            category=OfferingCategory.CODE_GENERATION,
            price_usdc=0.50,
            sla_hours=1,
            requirements=["error_trace", "code_snippet", "language"],
            deliverable_description="JSON: {fixed_code, root_cause, explanation, prevention_tip}",
        ),
        JobOffering(
            offering_id="iclone-regex-builder-v1",
            name="Regex Builder & Tester",
            description="Build, explain, and test a regex pattern for your use case. Returns pattern + test cases.",
            category=OfferingCategory.CODE_GENERATION,
            price_usdc=0.20,
            sla_hours=1,
            requirements=["description", "sample_inputs[]"],
            deliverable_description="JSON: {pattern, explanation, test_cases[], matches[], non_matches[]}",
        ),
        JobOffering(
            offering_id="iclone-data-format-converter-v1",
            name="Data Format Converter",
            description="Convert between JSON, CSV, XML, YAML, TOML, Markdown table. Any direction.",
            category=OfferingCategory.CODE_GENERATION,
            price_usdc=0.20,
            sla_hours=1,
            requirements=["input_data", "input_format", "output_format"],
            deliverable_description="JSON: {converted_data, output_format, warnings[]}",
        ),
        JobOffering(
            offering_id="iclone-scaffold-v1",
            name="Project Scaffold Generator",
            description="Generate a complete project scaffold: FastAPI, Next.js, Python CLI, n8n workflow, or custom stack.",
            category=OfferingCategory.CODE_GENERATION,
            price_usdc=1.00,
            sla_hours=3,
            requirements=["stack", "project_name", "features[]"],
            deliverable_description="JSON: {file_tree, files{path: content}, setup_instructions, env_example}",
        ),
        JobOffering(
            offering_id="iclone-code-review-v1",
            name="Code Review & Security Scan",
            description="OWASP Top 10 review + code quality analysis. Any language. Returns issues ranked by severity.",
            category=OfferingCategory.CODE_REVIEW,
            price_usdc=0.75,
            sla_hours=2,
            requirements=["code", "language"],
            deliverable_description="JSON: {issues[], severity_counts, recommendations[], score}",
        ),
        JobOffering(
            offering_id="iclone-sql-optimizer-v1",
            name="SQL Query Optimizer",
            description="Analyze and optimize any SQL query. Returns optimized version + explanation of changes.",
            category=OfferingCategory.CODE_REVIEW,
            price_usdc=0.35,
            sla_hours=1,
            requirements=["sql_query", "schema_context"],
            deliverable_description="JSON: {optimized_query, changes[], estimated_improvement, indexes_suggested[]}",
        ),
        JobOffering(
            offering_id="iclone-test-generator-v1",
            name="Test Generator",
            description="Generate unit tests for any function or module. Covers edge cases, error paths, and happy paths.",
            category=OfferingCategory.CODE_REVIEW,
            price_usdc=0.25,
            sla_hours=1,
            requirements=["code", "language", "test_framework"],
            deliverable_description="JSON: {test_code, cases_covered[], coverage_estimate}",
        ),
        JobOffering(
            offering_id="iclone-docs-generator-v1",
            name="Documentation Generator",
            description="Generate README, docstrings, or API docs from code. Returns formatted documentation.",
            category=OfferingCategory.CODE_REVIEW,
            price_usdc=0.15,
            sla_hours=1,
            requirements=["code", "doc_type"],  # doc_type: readme | docstrings | openapi
            deliverable_description="JSON: {documentation, format, sections[]}",
        ),

        # ── ENGINE 3: WALLET & CRYPTO ─────────────────────────────────────────
        # Underlying: Etherscan API + DeFiLlama + Claude analysis

        JobOffering(
            offering_id="iclone-wallet-quick-v1",
            name="Wallet Analyzer Quick",
            description="Token holdings + USD values for any EVM wallet. Returns snapshot in seconds.",
            category=OfferingCategory.WALLET_ANALYSIS,
            price_usdc=0.15,
            sla_hours=1,
            requirements=["wallet_address", "chain"],
            deliverable_description="JSON: {holdings[], total_usd, chain, timestamp}",
        ),
        JobOffering(
            offering_id="iclone-wallet-health-v1",
            name="Wallet Health Check",
            description="Multi-chain wallet audit: holdings, risky approvals, dust attacks, risk score 0–100.",
            category=OfferingCategory.WALLET_ANALYSIS,
            price_usdc=0.50,
            sla_hours=2,
            requirements=["wallet_address"],
            deliverable_description="JSON: {risk_score, holdings[], risky_approvals[], dust_detected, recommendations[]}",
        ),
        JobOffering(
            offering_id="iclone-wallet-deep-v1",
            name="Wallet Deep Analysis",
            description="Full multi-chain portfolio analysis: performance history, DeFi positions, yield opportunities, tax summary.",
            category=OfferingCategory.WALLET_ANALYSIS,
            price_usdc=1.00,
            sla_hours=3,
            requirements=["wallet_address", "chains[]"],
            deliverable_description="JSON: full portfolio report with PnL, DeFi positions, risk matrix, and opportunities.",
        ),
        JobOffering(
            offering_id="iclone-defi-opportunity-v1",
            name="DeFi Opportunity Scanner",
            description="Scan top protocols for yield opportunities above your threshold. Returns ranked list with risk-adjusted APY.",
            category=OfferingCategory.DEFI_INTEL,
            price_usdc=0.75,
            sla_hours=2,
            requirements=["min_apy", "chains[]", "risk_tolerance"],
            deliverable_description="JSON: {opportunities[], ranked_by_risk_adjusted_apy, data_sources[]}",
        ),
        JobOffering(
            offering_id="iclone-crypto-research-quick-v1",
            name="Crypto Research Quick",
            description="Fast analysis of any crypto asset. Price, volume, on-chain metrics, sentiment. 200-word brief.",
            category=OfferingCategory.DEFI_INTEL,
            price_usdc=0.50,
            sla_hours=1,
            requirements=["asset_symbol"],
            deliverable_description="JSON: {price, metrics, sentiment, 1-paragraph summary, signal}",
        ),
        JobOffering(
            offering_id="iclone-crypto-research-deep-v1",
            name="Crypto Research Deep",
            description="Full research report on any crypto asset or DeFi protocol. Macro context, tokenomics, risk, recommendation.",
            category=OfferingCategory.DEFI_INTEL,
            price_usdc=5.00,
            sla_hours=4,
            requirements=["asset_or_protocol", "research_depth"],
            deliverable_description="Full structured report: overview, metrics, on-chain data, risk assessment, recommendation.",
        ),

        # ── ENGINE 4: CONTENT & SOCIAL ────────────────────────────────────────
        # Underlying: Claude Haiku (low cost) + structured prompts

        JobOffering(
            offering_id="iclone-thread-quick-v1",
            name="Crypto Thread Quick",
            description="Generate a 3-tweet thread on any crypto topic. Hook + body + CTA. Ready to post.",
            category=OfferingCategory.CONTENT,
            price_usdc=0.25,
            sla_hours=1,
            requirements=["topic", "tone"],  # tone: bullish | neutral | analytical
            deliverable_description="JSON: {tweets[], char_counts[], hashtags[]}",
        ),
        JobOffering(
            offering_id="iclone-thread-standard-v1",
            name="Crypto Thread Standard",
            description="7-tweet thread with viral hook, data-backed body, and strong CTA. Optimised for engagement.",
            category=OfferingCategory.CONTENT,
            price_usdc=0.50,
            sla_hours=1,
            requirements=["topic", "tone", "data_points[]"],
            deliverable_description="JSON: {tweets[], engagement_tips[], hashtags[], best_time_to_post}",
        ),
        JobOffering(
            offering_id="iclone-blog-post-v1",
            name="Blog Post Generator",
            description="500-word article on any topic. SEO-optimised, structured with H2/H3, ready to publish.",
            category=OfferingCategory.CONTENT,
            price_usdc=1.00,
            sla_hours=2,
            requirements=["topic", "target_audience", "keywords[]"],
            deliverable_description="JSON: {title, markdown_content, meta_description, seo_score}",
        ),
        JobOffering(
            offering_id="iclone-newsletter-v1",
            name="Newsletter Digest",
            description="Weekly digest of top news in a category. Curated, summarised, ready to send.",
            category=OfferingCategory.CONTENT,
            price_usdc=2.00,
            sla_hours=3,
            requirements=["category", "num_items", "audience"],
            deliverable_description="JSON: {items[], intro, outro, markdown_ready}",
        ),

        # ── ENGINE 5: AGENT PLATFORM ──────────────────────────────────────────
        # Underlying: iCLONE training modules + Virtuals Protocol ACP

        JobOffering(
            offering_id="iclone-agent-training-module-v1",
            name="Agent Training Module",
            description="Add one knowledge module to any CLONE agent. Covers one domain (trading, security, ACP, etc.).",
            category=OfferingCategory.AGENT_TRAINING,
            price_usdc=5.00,
            sla_hours=4,
            requirements=["agent_id", "domain"],
            deliverable_description="Training module file + knowledge test results + integration confirmation.",
        ),
        JobOffering(
            offering_id="iclone-agent-training-full-v1",
            name="Full Agent Training Suite",
            description="Complete 15-module training suite for a CLONE agent. All domains: trading, security, ACP, DeFi, content.",
            category=OfferingCategory.AGENT_TRAINING,
            price_usdc=25.00,
            sla_hours=24,
            requirements=["agent_id", "agent_name", "wallet_address"],
            deliverable_description="15 training modules installed, knowledge tests passed, soul.md updated, deployment report.",
        ),
        JobOffering(
            offering_id="iclone-build-skill-quick-v1",
            name="Skill Build Quick",
            description="Build a simple skill (single function, <100 lines). Tested and documented.",
            category=OfferingCategory.SKILL_BUILDING,
            price_usdc=10.00,
            sla_hours=6,
            requirements=["skill_description", "input_schema", "output_schema"],
            deliverable_description="Python skill module + tests + Plaza listing draft.",
        ),
        JobOffering(
            offering_id="iclone-build-skill-standard-v1",
            name="Skill Build Standard",
            description="Build a full skill with multiple methods, error handling, tests, docs, and Plaza listing.",
            category=OfferingCategory.SKILL_BUILDING,
            price_usdc=30.00,
            sla_hours=12,
            requirements=["skill_description", "target_agent", "input_output_examples[]"],
            deliverable_description="Production-ready skill module, tests, documentation, and published Plaza listing.",
        ),
        JobOffering(
            offering_id="iclone-coordinate-agents-v1",
            name="Multi-Agent Coordination",
            description="iCLONE orchestrates 2–5 agents to complete a complex multi-step task in parallel.",
            category=OfferingCategory.AGENT_COORDINATION,
            price_usdc=10.00,
            sla_hours=6,
            requirements=["task_description", "agent_ids[]", "expected_output"],
            deliverable_description="Task completion report with outputs from all agents, execution log, final result.",
        ),
        JobOffering(
            offering_id="iclone-onboarding-v1",
            name="CLONE Platform Onboarding",
            description="Full onboarding: ACP registration, HUB setup, first skill recommendations, wallet check.",
            category=OfferingCategory.PLATFORM_ONBOARDING,
            price_usdc=2.00,
            sla_hours=1,
            requirements=["agent_id_or_user_id"],
            deliverable_description="Onboarding report: platform access confirmed, wallet linked, skills recommended.",
        ),
    ]

    def __init__(self):
        self._offerings: dict[str, JobOffering] = {
            o.offering_id: o for o in self.DEFAULT_OFFERINGS
        }
        self._active_jobs: dict[str, Job] = {}
        self._completed_jobs: list[Job] = []
        self._engine = ExecutionEngine()  # Real execution engine for all 32 offerings

    # -------------------------------------------------------------------------
    # Offerings management
    # -------------------------------------------------------------------------

    def list_offerings(self, active_only: bool = True) -> list[JobOffering]:
        """Return all published offerings."""
        offerings = list(self._offerings.values())
        if active_only:
            return [o for o in offerings if o.active]
        return offerings

    def get_offering(self, offering_id: str) -> SkillResult:
        """Get details of a specific offering."""
        offering = self._offerings.get(offering_id)
        if not offering:
            return SkillResult(
                success=False,
                output="",
                error=f"Offering '{offering_id}' not found.",
            )
        return SkillResult(
            success=True,
            output=f"Offering: {offering.name} — ${offering.price_usdc} USDC",
            data={
                "offering_id": offering.offering_id,
                "name": offering.name,
                "description": offering.description,
                "price_usdc": offering.price_usdc,
                "sla_hours": offering.sla_hours,
                "requirements": offering.requirements,
                "deliverable": offering.deliverable_description,
                "active": offering.active,
            },
        )

    # -------------------------------------------------------------------------
    # Job lifecycle
    # -------------------------------------------------------------------------

    def accept_job(
        self,
        job_id: str,
        offering_id: str,
        client_agent_id: str,
        requirements: dict[str, Any],
    ) -> SkillResult:
        """
        Accept an incoming job from a client agent.
        Validates requirements against the offering spec.
        """
        if not job_id or not offering_id or not client_agent_id:
            return SkillResult(
                success=False,
                output="",
                error="job_id, offering_id, and client_agent_id are required.",
            )

        offering = self._offerings.get(offering_id)
        if not offering:
            return SkillResult(
                success=False,
                output="",
                error=f"Offering '{offering_id}' not found.",
            )

        if not offering.active:
            return SkillResult(
                success=False,
                output="",
                error=f"Offering '{offering_id}' is not active.",
            )

        # Validate required fields
        missing = [r for r in offering.requirements if r not in requirements]
        if missing:
            return SkillResult(
                success=False,
                output="",
                error=f"Missing required fields: {missing}",
            )

        job = Job(
            job_id=job_id,
            offering_id=offering_id,
            client_agent_id=client_agent_id,
            status=JobStatus.ACCEPTED,
            price_usdc=offering.price_usdc,
            requirements_received=requirements,
        )
        self._active_jobs[job_id] = job

        db.upsert_acp_job(
            job_id=job_id,
            offering_id=offering_id,
            client_agent_id=client_agent_id,
            status=JobStatus.ACCEPTED,
            price_usdc=offering.price_usdc,
            requirements=requirements,
        )

        return SkillResult(
            success=True,
            output=f"Job '{job_id}' accepted from agent '{client_agent_id}'.",
            data={
                "job_id": job_id,
                "status": job.status,
                "price_usdc": job.price_usdc,
                "sla_hours": offering.sla_hours,
            },
        )

    def submit_deliverable(
        self,
        job_id: str,
        deliverable_content: str,
        deliverable_url: str,
    ) -> SkillResult:
        """
        Submit work deliverable for a job.
        Creates DeliverableMemo — client signs to release escrow.
        """
        job = self._active_jobs.get(job_id)
        if not job:
            return SkillResult(
                success=False,
                output="",
                error=f"Active job '{job_id}' not found.",
            )

        if not deliverable_content or not deliverable_url:
            return SkillResult(
                success=False,
                output="",
                error="deliverable_content and deliverable_url are required.",
            )

        delivered_at = datetime.now(timezone.utc).isoformat()

        memo = DeliverableMemo(
            job_id=job_id,
            provider_id=self.PROVIDER_ID,
            deliverable_hash=str(hash(deliverable_content)),
            deliverable_url=deliverable_url,
            summary=deliverable_content[:200],
            delivered_at=delivered_at,
        )

        job.status = JobStatus.DELIVERED
        job.deliverable = deliverable_content
        job.delivered_at = delivered_at

        db.upsert_acp_job(
            job_id=job_id,
            offering_id=job.offering_id,
            client_agent_id=job.client_agent_id,
            status=JobStatus.DELIVERED,
            price_usdc=job.price_usdc,
            deliverable=deliverable_content[:500],
            deliverable_url=deliverable_url,
            delivered_at=delivered_at,
        )

        return SkillResult(
            success=True,
            output=f"Deliverable submitted for job '{job_id}'. Awaiting client approval.",
            data={
                "job_id": job_id,
                "status": job.status,
                "deliverable_url": deliverable_url,
                "delivered_at": delivered_at,
                "memo_hash": memo.deliverable_hash,
                "next_step": "client_or_evaluator_must_sign_to_release_escrow",
            },
        )

    def complete_job(self, job_id: str) -> SkillResult:
        """
        Mark job as completed after client approval.
        USDC released from escrow on-chain.
        """
        job = self._active_jobs.get(job_id)
        if not job:
            return SkillResult(
                success=False,
                output="",
                error=f"Active job '{job_id}' not found.",
            )

        if job.status != JobStatus.DELIVERED:
            return SkillResult(
                success=False,
                output="",
                error=f"Job must be in DELIVERED status. Current: {job.status}",
            )

        job.status = JobStatus.COMPLETED
        self._completed_jobs.append(job)
        del self._active_jobs[job_id]

        db.upsert_acp_job(
            job_id=job_id,
            offering_id=job.offering_id,
            client_agent_id=job.client_agent_id,
            status=JobStatus.COMPLETED,
            price_usdc=job.price_usdc,
            deliverable=job.deliverable[:500] if job.deliverable else None,
            delivered_at=job.delivered_at,
        )

        return SkillResult(
            success=True,
            output=f"Job '{job_id}' completed. ${job.price_usdc} USDC released.",
            data={
                "job_id": job_id,
                "status": JobStatus.COMPLETED,
                "usdc_earned": job.price_usdc,
                "total_completed": len(self._completed_jobs),
            },
        )

    # -------------------------------------------------------------------------
    # Direct execution — the primary interface for running any offering
    # -------------------------------------------------------------------------

    def execute_offering(self, offering_id: str, requirements: dict[str, Any]) -> SkillResult:
        """
        Execute any of the 32 ACP offerings directly.

        This is the primary interface — accepts an offering_id and a
        requirements dict, routes to the correct execution engine method,
        and returns a SkillResult with the deliverable data.

        Usage:
            result = acp.execute_offering(
                "iclone-research-quick-v1",
                {"query": "What is Base blockchain?"}
            )
        """
        offering = self._offerings.get(offering_id)
        if not offering:
            return SkillResult(
                success=False,
                output="",
                error=f"Unknown offering: '{offering_id}'",
            )

        if not offering.active:
            return SkillResult(
                success=False,
                output="",
                error=f"Offering '{offering_id}' is currently inactive.",
            )

        # Validate required fields
        missing = [r for r in offering.requirements if r not in requirements]
        if missing:
            return SkillResult(
                success=False,
                output="",
                error=f"Missing required fields: {missing}",
            )

        return self._engine.execute(offering_id, requirements)

    # -------------------------------------------------------------------------
    # Stats & reputation
    # -------------------------------------------------------------------------

    def get_provider_stats(self) -> SkillResult:
        """Return iCLONE ACP provider statistics."""
        total_earned = sum(j.price_usdc for j in self._completed_jobs)

        return SkillResult(
            success=True,
            output=f"iCLONE ACP Stats — {len(self._completed_jobs)} jobs completed",
            data={
                "provider_id": self.PROVIDER_ID,
                "active_offerings": len(self.list_offerings()),
                "active_jobs": len(self._active_jobs),
                "completed_jobs": len(self._completed_jobs),
                "total_usdc_earned": total_earned,
                "reputation_standard": "ERC-8004",
            },
        )
