#!/usr/bin/env python3
"""
RegLens CLI — connects to the RegLens API.
Streams analysis results, shows node progress, handles HITL prompts.
"""
from __future__ import annotations
import json, asyncio, aiohttp, argparse, sys
from typing import List, Dict, Any


class Colors:
    BLUE    = '\033[94m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    RED     = '\033[91m'
    MAGENTA = '\033[95m'
    CYAN    = '\033[96m'
    WHITE   = '\033[97m'
    BOLD    = '\033[1m'
    END     = '\033[0m'


NODE_LABELS = {
    "discover":  "🔍 Discovering corpus",
    "retrieve":  "📚 Retrieving documents",
    "detect":    "🔎 Detecting sludge",
    "validate":  "✓  Validating citations",
    "hitl":      "👤 Awaiting expert review",
    "report":    "📝 Generating report",
    "fallback":  "⚠  Preliminary report",
}


class RegLensCLI:

    def __init__(self, base_url: str = "http://localhost:8058", token: str = ""):
        self.base_url   = base_url.rstrip("/")
        self.token      = token
        self.session_id: str | None = None
        # Matches the API's dev-mode identity (REGLENS_USER_ID default)
        self.user_id    = "00000000-0000-0000-0000-000000000001"

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _session_id(self) -> str:
        if not self.session_id:
            import uuid
            self.session_id = f"{self.user_id}~{uuid.uuid4()}"
        return self.session_id

    async def health(self) -> bool:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"{self.base_url}/health",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        ok   = data.get("status") == "healthy"
                        c    = Colors.GREEN if ok else Colors.YELLOW
                        print(f"{c}● API {data.get('status')}{Colors.END}")
                        return ok
                    return False
        except Exception as e:
            print(f"{Colors.RED}✗ Cannot reach {self.base_url}: {e}{Colors.END}")
            return False

    async def show_corpus(self) -> None:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"{self.base_url}/api/reglens/corpus",
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        print(f"\n{Colors.CYAN}{Colors.BOLD}Corpus Map{Colors.END}")
                        print(f"  Documents : {data.get('document_count', 0)}")
                        print(f"  Bodies    : {', '.join(data.get('regulatory_bodies', []))}")
                        print(f"  Domains   : {', '.join(data.get('domains', []))}")
                        print(f"  Types     : {', '.join(data.get('document_types', []))}")
                        print(f"  Summary   : {data.get('coverage_summary', '')}\n")
                    else:
                        print(f"{Colors.YELLOW}Could not fetch corpus map (HTTP {r.status}){Colors.END}")
        except Exception as e:
            print(f"{Colors.RED}Corpus fetch error: {e}{Colors.END}")

    async def analyze(self, query: str, exhaustive: bool = False) -> None:
        import uuid
        sid = self._session_id()
        payload = {
            "query":      query,
            "session_id": sid,
            "request_id": str(uuid.uuid4()),
            "exhaustive": exhaustive,
        }
        if exhaustive:
            print(f"{Colors.YELLOW}Exhaustive mode: sweeping the full corpus "
                  f"(one LLM digest per document — slower, complete coverage){Colors.END}")

        print(f"\n{Colors.BOLD}RegLens:{Colors.END}")
        hitl_triggered = False

        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{self.base_url}/api/reglens/analyze",
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as resp:
                    if resp.status != 200:
                        print(f"{Colors.RED}API {resp.status}: {await resp.text()}{Colors.END}")
                        return

                    async for raw in resp.content:
                        line = raw.decode("utf-8").strip()
                        if not line.startswith("data: "):
                            continue
                        try:
                            data = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue

                        t = data.get("type")

                        if t == "node":
                            label = NODE_LABELS.get(data.get("node", ""), data.get("node", ""))
                            print(f"\n{Colors.CYAN}{label}...{Colors.END}")

                        elif t == "corpus_map":
                            cm = data.get("data", {})
                            print(
                                f"  {Colors.WHITE}Corpus: {cm.get('coverage_summary', '')}{Colors.END}"
                            )

                        elif t == "findings":
                            n = data.get("count", 0)
                            print(f"  {Colors.YELLOW}Found {n} potential sludge findings{Colors.END}")

                        elif t == "text":
                            print(data.get("content", ""), end="", flush=True)

                        elif t == "audit":
                            print(
                                f"  {Colors.WHITE}{data.get('entry', '')}{Colors.END}"
                            )

                        elif t == "hitl_required":
                            hitl_triggered = True
                            break

                        elif t == "end":
                            break

                        elif t == "error":
                            print(
                                f"\n{Colors.RED}Error: {data.get('content', 'unknown')}{Colors.END}"
                            )
                            return

        except aiohttp.ClientError as e:
            print(f"{Colors.RED}Connection error: {e}{Colors.END}")
            return

        if hitl_triggered:
            # Show the reviewer exactly what they are deciding on —
            # findings with verbatim citations, sources, and confidence.
            await self.show_review_findings()
        else:
            print(f"\n{Colors.BLUE}{'─'*60}{Colors.END}")

    async def show_review_findings(self) -> None:
        """Render the pending findings for the HITL reviewer."""
        sid = self._session_id()
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"{self.base_url}/api/reglens/findings/{sid}",
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as r:
                    if r.status != 200:
                        print(f"{Colors.RED}Could not fetch findings (HTTP {r.status}){Colors.END}")
                        return
                    data = await r.json()
        except Exception as e:
            print(f"{Colors.RED}Findings fetch error: {e}{Colors.END}")
            return

        findings = data.get("findings", [])
        summary  = data.get("detection_summary", "")

        print(f"\n{Colors.YELLOW}{Colors.BOLD}{'='*64}")
        print("  EXPERT REVIEW REQUIRED")
        print(f"{'='*64}{Colors.END}")
        if summary:
            print(f"\n{Colors.WHITE}Summary: {summary}{Colors.END}")
        print(f"{Colors.WHITE}Validation: {data.get('validation_result', '?')} "
              f"after {data.get('iteration_count', 0)} correction cycle(s){Colors.END}\n")

        for f in findings:
            sev   = f.get("severity", "medium")
            color = Colors.RED if sev == "high" else Colors.YELLOW if sev == "medium" else Colors.WHITE
            conf  = f.get("confidence_score", 0.0)
            print(f"{color}{Colors.BOLD}[{f.get('finding_id', '?')}] {f.get('title', '')}{Colors.END}")
            print(f"  Type: {f.get('sludge_type', '?')} | Severity: {sev} | "
                  f"Confidence (evidence-based): {conf:.2f} | "
                  f"Action: {f.get('recommended_action', '?')}")
            print(f"  {f.get('description', '')[:300]}")
            print(f"  Rationale: {f.get('rationale', '')[:300]}")

            def _print_citations(label: str, citations: list) -> None:
                if not citations:
                    return
                print(f"  {Colors.CYAN}{label}:{Colors.END}")
                for c in citations:
                    if isinstance(c, dict):
                        doc   = c.get("document_title", "?")
                        ref   = c.get("source_reference", "")
                        quote = c.get("verbatim_quote", "")[:200]
                        loc   = f"{doc}{' — ' + ref if ref else ''}"
                        print(f"    - {loc}")
                        print(f"      \"{quote}\"")
                    else:
                        print(f"    - {str(c)[:200]}")

            _print_citations("Source provisions", f.get("source_provisions", []))
            _print_citations("Overlapping provisions", f.get("overlapping_provisions", []))
            print()

        print(
            f"{Colors.YELLOW}Your decision:\n"
            f"  approve [notes]  — publish these findings and generate the report\n"
            f"  reject  [notes]  — discard the analysis\n"
            f"  refine  [notes]  — send your feedback back to the analyst for another\n"
            f"                     pass (you will be asked whether to escalate to an\n"
            f"                     exhaustive full-corpus sweep){Colors.END}"
        )

    async def approve(self, action: str, notes: str = "", exhaustive: bool = False) -> None:
        """Send a HITL decision: approve | reject | refine."""
        sid = self._session_id()
        payload = {
            "session_id":     sid,
            "action":         action,
            "approved":       action == "approve",
            "reviewer_notes": notes,
            "exhaustive":     exhaustive,
        }
        timeout = 600 if action == "refine" else 120
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{self.base_url}/api/reglens/approve",
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as r:
                    if r.status != 200:
                        print(f"{Colors.RED}Decision failed (HTTP {r.status}): {await r.text()}{Colors.END}")
                        return
                    if action == "approve":
                        print(f"{Colors.GREEN}Analysis approved.{Colors.END}")
                        print(f"{Colors.CYAN}Generating report... use 'report' to retrieve it.{Colors.END}")
                    elif action == "reject":
                        print(f"{Colors.RED}Analysis rejected — nothing published.{Colors.END}")
                    else:
                        print(f"{Colors.CYAN}Feedback sent — the analyst re-ran the analysis"
                              f"{' with a full-corpus sweep' if exhaustive else ''}.{Colors.END}")
                        # The refined findings are waiting at the HITL gate again
                        await self.show_review_findings()
        except Exception as e:
            print(f"{Colors.RED}Decision error: {e}{Colors.END}")

    async def refine(self, notes: str = "") -> None:
        """Send the analysis back with reviewer feedback for another pass."""
        if not notes:
            notes = input("  What should the analyst look at differently? ").strip()
        if not notes:
            print(f"{Colors.YELLOW}Refine needs feedback to act on.{Colors.END}")
            return
        answer = input("  Escalate to exhaustive full-corpus sweep? [y/N] ").strip().lower()
        exhaustive = answer in ("y", "yes")
        print(f"{Colors.CYAN}Re-running analysis with your feedback — this can take a few minutes...{Colors.END}")
        await self.approve("refine", notes, exhaustive=exhaustive)

    async def get_report(self) -> None:
        sid = self._session_id()
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"{self.base_url}/api/reglens/session/{sid}/report",
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        report = data.get("final_report", "")
                        if report:
                            print(f"\n{Colors.BOLD}Final Report:{Colors.END}\n")
                            print(report)
                        else:
                            print(f"{Colors.YELLOW}Report not yet available.{Colors.END}")
                    else:
                        print(f"{Colors.RED}Could not fetch report (HTTP {r.status}){Colors.END}")
        except Exception as e:
            print(f"{Colors.RED}Report fetch error: {e}{Colors.END}")

    async def precheck(self, draft_title: str) -> None:
        """
        Policy & Regulation: Pre-rulemaking check.
        Prompts for draft text then runs check against existing corpus.
        """
        import uuid
        print(f"\n{Colors.CYAN}Pre-rulemaking check: '{draft_title}'{Colors.END}")
        print(f"{Colors.WHITE}Paste draft text (end with a line containing only '---'):{Colors.END}")

        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "---":
                    break
                lines.append(line)
            except EOFError:
                break

        draft_text = "\n".join(lines).strip()
        if not draft_text:
            print(f"{Colors.YELLOW}No draft text provided.{Colors.END}")
            return

        sid     = self._session_id()
        payload = {
            "draft_title": draft_title,
            "draft_text":  draft_text,
            "session_id":  sid,
            "request_id":  str(uuid.uuid4()),
        }

        print(f"\n{Colors.BOLD}Pre-rulemaking Analysis:{Colors.END}")

        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{self.base_url}/api/reglens/precheck",
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        print(f"{Colors.RED}API {resp.status}: {await resp.text()}{Colors.END}")
                        return

                    async for raw in resp.content:
                        line = raw.decode("utf-8").strip()
                        if not line.startswith("data: "):
                            continue
                        try:
                            data = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue

                        t = data.get("type")
                        if t == "progress":
                            print(data.get("content", ""), end="", flush=True)
                        elif t == "result":
                            self._print_precheck_result(data.get("data", {}))
                        elif t == "end":
                            break
                        elif t == "error":
                            print(f"\n{Colors.RED}Error: {data.get('content')}{Colors.END}")

        except aiohttp.ClientError as e:
            print(f"{Colors.RED}Connection error: {e}{Colors.END}")

    def _print_precheck_result(self, result: dict) -> None:
        total    = result.get("total_conflicts", 0)
        high     = result.get("high_priority", 0)
        score    = result.get("confidence_score", 0.0)
        summary  = result.get("summary", "")
        findings = result.get("findings", [])

        print(f"\n\n{Colors.CYAN}{Colors.BOLD}Pre-rulemaking Check Results{Colors.END}")
        print(f"  Conflicts found : {total} ({high} high priority)")
        print(f"  Confidence      : {score:.2f}")
        print(f"  Summary         : {summary}\n")

        for f in findings:
            sev   = f.get("severity", "medium")
            color = Colors.RED if sev == "high" else Colors.YELLOW if sev == "medium" else Colors.WHITE
            print(f"  {color}[{f.get('finding_id', '?')}] {f.get('title', '')}{Colors.END}")
            print(f"  Action: {f.get('recommended_action', '')} | {f.get('rationale', '')[:100]}")
            print()
        print(f"{Colors.BLUE}{'-'*60}{Colors.END}")

    async def compare_interactive(self) -> None:
        """
        Cross-border comparison — interactive input for two frameworks.
        """
        import uuid
        print(f"\n{Colors.CYAN}Cross-Border Regulatory Comparison{Colors.END}")
        print(f"{Colors.WHITE}(Tip: run 'corpus' first to see available regulatory_body values){Colors.END}\n")

        label_a = input("Framework A label (e.g. 'Bank of Namibia AML Framework'): ").strip()
        body_a  = input("Framework A regulatory_body filter (e.g. 'BoN'): ").strip()
        label_b = input("Framework B label (e.g. 'FATF Recommendations'): ").strip()
        body_b  = input("Framework B regulatory_body filter (e.g. 'FATF'): ").strip()
        topic   = input("Topic to compare (e.g. 'customer due diligence'): ").strip()

        if not all([label_a, label_b, topic]):
            print(f"{Colors.YELLOW}Labels and topic are required.{Colors.END}")
            return

        sid     = self._session_id()
        payload = {
            "label_a":    label_a,
            "label_b":    label_b,
            "filter_a":   {"regulatory_body": body_a} if body_a else {},
            "filter_b":   {"regulatory_body": body_b} if body_b else {},
            "topic":      topic,
            "session_id": sid,
            "request_id": str(uuid.uuid4()),
        }

        print(f"\n{Colors.BOLD}Cross-Border Analysis:{Colors.END}")

        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{self.base_url}/api/reglens/compare",
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=180),
                ) as resp:
                    if resp.status != 200:
                        print(f"{Colors.RED}API {resp.status}: {await resp.text()}{Colors.END}")
                        return

                    async for raw in resp.content:
                        line = raw.decode("utf-8").strip()
                        if not line.startswith("data: "):
                            continue
                        try:
                            data = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue

                        t = data.get("type")
                        if t == "progress":
                            print(data.get("content", ""), end="", flush=True)
                        elif t == "result":
                            self._print_compare_result(data.get("data", {}))
                        elif t == "end":
                            break
                        elif t == "error":
                            print(f"\n{Colors.RED}Error: {data.get('content')}{Colors.END}")

        except aiohttp.ClientError as e:
            print(f"{Colors.RED}Connection error: {e}{Colors.END}")

    def _print_compare_result(self, result: dict) -> None:
        score    = result.get("harmonisation_score", 0.0)
        total    = result.get("total_gaps", 0)
        friction = result.get("key_friction_points", [])
        recs     = result.get("coordination_recommendations", [])
        summary  = result.get("executive_summary", "")
        gaps     = result.get("gaps", [])

        if score >= 0.7:
            score_color = Colors.GREEN
        elif score >= 0.4:
            score_color = Colors.YELLOW
        else:
            score_color = Colors.RED

        print(f"\n\n{Colors.CYAN}{Colors.BOLD}Cross-Border Analysis Results{Colors.END}")
        print(f"  {result.get('label_a')} vs {result.get('label_b')}")
        print(f"  Topic              : {result.get('topic')}")
        print(f"  Harmonisation Score: {score_color}{score:.2f}{Colors.END}  (0=divergent, 1=harmonised)")
        print(f"  Gaps Found         : {total}")
        print(f"\n  {Colors.BOLD}Executive Summary:{Colors.END}")
        print(f"  {summary}\n")

        if friction:
            print(f"  {Colors.BOLD}Key Friction Points:{Colors.END}")
            for fp in friction[:5]:
                print(f"    - {fp}")

        if recs:
            print(f"\n  {Colors.BOLD}Coordination Recommendations:{Colors.END}")
            for r in recs[:5]:
                print(f"    - {r}")

        if gaps:
            high_gaps = [g for g in gaps if g.get("priority") == "high"]
            if high_gaps:
                print(f"\n  {Colors.BOLD}{Colors.RED}High Priority Gaps:{Colors.END}")
                for g in high_gaps[:5]:
                    print(f"    [{g.get('gap_id', '?')}] {g.get('description', '')[:100]}")
                    print(f"    Type: {g.get('divergence_type')} | Fix: {g.get('harmonisation_recommendation', '')[:80]}")
                    print()

        print(f"{Colors.BLUE}{'-'*60}{Colors.END}")

    async def show_usecases(self) -> None:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"{self.base_url}/api/reglens/usecases",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as r:
                    data = await r.json()
                    print(f"\n{Colors.CYAN}{Colors.BOLD}RegLens Use Cases{Colors.END}")
                    for uc in data.get("use_cases", []):
                        print(f"\n  {Colors.BOLD}{uc['title']}{Colors.END}")
                        print(f"  {uc['description']}")
                        print(f"  Endpoint : {uc['endpoint']}")
                        print(f"  Example  : {uc['example']}")
                        print(f"  Tracks   : {', '.join(uc['tracks'])}")
                    print()
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.END}")

    def show_parsers(self) -> None:
        """Show which document parsers are available locally."""
        try:
            from ingestion.parser import get_parser_status
        except ImportError:
            print(f"{Colors.YELLOW}ingestion package not importable from this directory.{Colors.END}")
            return
        status = get_parser_status()
        print(f"\n{Colors.CYAN}{Colors.BOLD}Parser Status{Colors.END}")
        print(f"  Best available : {Colors.GREEN}{status.get('best_available')}{Colors.END}")
        print(f"  LlamaParse     : {'yes' if status.get('llamaparse') else 'no'} "
              f"(installed={status.get('llamaparse_installed')} "
              f"api_key={status.get('llamaparse_api_key_set')})")
        print(f"  Docling        : {'yes' if status.get('docling') else 'no'}")
        print(f"  Plain text     : yes")
        if "warning" in status:
            print(f"\n  {Colors.YELLOW}{status['warning']}{Colors.END}")
        print()

    def _print_help(self) -> None:
        print(
            f"\n{Colors.BOLD}RegLens Commands{Colors.END}\n"
            f"  {Colors.CYAN}analyze  <query>{Colors.END}    Sludge detection (add --exhaustive for full-corpus sweep)\n"
            f"  {Colors.CYAN}precheck <title>{Colors.END}    Pre-rulemaking check (paste draft)\n"
            f"  {Colors.CYAN}compare{Colors.END}             Cross-border framework comparison\n"
            f"  {Colors.CYAN}corpus{Colors.END}              Show ingested corpus map\n"
            f"  {Colors.CYAN}usecases{Colors.END}            List all use cases and tracks\n"
            f"  {Colors.CYAN}parsers{Colors.END}             Show available document parsers\n"
            f"  {Colors.CYAN}review{Colors.END}              Show findings awaiting review (with citations)\n"
            f"  {Colors.CYAN}approve  [notes]{Colors.END}    Approve findings after HITL\n"
            f"  {Colors.CYAN}reject   [notes]{Colors.END}    Reject findings\n"
            f"  {Colors.CYAN}refine   [notes]{Colors.END}    Send feedback back for another pass (optionally exhaustive)\n"
            f"  {Colors.CYAN}report{Colors.END}              Retrieve final report\n"
            f"  {Colors.CYAN}health{Colors.END}              API health check\n"
            f"  {Colors.CYAN}clear{Colors.END}               Reset session\n"
            f"  {Colors.CYAN}exit{Colors.END}                Quit\n"
        )

    async def run(self) -> None:
        print(
            f"\n{Colors.CYAN}{Colors.BOLD}"
            f"{'='*60}\n"
            f"  RegLens — Regulatory Sludge Intelligence Agent\n"
            f"{'='*60}{Colors.END}"
        )
        print(f"{Colors.WHITE}Server: {self.base_url}{Colors.END}")
        print(
            f"{Colors.WHITE}Commands: analyze [--exhaustive] <query> | precheck <title> | compare | "
            f"review | approve | reject | refine | report | usecases | corpus | parsers | "
            f"health | clear | exit{Colors.END}\n"
        )

        if not await self.health():
            print(f"{Colors.RED}Cannot connect. Start the API first: uvicorn agent.api:app --port 8058{Colors.END}")
            return

        await self.show_corpus()

        while True:
            try:
                user_input = input(f"{Colors.BOLD}You: {Colors.END}").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{Colors.CYAN}Goodbye!{Colors.END}")
                break

            if not user_input:
                continue

            parts = user_input.split(None, 1)
            cmd   = parts[0].lower()
            rest  = parts[1] if len(parts) > 1 else ""

            match cmd:
                case "exit" | "quit":
                    print(f"{Colors.CYAN}Goodbye!{Colors.END}")
                    break
                case "health":
                    await self.health()
                case "corpus":
                    await self.show_corpus()
                case "clear":
                    self.session_id = None
                    print(f"{Colors.GREEN}✓ Session cleared{Colors.END}")
                case "approve":
                    notes = rest or input(f"  Reviewer notes (optional): ").strip()
                    await self.approve("approve", notes)
                case "reject":
                    notes = rest or input(f"  Rejection reason (optional): ").strip()
                    await self.approve("reject", notes)
                case "refine":
                    await self.refine(rest)
                case "review":
                    await self.show_review_findings()
                case "report":
                    await self.get_report()
                case "analyze":
                    if rest:
                        exhaustive = rest.startswith("--exhaustive")
                        query = rest.removeprefix("--exhaustive").strip()
                        if query:
                            await self.analyze(query, exhaustive=exhaustive)
                        else:
                            print(f"{Colors.YELLOW}Usage: analyze [--exhaustive] <query>{Colors.END}")
                    else:
                        print(f"{Colors.YELLOW}Usage: analyze [--exhaustive] <query>{Colors.END}")
                case "precheck":
                    if rest:
                        await self.precheck(rest)
                    else:
                        print(f"{Colors.YELLOW}Usage: precheck <draft title>{Colors.END}")
                case "compare":
                    await self.compare_interactive()
                case "usecases":
                    await self.show_usecases()
                case "parsers":
                    self.show_parsers()
                case "help":
                    self._print_help()
                case _:
                    # Treat as analyze query if no command matched
                    await self.analyze(user_input)


def main() -> None:
    parser = argparse.ArgumentParser(description="RegLens CLI")
    parser.add_argument("--url",   default="http://localhost:8058")
    parser.add_argument("--port",  type=int)
    parser.add_argument("--token", default="", help="REGLENS_API_TOKEN bearer token (optional in dev mode)")
    args = parser.parse_args()

    url = args.url
    if args.port:
        proto, rest = (url.split("://", 1) + [""])[:2]
        host = rest.split(":")[0].split("/")[0]
        url  = f"{proto}://{host}:{args.port}"

    try:
        asyncio.run(RegLensCLI(url, args.token).run())
    except KeyboardInterrupt:
        print(f"\n{Colors.CYAN}Goodbye!{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}CLI error: {e}{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    main()