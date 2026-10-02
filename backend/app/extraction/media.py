"""Video metadata via PyAV (FFmpeg bundled inside the Python package — nothing to install).

We read container facts only: duration, resolution, codec, frame rate and the recording
time the device wrote into the file. FALCON does not run face recognition (plan §52).
"""

from datetime import datetime
from typing import Any

from app.extraction.timeparse import parse_timestamp
from app.storage import local as storage


def video_metadata(key: str) -> dict[str, Any]:
    import av

    with av.open(str(storage.path_of(key))) as container:
        info: dict[str, Any] = {
            "format": container.format.name,
            "duration_s": round(container.duration / av.time_base, 2)
            if container.duration
            else None,
        }
        video = next((s for s in container.streams if s.type == "video"), None)
        if video is not None:
            info |= {
                "codec": video.codec_context.name,
                "width": video.codec_context.width,
                "height": video.codec_context.height,
                "frame_rate": float(video.average_rate) if video.average_rate else None,
            }
        info["has_audio"] = any(s.type == "audio" for s in container.streams)
        created = container.metadata.get("creation_time")
        if created:
            info["creation_time"] = created
    return info


def recording_start(info: dict[str, Any]) -> tuple[datetime, bool] | None:
    parsed = parse_timestamp(info.get("creation_time"))
    return (parsed.value, parsed.zone_known) if parsed else None
