import difflib

def make_diff(before: str, after: str, path: str) -> str:
    before_lines = before.splitlines(keepends=True)
    after_lines  = after.splitlines(keepends=True)
    diff_lines = difflib.unified_diff(
        before_lines, after_lines,
        fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""
    )
    return "".join(diff_lines)
