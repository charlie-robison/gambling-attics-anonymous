"""All LLM prompt templates for the research agent.

Centralised here for easy iteration during the hackathon.
"""

# ---------------------------------------------------------------------------
# Stage 1 – Individual research prompts (used with web_search_preview)
# ---------------------------------------------------------------------------

MAIN_EVENT_RESEARCH_PROMPT = """\
You are an expert prediction-market researcher. Your job is to produce a \
thorough, well-sourced research report on the following event.

EVENT TITLE: {title}
DESCRIPTION: {description}

Instructions:
1. Search for the LATEST news, analysis, and developments related to this \
event.  Prioritise information from the last 30 days.
2. Cover:
   - Current state of affairs and background context
   - Recent major developments or turning points
   - Key factors and variables that could change the outcome
   - Expert opinions, polls, forecasts, or official statements
   - Upcoming catalysts, deadlines, or scheduled events
3. Aim for roughly 1-2 pages of substantive research. Be thorough – a \
trader will rely on this to understand the full picture.
4. Cite every factual claim with its source URL inline.
5. Do NOT give trading advice or recommendations.
"""

SUB_EVENT_RESEARCH_PROMPT = """\
You are an expert prediction-market researcher. Your job is to produce a \
thorough, well-sourced research report on the following specific question.

QUESTION: {title}
DESCRIPTION: {description}

Instructions:
1. Search for the LATEST news and data specifically relevant to this \
question.  Prioritise information from the last 30 days.
2. Cover:
   - Direct evidence for and against each possible outcome
   - Recent developments that shift the probabilities
   - Quantitative data where available (polls, statistics, forecasts)
   - Expert or official positions on this specific question
   - Upcoming events or deadlines that could be decisive
3. Aim for roughly 1-2 pages of substantive research.
4. Cite every factual claim with its source URL inline.
5. Do NOT give trading advice or recommendations.
"""

# ---------------------------------------------------------------------------
# Stage 2 – Synthesis prompts (used WITHOUT web search, pure reasoning)
# ---------------------------------------------------------------------------

SYNTHESIS_PROMPT = """\
You are an expert prediction-market analyst. Below you will find research \
on a main event and its related sub-events. Your job is to synthesise \
everything into a structured JSON analysis.

MAIN EVENT: {main_event_title}
{main_event_description}

=== MAIN EVENT RESEARCH ===
{main_event_research_block}

=== SUB-EVENTS RESEARCH ===
{sub_events_research_block}

Return ONLY valid JSON (no markdown fences, no commentary) matching this \
exact schema:

{{
  "main_event_research": {{
    "summary": "<2-4 paragraph synthesis of the main event>",
    "key_findings": ["<finding 1>", "<finding 2>", "..."],
    "sentiment": "<very_bearish|bearish|neutral|bullish|very_bullish>",
    "sentiment_rationale": "<1-2 sentence explanation>"
  }},
  "sub_event_analyses": [
    {{
      "sub_event_id": "<id>",
      "sub_event_title": "<title>",
      "summary": "<2-4 paragraph summary>",
      "key_findings": ["<finding 1>", "..."],
      "sentiment": "<very_bearish|bearish|neutral|bullish|very_bullish>",
      "sentiment_rationale": "<explanation>"
    }}
  ],
  "relationships": [
    {{
      "sub_event_id": "<id>",
      "sub_event_title": "<title>",
      "relationship_summary": "<how this sub-event connects to the main event>",
      "influencing_news": "<what specific news/developments around this sub-event could influence the main event, and how>"
    }}
  ],
  "synthesis": "<3-5 paragraph overall narrative tying everything together>"
}}

Rules:
- Be analytical and evidence-based, never speculative.
- Base sentiment on concrete evidence from the research.
- The synthesis should give a reader the full picture at a glance.
- Do NOT provide trading advice or recommendations.
- Acknowledge uncertainty where evidence is mixed or limited.
- Every sub-event from the input MUST appear in both sub_event_analyses \
and relationships.
"""

SYNTHESIS_NO_MAIN_EVENT_PROMPT = """\
You are an expert prediction-market analyst. Below you will find research \
on several prediction-market questions. Your job is to synthesise \
everything into a structured JSON analysis.

=== MARKETS RESEARCH ===
{sub_events_research_block}

Return ONLY valid JSON (no markdown fences, no commentary) matching this \
exact schema:

{{
  "sub_event_analyses": [
    {{
      "sub_event_id": "<id>",
      "sub_event_title": "<title>",
      "summary": "<2-4 paragraph summary>",
      "key_findings": ["<finding 1>", "..."],
      "sentiment": "<very_bearish|bearish|neutral|bullish|very_bullish>",
      "sentiment_rationale": "<explanation>"
    }}
  ],
  "synthesis": "<2-4 paragraph overall narrative summarising or connecting the markets>"
}}

Rules:
- Be analytical and evidence-based.
- Base sentiment on concrete evidence.
- Do NOT provide trading advice.
- Acknowledge uncertainty where evidence is mixed.
- Every sub-event from the input MUST appear in sub_event_analyses.
"""
