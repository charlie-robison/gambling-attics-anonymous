"""CLI entry point for testing the risk management agent.

Usage:
    # Two separate files (how the MCP will actually call it):
    python run_risk.py --research results.json --markets sample_markets.json

    # Single combined file (everything in one JSON):
    python run_risk.py --input combined.json

    # Built-in sample (no files needed):
    python run_risk.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from dotenv import load_dotenv

from risk_management_agent import (
    RiskAgentConfig,
    RiskManagementAgent,
    RiskManagementInput,
)

# ---------------------------------------------------------------------------
# Sample data for quick testing (used when no files provided)
# ---------------------------------------------------------------------------

SAMPLE_MARKETS = {
    "main_event": {
        "title": "Will the U.S. strike Iran?",
        "description": (
            "Resolves YES if US conducts drone, missile, or air strike on "
            "Iranian soil or official Iranian embassy/consulate."
        ),
    },
    "markets": [
        {
            "id": "iran-strike-today",
            "title": "U.S. strikes Iran today (Feb 21)",
            "current_price": 0.15,
        },
        {
            "id": "iran-strike-feb22",
            "title": "U.S. strikes Iran by Feb 22",
            "current_price": 0.22,
        },
        {
            "id": "iran-strike-feb23",
            "title": "U.S. strikes Iran by Feb 23",
            "current_price": 0.28,
        },
        {
            "id": "iran-strike-feb24",
            "title": "U.S. strikes Iran by Feb 24",
            "current_price": 0.32,
        },
        {
            "id": "iran-strike-week",
            "title": "U.S. strikes Iran within 7 days (by Feb 28)",
            "current_price": 0.45,
        },
    ],
}

SAMPLE_RESEARCH = {
    "main_event_research": {
        "event_title": "US strikes Iran by...?",
        "summary": "Acutely tense environment with US force buildup and explicit strike threats.",
        "key_findings": [
            "US has reinforced military posture with carrier strike groups and 60+ jets in Jordan",
            "Trump has issued a 10-15 day nuclear deal deadline and is considering limited strikes",
            "Iran warns any attack triggers decisive region-wide retaliation",
            "Diplomacy through Oman acts as brake on immediate escalation",
            "Prediction markets price a US strike in 2026 above 50%",
        ],
        "news_links": [],
        "sentiment": "bullish",
        "sentiment_rationale": "Force posture and presidential threats indicate elevated probability.",
    },
    "sub_event_research": [],
    "relationships": [],
    "synthesis": "The crisis sits at the junction of a militarizing US posture and an embattled Iranian regime. Strike aircraft are positioned and Trump has imposed a near-term deadline. But diplomacy continues and escalation risks constrain action.",
    "research_timestamp": "2026-02-21T20:25:43+00:00",
    "disclaimer": "For informational purposes only.",
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Prediction Market Risk Management Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_risk.py --research results.json --markets sample_markets.json\n"
            "  python run_risk.py --research results.json --markets sample_markets.json -o signals.json\n"
            "  python run_risk.py   (uses built-in sample)\n"
        ),
    )

    # Two-file mode (the real workflow)
    parser.add_argument(
        "--research",
        type=str,
        help="Path to the research agent output JSON (e.g. results.json)",
    )
    parser.add_argument(
        "--markets",
        type=str,
        help="Path to the markets JSON (main_event + markets list)",
    )

    # Single-file mode (for testing / API parity)
    parser.add_argument(
        "--input",
        type=str,
        help="Path to a single combined JSON (research_output + main_event + markets)",
    )

    # Options
    parser.add_argument(
        "--model", type=str, default="gpt-5.1", help="OpenAI model to use"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="Total timeout in seconds",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Path to write JSON output (default: print to stdout)",
    )
    args = parser.parse_args()

    # ── Load input ────────────────────────────────────────────────
    if args.research and args.markets:
        # Two-file mode: research output + markets (the real workflow)
        with open(args.research) as f:
            research_output = json.load(f)
        with open(args.markets) as f:
            markets_data = json.load(f)

        input_dict = {
            "research_output": research_output,
            "main_event": markets_data["main_event"],
            "markets": markets_data["markets"],
        }

    elif args.input:
        # Single combined file
        with open(args.input) as f:
            input_dict = json.load(f)

    elif args.research and not args.markets:
        parser.error("--research requires --markets")

    elif args.markets and not args.research:
        parser.error("--markets requires --research")

    else:
        # Built-in sample
        print("Using built-in sample input...", file=sys.stderr)
        input_dict = {
            "research_output": SAMPLE_RESEARCH,
            **SAMPLE_MARKETS,
        }

    # ── Validate ──────────────────────────────────────────────────
    risk_input = RiskManagementInput.model_validate(input_dict)

    # ── Configure ─────────────────────────────────────────────────
    config = RiskAgentConfig(model=args.model, total_timeout=args.timeout)
    agent = RiskManagementAgent(config=config)

    # ── Log ───────────────────────────────────────────────────────
    n = len(risk_input.markets)
    batch_count = (n + config.batch_size - 1) // config.batch_size
    print(
        f"Analysing {n} market(s) in {batch_count} parallel batch(es)...",
        file=sys.stderr,
    )
    print(f"Main event: {risk_input.main_event.title}", file=sys.stderr)

    # ── Run ───────────────────────────────────────────────────────
    result = await agent.run(risk_input)

    # ── Output ────────────────────────────────────────────────────
    output_json = result.model_dump_json(indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_json + "\n")
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    asyncio.run(main())
