"""
iCLONE — Production ACP Server (CLI-backed)

Architecture:
  acp events listen → events.jsonl
  drain loop (5s) → route by availableTools
  setBudget  → acp provider set-budget
  submit     → execute_offering() → acp provider submit
  Supabase   → record every state transition

Run:
  ~/Desktop/AI/iclone/venv312/bin/python3.12 agent/server.py
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path.home() / ".env.local")
load_dotenv(Path(__file__).parent.parent / ".env", override=False)

sys.path.insert(0, str(Path(__file__).parent))

from iclone.skills.acp_skill import ACPSkill
from iclone import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("iclone.server")

EVENTS_FILE = Path("/tmp/iclone-events.jsonl")
CHAIN_ID = 8453  # Base mainnet
POLL_INTERVAL = 5  # seconds

# acp-cli: Homebrew on Mac, npm global on Linux
_ACP_CANDIDATES = [
    "/opt/homebrew/bin/acp",   # macOS Apple Silicon
    "/usr/local/bin/acp",      # macOS Intel / Linux npm global
    "/usr/bin/acp",            # Linux system install
]
ACP_BIN = next((p for p in _ACP_CANDIDATES if Path(p).exists()), "acp")


def acp(*args: str, check: bool = True) -> dict[str, Any]:
    """Run an acp-cli command and return parsed JSON output."""
    cmd = [ACP_BIN, *args, "--json"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout.strip() or result.stderr.strip()
        if not output:
            return {}
        parsed = json.loads(output)
        if check and result.returncode != 0 and "error" in parsed:
            raise RuntimeError(f"acp {' '.join(args)}: {parsed['error']}")
        return parsed
    except json.JSONDecodeError:
        logger.error("acp %s → non-JSON output: %s", " ".join(args), result.stdout[:200])
        return {}
    except subprocess.TimeoutExpired:
        logger.error("acp %s timed out", " ".join(args))
        return {}


def start_listener() -> subprocess.Popen:
    """Start the event listener as a background process."""
    EVENTS_FILE.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [ACP_BIN, "events", "listen", "--output", str(EVENTS_FILE), "--json"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info("Event listener started (PID %d) → %s", proc.pid, EVENTS_FILE)
    return proc


def drain_events(limit: int = 20) -> list[dict]:
    """Drain pending events from the file. Returns list of event dicts."""
    if not EVENTS_FILE.exists():
        return []
    result = acp("events", "drain", "--file", str(EVENTS_FILE), "--limit", str(limit), check=False)
    return result.get("events", [])


class ICloneACPServer:
    def __init__(self):
        self.skill = ACPSkill()
        self.offerings = self._load_offerings()
        # Per-job state: job_id → {requirements, offering_id, chain_id}
        self.job_state: dict[str, dict] = {}
        self.jobs_processed = 0
        self.jobs_failed = 0

    def _load_offerings(self) -> dict[str, dict]:
        """Load offerings by name (CLI uses name, not id)."""
        offerings_path = Path(__file__).parent.parent / "published_offerings.json"
        if not offerings_path.exists():
            return {}
        data = json.loads(offerings_path.read_text())
        # Index by both offering_id and name for flexible lookup
        result = {}
        for o in data.get("published", []):
            result[o["offering_id"]] = o
            # Normalize CLI offering name → offering_id mapping
            cli_name = o["offering_id"].replace("iclone-", "").replace("-v1", "").replace("-", "_")
            result[cli_name] = o
        return result

    def _get_offering_by_name(self, name: str) -> dict | None:
        """Look up offering by CLI name (camelCase or snake_case)."""
        # Direct lookup
        if name in self.offerings:
            return self.offerings[name]
        # Try ACPSkill's internal registry
        acp_off = self.skill._offerings.get(name)
        if acp_off:
            return {"price_usdc": acp_off.price_usdc, "offering_id": name}
        # Fuzzy: strip iclone prefix, lowercase
        normalized = name.lower().replace("iclone", "").strip("-_")
        for key, val in self.offerings.items():
            if normalized in key.lower():
                return val
        return None

    def handle_event(self, event: dict) -> None:
        job_id = str(event.get("jobId", ""))
        chain_id = int(event.get("chainId", CHAIN_ID))
        status = event.get("status", "")
        roles = event.get("roles", [])
        tools = event.get("availableTools", [])
        entry = event.get("entry", {})

        if "provider" not in roles:
            return  # not our job

        logger.info("Event — job: %s | status: %s | tools: %s", job_id, status, tools)

        if "setBudget" in tools:
            self._handle_set_budget(job_id, chain_id, entry)
        elif "submit" in tools:
            self._handle_submit(job_id, chain_id, entry)
        elif status in ("completed", "rejected", "expired"):
            self._handle_terminal(job_id, status)

    def _handle_set_budget(self, job_id: str, chain_id: int, entry: dict) -> None:
        """Set budget = offering price, record job to Supabase."""
        # Extract requirement from entry message
        content_raw = entry.get("content", "{}")
        try:
            content = json.loads(content_raw) if isinstance(content_raw, str) else content_raw
        except json.JSONDecodeError:
            content = {"raw": content_raw}

        offering_name = content.get("offering_id", content.get("offeringName", ""))
        requirements = content.get("requirements", content)

        offering = self._get_offering_by_name(offering_name) if offering_name else None
        price = offering["price_usdc"] if offering else 0.25  # default
        offering_id = offering["offering_id"] if offering else offering_name

        self.job_state[job_id] = {
            "requirements": requirements,
            "offering_id": offering_id,
            "chain_id": chain_id,
            "price_usdc": price,
        }

        logger.info("Setting budget for job %s: $%.2f (offering: %s)", job_id, price, offering_id)
        result = acp(
            "provider", "set-budget",
            "--job-id", job_id,
            "--amount", str(price),
            "--chain-id", str(chain_id),
            check=False,
        )

        if result.get("success"):
            logger.info("Budget set for job %s", job_id)
            db.upsert_acp_job(
                job_id=job_id,
                offering_id=offering_id,
                client_agent_id=entry.get("clientAddress", ""),
                status="accepted",
                price_usdc=price,
                requirements=requirements,
            )
        else:
            logger.error("Failed to set budget for job %s: %s", job_id, result)

    def _handle_submit(self, job_id: str, chain_id: int, entry: dict) -> None:
        """Execute skill and submit deliverable."""
        state = self.job_state.get(job_id, {})
        offering_id = state.get("offering_id", "")
        requirements = state.get("requirements", {})
        price_usdc = state.get("price_usdc", 0.0)
        client_address = entry.get("clientAddress", "")

        logger.info("Executing job %s — offering: %s", job_id, offering_id)

        result = self.skill.execute_offering(offering_id, requirements)

        if not result.success:
            logger.error("Execution failed for job %s: %s", job_id, result.error)
            self.jobs_failed += 1
            db.upsert_acp_job(
                job_id=job_id,
                offering_id=offering_id,
                client_agent_id=client_address,
                status="disputed",
                price_usdc=price_usdc,
                error_message=result.error,
            )
            # Submit error message so client knows
            acp(
                "provider", "submit",
                "--job-id", job_id,
                "--deliverable", json.dumps({"error": result.error, "status": "failed"}),
                "--chain-id", str(chain_id),
                check=False,
            )
            return

        deliverable = json.dumps(result.data, ensure_ascii=False)

        sub = acp(
            "provider", "submit",
            "--job-id", job_id,
            "--deliverable", deliverable[:8000],
            "--chain-id", str(chain_id),
            check=False,
        )

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        if sub.get("success"):
            logger.info("Deliverable submitted for job %s", job_id)
            self.jobs_processed += 1
            db.upsert_acp_job(
                job_id=job_id,
                offering_id=offering_id,
                client_agent_id=client_address,
                status="delivered",
                price_usdc=price_usdc,
                deliverable=deliverable[:500],
                delivered_at=now,
            )
        else:
            logger.error("Submit failed for job %s: %s", job_id, sub)
            self.jobs_failed += 1
            db.upsert_acp_job(
                job_id=job_id,
                offering_id=offering_id,
                client_agent_id=client_address,
                status="disputed",
                price_usdc=price_usdc,
                error_message=str(sub),
            )

        logger.info(
            "Job %s done — processed: %d | failed: %d",
            job_id, self.jobs_processed, self.jobs_failed,
        )

    def _handle_terminal(self, job_id: str, status: str) -> None:
        state = self.job_state.pop(job_id, {})
        if status == "completed":
            logger.info("Job %s completed — payment released", job_id)
            db.upsert_acp_job(
                job_id=job_id,
                offering_id=state.get("offering_id", ""),
                client_agent_id="",
                status="completed",
                price_usdc=state.get("price_usdc", 0.0),
                usdc_earned=state.get("price_usdc", 0.0),
            )
        else:
            logger.info("Job %s ended with status: %s", job_id, status)

    def run(self) -> None:
        logger.info("Starting iCLONE ACP Server (CLI-backed)...")

        # Verify CLI auth
        whoami = acp("agent", "whoami", check=False)
        if "error" in whoami:
            logger.error("acp agent whoami failed — run: acp configure && acp agent use")
            sys.exit(1)

        agent_name = whoami.get("name", "?")
        wallet = whoami.get("walletAddress", "?")
        offering_count = len(whoami.get("offerings", []))
        logger.info(
            "Agent: %s | Wallet: %s | Offerings: %d",
            agent_name, wallet, offering_count,
        )

        listener = start_listener()
        time.sleep(2)  # let listener initialise

        logger.info(
            "iCLONE LIVE — polling every %ds | wallet: %s",
            POLL_INTERVAL, wallet,
        )

        try:
            while True:
                # Restart listener if it died
                if listener.poll() is not None:
                    logger.warning("Event listener died — restarting...")
                    listener = start_listener()
                    time.sleep(2)

                events = drain_events()
                for event in events:
                    try:
                        self.handle_event(event)
                    except Exception as e:
                        logger.error("Unhandled error processing event: %s", e, exc_info=True)

                time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            listener.terminate()


if __name__ == "__main__":
    server = ICloneACPServer()
    server.run()
