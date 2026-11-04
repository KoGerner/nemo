"""Ticket 288: nemo's chat in Harbour, Chainlit's own frontend copied and dressed.

`~/work/ai4bcm-site/chat/frontend.py`'s approach, for nemo's Chainlit (both 2.12.0). The app calls
`install` as it loads: the first time a skin is seen, the packaged `frontend/dist` is copied byte
for byte into `skin/.chainlit-build/<key>/` (git-ignored), its index.html edited, and Chainlit's
server is pointed at the copy. The installed package is never written.

WHY A COPY

    Chainlit's configuration can recolour the page through CSS variables and link one more
    stylesheet. It cannot touch the part of its index.html that makes the tester's browser fetch
    from other people's servers: two preconnects and the Inter stylesheet from Google Fonts, and
    KaTeX's CSS from jsDelivr. A copy can.

WHAT IT CHANGES, AND NOTHING ELSE

    index.html   the preconnects, the Inter block and the KaTeX stylesheet come out; after the
                 bundle's own stylesheet go 287's one Harbour stylesheet (the tokens and the
                 self-hosted fonts, served by the skin's /harbour route) and the chat's own, so
                 both win every tie by coming later
    assets/nemo/chat.css   the theme block below, then skin/chat.css, then the chart card's
                           page switch (t403 r6, `impact_chart.PAGE_SWITCH`)

    Every edit is an exact string that must occur exactly once: a Chainlit upgrade that changes
    the file stops the app at start with the string it could not find, rather than serving
    Google Fonts under a green suite.

NO COLOUR IS WRITTEN HERE

    Chainlit reads its colours as shadcn triplets ("H S% L%"), so each theme variable is computed
    from a pinned token in `harbour/tokens/colors.css` and checked to convert back to that token's
    exact hex. Its light and dark blocks get the same values: the chat is light only.

The build directory is named for what it is made of (Chainlit's version, the edited index.html
and chat.css), so a changed skin gets a fresh directory and an unchanged one is reused as it is.
"""
from __future__ import annotations

import colorsys
import hashlib
import importlib.metadata
import importlib.util
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import impact_chart

import stage_door

SKIN = Path(__file__).resolve().parent
COLOURS = SKIN / "harbour" / "tokens" / "colors.css"
CHAT_CSS = SKIN / "chat.css"
BUILDS = SKIN / ".chainlit-build"
#: Where the chat's own stylesheet sits in the build, and so under <root>/assets/ once served.
SKIN_REL = "assets/nemo"

# ── the edits to index.html ───────────────────────────────────────────────────────────────────
PRECONNECTS = (
    '    <link rel="preconnect" href="https://fonts.googleapis.com" />\n'
    '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
)
INTER = (
    "    <!-- FONT START -->\n"
    "    <link\n"
    '      href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap"\n'
    '      rel="stylesheet"\n'
    "    />\n"
    "    <!-- FONT END -->\n"
)
KATEX = (
    "    <link\n"
    '      rel="stylesheet"\n'
    '      href="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.css"\n'
    "    />\n"
)
HEAD_END = "  </head>\n"
#: What must not survive anywhere in the edited file.
FOREIGN_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com", "cdn.jsdelivr.net")


def links(css: bytes) -> str:
    """287's stylesheet, then the chat's, its URL carrying a hash of its bytes so a returning
    tester never keeps a cached skin. Both start with "/": Chainlit prefixes every `href="/` in
    this file with its root path when it serves it."""
    v = hashlib.sha256(css).hexdigest()[:10]
    return ('    <link rel="stylesheet" href="/harbour/harbour.css" />\n'
            f'    <link rel="stylesheet" href="/{SKIN_REL}/chat.css?v={v}" />\n')


def edits(css: bytes) -> tuple[tuple[str, str, str], ...]:
    return (
        ("the Google Fonts preconnects", PRECONNECTS, ""),
        ("the Inter stylesheet from Google Fonts", INTER, ""),
        ("the KaTeX stylesheet from jsDelivr", KATEX, ""),
        ("Harbour and the chat's stylesheet, after the bundle", HEAD_END, links(css) + HEAD_END),
    )


# ── Chainlit's theme variables, each from a pinned token ──────────────────────────────────────
# Chainlit 2.12 is shadcn/Tailwind: `bg-accent` means hsl(var(--accent)). Every variable its light
# AND dark blocks declare is set here, so no stock colour is left to show through.
THEME = {
    # The chat is the white card of direction C; his turns sit on the grey (--accent, which
    # Chainlit gives his bubble and the composer), nemo's on white with a hairline (chat.css).
    "--background": "--color-white",
    "--foreground": "--color-navy",
    "--card": "--color-white",
    "--card-foreground": "--color-navy",
    "--popover": "--color-white",
    "--popover-foreground": "--color-navy",
    # The send button is Harbour's primary action: amber, only ever under navy.
    "--primary": "--color-amber",
    "--primary-foreground": "--color-navy",
    "--secondary": "--color-harbour-grey",
    "--secondary-foreground": "--color-navy",
    "--muted": "--color-harbour-grey",
    "--muted-foreground": "--color-muted",
    "--accent": "--color-harbour-grey",
    "--accent-foreground": "--color-navy",
    # Harbour has no red; rust is its accent stroke, and the focus ring.
    "--destructive": "--color-rust",
    "--destructive-foreground": "--color-white",
    "--border": "--color-hairline",
    "--input": "--color-hairline",
    "--ring": "--color-rust",
    "--chart-1": "--color-navy",
    "--chart-2": "--color-amber",
    "--chart-3": "--color-rust",
    "--chart-4": "--color-slate",
    "--chart-5": "--color-muted",
    "--sidebar-background": "--color-harbour-grey",
    "--sidebar-foreground": "--color-navy",
    "--sidebar-primary": "--color-navy",
    "--sidebar-primary-foreground": "--color-white",
    "--sidebar-accent": "--color-white",
    "--sidebar-accent-foreground": "--color-navy",
    "--sidebar-border": "--color-hairline",
    "--sidebar-ring": "--color-rust",
}
#: Not colours, but Chainlit reads them from the same block.
THEME_REFS = {"--radius": "var(--radius-inputs)", "--font-sans": "var(--font-body)"}


class BuildError(RuntimeError):
    pass


def token_colours(css: str) -> dict[str, str]:
    """Every `--name:#rrggbb;` the pinned colours name, lower-cased."""
    return {m[1]: m[2].lower() for m in re.finditer(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;",
                                                     css)}


def triplet_to_hex(h: float, s: float, l: float) -> str:  # noqa: E741  (colorsys's own names)
    rgb = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
    return "#" + "".join(f"{round(c * 255):02x}" for c in rgb)


def hex_to_triplet(value: str) -> str:
    """"#0b1f3a" → its "H S% L%", at the fewest decimals that convert back exactly."""
    r, g, b = (int(value[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)  # noqa: E741
    for places in range(5):
        hh, ss, ll = (round(h * 360, places), round(s * 100, places), round(l * 100, places))
        if triplet_to_hex(hh, ss, ll) == value.lower():
            hue, sat, light = (_short(x, places) for x in (hh, ss, ll))
            return f"{hue} {sat}% {light}%"
    raise BuildError(f"{value} has no triplet that converts back to it exactly")


def _short(x: float, places: int) -> str:
    text = f"{x:.{places}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def theme_block(colours: dict[str, str]) -> str:
    lines = [":root,", ".dark {"]
    for var, token in THEME.items():
        if token not in colours:
            raise BuildError(f"{var} is mapped to {token}, which colors.css does not define")
        lines.append(f"  {var}: {hex_to_triplet(colours[token])}; /* {token} */")
    lines += [f"  {var}: {ref};" for var, ref in THEME_REFS.items()]
    return "\n".join([*lines, "}"]) + "\n"


def chat_css() -> bytes:
    return "\n".join([
        "/* GENERATED by skin/chat_build.py; do not edit here. Chainlit's theme variables, each\n"
        " * from a pinned token in harbour/tokens/colors.css, then skin/chat.css. */\n",
        theme_block(token_colours(COLOURS.read_text(encoding="utf-8"))),
        CHAT_CSS.read_text(encoding="utf-8"),
        "/* t403 r6: the chart card's laptop chart or its phone split, by the page's width,\n"
        " * at the chart's own break (impact_chart.PAGE_SWITCH) */",
        impact_chart.PAGE_SWITCH + "\n",
    ]).encode("utf-8")


def edit_index(html: str, css: bytes) -> str:
    for what, find, replace in edits(css):
        if (count := html.count(find)) != 1:
            raise BuildError(f"index.html: expected {what} exactly once and found it {count} "
                             f"times. Chainlit's frontend changed. Looked for:\n{find}")
        html = html.replace(find, replace)
    if hosts := [h for h in FOREIGN_HOSTS if h in html]:
        raise BuildError(f"index.html still references {hosts} after the edits")
    return html


def packaged_dist() -> tuple[Path, str]:
    """The installed chainlit's frontend/dist, found without importing chainlit."""
    spec = importlib.util.find_spec("chainlit")
    if spec is None or not spec.submodule_search_locations:
        raise BuildError("chainlit is not installed for this interpreter")
    dist = Path(list(spec.submodule_search_locations)[0]) / "frontend" / "dist"
    return dist, importlib.metadata.version("chainlit")


def build(dist: Path, version: str, builds: Path = BUILDS) -> Path:
    """The dressed copy of `dist`, made once per skin and reused while the skin is unchanged.

    It is written beside its final place and renamed into it, so a second process making the same
    build at the same time finds either nothing or the whole of it, never half.
    """
    css = chat_css()
    index = edit_index((dist / "index.html").read_text(encoding="utf-8"), css)
    key = hashlib.sha256(b"\0".join([version.encode(), index.encode(), css])).hexdigest()[:16]
    out = builds / f"{version}-{key}"
    if (out / SKIN_REL / "chat.css").is_file():
        return out
    builds.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".tmp-", dir=builds))
    try:
        shutil.copytree(dist, tmp, dirs_exist_ok=True)
        (tmp / "index.html").write_text(index, encoding="utf-8")
        (tmp / SKIN_REL).mkdir(parents=True, exist_ok=True)
        (tmp / SKIN_REL / "chat.css").write_bytes(css)
        os.rename(tmp, out)
    except OSError:
        if not (out / SKIN_REL / "chat.css").is_file():
            raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for old in builds.iterdir():  # an earlier skin's copy, never the one just made
        if old != out and not old.name.startswith(".tmp-"):
            shutil.rmtree(old, ignore_errors=True)
    return out


def install(server: Any, config: Any) -> Path | None:
    """Point Chainlit's running server at the dressed copy, and open it light.

    `server` is `chainlit.server`, whose `build_dir` is read on every request for the page and its
    assets; `config` is `chainlit.config.config`, which the page reads its settings from. A server
    with no frontend to dress is left alone: the features suite loads the app over stand-ins for
    Chainlit (`skin_harness.py`), in an interpreter where Chainlit is not installed.
    """
    if not hasattr(server, "build_dir"):
        return None
    out = build(*packaged_dist())
    server.build_dir = str(out)
    config.ui.default_theme = "light"
    translations(type(config))
    return out


def translations(config_class: Any) -> None:
    """The skin's words in every language Chainlit serves, on ONE wrapper of `load_translation`,
    which `/project/translations` calls on each request. Chainlit reads its translations from the
    app root's `.chainlit/translations`, picked by the browser's language; those files sit outside
    the repo, so the skin sets its keys in whichever translation is served:

    - t321: the line under the composer (`chat.watermark`, Chainlit's "LLMs can make mistakes.
      Check important info.") says the chat is not private (`stage_door.NOT_PRIVATE`);
    - t338: the step above nemo's answer reads "thinking · <lane>": Chainlit's own "Using" /
      "Used" in front of a step's name (`chat.messages.status`, a German phone read "Verwendete
      thinking · …") are blanked.
    """
    loaded = config_class.load_translation

    def load_translation(self: Any, language: str) -> dict[str, Any]:
        words: dict[str, Any] = loaded(self, language)
        chat = words.setdefault("chat", {})
        chat["watermark"] = stage_door.NOT_PRIVATE
        status = chat.setdefault("messages", {}).setdefault("status", {})
        status.update(using="", used="")
        return words

    config_class.load_translation = load_translation
