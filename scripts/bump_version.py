#!/usr/bin/env python3
"""
Bump + changelog för semver baserat på Conventional Commits.

Den är avsedd att fungera även i en workspace som saknar `.git` genom att
läsa commit-meddelanden från `--commits-file` (eller stdin).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
HEADER_RE = re.compile(
    r"^(?P<type>[a-zA-Z]+)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"(?P<breaking>!)?:\s*(?P<desc>.+?)\s*$"
)
BREAKING_FOOTER_RE = re.compile(r"^BREAKING CHANGE:\s*", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class ConventionalCommit:
    type: str
    scope: Optional[str]
    desc: str
    breaking: bool


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_semver(version: str, version_path: Path) -> str:
    version = version.strip()
    if not SEMVER_RE.match(version):
        raise ValueError(
            f"Ogiltigt versionsformat i {version_path}: {version!r}. Förväntat: MAJOR.MINOR.PATCH"
        )
    return version


def parse_semver(version: str) -> tuple[int, int, int]:
    major_s, minor_s, patch_s = version.split(".", 2)
    return int(major_s), int(minor_s), int(patch_s)


def bump_version(current: str, level: str) -> str:
    major, minor, patch = parse_semver(current)
    if level == "major":
        major += 1
        minor = 0
        patch = 0
    elif level == "minor":
        minor += 1
        patch = 0
    elif level == "patch":
        patch += 1
    else:
        raise ValueError(f"Ogiltig bump-level: {level!r}")
    return f"{major}.{minor}.{patch}"


def parse_conventional_header(message: str) -> Optional[ConventionalCommit]:
    """
    Försök tolka *första raden* i `message` enligt Conventional Commits.
    """
    # Git log -p kan innehålla fler rader; vi tolkar headern som första icke-tomraden.
    first_nonempty = next((line for line in message.splitlines() if line.strip()), "")
    if not first_nonempty:
        return None

    m = HEADER_RE.match(first_nonempty.strip())
    if not m:
        return None

    typ = m.group("type").lower()
    scope = m.group("scope")
    breaking_from_header = m.group("breaking") == "!"
    breaking_from_footer = BREAKING_FOOTER_RE.search(message or "") is not None
    breaking = breaking_from_header or breaking_from_footer

    desc = m.group("desc").strip()
    return ConventionalCommit(type=typ, scope=scope, desc=desc, breaking=breaking)


def parse_commits_from_text(commits_text: str) -> list[ConventionalCommit]:
    """
    Stöd:
    - en commit per rad (ämnesrad/Conventional header)
    - eller flera commmit-meddelanden separerade av en tom rad.
    """
    chunks = [c.strip() for c in commits_text.split("\n\n") if c.strip()]
    if len(chunks) > 1:
        messages = chunks
    else:
        # Fall back: en header per rad.
        messages = [line.strip() for line in commits_text.splitlines() if line.strip()]

    commits: list[ConventionalCommit] = []
    for msg in messages:
        parsed = parse_conventional_header(msg)
        if parsed is not None:
            commits.append(parsed)
    return commits


def get_commits_from_git(git_range: str) -> list[ConventionalCommit]:
    """
    Hämtar full commit message body (%B) för angivet git-range.
    """
    cmd = [
        "git",
        "log",
        "--no-merges",
        "--pretty=%B%n==END==%n",
        git_range,
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    except Exception as e:
        raise RuntimeError(
            "Kunde inte hämta commits från git. "
            "Använd --commits-file istället. Underliggande fel: " + str(e)
        ) from e

    raw_blocks = [b.strip() for b in out.split("==END==") if b.strip()]
    commits: list[ConventionalCommit] = []
    for block in raw_blocks:
        parsed = parse_conventional_header(block)
        if parsed is not None:
            commits.append(parsed)
    return commits


def classify_bump(commits: Iterable[ConventionalCommit]) -> str:
    commits_list = list(commits)
    if not commits_list:
        return "patch"

    if any(c.breaking for c in commits_list):
        return "major"
    if any(c.type == "feat" for c in commits_list):
        return "minor"
    return "patch"


def format_changelog_bullet(commit: ConventionalCommit) -> str:
    desc = commit.desc
    if commit.scope:
        desc = f"{commit.scope}: {desc}"
    if commit.breaking:
        desc = f"{desc} (BREAKING)"
    return f"- {desc}"


def parse_unreleased_section(lines: list[str]) -> tuple[int, int]:
    """
    Returnerar (start_idx, end_idx) för `## Unreleased` (exkl. nästa `## `).
    """
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "## Unreleased":
            start_idx = i
            break
    if start_idx is None:
        raise RuntimeError("Kunde inte hitta `## Unreleased` i CHANGELOG.md")

    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        if lines[j].startswith("## ") and lines[j].strip() != "## Unreleased":
            end_idx = j
            break
    return start_idx, end_idx


def parse_subsections(section_body_lines: list[str]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """
    Returnerar:
      - preface_lines: rader innan första `### ...` (oftast blankrader)
      - subsections: lista av (heading_line, content_lines)
    """
    first_heading = None
    for idx, line in enumerate(section_body_lines):
        if line.startswith("### "):
            first_heading = idx
            break

    if first_heading is None:
        # Inget att flytta uppdelat - lägg allt som "Added" fallback.
        preface_lines = []
        return preface_lines, [("### Changed", section_body_lines)]

    preface_lines = section_body_lines[:first_heading]
    subsections: list[tuple[str, list[str]]] = []

    idx = first_heading
    while idx < len(section_body_lines):
        line = section_body_lines[idx]
        if not line.startswith("### "):
            idx += 1
            continue

        heading = line.strip()
        idx += 1
        content: list[str] = []
        while idx < len(section_body_lines) and not section_body_lines[idx].startswith("### "):
            content.append(section_body_lines[idx])
            idx += 1
        subsections.append((heading, content))

    return preface_lines, subsections


def upsert_bullets(
    subsections: list[tuple[str, list[str]]],
    heading: str,
    bullets: list[str],
) -> list[tuple[str, list[str]]]:
    """
    Append:a bullets under rätt `### Heading` (och skapa heading om den saknas).
    """

    target_heading = f"### {heading}"

    found = False
    updated: list[tuple[str, list[str]]] = []

    for h, content in subsections:
        if h.strip() == target_heading:
            found = True
            # Byt ut befintligt innehåll under rubriken mot de genererade bullets.
            # (Det gör bump-processen deterministisk även om CHANGELOG.md:s Unreleased
            # har text/bullets som redan skrivits in manuellt.)
            split_at = len(content)
            while split_at > 0 and content[split_at - 1].strip() == "":
                split_at -= 1
            tail_blanks = content[split_at:]
            new_content = bullets + tail_blanks
            updated.append((h, new_content))
        else:
            updated.append((h, content))

    if not found and bullets:
        updated.append((target_heading, bullets))

    return updated


def build_new_changelog(
    changelog_text: str,
    new_version: str,
    commit_buckets: dict[str, list[ConventionalCommit]],
) -> str:
    lines = changelog_text.splitlines()
    unreleased_start, unreleased_end = parse_unreleased_section(lines)

    prefix = lines[:unreleased_start]
    unreleased_body_lines = lines[unreleased_start + 1 : unreleased_end]

    preface_lines, subsections = parse_subsections(unreleased_body_lines)

    # Skapa "new release"-sektion: allt som låg i Unreleased flyttas,
    # och commit-bullets appendas där det passar.
    released_subsections = [(h, list(content)) for (h, content) in subsections]

    for bucket_heading, commits in commit_buckets.items():
        if not commits:
            continue
        bullets = [format_changelog_bullet(c) for c in commits]
        released_subsections = upsert_bullets(
            released_subsections, bucket_heading, bullets=bullets
        )

    date_str = _dt.date.today().isoformat()
    new_release_lines: list[str] = []
    new_release_lines.append(f"## {new_version} - {date_str}")
    new_release_lines.extend(preface_lines)
    # Ensure visual separation between preface_lines and first heading.
    if preface_lines and preface_lines[-1].strip() != "":
        new_release_lines.append("")

    for heading, content in released_subsections:
        new_release_lines.append(heading)
        new_release_lines.extend(content)
        # content can include trailing blanks; we do not force an extra blank line here.

    # Ny "Unreleased": samma headings som den nya released-sektionen, men tomma bullets.
    unreleased_new_lines: list[str] = ["## Unreleased"]
    unreleased_new_lines.extend(preface_lines)
    for heading, _content in released_subsections:
        unreleased_new_lines.append(heading)
    # (ingen bullets)

    suffix = lines[unreleased_end:]

    # Slutmontering: prefix + ny release + tom Unreleased + suffix
    out_lines: list[str] = []
    out_lines.extend(prefix)
    if prefix and prefix[-1].strip() != "":
        out_lines.append("")
    out_lines.extend(new_release_lines)
    out_lines.append("")
    out_lines.extend(unreleased_new_lines)
    out_lines.extend(suffix)

    # splitlines() tar bort slut-rad; lägg tillbaka newline vid behov
    out_text = "\n".join(out_lines).rstrip() + "\n"
    return out_text


def collect_commit_buckets(commits: list[ConventionalCommit]) -> dict[str, list[ConventionalCommit]]:
    buckets: dict[str, list[ConventionalCommit]] = {
        "Added": [],
        "Fixed": [],
        "Changed": [],
    }
    for c in commits:
        if c.type == "feat":
            buckets["Added"].append(c)
        elif c.type == "fix":
            buckets["Fixed"].append(c)
        else:
            buckets["Changed"].append(c)
    return {k: v for k, v in buckets.items() if v}


def _git_available() -> bool:
    try:
        subprocess.check_output(
            ["git", "rev-parse", "--is-inside-work-tree"],
            stderr=subprocess.STDOUT,
            text=True,
        )
        return True
    except Exception:
        return False


def _git_tag_exists(tag_name: str) -> bool:
    # `rev-parse` exit-kod 0 om taggen finns, 1 annars.
    try:
        subprocess.check_call(
            ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag_name}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _git_has_remote(remote_name: str) -> bool:
    try:
        subprocess.check_call(
            ["git", "remote", "get-url", remote_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _git_commit_files(version_path: Path, changelog_path: Path, message: str) -> None:
    subprocess.check_call(["git", "add", str(version_path), str(changelog_path)])
    subprocess.check_call(["git", "commit", "-m", message])


def _git_create_annotated_tag(tag_name: str, message: str) -> None:
    subprocess.check_call(["git", "tag", "-a", tag_name, "-m", message])


def _git_push_tag(remote_name: str, tag_name: str) -> None:
    subprocess.check_call(["git", "push", remote_name, tag_name])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Bump version + changelog via Conventional Commits.")
    parser.add_argument("--version-file", default="VERSION", help="Path till VERSION-fil.")
    parser.add_argument("--changelog", default="CHANGELOG.md", help="Path till CHANGELOG.md.")
    parser.add_argument(
        "--commits-file",
        default=None,
        help="Fil med commit-meddelanden (en per rad eller separerade av tom rad).",
    )
    parser.add_argument(
        "--git-range",
        default=None,
        help="Git-range att läsa från, t.ex. 'v1.0.0..HEAD'. Används bara om --commits-file saknas.",
    )
    parser.add_argument(
        "--bump",
        choices=["major", "minor", "patch"],
        default=None,
        help="Tvinga bump-level (annars beräknas den från Conventional Commits).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skriv ut förslag men gör inga ändringar.",
    )
    parser.add_argument(
        "--commit-changes",
        action="store_true",
        help="Skriv VERSION + CHANGELOG.md och skapa en git-commit för ändringarna.",
    )
    parser.add_argument(
        "--create-tag",
        action="store_true",
        help="Skapa en git-tag vX.Y.Z (kräver --commit-changes så att taggen pekar på rätt commit).",
    )
    parser.add_argument(
        "--tag-prefix",
        default="v",
        help="Prefix för taggar, t.ex. 'v' => v1.2.3",
    )
    parser.add_argument(
        "--commit-message",
        default=None,
        help="Commit-meddelande för versionbumpen. Standard: 'chore: bump version to X.Y.Z'",
    )
    parser.add_argument(
        "--tag-message",
        default=None,
        help="Meddelande för taggannotering. Standard: 'Release X.Y.Z'",
    )
    parser.add_argument(
        "--push-tag",
        action="store_true",
        help="Pusha taggen till 'origin'. Kräver --create-tag.",
    )

    args = parser.parse_args(argv)

    version_path = Path(args.version_file)
    changelog_path = Path(args.changelog)

    if not version_path.exists():
        raise SystemExit(f"Hittar inte {version_path}")
    if not changelog_path.exists():
        raise SystemExit(f"Hittar inte {changelog_path}")

    current_version = validate_semver(read_text(version_path).strip(), version_path)
    changelog_text = read_text(changelog_path)

    commits: list[ConventionalCommit] = []
    if args.commits_file:
        commits_text = read_text(Path(args.commits_file))
        commits = parse_commits_from_text(commits_text)
    elif not sys.stdin.isatty():
        commits_text = sys.stdin.read()
        commits = parse_commits_from_text(commits_text)
    else:
        # Försök via git om range finns.
        if args.git_range:
            commits = get_commits_from_git(args.git_range)
        else:
            raise SystemExit(
                "Saknar input: använd --commits-file (eller piped stdin), "
                "eller ange --git-range om git-historik finns."
            )

    bump_level = args.bump or classify_bump(commits)
    next_version = bump_version(current_version, bump_level)

    commit_buckets = collect_commit_buckets(commits)

    print(f"Nuvarande version: {current_version}")
    print(f"Bump-level: {bump_level}")
    print(f"Nästa version: {next_version}")
    if commits:
        print("Commit-bild:")
        for k in ("Added", "Fixed", "Changed"):
            if k in commit_buckets:
                print(f"  {k}: {len(commit_buckets[k])}")

    if args.dry_run:
        print("--dry-run: inga filer uppdaterades")
        return 0

    # Skriv VERSION.
    version_path.write_text(next_version + "\n", encoding="utf-8")

    # Bygg + skriv CHANGELOG.md.
    new_changelog = build_new_changelog(
        changelog_text=changelog_text,
        new_version=next_version,
        commit_buckets=commit_buckets,
    )
    changelog_path.write_text(new_changelog, encoding="utf-8")

    if args.commit_changes or args.create_tag or args.push_tag:
        if not _git_available():
            raise SystemExit("Git verkar inte vara tillgängligt eller så är detta inte en git-worktree.")
        if args.create_tag and not args.commit_changes:
            raise SystemExit("--create-tag kräver --commit-changes så att taggen pekar på rätt commit.")
        if args.push_tag and not args.create_tag:
            raise SystemExit("--push-tag kräver --create-tag.")
        if args.push_tag and not _git_has_remote("origin"):
            raise SystemExit("Kan inte pusha tagg: saknar 'origin' remote i git.")

    if args.commit_changes:
        msg = args.commit_message or f"chore: bump version to {next_version}"
        _git_commit_files(version_path, changelog_path, msg)

    if args.create_tag:
        tag_name = f"{args.tag_prefix}{next_version}"
        if _git_tag_exists(tag_name):
            print(f"Taggen {tag_name} finns redan; hoppar över.")
        else:
            tmsg = args.tag_message or f"Release {next_version}"
            _git_create_annotated_tag(tag_name, tmsg)

        if args.push_tag:
            _git_push_tag("origin", tag_name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

