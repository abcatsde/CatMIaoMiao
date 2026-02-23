from pathlib import Path


class MemoryStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> str:
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8").strip()

    def save(self, text: str) -> None:
        self.path.write_text(text, encoding="utf-8")
