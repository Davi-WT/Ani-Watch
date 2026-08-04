#!/usr/bin/env python3
"""Ani-Watch: a friendly Qt frontend for ani-cli."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import traceback
from typing import Any, Callable

try:
    from PyQt6.QtCore import (
        QObject,
        QProcess,
        QProcessEnvironment,
        QRunnable,
        QTimer,
        Qt,
        QThreadPool,
        pyqtSignal,
    )
    from PyQt6.QtGui import QFont, QKeySequence, QShortcut
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )
    QT6 = True
except ImportError:
    try:
        from PyQt5.QtCore import (
            QObject,
            QProcess,
            QProcessEnvironment,
            QRunnable,
            QTimer,
            Qt,
            QThreadPool,
            pyqtSignal,
        )
        from PyQt5.QtGui import QFont, QKeySequence
        from PyQt5.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QFrame,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QProgressBar,
            QPushButton,
            QShortcut,
            QSplitter,
            QVBoxLayout,
            QWidget,
        )
        QT6 = False
    except ImportError as exc:
        print(
            "PyQt não está instalado. Execute: python3 -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

from ani_watch_core import (
    AniCliError,
    AnimeResult,
    Episode,
    ani_cli_version,
    build_ani_cli_command,
    build_player_command,
    dependency_status,
    extract_selected_link,
    fetch_episodes,
    find_ani_cli,
    install_ani_cli,
    missing_required_dependencies,
    prepare_process_command,
    search_anime,
)


APP_NAME = "Ani-Watch"
ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter if QT6 else Qt.AlignCenter
HORIZONTAL = Qt.Orientation.Horizontal if QT6 else Qt.Horizontal
USER_ROLE = Qt.ItemDataRole.UserRole if QT6 else Qt.UserRole
PROCESS_NOT_RUNNING = QProcess.ProcessState.NotRunning if QT6 else QProcess.NotRunning


class TaskSignals(QObject):
    success = pyqtSignal(object)
    error = pyqtSignal(str)
    finished = pyqtSignal()


class Task(QRunnable):
    def __init__(self, function: Callable[[], Any]):
        super().__init__()
        self.function = function
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            result = self.function()
        except AniCliError as exc:
            self.signals.error.emit(str(exc))
        except Exception:
            traceback.print_exc()
            self.signals.error.emit("Ocorreu um erro inesperado. Consulte o terminal para detalhes.")
        else:
            self.signals.success.emit(result)
        finally:
            self.signals.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.executable: Path | None = None
        self.results: list[AnimeResult] = []
        self.selected: AnimeResult | None = None
        self.last_query = ""
        self.tasks: set[Task] = set()
        self.process: QProcess | None = None
        self.process_kind: str | None = None
        self.process_output = ""
        self.pending_player = "mpv"
        self.pending_title = ""
        self.pending_episode = ""
        self.pending_subtitle_language = "en"
        self.pending_subtitle_label = "Inglês"
        self.pool = QThreadPool.globalInstance()

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(940, 640)
        self.resize(1120, 760)
        self._build_ui()
        self._apply_theme()
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self._focus_search)
        self._refresh_installation(auto_install=os.name != "nt")

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(28, 24, 28, 24)
        root_layout.setSpacing(18)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        brand = QLabel("ANI  /  WATCH")
        brand.setObjectName("brand")
        title = QLabel("Sua sessão começa aqui.")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Pesquise, escolha o episódio e deixe o ani-cli abrir o player.")
        subtitle.setObjectName("muted")
        title_box.addWidget(brand)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        self.status_badge = QLabel("Verificando…")
        self.status_badge.setObjectName("statusBadge")
        self.status_badge.setAlignment(ALIGN_CENTER)
        self.status_badge.setFixedHeight(32)
        self.install_button = QPushButton("Instalar / atualizar")
        self.install_button.setObjectName("secondaryButton")
        self.install_button.clicked.connect(self._install_or_update)
        header.addWidget(self.status_badge)
        header.addWidget(self.install_button)
        root_layout.addLayout(header)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.hide()
        root_layout.addWidget(self.progress)

        splitter = QSplitter(HORIZONTAL)
        splitter.setChildrenCollapsible(False)

        search_panel = QFrame()
        search_panel.setObjectName("panel")
        search_layout = QVBoxLayout(search_panel)
        search_layout.setContentsMargins(20, 20, 20, 20)
        search_layout.setSpacing(12)
        search_title = QLabel("Explorar")
        search_title.setObjectName("sectionTitle")
        search_layout.addWidget(search_title)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Ex.: One Piece")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._search)
        self.search_button = QPushButton("Buscar")
        self.search_button.setObjectName("primaryButton")
        self.search_button.clicked.connect(self._search)
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.search_button)
        search_layout.addLayout(search_row)

        self.results_label = QLabel("Digite um título para começar")
        self.results_label.setObjectName("muted")
        search_layout.addWidget(self.results_label)
        self.results_list = QListWidget()
        self.results_list.setObjectName("resultsList")
        self.results_list.itemSelectionChanged.connect(self._select_result)
        self.results_list.itemDoubleClicked.connect(lambda _item: self._play())
        search_layout.addWidget(self.results_list, 1)
        splitter.addWidget(search_panel)

        detail_panel = QFrame()
        detail_panel.setObjectName("panel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(24, 22, 24, 22)
        detail_layout.setSpacing(14)

        self.selected_kicker = QLabel("NENHUM TÍTULO SELECIONADO")
        self.selected_kicker.setObjectName("brand")
        self.selected_title = QLabel("Escolha um anime na lista")
        self.selected_title.setObjectName("selectedTitle")
        self.selected_title.setWordWrap(True)
        detail_layout.addWidget(self.selected_kicker)
        detail_layout.addWidget(self.selected_title)

        options = QHBoxLayout()
        episode_box = QVBoxLayout()
        episode_label = QLabel("Episódio")
        episode_label.setObjectName("fieldLabel")
        self.episode_combo = QComboBox()
        self.episode_combo.setEnabled(False)
        episode_box.addWidget(episode_label)
        episode_box.addWidget(self.episode_combo)

        quality_box = QVBoxLayout()
        quality_label = QLabel("Qualidade")
        quality_label.setObjectName("fieldLabel")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["best", "1080p", "720p", "480p", "360p", "worst"])
        quality_box.addWidget(quality_label)
        quality_box.addWidget(self.quality_combo)

        player_box = QVBoxLayout()
        player_label = QLabel("Player")
        player_label.setObjectName("fieldLabel")
        self.player_combo = QComboBox()
        self.player_combo.addItems(["mpv", "vlc"])
        player_box.addWidget(player_label)
        player_box.addWidget(self.player_combo)

        subtitle_box = QVBoxLayout()
        subtitle_label = QLabel("Legenda")
        subtitle_label.setObjectName("fieldLabel")
        self.subtitle_combo = QComboBox()
        self.subtitle_combo.addItem("Português", "pt-BR")
        self.subtitle_combo.addItem("Inglês", "en")
        self.subtitle_combo.setCurrentIndex(1)
        self.subtitle_combo.setToolTip(
            "Preferência de faixa; vídeos com legenda gravada não podem ser alterados."
        )
        subtitle_box.addWidget(subtitle_label)
        subtitle_box.addWidget(self.subtitle_combo)
        options.addLayout(episode_box, 2)
        options.addLayout(quality_box, 1)
        options.addLayout(player_box, 1)
        options.addLayout(subtitle_box, 1)
        detail_layout.addLayout(options)

        self.dubbed_checkbox = QCheckBox("Usar versão dublada quando disponível")
        detail_layout.addWidget(self.dubbed_checkbox)

        actions = QHBoxLayout()
        self.play_button = QPushButton("▶  Assistir agora")
        self.play_button.setObjectName("primaryButton")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self._play)
        self.download_button = QPushButton("↓  Baixar episódio")
        self.download_button.setObjectName("secondaryButton")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(lambda: self._play(download=True))
        actions.addWidget(self.play_button, 2)
        actions.addWidget(self.download_button, 1)
        detail_layout.addLayout(actions)

        detail_layout.addSpacing(4)
        activity_title = QLabel("Atividade")
        activity_title.setObjectName("sectionTitle")
        detail_layout.addWidget(activity_title)
        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(300)
        self.log.setPlaceholderText("As mensagens do ani-cli aparecerão aqui.")
        detail_layout.addWidget(self.log, 1)
        splitter.addWidget(detail_panel)
        splitter.setSizes([420, 650])
        root_layout.addWidget(splitter, 1)

        footer = QHBoxLayout()
        self.dependencies_label = QLabel("Dependências: verificando…")
        self.dependencies_label.setObjectName("muted")
        footer.addWidget(self.dependencies_label)
        footer.addStretch()
        hint = QLabel("Ctrl+L para pesquisar")
        hint.setObjectName("muted")
        footer.addWidget(hint)
        root_layout.addLayout(footer)
        self.setCentralWidget(root)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            * { font-family: Inter, 'Noto Sans', sans-serif; }
            QMainWindow { background: #0b0d12; }
            QWidget { color: #edf0f7; }
            QLabel#brand { color: #8b7cff; font-size: 11px; font-weight: 800; letter-spacing: 2px; }
            QLabel#pageTitle { font-size: 28px; font-weight: 750; }
            QLabel#selectedTitle { font-size: 24px; font-weight: 720; }
            QLabel#sectionTitle { font-size: 15px; font-weight: 700; }
            QLabel#fieldLabel { color: #a7adbb; font-size: 11px; font-weight: 700; }
            QLabel#muted { color: #858b99; }
            QLabel#statusBadge { background: #17221d; color: #78dba5; border: 1px solid #284b38;
                border-radius: 14px; padding: 7px 12px; font-weight: 700; }
            QFrame#panel { background: #12151d; border: 1px solid #232735; border-radius: 16px; }
            QLineEdit, QComboBox { background: #191d27; border: 1px solid #2b3040; border-radius: 9px;
                padding: 10px 12px; min-height: 20px; selection-background-color: #6f5cff; }
            QLineEdit:focus, QComboBox:focus { border-color: #7b6cff; }
            QComboBox::drop-down { border: none; width: 28px; }
            QComboBox QAbstractItemView { background: #191d27; color: #edf0f7; border: 1px solid #34394a;
                selection-background-color: #6f5cff; }
            QPushButton { border: none; border-radius: 9px; padding: 10px 16px; font-weight: 700; }
            QPushButton#primaryButton { background: #7262f3; color: white; }
            QPushButton#primaryButton:hover { background: #8678ff; }
            QPushButton#secondaryButton { background: #202431; color: #dfe3ec; border: 1px solid #303647; }
            QPushButton#secondaryButton:hover { background: #292e3d; }
            QPushButton#primaryButton:disabled, QPushButton#secondaryButton:disabled {
                background: #1a1d25; color: #555b69; border-color: #242832; }
            QListWidget#resultsList { background: transparent; border: none; outline: none; }
            QListWidget#resultsList::item { background: #181c25; border: 1px solid transparent;
                border-radius: 9px; padding: 13px 12px; margin: 3px 0; }
            QListWidget#resultsList::item:hover { border-color: #3b4052; }
            QListWidget#resultsList::item:selected { background: #25223d; color: #f4f2ff; border-color: #685bd2; }
            QPlainTextEdit#log { background: #0d0f14; color: #b8c0d2; border: 1px solid #252a37;
                border-radius: 10px; padding: 10px; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
            QCheckBox { spacing: 9px; color: #bac0cd; }
            QCheckBox::indicator { width: 17px; height: 17px; }
            QProgressBar { border: none; background: transparent; }
            QProgressBar::chunk { background: #7868ff; border-radius: 1px; }
            QSplitter::handle { background: transparent; width: 14px; }
            QScrollBar:vertical { width: 9px; background: transparent; }
            QScrollBar::handle:vertical { background: #343949; border-radius: 4px; min-height: 30px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            """
        )

    def _start_task(
        self,
        function: Callable[[], Any],
        success: Callable[[Any], None],
        error: Callable[[str], None] | None = None,
    ) -> None:
        task = Task(function)
        self.tasks.add(task)
        task.signals.success.connect(success)
        task.signals.error.connect(error or self._show_error)
        task.signals.finished.connect(lambda: self._finish_task(task))
        self.pool.start(task)

    def _finish_task(self, task: Task) -> None:
        self.tasks.discard(task)
        if not self.tasks:
            self.progress.hide()

    def _set_busy(self, busy: bool = True) -> None:
        self.progress.setVisible(busy)

    def _append_log(self, message: str) -> None:
        if message.strip():
            self.log.appendPlainText(message.rstrip())

    def _focus_search(self) -> None:
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _refresh_installation(self, auto_install: bool = False) -> None:
        self.executable = find_ani_cli()
        if self.executable is None and auto_install:
            self._append_log("ani-cli não encontrado. Iniciando instalação para este usuário…")
            self._install_or_update()
            return

        version = ani_cli_version(self.executable)
        if self.executable and version:
            self.status_badge.setText(f"● ani-cli {version}")
            self.status_badge.setStyleSheet("")
            self.install_button.setText("Atualizar")
        else:
            self.status_badge.setText("● não instalado")
            self.status_badge.setStyleSheet(
                "background:#2a1b1d;color:#ff9b9b;border:1px solid #5a3034;"
                "border-radius:14px;padding:7px 12px;font-weight:700;"
            )
            self.install_button.setText("Como instalar" if os.name == "nt" else "Instalar")

        status = dependency_status()
        missing = missing_required_dependencies(status)
        optional_missing = [name for name in ("yt-dlp", "ffmpeg") if not status[name]]
        if missing:
            self.dependencies_label.setText("Faltando: " + ", ".join(missing))
            self.dependencies_label.setStyleSheet("color: #ffb36b;")
        elif optional_missing:
            self.dependencies_label.setText(
                "Pronto para assistir · download opcional: " + ", ".join(optional_missing)
            )
        else:
            self.dependencies_label.setText("Todas as dependências estão prontas")
            self.dependencies_label.setStyleSheet("color: #78dba5;")

    def _install_or_update(self) -> None:
        if os.name == "nt":
            QMessageBox.information(
                self,
                APP_NAME,
                "No Windows, instale o ani-cli pelo Scoop e mantenha o Git Bash "
                "disponível no PATH. Depois, reabra o Ani-Watch.\n\n"
                "Comando: scoop install ani-cli",
            )
            return
        self.install_button.setEnabled(False)
        self._set_busy()

        def installed(path: Path) -> None:
            self._append_log(f"Instalação concluída: {path}")
            self.install_button.setEnabled(True)
            self._refresh_installation()

        def failed(message: str) -> None:
            self.install_button.setEnabled(True)
            self._show_error(message)
            self._refresh_installation()

        self._start_task(install_ani_cli, installed, failed)

    def _search(self) -> None:
        if not self.search_button.isEnabled():
            return
        query = self.search_input.text().strip()
        if not query:
            self._show_error("Digite o nome de um anime.")
            return
        self.last_query = query
        self.selected = None
        self.selected_kicker.setText("NENHUM TÍTULO SELECIONADO")
        self.selected_title.setText("Escolha um anime na lista")
        self.episode_combo.clear()
        self.episode_combo.setEnabled(False)
        self._update_action_buttons()
        self.search_button.setEnabled(False)
        self.results_list.clear()
        self.results_label.setText("Buscando…")
        self._set_busy()

        def found(results: list[AnimeResult]) -> None:
            self.results = results
            self.results_label.setText(f"{len(results)} resultado(s)")
            for anime in results:
                item = QListWidgetItem(anime.title)
                item.setData(USER_ROLE, anime)
                item.setToolTip(anime.anime_id)
                self.results_list.addItem(item)
            self.search_button.setEnabled(True)
            if results:
                self.results_list.setCurrentRow(0)

        def failed(message: str) -> None:
            self.results_label.setText("Não foi possível concluir a busca")
            self.search_button.setEnabled(True)
            self._show_error(message)

        self._start_task(lambda: search_anime(query), found, failed)

    def _select_result(self) -> None:
        items = self.results_list.selectedItems()
        if not items:
            return
        self.selected = items[0].data(USER_ROLE)
        self.selected_kicker.setText(f"RESULTADO {self.selected.index:02d}")
        self.selected_title.setText(self.selected.title)
        self.episode_combo.clear()
        self.episode_combo.setEnabled(False)
        self.play_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self._append_log(f"Carregando episódios de {self.selected.title}…")
        selected_id = self.selected.anime_id
        self._set_busy()

        def loaded(episodes: list[Episode]) -> None:
            if not self.selected or self.selected.anime_id != selected_id:
                return
            for episode in episodes:
                label = f"{episode.number}  ·  filler" if episode.filler else episode.number
                self.episode_combo.addItem(label, episode.number)
            self.episode_combo.setEnabled(True)
            self._update_action_buttons()
            self._append_log(f"{len(episodes)} episódio(s) disponível(is).")

        self._start_task(lambda: fetch_episodes(selected_id), loaded)

    def _play(self, download: bool = False) -> None:
        if self.process is not None:
            return
        if not self.selected or self.episode_combo.currentIndex() < 0:
            self._show_error("Selecione um anime e um episódio.")
            return
        self.executable = find_ani_cli()
        if self.executable is None:
            self._show_error("O ani-cli ainda não está instalado.")
            return
        status = dependency_status()
        missing = missing_required_dependencies(status)
        if missing:
            self._show_error("Instale primeiro: " + ", ".join(missing))
            return
        selected_player = self.player_combo.currentText()
        if not download and not status[selected_player]:
            self._show_error(f"O player {selected_player} não está instalado.")
            return
        if download and not status["yt-dlp"] and not status["ffmpeg"]:
            self._show_error("Para baixar, instale yt-dlp ou ffmpeg.")
            return

        episode = str(self.episode_combo.currentData())
        command = build_ani_cli_command(
            self.executable,
            self.last_query,
            self.selected.index,
            episode,
            self.quality_combo.currentText(),
            dubbed=self.dubbed_checkbox.isChecked(),
            # For playback, ani-cli resolves the stream in debug mode. The GUI
            # starts the real player itself so its lifetime can be monitored.
            player=selected_player if download else "mpv",
            download=download,
        )
        self._append_log(
            ("Baixando" if download else "Abrindo")
            + f" {self.selected.title} · episódio {episode}…"
        )
        self.pending_player = selected_player
        self.pending_title = self.selected.title
        self.pending_episode = episode
        self.pending_subtitle_language = str(self.subtitle_combo.currentData())
        self.pending_subtitle_label = self.subtitle_combo.currentText()
        self.process_kind = "download" if download else "resolve"
        self.process_output = ""
        self._update_action_buttons()
        self.process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("TERM", os.environ.get("TERM", "xterm-256color"))
        if not download:
            environment.insert("ANI_CLI_PLAYER", "debug")
        self.process.setProcessEnvironment(environment)
        process_command = prepare_process_command(command)
        self.process.setProgram(process_command[0])
        self.process.setArguments(process_command[1:])
        self.process.readyReadStandardOutput.connect(self._read_process_output)
        self.process.readyReadStandardError.connect(self._read_process_error)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.process.start()

    def _read_process_output(self) -> None:
        if self.process:
            text = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
            self.process_output += text
            self._append_log(self._strip_ansi(text))

    def _read_process_error(self) -> None:
        if self.process:
            text = bytes(self.process.readAllStandardError()).decode(errors="replace")
            self.process_output += text
            self._append_log(self._strip_ansi(text))

    def _process_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        kind = self.process_kind
        output = self.process_output
        if self.process:
            output += bytes(self.process.readAllStandardOutput()).decode(errors="replace")
            output += bytes(self.process.readAllStandardError()).decode(errors="replace")
            self.process.deleteLater()
        self.process = None
        self.process_kind = None
        self.process_output = ""

        if kind == "resolve" and exit_code == 0:
            try:
                media_url = extract_selected_link(output)
            except AniCliError as exc:
                self._append_log(f"Erro: {exc}")
                self._update_action_buttons()
                return
            self._start_player(media_url)
            return

        if exit_code == 0:
            if kind == "player":
                self._append_log("Player fechado. Você já pode escolher outro episódio.")
            else:
                self._append_log("Concluído.")
        else:
            process_name = "player" if kind == "player" else "ani-cli"
            self._append_log(f"O {process_name} terminou com código {exit_code}.")
        self._update_action_buttons()

    def _start_player(self, media_url: str) -> None:
        title = f"{self.pending_title} Episode {self.pending_episode}"
        command = build_player_command(
            self.pending_player,
            media_url,
            title,
            self.pending_subtitle_language,
        )

        self.process_kind = "player"
        self.process_output = ""
        self.process = QProcess(self)
        self.process.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
        self.process.setProgram(command[0])
        self.process.setArguments(command[1:])
        self.process.readyReadStandardOutput.connect(self._read_process_output)
        self.process.readyReadStandardError.connect(self._read_process_error)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self._append_log(
            f"Reproduzindo no {self.pending_player} · preferência de legenda: "
            f"{self.pending_subtitle_label}. Feche o player para liberar os controles."
        )
        self._update_action_buttons()
        self.process.start()

    def _process_error(self, _error: QProcess.ProcessError) -> None:
        self._append_log("Não foi possível iniciar o processo de reprodução.")
        # FailedToStart does not consistently emit finished on every Qt version.
        QTimer.singleShot(0, self._recover_failed_process)

    def _recover_failed_process(self) -> None:
        if self.process and self.process.state() == PROCESS_NOT_RUNNING:
            self.process.deleteLater()
            self.process = None
            self.process_kind = None
            self.process_output = ""
            self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        ready = (
            self.selected is not None
            and self.episode_combo.currentIndex() >= 0
            and self.process is None
            and self.process_kind is None
        )
        self.play_button.setEnabled(ready)
        self.download_button.setEnabled(ready)
        if self.process_kind == "player":
            self.play_button.setText("▶  Reproduzindo…")
        elif self.process_kind == "download":
            self.play_button.setText("↓  Baixando…")
        elif self.process_kind == "resolve":
            self.play_button.setText("◌  Preparando…")
        else:
            self.play_button.setText("▶  Assistir agora")

    @staticmethod
    def _strip_ansi(text: str) -> str:
        import re

        return re.sub(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|$))", "", text)

    def _show_error(self, message: str) -> None:
        self._append_log("Erro: " + message)
        QMessageBox.warning(self, APP_NAME, message)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setFont(QFont("Inter", 10))
    window = MainWindow()
    window.show()
    return app.exec() if QT6 else app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
