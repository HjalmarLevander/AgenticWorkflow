"""RAG over your reference code: chunks everything in style_vault/, embeds it
locally via Chroma's built-in model, and retrieves the snippets most relevant
to the current task so the Engineer agent aligns with your style — not just
whatever happened to be in the vault.
"""
from pathlib import Path

import chromadb

VAULT_DIR = Path(__file__).parent.parent / "style_vault"
DB_DIR = Path(__file__).parent / ".chroma"
CHUNK_LINES = 40
TOP_K = 6
BATCH_SIZE = 500
MAX_FILE_BYTES = 300_000  # skip generated/data files that dwarf real source

# Reference repos bring their own noise — vendor dirs, build artifacts, and
# non-text formats aren't useful style signal and some aren't even readable text.
TEXT_EXTENSIONS = {".py", ".md", ".rst", ".txt", ".ipynb"}
SKIP_DIR_NAMES = {".git", "__pycache__", "node_modules", ".ipynb_checkpoints", ".venv"}

_client = chromadb.PersistentClient(path=str(DB_DIR))
_collection = _client.get_or_create_collection("style_vault")


def _chunks(path: Path) -> list[str]:
    lines = path.read_text(errors="ignore").splitlines()
    return [
        "\n".join(lines[i : i + CHUNK_LINES])
        for i in range(0, len(lines), CHUNK_LINES)
        if lines[i : i + CHUNK_LINES]
    ]


def _vault_files():
    if not VAULT_DIR.exists():
        return
    for path in sorted(VAULT_DIR.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_EXTENSIONS:
            continue
        if SKIP_DIR_NAMES & set(path.relative_to(VAULT_DIR).parts):
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        yield path


def ingest() -> int:
    """Re-embeds everything under style_vault/. Call on startup or after
    uploading new files. Upserts, so it's safe to call repeatedly."""
    ids, docs, metas = [], [], []
    for path in _vault_files():
        rel = str(path.relative_to(VAULT_DIR))
        for i, chunk in enumerate(_chunks(path)):
            ids.append(f"{rel}:{i}")
            docs.append(chunk)
            metas.append({"path": rel})

    for i in range(0, len(ids), BATCH_SIZE):
        _collection.upsert(
            ids=ids[i : i + BATCH_SIZE],
            documents=docs[i : i + BATCH_SIZE],
            metadatas=metas[i : i + BATCH_SIZE],
        )
        print(f"embedded {min(i + BATCH_SIZE, len(ids))}/{len(ids)} chunks", flush=True)
    return len(ids)


def query_style(task_description: str) -> str:
    """Returns the snippets most relevant to the task, formatted for injection
    into the Engineer's system prompt. Empty string if the vault is empty."""
    if _collection.count() == 0:
        return ""

    results = _collection.query(query_texts=[task_description], n_results=min(TOP_K, _collection.count()))
    chunks = zip(results["metadatas"][0], results["documents"][0])
    return "\n\n".join(f"# {meta['path']}\n{doc}" for meta, doc in chunks)
