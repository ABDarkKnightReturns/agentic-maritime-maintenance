import os
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

claude_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

VESSEL = "MV-Callisto"
VESSEL_IMO = "IMO 9234567"

# Model per agent — Haiku for high-frequency, Sonnet for analysis, Opus for synthesis
AGENT_MODELS = {
    "realtime_watchkeeper": "claude-haiku-4-5",
    "deep_diagnostics":     "claude-sonnet-4-6",
    "maintenance_planner":  "claude-sonnet-4-6",
    "ism_compliance":       "claude-sonnet-4-6",
    "fleet_intelligence":   "claude-opus-4-7",
}
