"""Gemini가 생성한 제한된 Python 스크립트로 프로젝트 파일을 편집한다."""

from __future__ import annotations

import ast
import difflib
import re
from pathlib import Path, PurePosixPath


EDITOR_SYSTEM_PROMPT = """당신은 Python 프로젝트 편집기입니다.
사용자의 요청을 수행하는 Python 스크립트만 ```python 코드 블록 하나로 출력하세요.
import, open, eval, exec, compile, globals, locals, getattr, setattr를 사용하지 마세요.
사용 가능한 함수는 list_files(), read_text(path), write_text(path, content),
delete_file(path), exists(path)입니다. path는 프로젝트 루트 기준 상대 경로여야 합니다.
파일을 읽고 필요한 부분만 정확히 수정하세요. 설명은 출력하지 마세요.
"""

_IGNORED_PARTS = {
    ".git", ".runtime", ".venv", "venv", "__pycache__", "node_modules",
    "archive",
}
_TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini",
    ".cfg", ".html", ".css", ".js", ".ts", ".tsx", ".jsx", ".sh",
    ".ps1", ".sql",
}
_FORBIDDEN_NAMES = {
    "open", "eval", "exec", "compile", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "__import__", "input", "breakpoint",
}


def _project_files(project_root: Path) -> list[str]:
    result: list[str] = []
    for path in project_root.rglob("*"):
        if not path.is_file() or any(part in _IGNORED_PARTS for part in path.parts):
            continue
        relative = path.relative_to(project_root).as_posix()
        if path.suffix.lower() in _TEXT_SUFFIXES or path.name in {"Dockerfile", "Makefile"}:
            result.append(relative)
    return sorted(result)


def build_project_context(project_root: Path, request: str, max_chars: int = 60_000) -> str:
    """파일 트리와 요청에 관련성이 높은 소스 내용을 프롬프트용으로 만든다."""
    files = _project_files(project_root)
    tokens = {t.lower() for t in re.findall(r"[A-Za-z0-9_.\-/]+", request) if len(t) > 2}

    def score(name: str) -> tuple[int, int]:
        lowered = name.lower()
        value = sum(10 for token in tokens if token in lowered)
        if lowered.endswith(("readme.md", "pyproject.toml", "requirements.txt")):
            value += 1
        return (-value, len(name))

    sections = ["[PROJECT FILES]", "\n".join(files), "\n[FILE CONTENTS]"]
    used = sum(len(item) for item in sections)
    for name in sorted(files, key=score):
        path = project_root / name
        try:
            if path.stat().st_size > 80_000:
                continue
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        block = f"\n--- {name} ---\n{content}\n"
        if used + len(block) > max_chars:
            continue
        sections.append(block)
        used += len(block)
    return "".join(sections)


def extract_python_script(reply: str) -> str:
    matches = re.findall(r"```(?:python|py)?\s*\n(.*?)```", reply, flags=re.DOTALL | re.IGNORECASE)
    script = (matches[0] if matches else reply).strip()
    if not script:
        raise ValueError("Gemini가 편집 스크립트를 반환하지 않았습니다.")
    return script


def validate_script(script: str) -> ast.AST:
    tree = ast.parse(script, filename="gemini_generated_edit.py")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            raise ValueError(f"허용되지 않은 문법입니다: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise ValueError(f"허용되지 않은 이름입니다: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError(f"dunder 속성 접근은 허용되지 않습니다: {node.attr}")
    return tree


def _safe_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("파일 경로는 비어 있지 않은 문자열이어야 합니다.")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or path.parts[0] in _IGNORED_PARTS:
        raise ValueError(f"프로젝트 밖 또는 보호된 경로는 사용할 수 없습니다: {value}")
    return path.as_posix()


class EditSession:
    """생성 스크립트의 변경을 메모리에 준비하고 확인 후 디스크에 반영한다."""

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.pending: dict[str, str | None] = {}

    def list_files(self) -> list[str]:
        return _project_files(self.project_root)

    def read_text(self, path: str) -> str:
        relative = _safe_relative_path(path)
        if relative in self.pending:
            content = self.pending[relative]
            if content is None:
                raise FileNotFoundError(relative)
            return content
        return (self.project_root / relative).read_text(encoding="utf-8")

    def exists(self, path: str) -> bool:
        relative = _safe_relative_path(path)
        if relative in self.pending:
            return self.pending[relative] is not None
        return (self.project_root / relative).is_file()

    def write_text(self, path: str, content: str) -> None:
        relative = _safe_relative_path(path)
        if not isinstance(content, str):
            raise TypeError("content는 문자열이어야 합니다.")
        self.pending[relative] = content

    def delete_file(self, path: str) -> None:
        relative = _safe_relative_path(path)
        if not self.exists(relative):
            raise FileNotFoundError(relative)
        self.pending[relative] = None

    def run(self, script: str) -> None:
        tree = validate_script(script)
        safe_builtins = {
            "len": len, "range": range, "enumerate": enumerate, "zip": zip,
            "str": str, "int": int, "float": float, "bool": bool,
            "list": list, "dict": dict, "set": set, "tuple": tuple,
            "min": min, "max": max, "sum": sum, "sorted": sorted,
            "any": any, "all": all,
        }
        namespace = {
            "__builtins__": safe_builtins,
            "list_files": self.list_files,
            "read_text": self.read_text,
            "write_text": self.write_text,
            "delete_file": self.delete_file,
            "exists": self.exists,
        }
        exec(compile(tree, "gemini_generated_edit.py", "exec"), namespace, namespace)

    def diff(self) -> str:
        chunks: list[str] = []
        for relative, new_content in sorted(self.pending.items()):
            path = self.project_root / relative
            old_content = path.read_text(encoding="utf-8") if path.is_file() else ""
            chunks.extend(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                (new_content or "").splitlines(keepends=True),
                fromfile=f"a/{relative}", tofile=f"b/{relative}",
            ))
        return "".join(chunks)

    def apply(self) -> None:
        for relative, content in self.pending.items():
            path = self.project_root / relative
            if content is None:
                path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")


def build_edit_prompt(project_root: Path, request: str) -> str:
    context = build_project_context(project_root, request)
    return f"사용자 요청:\n{request}\n\n{context}"
