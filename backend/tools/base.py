from dataclasses import dataclass, field


@dataclass
class GeoContext:
    """Context passed through Agent Runner to all tools."""

    trace_id: str
    artifacts: list[dict] = field(default_factory=list)

    def emit_artifact(self, artifact: dict) -> str:
        """Register an artifact for the UI and return its id."""
        artifact_id = f"art_{len(self.artifacts) + 1}"
        artifact["id"] = artifact_id
        self.artifacts.append(artifact)
        return artifact_id


def safe_args_preview(args: dict, max_list: int = 10, max_str: int = 200) -> dict:
    """Truncate large args for logging (TZ:11.4)."""
    preview = {}
    for k, v in args.items():
        if isinstance(v, list) and len(v) > max_list:
            preview[k] = f"[{len(v)} items]"
        elif isinstance(v, str) and len(v) > max_str:
            preview[k] = v[:max_str] + "..."
        else:
            preview[k] = v
    return preview
