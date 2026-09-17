"""
Rendu HTML de DOCUMENTATION.md, servi sur /documentation.

Le fichier Markdown reste la seule source : il est relu dès qu'il change sur le disque.
Les ancres des titres suivent la convention GitHub pour que les liens internes du
document (#vue-densemble, #démarrage-de-lapi, …) fonctionnent aussi dans la page HTML.
"""
import os
import re

from markdown_it import MarkdownIt

from . import utils

DOC_PATH = os.path.join(utils.ROOT_DIR, "DOCUMENTATION.md")

_markdown = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])
_cache = {"mtime": None, "result": None}


def slugify(text):
    # Même règle que GitHub : minuscules, ponctuation retirée, espaces remplacés par des tirets
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")


def _heading_text(inline_token):
    return "".join(child.content for child in inline_token.children or [])


def _render(source):
    tokens = _markdown.parse(source)
    title = None
    toc = []
    used_slugs = {}

    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            text = _heading_text(tokens[index + 1])
            slug = slugify(text)
            count = used_slugs.get(slug, 0)
            used_slugs[slug] = count + 1
            if count:
                slug = f"{slug}-{count}"
            token.attrSet("id", slug)
            level = int(token.tag[1])
            if level == 1 and title is None:
                title = text
            elif level in (2, 3) and slug != "sommaire":
                toc.append({"level": level, "text": text, "slug": slug})

        elif token.type == "inline":
            # Les liens relatifs visent d'autres fichiers du dépôt : ils n'ont pas d'adresse sur l'API
            local_links = []
            for child in token.children or []:
                if child.type == "link_open":
                    href = child.attrGet("href") or ""
                    local = not href.startswith(("http://", "https://", "mailto:", "#", "/"))
                    local_links.append(local)
                    if local:
                        child.tag = "span"
                        child.attrs = {"class": "doc-ref", "title": href}
                elif child.type == "link_close" and local_links.pop():
                    child.tag = "span"

    html = _markdown.renderer.render(tokens, _markdown.options, {})
    html = html.replace("<table>", '<div class="doc-table"><table>').replace("</table>", "</table></div>")
    return {"title": title or "Documentation", "toc": toc, "html": html}


def get_documentation():
    """Renvoie {title, toc, html} ; None si DOCUMENTATION.md est absent."""
    try:
        mtime = os.path.getmtime(DOC_PATH)
    except OSError:
        return None
    if _cache["mtime"] != mtime:
        with open(DOC_PATH, encoding="utf-8") as file:
            _cache["result"] = _render(file.read())
        _cache["mtime"] = mtime
    return _cache["result"]
