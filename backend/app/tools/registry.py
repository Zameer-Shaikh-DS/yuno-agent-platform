import json
import math
from typing import Callable
from langchain_core.tools import tool
from ..database import SessionLocal
from ..models.note import NoteEntry

AVAILABLE_TOOLS = ["calculator", "web_search", "note_store"]


@tool
def calculator(expression: str) -> str:
    """Evaluate a safe math expression. Example: '2 + 2 * 3'."""
    allowed = set("0123456789+-*/().% ")
    if not all(c in allowed for c in expression):
        return "Error: invalid characters in expression"
    try:
        result = eval(expression, {"__builtins__": {}}, {"math": math})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


@tool
def web_search(query: str) -> str:
    """Search the web for information (DuckDuckGo instant answer API)."""
    import httpx
    try:
        r = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_redirect": 1},
            timeout=10.0,
        )
        data = r.json()
        abstract = data.get("AbstractText") or data.get("Answer") or ""
        related = data.get("RelatedTopics", [])[:3]
        snippets = []
        for item in related:
            if isinstance(item, dict) and item.get("Text"):
                snippets.append(item["Text"])
        if abstract:
            return abstract
        if snippets:
            return "\n".join(snippets)
        return f"No instant results for: {query}. Try rephrasing."
    except Exception as e:
        return f"Search failed: {e}"


@tool
def note_store(action: str, key: str, content: str = "") -> str:
    """
    Save or retrieve persistent notes.
    action: 'save' to upsert note, 'get' to retrieve by key.
    key: unique identifier for the note.
    content: text to save (only used when action='save').
    """
    db = SessionLocal()
    try:
        if action == "save":
            note = db.query(NoteEntry).filter(NoteEntry.key == key).first()
            if note:
                note.content = content
            else:
                note = NoteEntry(key=key, content=content)
                db.add(note)
            db.commit()
            return f"Saved note '{key}'"

        if action == "get":
            note = db.query(NoteEntry).filter(NoteEntry.key == key).first()
            return note.content if note else f"No note found for '{key}'"

        return "Use action 'save' or 'get'"
    except Exception as e:
        return f"note_store error: {e}"
    finally:
        db.close()


_TOOL_MAP: dict[str, Callable] = {
    "calculator": calculator,
    "web_search": web_search,
    "note_store": note_store,
}


def get_tools_for_agent(tool_names: list[str]) -> list:
    return [_TOOL_MAP[n] for n in tool_names if n in _TOOL_MAP]
