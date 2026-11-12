"""Logical role contracts, not claims of seven deployed autonomous cloud agents."""
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class AgentContract:
    id: str
    name: str
    responsibility: str
    instruction_file: str
    permissions: tuple
    may_approve_publication: bool = False


AGENTS = (
    AgentContract("CREATIVE_DIRECTOR", "Creative Director", "Strategy, topic mix, versioned briefs and owner-review handoff", "agents/creative_director.md", ("plan", "draft", "review_handoff")),
    AgentContract("COFFEE_RESEARCH", "Coffee Research Agent", "Source-backed coffee facts and owner-confirmed product information", "agents/coffee_research.md", ("research", "evidence_review")),
    AgentContract("SCRIPTWRITER", "Scriptwriting Agent", "Indonesian hooks, narration, caption chunks and shot lists", "agents/scriptwriting.md", ("script_draft", "version")),
    AgentContract("VISUAL_DIRECTOR", "Visual Director Agent", "Original reusable 3D character/environment instructions and canonical asset checks", "agents/visual_director.md", ("visual_draft", "asset_review")),
    AgentContract("ANIMATION", "Animation Agent", "Local headless Blender rendering; optional manually imported animation", "agents/animation.md", ("local_render", "manual_import")),
    AgentContract("AUDIO_EDIT", "Audio & Editing Agent", "Local Indonesian TTS, captions, original SFX and FFmpeg delivery", "agents/audio_editing.md", ("local_tts", "edit", "technical_qa")),
    AgentContract("PERFORMANCE", "Performance Agent", "Observed retention, reach, saves, shares, completion and attributed sales", "agents/performance.md", ("metrics_import", "read_only_analysis")),
)


def registry():
    return {"runtime": "local modular workflow; model drafting optional and disabled by default", "deployed": False,
            "publication_authority": "explicit human owner only", "agents": [asdict(agent) for agent in AGENTS]}
