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

import subprocess

from scripts.prepare_submission import (
    SECRETS,
    credentials_safe,
    line_limit_clean,
    tag_command,
)


def test_the_two_credential_files_are_the_ones_guarded():
    assert set(SECRETS) == {"credentials.json", "token.json"}


def test_the_repo_currently_passes_the_credential_gate():
    ok, detail = credentials_safe()

    assert ok, detail


def test_a_tracked_secret_fails_even_when_gitignored(tmp_path):
    """The dangerous middle state: listed in .gitignore but already in the
    index, where ignoring it does nothing at all."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("token.json\n")
    (tmp_path / "token.json").write_text("{}")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-f", "token.json"],
                   check=True)

    ok, detail = credentials_safe(str(tmp_path))

    assert not ok
    assert "token.json" in detail


def test_an_unignored_secret_fails(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "credentials.json").write_text("{}")

    ok, detail = credentials_safe(str(tmp_path))

    assert not ok
    assert "credentials.json" in detail


def test_an_absent_secret_is_not_a_failure(tmp_path):
    """A clean checkout has neither file. That is safe, not broken."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("token.json\ncredentials.json\n")

    ok, _ = credentials_safe(str(tmp_path))

    assert ok


# --- the line limit gate ---------------------------------------------------


def test_the_repo_currently_passes_the_line_limit():
    ok, offenders = line_limit_clean()

    assert ok, offenders


def test_the_limit_is_the_leagues_hundred_and_fifty():
    import inspect

    from scripts import prepare_submission

    assert "150" in inspect.getsource(prepare_submission)


# --- the tag -----------------------------------------------------------------


def test_the_tag_command_is_annotated_and_named():
    command = tag_command()

    assert command[:3] == ["git", "tag", "-a"]
    assert "v1.0-submission" in command
    assert "-m" in command


def test_the_message_names_the_project_and_the_course():
    command = tag_command()
    message = command[command.index("-m") + 1]

    assert "uoh-rl07" in message


def test_nothing_is_pushed_without_being_asked():
    """A script that tags AND pushes on import is a script that publishes by
    accident."""
    import inspect

    from scripts import prepare_submission

    source = inspect.getsource(prepare_submission)
    assert "--push" in source, "pushing must be opt-in"
