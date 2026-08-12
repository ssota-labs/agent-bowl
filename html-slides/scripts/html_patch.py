#!/usr/bin/env python3
"""Source-preserving HTML/CSS patch helpers for html-slides visual editor.

Never re-serializes the whole document. Patches only the minimal span for a
leaf text node or a style attribute on a data-region / data-part target.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path

SUPPORTED_STYLE_PROPS = (
    "color",
    "background-color",
    "font-size",
    "font-weight",
    "text-align",
    "width",
    "height",
    "padding",
    "gap",
    "border-radius",
)

THEME_START = "/* slidecraft:tokens:start */"
THEME_END = "/* slidecraft:tokens:end */"

_ATTR_RE = re.compile(
    r'([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+)))?'
)
_TAG_OPEN_RE = re.compile(r"<([A-Za-z][\w:-]*)([^>]*)>", re.DOTALL)
_TAG_CLOSE_RE = re.compile(r"</([A-Za-z][\w:-]*)\s*>")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class PatchError(ValueError):
    def __init__(self, message: str, code: str = "bad_request"):
        super().__init__(message)
        self.code = code


def file_revision(path: Path) -> str:
    data = path.read_bytes() if path.exists() else b""
    return hashlib.sha1(data).hexdigest()[:16]


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), delete=False
    ) as tmp:
        tmp.write(text)
        tmp.flush()
        name = tmp.name
    Path(name).replace(path)


def _strip_comments(html: str):
    """Return html with comments blanked (same length) so tag scans ignore them."""
    out = list(html)
    for m in _COMMENT_RE.finditer(html):
        for i in range(m.start(), m.end()):
            out[i] = " "
    return "".join(out)


def _parse_attrs(attr_blob: str) -> dict:
    attrs = {}
    for m in _ATTR_RE.finditer(attr_blob.strip()):
        key = m.group(1).lower()
        if key.startswith("/"):
            continue
        val = m.group(2)
        if val is None:
            val = m.group(3)
        if val is None:
            val = m.group(4)
        if val is None:
            val = ""
        attrs[key] = val
    return attrs


def _find_elements(html: str):
    """Yield dicts for each element with start/end of open tag and element span."""
    scan = _strip_comments(html)
    stack = []
    i = 0
    n = len(scan)
    while i < n:
        if scan[i] != "<":
            i += 1
            continue
        if scan.startswith("<!", i) or scan.startswith("<?", i):
            gt = scan.find(">", i)
            i = n if gt < 0 else gt + 1
            continue
        close = _TAG_CLOSE_RE.match(scan, i)
        if close:
            name = close.group(1).lower()
            while stack and stack[-1]["name"] != name:
                # auto-close mismatched (best effort)
                orphan = stack.pop()
                orphan["end"] = i
                yield orphan
            if stack and stack[-1]["name"] == name:
                el = stack.pop()
                el["end"] = close.end()
                yield el
            i = close.end()
            continue
        open_m = _TAG_OPEN_RE.match(scan, i)
        if not open_m:
            i += 1
            continue
        name = open_m.group(1).lower()
        attr_blob = open_m.group(2)
        self_close = attr_blob.rstrip().endswith("/") or name in _VOID
        attrs = _parse_attrs(attr_blob[:-1] if attr_blob.rstrip().endswith("/") else attr_blob)
        el = {
            "name": name,
            "attrs": attrs,
            "open_start": open_m.start(),
            "open_end": open_m.end(),
            "attr_blob": attr_blob[:-1] if attr_blob.rstrip().endswith("/") else attr_blob,
            "self_close": self_close,
            "end": open_m.end() if self_close else None,
        }
        if self_close:
            yield el
        else:
            stack.append(el)
        i = open_m.end()
    for el in stack:
        el["end"] = n
        yield el


def find_targets(html: str, region: str, part: str | None = None):
    matches = []
    elements = list(_find_elements(html))
    for el in elements:
        if el["attrs"].get("data-region") != region:
            continue
        if part is None:
            matches.append(el)
            continue
        # same element may carry both data-region and data-part
        if el["attrs"].get("data-part") == part:
            matches.append(el)
            continue
        for child in elements:
            if child["attrs"].get("data-part") != part:
                continue
            if child["open_start"] <= el["open_start"]:
                continue
            if el["end"] is not None and child["open_start"] >= el["end"]:
                continue
            if el["end"] is not None and (child.get("end") or child["open_end"]) > el["end"]:
                continue
            matches.append(child)
    return matches


def _leaf_text_span(html: str, el: dict):
    """Return (start, end, text) for a single leaf text node, or raise."""
    if el.get("self_close") or el.get("end") is None:
        raise PatchError("target has no text content", "no_text")
    inner = html[el["open_end"]: el["end"]]
    # strip trailing closing tag
    close = re.search(r"</[A-Za-z][\w:-]*\s*>\s*$", inner)
    if not close:
        raise PatchError("malformed target element", "malformed")
    body = inner[: close.start()]
    if re.search(r"<[A-Za-z]", body):
        raise PatchError("text is not a leaf node (nested markup)", "non_leaf")
    # preserve surrounding whitespace of the body as outside the editable core
    m = re.match(r"(\s*)(.*?)(\s*)\Z", body, re.DOTALL)
    if not m:
        raise PatchError("empty text target", "no_text")
    lead, core, trail = m.group(1), m.group(2), m.group(3)
    start = el["open_end"] + len(lead)
    end = start + len(core)
    return start, end, core


def _rewrite_style_attr(attr_blob: str, style_changes: dict) -> str:
    """Return new attribute blob with style declarations merged."""
    attrs = []
    style_raw = None
    style_idx = None
    for m in _ATTR_RE.finditer(attr_blob.strip()):
        key = m.group(1)
        if key.startswith("/"):
            continue
        q = '"' if m.group(2) is not None else ("'" if m.group(3) is not None else None)
        val = m.group(2) if m.group(2) is not None else (
            m.group(3) if m.group(3) is not None else (m.group(4) if m.group(4) is not None else "")
        )
        if key.lower() == "style":
            style_raw = val
            style_idx = len(attrs)
            attrs.append([key, val, q or '"'])
        else:
            attrs.append([key, val, q or '"'])

    decls = []
    if style_raw:
        for chunk in style_raw.split(";"):
            chunk = chunk.strip()
            if not chunk or ":" not in chunk:
                continue
            prop, _, value = chunk.partition(":")
            decls.append([prop.strip(), value.strip()])

    for prop, value in style_changes.items():
        if prop not in SUPPORTED_STYLE_PROPS:
            raise PatchError(f"unsupported style property: {prop}", "bad_style")
        found = False
        for d in decls:
            if d[0] is None:
                continue
            if d[0].lower() == prop.lower():
                found = True
                if value is None:
                    d[0] = None  # mark delete
                else:
                    d[1] = str(value)
                break
        if not found and value is not None:
            decls.append([prop, str(value)])

    decls = [d for d in decls if d[0] is not None]
    new_style = "; ".join(f"{p}: {v}" for p, v in decls)
    if new_style:
        new_style += ";" if not new_style.endswith(";") else ""
        # normalize trailing
        new_style = "; ".join(f"{p}: {v}" for p, v in decls)

    if style_idx is None:
        if new_style:
            # insert style before trailing slash space
            blob = attr_blob
            insert = f' style="{new_style}"'
            if blob.rstrip().endswith("/"):
                return blob.rstrip()[:-1].rstrip() + insert + " /"
            return blob + insert
        return attr_blob

    if not new_style:
        # remove style attribute entirely
        del attrs[style_idx]
    else:
        attrs[style_idx][1] = new_style

    parts = []
    for key, val, q in attrs:
        if val == "" and key.lower() in ("data-overlap-ok",):
            parts.append(f" {key}")
        else:
            parts.append(f" {key}={q}{val}{q}")
    # preserve leading space convention
    leading = " " if attr_blob[:1].isspace() or parts else ""
    # If original had only attrs without leading space in blob, keep as-is
    rebuilt = "".join(parts)
    if attr_blob and not attr_blob[0].isspace() and rebuilt.startswith(" "):
        rebuilt = rebuilt[1:]
        # still need space between tag name and first attr — open tag builder adds it
        rebuilt = " " + rebuilt if rebuilt else ""
    # Prefer keeping a leading space when there are attrs
    if rebuilt and not rebuilt.startswith(" ") and not rebuilt.startswith("/"):
        rebuilt = " " + rebuilt
    return rebuilt if rebuilt else (" " if attr_blob.strip() == "" else "")


def apply_html_patch(html: str, region: str, part: str | None, changes: dict) -> str:
    targets = find_targets(html, region, part)
    if not targets:
        raise PatchError(
            f"target not found: {region}" + (f".{part}" if part else ""),
            "not_found",
        )
    if len(targets) > 1:
        raise PatchError(
            f"duplicate target: {region}" + (f".{part}" if part else ""),
            "duplicate",
        )
    el = targets[0]
    out = html

    if "text" in changes:
        start, end, _old = _leaf_text_span(out, el)
        new_text = changes["text"]
        if not isinstance(new_text, str):
            raise PatchError("text must be a string", "bad_text")
        # escape minimal entities for safety in text nodes
        new_text = (
            new_text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        out = out[:start] + new_text + out[end:]
        # re-find element after text change (offsets may shift only after open_end)
        targets = find_targets(out, region, part)
        el = targets[0]

    if "style" in changes and changes["style"] is not None:
        if not isinstance(changes["style"], dict):
            raise PatchError("style must be an object", "bad_style")
        new_blob = _rewrite_style_attr(el["attr_blob"], changes["style"])
        # rebuild open tag
        name = el["name"]
        open_src = out[el["open_start"]: el["open_end"]]
        self_close = open_src.rstrip().endswith("/>") or (
            open_src.rstrip().endswith(">") and el["name"] in _VOID and "/" in open_src[-3:]
        )
        # simpler: use el flags
        if el["self_close"] and el["name"] in _VOID:
            new_open = f"<{name}{new_blob}>"
        elif el["self_close"]:
            new_open = f"<{name}{new_blob} />"
        else:
            new_open = f"<{name}{new_blob}>"
        out = out[: el["open_start"]] + new_open + out[el["open_end"]:]

    return out


# ------------------------------------------------------------------ theme tokens

_TOKEN_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")


def read_theme_tokens(css: str) -> dict:
    block = css
    if THEME_START in css and THEME_END in css:
        start = css.index(THEME_START) + len(THEME_START)
        end = css.index(THEME_END)
        block = css[start:end]
    else:
        m = re.search(r":root\s*\{([^}]*)\}", css, re.DOTALL)
        if m:
            block = m.group(1)
    tokens = {}
    for m in _TOKEN_RE.finditer(block):
        tokens[m.group(1)] = m.group(2).strip()
    return tokens


def ensure_theme_markers(css: str) -> str:
    if THEME_START in css and THEME_END in css:
        return css
    m = re.search(r"(:root\s*)\{", css)
    if not m:
        body = "\n".join(f"  {k}: {v};" for k, v in {
            "--bg": "#ffffff",
            "--brand": "#1e2761",
            "--accent": "#f96167",
        }.items())
        return f"{THEME_START}\n:root {{\n{body}\n}}\n{THEME_END}\n" + css
    # insert markers around existing :root block
    brace = css.index("{", m.start())
    depth = 0
    i = brace
    while i < len(css):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    else:
        raise PatchError("malformed :root block", "malformed")
    before = css[: m.start()]
    block = css[m.start(): end]
    after = css[end:]
    return f"{before}{THEME_START}\n{block}\n{THEME_END}{after}"


def apply_theme_patch(css: str, changes: dict) -> str:
    css = ensure_theme_markers(css)
    start = css.index(THEME_START) + len(THEME_START)
    end = css.index(THEME_END)
    head, block, tail = css[:start], css[start:end], css[end:]
    for name, value in changes.items():
        if not re.fullmatch(r"--[\w-]+", name):
            raise PatchError(f"invalid token name: {name}", "bad_token")
        if value is None:
            block, n = re.subn(
                rf"([ \t]*){re.escape(name)}\s*:\s*[^;]+;\n?",
                "",
                block,
                count=1,
            )
            if n == 0:
                raise PatchError(f"token not found: {name}", "not_found")
            continue
        if not isinstance(value, str) or not value.strip():
            raise PatchError(f"invalid token value for {name}", "bad_token")
        pat = rf"({re.escape(name)}\s*:\s*)([^;]+)(;)"
        if re.search(pat, block):
            block = re.sub(pat, rf"\g<1>{value.strip()}\g<3>", block, count=1)
        else:
            # insert before closing brace of :root
            block = re.sub(
                r"(\n?\})",
                f"\n  {name}: {value.strip()};\\1",
                block,
                count=1,
            )
    return head + block + tail
