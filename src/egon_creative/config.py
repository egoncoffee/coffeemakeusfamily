from dataclasses import dataclass
import os
import math
from pathlib import Path
import shutil


@dataclass(frozen=True)
class Settings:
    state_dir: Path
    max_cost_idr: float = 25000.0
    watts_estimate: float = 300.0
    tariff_idr_kwh: float = 3000.0
    max_job_seconds: int = 3600
    blender: str = "blender"
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    tts_voice: str = "Damayanti"
    animation_fps: int = 24
    output_fps: int = 24
    render_engine: str = "EEVEE"

    def __post_init__(self):
        if not 0 < self.max_cost_idr <= 25000:
            raise ValueError("Video ceiling must be positive and at most IDR 25,000")
        if not all(math.isfinite(x) and x > 0 for x in [self.watts_estimate, self.tariff_idr_kwh, self.max_job_seconds]):
            raise ValueError("Power estimate, tariff and deadline must be positive")
        if self.animation_fps < 1 or self.output_fps < self.animation_fps:
            raise ValueError("Invalid animation/output frame rate")
        if self.render_engine not in {"EEVEE", "WORKBENCH"}:
            raise ValueError("Unknown local Blender engine")

    @property
    def db_path(self):
        return self.state_dir / "production.sqlite3"

    @property
    def reserved_local_idr(self):
        return self.watts_estimate / 1000 * self.tariff_idr_kwh * self.max_job_seconds / 3600

    @classmethod
    def from_env(cls):
        fallback = Path.home() / ".local/share/egon-creative"
        blender_candidates = [
            os.environ.get("EGON_BLENDER"), shutil.which("blender"),
            str(Path.home() / ".codex/tools/Blender.app/Contents/MacOS/Blender"),
            "/Applications/Blender.app/Contents/MacOS/Blender",
        ]
        blender = next((p for p in blender_candidates if p and Path(p).is_file()), "blender")
        return cls(
            state_dir=Path(os.environ.get("EGON_VIDEO_STATE_DIR", str(fallback))).expanduser().resolve(),
            max_cost_idr=float(os.environ.get("EGON_VIDEO_MAX_COST_IDR", "25000")),
            watts_estimate=float(os.environ.get("EGON_POWER_WATTS_ESTIMATE", "300")),
            tariff_idr_kwh=float(os.environ.get("EGON_TARIFF_IDR_KWH_ESTIMATE", "3000")),
            max_job_seconds=int(os.environ.get("EGON_VIDEO_DEADLINE_SECONDS", "3600")),
            blender=blender,
            ffmpeg=os.environ.get("EGON_FFMPEG", "ffmpeg"),
            ffprobe=os.environ.get("EGON_FFPROBE", "ffprobe"),
            tts_voice=os.environ.get("EGON_TTS_VOICE", "Damayanti"),
            render_engine=os.environ.get("EGON_RENDER_ENGINE", "EEVEE"),
        )
