"""Pre-flight gates that must hold before a submission is tagged.

Four gates, and the credential one is the reason this exists as a script
rather than a checklist: `credentials.json` and `token.json` are live bearer
tokens. They are gitignored today, but "today" is not a guarantee -- a
`.gitignore` edit or a `git add -f` would put a Gmail send-token in a public
repository, and the tag would immortalise the commit that did it.

So the gate refuses to tag unless it has just re-verified, from git itself,
that both are ignored AND untracked. Ignored-but-tracked is the dangerous
middle state a naive `.gitignore` grep would pass.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SECRETS = ("credentials.json", "token.json")


def credentials_safe(repo=".") -> tuple[bool, str]:
    """Check if credential files are safe to commit.

    Verifies that each file in SECRETS is either absent or both untracked and
    gitignored. Tracked-but-ignored is the dangerous case where `.gitignore`
    cannot protect a file already in the index.
    """
    for name in SECRETS:
        path = Path(repo) / name
        if not path.exists():
            continue
        # Check if tracked by git
        result = subprocess.run(
            ["git", "-C", repo, "ls-files", "--error-unmatch", name],
            capture_output=True
        )
        if result.returncode == 0:
            return (False, f"{name}: tracked by git")
        # Check if ignored
        result = subprocess.run(
            ["git", "-C", repo, "check-ignore", "-q", name],
            capture_output=True
        )
        if result.returncode != 0:
            return (False, f"{name}: not gitignored")
    return (True, "")


def line_limit_clean(repo=".", limit=150) -> tuple[bool, list]:
    """Check that all tracked Python files stay under line limit.

    The 150-line constraint ensures modules remain focused and testable.
    Returns a list of "path:count" strings for any files exceeding the limit.
    """
    result = subprocess.run(
        ["git", "-C", repo, "ls-files", "*.py"],
        capture_output=True, text=True
    )
    offenders = []
    for path_str in result.stdout.splitlines():
        path = Path(repo) / path_str
        if path.exists():
            content = path.read_text()
            lines = len(content.splitlines())
            if lines > limit:
                offenders.append(f"{path_str}:{lines}")
    return (not offenders, offenders)


def tag_command(tag="v1.0-submission") -> list[str]:
    """Build the git tag command for submission.

    Returns an annotated tag with a message naming the project and course.
    """
    return ["git", "tag", "-a", tag, "-m",
            "Final submission: Police-Thief P2P, uoh-rl07"]


def main(argv=None) -> int:
    """Run all pre-flight gates before tagging a submission.

    Credential gate runs first (most dangerous). Gates in order: credential,
    line limit, lint, test. Any failure stops without tagging. Tagging and
    pushing are opt-in via flags.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", action="store_true")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args(argv)
    if args.push:
        args.tag = True

    ok, detail = credentials_safe()
    if not ok:
        print(f"FAIL: credential gate: {detail}")
        return 1
    print("PASS: credential gate")

    ok, offenders = line_limit_clean()
    if not ok:
        print(f"FAIL: line limit gate: {', '.join(offenders)}")
        return 1
    print("PASS: line limit gate")

    result = subprocess.run(["uvx", "ruff", "check", "src", "tests", "scripts"])
    if result.returncode != 0:
        print("FAIL: ruff check")
        return 1
    print("PASS: ruff check")

    if args.skip_tests:
        # Said out loud: a skipped gate reported as PASS is a gate that lies,
        # and this one is the difference between "green" and "not run".
        print("SKIP: pytest (--skip-tests)")
    else:
        if subprocess.run([".venv/bin/pytest", "-q"]).returncode != 0:
            print("FAIL: pytest")
            return 1
        print("PASS: pytest")

    tag_cmd = tag_command()
    if not args.tag:
        import shlex
        print(f"Tag command: {shlex.join(tag_cmd)}")
        return 0

    subprocess.run(tag_cmd, check=True)
    print("PASS: tagged v1.0-submission")
    if args.push:
        subprocess.run(["git", "push", "origin", "v1.0-submission"],
                       check=True)
        print("PASS: pushed to origin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
