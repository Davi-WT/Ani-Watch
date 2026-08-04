"""Core services for the Ani-Watch frontend.

This module intentionally uses only Python's standard library so it can also be
tested on systems where the Qt frontend has not been installed yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


ANI_CLI_URL = "https://raw.githubusercontent.com/pystardust/ani-cli/master/ani-cli"
ANIDB_BASE_URL = "https://anidb.app"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class AniCliError(RuntimeError):
    """An error that is safe to display in the graphical interface."""


@dataclass(frozen=True, slots=True)
class AnimeResult:
    index: int
    anime_id: str
    title: str


@dataclass(frozen=True, slots=True)
class Episode:
    number: str
    filler: bool = False


def _request_text(url: str, timeout: int = 20) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise AniCliError(f"O servidor respondeu com erro HTTP {exc.code}.") from exc
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise AniCliError(f"Não foi possível acessar a internet: {reason}") from exc
    except TimeoutError as exc:
        raise AniCliError("A conexão demorou demais. Tente novamente.") from exc


def local_install_path() -> Path:
    return Path.home() / ".local" / "bin" / "ani-cli"


def find_ani_cli() -> Path | None:
    candidate = local_install_path()
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    executable = shutil.which("ani-cli")
    return Path(executable) if executable else None


def ani_cli_version(executable: Path | None = None) -> str | None:
    executable = executable or find_ani_cli()
    if executable is None:
        return None
    try:
        command = prepare_process_command([str(executable), "--version"])
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    version = (result.stdout or result.stderr).strip().splitlines()
    return version[-1] if version and result.returncode == 0 else None


def install_ani_cli(progress: Callable[[str], None] | None = None) -> Path:
    """Install the official script for the current user, without sudo."""

    if os.name == "nt":
        raise AniCliError(
            "No Windows, o ani-cli precisa do Git Bash e deve ser instalado pelo Scoop."
        )

    notify = progress or (lambda _message: None)
    destination = local_install_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    notify("Baixando o ani-cli oficial…")
    script = _request_text(ANI_CLI_URL)

    if not script.startswith("#!/bin/sh") or 'version_number="' not in script:
        raise AniCliError("O arquivo recebido não parece ser uma versão válida do ani-cli.")

    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=".ani-cli-",
            delete=False,
        ) as temporary:
            temporary.write(script)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        mode = os.stat(temporary_name).st_mode
        os.chmod(temporary_name, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(temporary_name, destination)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)

    notify(f"Instalado em {destination}")
    return destination


def dependency_status() -> dict[str, bool]:
    """Return the dependencies relevant to normal playback and downloads."""

    names = (
        "bash",
        "curl",
        "grep",
        "sed",
        "fzf",
        "mpv",
        "vlc",
        "yt-dlp",
        "ffmpeg",
    )
    return {name: shutil.which(name) is not None for name in names}


def missing_required_dependencies(
    status: dict[str, bool] | None = None,
    platform_name: str | None = None,
) -> list[str]:
    status = status or dependency_status()
    platform_name = platform_name or os.name
    command_dependencies = (
        ("bash", "fzf") if platform_name == "nt" else ("curl", "grep", "sed", "fzf")
    )
    missing = [name for name in command_dependencies if not status[name]]
    if not status["mpv"] and not status["vlc"]:
        missing.append("mpv ou vlc")
    return missing


def prepare_process_command(
    command: list[str],
    platform_name: str | None = None,
    command_interpreter: str | None = None,
) -> list[str]:
    """Wrap Windows batch launchers so QProcess can execute them reliably."""

    if not command:
        raise AniCliError("Não há um comando para executar.")
    platform_name = platform_name or os.name
    if platform_name != "nt" or Path(command[0]).suffix.lower() not in {".bat", ".cmd"}:
        return command

    interpreter = command_interpreter or os.environ.get("COMSPEC", "cmd.exe")
    shell_command = subprocess.list2cmdline(command)
    return [interpreter, "/d", "/s", "/c", shell_command]


def search_anime(query: str) -> list[AnimeResult]:
    query = query.strip()
    if not query:
        raise AniCliError("Digite o nome de um anime.")

    page = _request_text(f"{ANIDB_BASE_URL}/browse?q={quote_plus(query)}")
    if "Just a moment" in page:
        raise AniCliError("A busca foi bloqueada pelo Cloudflare. Tente novamente mais tarde.")

    # This follows the same HTML fields used by the upstream ani-cli script.
    flat_page = page.replace("\n", " ")
    chunks = re.split(r"(?=<a\s+href)", flat_page, flags=re.IGNORECASE)
    matches: list[tuple[str, str]] = []
    pattern = re.compile(
        r'anime/([a-z0-9-]+-[0-9]+)".*?alt="([^"]+)"', re.IGNORECASE
    )
    for chunk in chunks:
        match = pattern.search(chunk)
        if not match:
            continue
        matches.append((match.group(1), unescape(match.group(2))))

    if not matches:
        raise AniCliError("Nenhum resultado encontrado.")
    return [
        AnimeResult(index=index, anime_id=anime_id, title=title)
        for index, (anime_id, title) in enumerate(matches, start=1)
    ]


def fetch_episodes(anime_id: str) -> list[Episode]:
    numeric_id = anime_id.rsplit("-", 1)[-1]
    if not numeric_id.isdigit():
        raise AniCliError("O identificador do anime é inválido.")

    raw_data = _request_text(f"{ANIDB_BASE_URL}/api/frontend/anime/{numeric_id}/episodes")
    try:
        payload = json.loads(raw_data)
        records = payload.get("episodes", payload) if isinstance(payload, dict) else payload
        episodes = [
            Episode(number=str(item["number"]), filler=bool(item.get("filler", False)))
            for item in records
            if isinstance(item, dict) and item.get("number") is not None
        ]
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        raise AniCliError("O servidor retornou uma lista de episódios inválida.") from exc

    if not episodes:
        raise AniCliError("Nenhum episódio disponível para este título.")
    return episodes


def build_ani_cli_command(
    executable: Path,
    query: str,
    result_index: int,
    episode: str,
    quality: str = "best",
    *,
    dubbed: bool = False,
    player: str = "mpv",
    download: bool = False,
) -> list[str]:
    if not query.strip() or result_index < 1 or not episode.strip():
        raise AniCliError("Selecione um anime e um episódio.")
    command = [
        str(executable),
        query.strip(),
        "--select-nth",
        str(result_index),
        "--episode",
        episode.strip(),
        "--quality",
        quality,
    ]
    if dubbed:
        command.append("--dub")
    if player == "vlc":
        command.append("--vlc")
    if download:
        command.append("--download")
    return command


def build_player_command(
    player: str,
    media_url: str,
    title: str,
    subtitle_language: str = "en",
) -> list[str]:
    """Build a player command with the requested subtitle preference."""

    language_codes = {
        "pt-BR": ("pt-BR", "pt", "por", "en", "eng"),
        "en": ("en", "eng"),
    }
    try:
        preferred_languages = ",".join(language_codes[subtitle_language])
    except KeyError as exc:
        raise AniCliError("O idioma de legenda selecionado não é válido.") from exc

    if player == "vlc":
        return [
            "vlc",
            "--no-one-instance",
            "--play-and-exit",
            f"--meta-title={title}",
            f"--sub-language={preferred_languages}",
            media_url,
        ]
    if player == "mpv":
        return [
            "mpv",
            f"--force-media-title={title}",
            f"--slang={preferred_languages}",
            media_url,
        ]
    raise AniCliError("O player selecionado não é válido.")


def extract_selected_link(output: str) -> str:
    """Extract the final media URL printed by ani-cli's debug player."""

    clean_output = re.sub(
        r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|$))", "", output
    )
    match = re.search(r"Selected link:\s*(https?://\S+)", clean_output)
    if not match:
        raise AniCliError("O ani-cli não retornou um link de reprodução válido.")
    return match.group(1)
