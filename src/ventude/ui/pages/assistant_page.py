from __future__ import annotations

import asyncio
import base64
import contextlib
import html
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ventude.assistant.service import AssistantService
from ventude.assistant.types import Completed, Failed, TextDelta, ToolUsed
from ventude.core.async_worker import AsyncWorker
from ventude.core.events import EventBus
from ventude.ui import themes
from ventude.ui.icons import icon_button

log = logging.getLogger(__name__)
MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
MAX_IMAGE = 5_000_000
STATUS_PT = {"executed": "executada", "denied": "negada", "error": "erro"}


class _Bridge(QObject):
    delta = Signal(str)
    tool = Signal(str, str, str)
    done = Signal()
    failed = Signal(str)
    approval = Signal(str)
    info = Signal(str)
    models = Signal(list)


def image_to_data_url(path: str) -> str:
    p = Path(path)
    mime = MIME.get(p.suffix.lower())
    if not mime:
        raise ValueError("Formato de imagem não suportado.")
    if p.stat().st_size > MAX_IMAGE:
        raise ValueError("Imagem maior que 5 MB.")
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


class AssistantPage(QWidget):
    def __init__(self, service_factory: Any, worker: AsyncWorker, bus: EventBus) -> None:
        super().__init__()
        self.worker, self.bus = worker, bus
        self.bridge = _Bridge()
        self._approval_future: asyncio.Future[bool] | None = None
        self._task: asyncio.Task[None] | None = None
        self._images: list[str] = []
        self.busy = False
        self.service: AssistantService = service_factory(self._approve)
        self._build()
        b = self.bridge
        b.delta.connect(self._on_delta)
        b.tool.connect(self._on_tool)
        b.done.connect(self._on_done)
        b.failed.connect(self._on_failed)
        b.approval.connect(self._on_approval)
        b.info.connect(self.status.setText)
        b.models.connect(self._on_models)
        self._render_history()
        self._refresh_sessions()
        self._provider_changed()

    # ---------- UI ----------
    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        top = QHBoxLayout()
        self.sessions = QComboBox()
        self.sessions.setMinimumWidth(0)
        self.sessions.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.sessions.setMinimumContentsLength(18)
        self.sessions.setToolTip("Suas conversas salvas neste computador")
        self.sessions.setAccessibleName("Sessões da IA")
        self.sessions.currentIndexChanged.connect(self._select_session)
        self.new_btn = icon_button("plus", "Nova conversa")
        self.new_btn.clicked.connect(self._new_conversation)
        self.memory_btn = icon_button("sparkles", "Sobre você · memória da IA")
        self.memory_btn.clicked.connect(self._edit_memory)
        self.config_btn = icon_button("settings", "Conta e modelo")
        self.config_btn.setCheckable(True)
        top.addWidget(self.sessions, 1)
        for w in (self.new_btn, self.memory_btn, self.config_btn):
            top.addWidget(w)
        lay.addLayout(top)

        self.connection_panel = QWidget()
        config = QVBoxLayout(self.connection_panel)
        config.setContentsMargins(0, 0, 0, 0)
        controls = QHBoxLayout()
        self.provider = QComboBox()
        for pid, p in self.service.providers.items():
            self.provider.addItem(p.label, pid)
        self.provider.currentIndexChanged.connect(self._provider_changed)
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setMinimumWidth(150)
        self.model.lineEdit().setPlaceholderText("modelo")
        refresh = icon_button("refresh", "Buscar modelos disponíveis para a conta")
        refresh.clicked.connect(self._load_models)
        self.connect_btn = QPushButton("Conectar")
        self.connect_btn.clicked.connect(self._connect_clicked)
        self.key_btn = icon_button("key", "Configurar chave da API")
        self.key_btn.clicked.connect(self._set_key)
        for w in (self.provider, self.model, refresh, self.connect_btn, self.key_btn):
            controls.addWidget(w, 1 if w in (self.provider, self.model) else 0)
        config.addLayout(controls)

        self.status = QLabel()
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        config.addWidget(self.status)
        lay.addWidget(self.connection_panel)
        self.config_btn.toggled.connect(self.connection_panel.setVisible)
        self.config_btn.setChecked(True)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.setStyleSheet(
            f"QTextBrowser {{ background:{themes.GRAPHITE}; border:1px solid {themes.BORDER};"
            " border-radius:18px; padding:14px; }"
        )
        lay.addWidget(self.view, 1)

        self.tools_label = QLabel()
        self.tools_label.setObjectName("Muted")
        self.tools_label.setWordWrap(True)
        self.tools_label.setVisible(False)
        lay.addWidget(self.tools_label)

        self.approval_box = QWidget()
        ab = QHBoxLayout(self.approval_box)
        ab.setContentsMargins(0, 0, 0, 0)
        self.approval_text = QLabel()
        self.approval_text.setTextFormat(Qt.TextFormat.PlainText)
        self.approval_text.setWordWrap(True)
        self.approval_text.setStyleSheet(f"color:{themes.GREEN};")
        yes = QPushButton("Aprovar")
        yes.setObjectName("Primary")
        no = QPushButton("Negar")
        yes.clicked.connect(lambda: self._resolve_approval(True))
        no.clicked.connect(lambda: self._resolve_approval(False))
        ab.addWidget(self.approval_text, 1)
        ab.addWidget(yes)
        ab.addWidget(no)
        self.approval_box.hide()
        lay.addWidget(self.approval_box)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("O que vamos fazer agora?")
        self.input.setMinimumHeight(40)
        self.input.returnPressed.connect(self._send)
        self.attach_btn = icon_button("paperclip", "Anexar imagem", 40)
        self.attach_btn.clicked.connect(self._attach)
        self.send_btn = icon_button("send", "Enviar mensagem", 40)
        self.send_btn.setObjectName("Primary")
        self.send_btn.clicked.connect(self._send)
        self.stop_btn = icon_button("stop", "Interromper resposta", 40)
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)
        self.stop_btn.hide()
        for w in (self.input, self.attach_btn, self.send_btn, self.stop_btn):
            row.addWidget(w, 1 if w is self.input else 0)
        lay.addLayout(row)

    def _bubble(self, who: str, text: str) -> str:
        color = themes.GREEN if who == "Você" else themes.TEXT_MUTED
        body = html.escape(text).replace("\n", "<br>")
        return f"<p><b style='color:{color}'>{who}</b><br>{body}</p>"

    def _render_history(self) -> None:
        self.view.clear()
        messages = self.service.agent.messages()
        if not messages:
            self.view.setHtml(
                f"<div align='center' style='color:{themes.TEXT_MUTED};'>"
                "<br><br><p style='font-size:22px;'>Nova conversa</p>"
                "<p>Em <b>Sobre você</b>, escolha o que a IA pode lembrar.</p></div>"
            )
        for m in messages:
            self.view.append(self._bubble("Você" if m.role == "user" else "Ventude", m.text))

    def _refresh_sessions(self) -> None:
        self.sessions.blockSignals(True)
        self.sessions.clear()
        for cid, title in self.service.agent.history.conversations():
            self.sessions.addItem(title, cid)
        self.sessions.setCurrentIndex(self.sessions.findData(self.service.agent.conversation_id))
        self.sessions.blockSignals(False)

    def _select_session(self, index: int) -> None:
        if self.busy or index < 0:
            return
        self.service.agent.select_conversation(int(self.sessions.itemData(index)))
        self._images.clear()
        self.attach_btn.setText("")
        self._render_history()

    def _edit_memory(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Sobre você")
        dialog.resize(500, 390)
        dialog.setStyleSheet(f"QDialog {{ background:{themes.BLACK}; }}")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 20)
        title = QLabel("Uma IA que conhece suas preferências")
        title.setObjectName("Title")
        layout.addWidget(title)
        note = QLabel(
            "Escreva como gosta de ser chamado, seus interesses e como prefere as respostas. "
            "Este perfil fica neste PC e é enviado ao provedor ao conversar. "
            "Novas lembranças sugeridas pela IA só são salvas após sua confirmação."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        enabled = QCheckBox("Usar memória entre conversas")
        enabled.setChecked(self.service.memory.enabled)
        layout.addWidget(enabled)
        editor = QTextEdit()
        editor.setPlaceholderText(
            "Meu nome é…\nPrefiro respostas curtas.\nEstou aprendendo…"
        )
        editor.setPlainText(self.service.memory.profile)
        layout.addWidget(editor, 1)
        error = QLabel()
        error.setWordWrap(True)
        error.setStyleSheet(f"color:{themes.DANGER};")
        layout.addWidget(error)
        actions = QHBoxLayout()
        clear = icon_button("trash", "Limpar o perfil (clique em Salvar para confirmar)")
        clear.clicked.connect(editor.clear)
        actions.addWidget(clear)
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(dialog.reject)
        save = QPushButton("Salvar")
        save.setObjectName("Primary")

        def save_memory() -> None:
            try:
                self.service.memory.save(editor.toPlainText(), enabled.isChecked())
            except ValueError as exc:
                error.setText(str(exc))
                return
            dialog.accept()

        save.clicked.connect(save_memory)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)
        self._dialog(dialog.exec)

    @property
    def current(self) -> Any:
        return self.service.providers[self.provider.currentData()]

    def _provider_changed(self) -> None:
        p = self.current
        ok, msg = p.availability()
        self.status.setText(msg)
        uses_account = p.id in ("chatgpt", "codex")
        self.connect_btn.setVisible(uses_account)
        self.connect_btn.setText("Desconectar" if self.service.auth.credentials() else "Conectar")
        self.key_btn.setVisible(p.id == "openai_api")
        self.attach_btn.setEnabled(p.supports_images)
        self.tools_label.setText(
            "Ferramentas do Ventude: ativas (ações sensíveis pedem aprovação)."
            if p.supports_tools
            else "Ferramentas do Ventude: indisponíveis neste provedor."
        )

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.send_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)
        self.stop_btn.setVisible(busy)
        self.send_btn.setVisible(not busy)
        self.provider.setEnabled(not busy)
        self.model.setEnabled(not busy)
        for w in (self.sessions, self.new_btn, self.memory_btn, self.connect_btn, self.key_btn):
            w.setEnabled(not busy)

    # ---------- ações ----------
    def _dialog(self, fn: Any) -> Any:
        self.bus.menu_opened.emit()
        try:
            return fn()
        finally:
            self.bus.menu_closed.emit()

    def _attach(self) -> None:
        path, _ = self._dialog(
            lambda: QFileDialog.getOpenFileName(
                self, "Anexar imagem", "", "Imagens (*.png *.jpg *.jpeg *.webp *.gif)"
            )
        )
        if not path:
            return
        try:
            self._images.append(image_to_data_url(path))
        except (OSError, ValueError) as exc:
            self.status.setText(str(exc))
            return
        self.attach_btn.setText(str(len(self._images)))
        self.attach_btn.setToolTip(f"{len(self._images)} imagem(ns) anexada(s)")

    def _set_key(self) -> None:
        key, ok = self._dialog(
            lambda: QInputDialog.getText(
                self,
                "Chave de API da OpenAI",
                "Cole a chave (fica cifrada com DPAPI; vazio remove):",
                QLineEdit.EchoMode.Password,
            )
        )
        if ok:
            self.service.set_api_key(key)
            self._provider_changed()

    def _connect_clicked(self) -> None:
        if self.service.auth.credentials():
            self.worker.submit(self._sign_out())
        else:
            self.status.setText("Abrindo o navegador para entrar com o ChatGPT...")
            self.worker.submit(self._sign_in())

    async def _sign_in(self) -> None:
        try:
            email = await self.service.auth.sign_in()
            self.bridge.info.emit(f"Conectado: {email or 'conta do ChatGPT'}")
        except Exception as exc:  # noqa: BLE001
            log.warning("Login falhou: %s", exc.__class__.__name__)
            self.bridge.info.emit(f"Login não concluído: {exc}")
        self.bridge.done.emit()

    async def _sign_out(self) -> None:
        confirmed = await self.service.auth.sign_out()
        self.bridge.info.emit(
            "Desconectado."
            if confirmed
            else "Desconectado localmente; a revogação remota não foi confirmada. "
            "Você pode desconectar o app em Configurações do ChatGPT."
        )
        self.bridge.done.emit()

    def _load_models(self) -> None:
        p = self.current

        async def run() -> None:
            try:
                self.bridge.models.emit(await p.list_models())
            except Exception as exc:  # noqa: BLE001
                self.bridge.info.emit(f"Não foi possível listar modelos: {exc}")

        self.worker.submit(run())

    def _on_models(self, models: list) -> None:
        cur = self.model.currentText()
        self.model.clear()
        for slug, name in models:
            self.model.addItem(name, slug)
        if cur:
            self.model.setEditText(cur)
        self.status.setText(f"{len(models)} modelos disponíveis.")

    def _model_slug(self) -> str:
        i = self.model.currentIndex()
        if i >= 0 and self.model.itemText(i) == self.model.currentText():
            return str(self.model.itemData(i) or self.model.currentText())
        return self.model.currentText().strip()

    def _send(self) -> None:
        text = self.input.text().strip()
        if not text or self.busy:
            return
        model = self._model_slug()
        if not model:
            self.config_btn.setChecked(True)
            self.status.setText("Escolha um modelo: atualize a lista ou digite o nome.")
            return
        images, self._images = self._images, []
        self.attach_btn.setText("")
        self.attach_btn.setToolTip("Anexar imagem")
        self.input.clear()
        if not self.service.agent.messages():
            self.view.clear()
        self.view.append(
            self._bubble("Você", text + (f" [{len(images)} imagem(ns)]" if images else ""))
        )
        self.view.append(f"<p><b style='color:{themes.TEXT_MUTED}'>Ventude</b><br></p>")
        self._used: list[str] = []
        self._set_busy(True)
        provider = self.current

        async def run() -> None:
            self._task = asyncio.current_task()
            try:
                async for ev in self.service.agent.send(provider, model, text, images):
                    if isinstance(ev, TextDelta):
                        self.bridge.delta.emit(ev.text)
                    elif isinstance(ev, ToolUsed):
                        self.bridge.tool.emit(ev.name, ev.status, ev.summary)
                    elif isinstance(ev, Failed):
                        self.bridge.failed.emit(ev.message)
                    elif isinstance(ev, Completed):
                        pass
            except asyncio.CancelledError:
                self.bridge.failed.emit("Interrompido.")
            except Exception as exc:  # noqa: BLE001
                log.exception("Falha na conversa")
                self.bridge.failed.emit(f"Não foi possível concluir a resposta: {exc}")
            finally:
                self._task = None
                self.bridge.done.emit()

        self.worker.submit(run())

    def _stop(self) -> None:
        task = self._task
        if task:
            self.worker.call(task.cancel)
        self._resolve_approval(False)

    # ---------- callbacks (thread da UI) ----------
    def _on_delta(self, text: str) -> None:
        c = self.view.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        c.insertText(text)
        self.view.setTextCursor(c)
        self.view.ensureCursorVisible()

    def _on_tool(self, name: str, status: str, _summary: str) -> None:
        self._used.append(f"{name} ({STATUS_PT.get(status, status)})")
        self.tools_label.setText("Ferramentas usadas: " + ", ".join(self._used))
        self.tools_label.show()

    def _on_failed(self, msg: str) -> None:
        self.view.append(f"<p style='color:{themes.DANGER}'>{html.escape(msg)}</p>")

    def _on_done(self) -> None:
        self._set_busy(False)
        self._provider_changed()
        self._refresh_sessions()

    def _new_conversation(self) -> None:
        if self.busy:
            return
        self.service.agent.new_conversation()
        self._images.clear()
        self.attach_btn.setText("")
        self._refresh_sessions()
        self._render_history()
        self.input.setFocus(Qt.FocusReason.OtherFocusReason)

    # ---------- aprovações ----------
    async def _approve(self, tool: str, args: dict, summary: str) -> bool:
        fut: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._approval_future = fut
        self.bridge.approval.emit(summary)
        try:
            return await asyncio.wait_for(fut, 180)
        except TimeoutError:
            return False
        finally:
            self._approval_future = None
            self.bridge.approval.emit("")

    def _on_approval(self, summary: str) -> None:
        if summary:
            self.approval_text.setText(f"Permitir: {summary}?")
            self.approval_box.show()
            self.bus.menu_opened.emit()
        elif self.approval_box.isVisible():
            self.approval_box.hide()
            self.bus.menu_closed.emit()

    def _resolve_approval(self, ok: bool) -> None:
        fut = self._approval_future
        if fut is not None:
            self.worker.call(lambda: fut.done() or fut.set_result(ok))

    def shutdown(self) -> None:
        async def close() -> None:
            if self._task is not None:
                self._task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._task
            await self.service.close()

        fut = self.worker.submit(close())
        try:
            fut.result(timeout=5)
        except Exception:  # noqa: BLE001
            log.debug("close do assistente falhou", exc_info=True)
