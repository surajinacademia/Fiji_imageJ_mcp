"""Map common Java/JVM failures to short agent-facing hints (plan §8)."""

from __future__ import annotations


def friendly_java_hint(exc: BaseException) -> str | None:
    """Return a one-line hint if ``exc`` looks like a known Java-side failure."""
    name = type(exc).__name__
    text = f"{name} {exc!s}".lower()

    if "outofmemory" in text or "out of memory" in text:
        return (
            "Java heap ran out of memory. Close unused images in Fiji, increase JVM -Xmx, "
            "or process smaller crops, then retry."
        )
    if "headless" in text:
        return (
            "This operation needs AWT/GUI. Start the server with FIJI_MODE=gui (or smart with a display), "
            "or avoid GUI-only plugins in headless mode."
        )
    if "noclassdeffound" in text or "classnotfound" in text:
        return (
            "A Java class was not found (missing plugin or wrong Fiji install). "
            "Confirm FIJI_PATH points to a full Fiji.app with update sites enabled."
        )
    if "illegalargument" in text and "null" in text:
        return "ImageJ rejected null/invalid arguments. Check macro parameters and that the expected image is active."
    if "arrayindex" in text or "indexoutofbounds" in text:
        return (
            "An index was out of range (empty ROI, wrong slice, or empty Results table). "
            "Verify dimensions and selections before retrying."
        )
    return None
