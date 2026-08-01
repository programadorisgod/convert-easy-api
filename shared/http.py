"""HTTP helpers shared across controllers."""

import re
from pathlib import Path

# Characters that break HTTP headers (CR/LF → header injection) or the
# Content-Disposition filename="..." quoting.
_UNSAFE_FILENAME_RE = re.compile(r"[\r\n\x00-\x1f\x7f\"\\]")


def safe_download_filename(filename: str | None, fallback: str = "download") -> str:
    """Return a header-safe file name: basename only, no control chars/CRLF.

    A user-controlled file name must never reach a response header raw:
    CR/LF would inject arbitrary headers, quotes would break the
    Content-Disposition quoting. Also strips directory components so a
    name like ``../../etc/passwd`` cannot leak paths to the client.
    """
    if not filename:
        return fallback

    name = Path(filename).name
    name = _UNSAFE_FILENAME_RE.sub("", name).strip(" .")
    return name or fallback
