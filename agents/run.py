"""CLI entry point for testing the Polymarket research agent.

Usage:
    python run.py                              # Built-in sample input
    python run.py --input path/to/input.json   # Custom JSON file
    echo '{"sub_events": [...]}' | python run.py --stdin
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from dotenv import load_dotenv

from research_agent import AgentConfig, ResearchAgent, ResearchInput

# ---------------------------------------------------------------------------
# Sample input for quick testing
# ---------------------------------------------------------------------------

SAMPLE_INPUT = {
    "main_event": {
        "title": "US strikes Iran by...?",
        "description": (
            "This market will resolve to Yes if the US initiates a drone, "
            "missile, or air strike on Iranian soil or any official Iranian "
            "embassy or consulate."
        ),
    },
    "sub_events": [
        {
            "title": "Khamenei out as Supreme Leader of Iran in 2026?",
            "description": (
                "Will Iran's Supreme Leader, Ali Khamenei, be removed from "
                "power for any length of time by December 31, 2026?"
            ),
        },
        {
            "title": "Khamenei out as Supreme Leader of Iran by June 30?",
            "description": (
                "Will Iran's Supreme Leader, Ali Khamenei, be removed from "
                "power for any length of time by June 30, 2026?"
            ),
        },
    ],
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Polymarket Research Agent")
    parser.add_argument("--input", type=str, help="Path to JSON input file")
    parser.add_argument(
        "--stdin", action="store_true", help="Read JSON from stdin"
    )
    parser.add_argument(
        "--model", type=str, default="gpt-5.1", help="OpenAI model to use"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Total timeout in seconds",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Path to write JSON output file (default: print to stdout)",
    )
    args = parser.parse_args()

    # Load input
    if args.stdin:
        raw = sys.stdin.read()
        input_dict = json.loads(raw)
    elif args.input:
        with open(args.input) as f:
            input_dict = json.load(f)
    else:
        print("Using built-in sample input...", file=sys.stderr)
        input_dict = SAMPLE_INPUT

    # Validate
    research_input = ResearchInput.model_validate(input_dict)

    # Configure
    config = AgentConfig(model=args.model, total_timeout=args.timeout)
    agent = ResearchAgent(config=config)

    # Log what we're doing
    n = len(research_input.sub_events)
    print(f"Researching {n} sub-event(s)...", file=sys.stderr)
    if research_input.main_event:
        print(
            f"Main event: {research_input.main_event.title}", file=sys.stderr
        )

    # Run
    result = await agent.run(research_input)

    # Output
    output_json = result.model_dump_json(indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_json + "\n")
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    asyncio.run(main())
