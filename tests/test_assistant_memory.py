import asyncio
import sqlite3

import pytest

from ventude.assistant.agent import Agent
from ventude.assistant.history import ChatHistory
from ventude.assistant.memory import MAX_PROFILE, PersonalMemory, memory_tools
from ventude.assistant.permissions import PermissionManager
from ventude.assistant.providers.base import Provider
from ventude.assistant.tools.base import ToolError, ToolRegistry
from ventude.assistant.types import ChatMessage, Completed


class RecordingProvider(Provider):
    supports_tools = True

    def __init__(self):
        self.inputs = []

    def availability(self):
        return True, ""

    async def list_models(self):
        return []

    async def stream(self, model, instructions, history, tools, extra_input):
        self.inputs.append((instructions, list(history), tools))
        yield Completed("Olá")


def test_personal_memory_persists_and_can_be_disabled_or_cleared(tmp_path):
    path = tmp_path / "memory.db"
    memory = PersonalMemory(path)
    memory.remember("Prefiro respostas curtas.")
    memory.remember("Prefiro respostas curtas.")
    memory.close()
    memory = PersonalMemory(path)
    assert memory.profile == "Prefiro respostas curtas."
    memory.save(memory.profile, False)
    assert "Prefiro respostas curtas." not in memory.context()
    with pytest.raises(ToolError, match="desativada"):
        memory.remember("Gosto de música.")
    memory.save("", True)
    assert not memory.profile
    with pytest.raises(ValueError):
        memory.save("x" * (MAX_PROFILE + 1), True)
    memory.close()


def test_memory_requires_approval_and_is_used_in_new_sessions(tmp_path):
    memory = PersonalMemory(tmp_path / "memory.db")
    conn = sqlite3.connect(":memory:")
    approvals = []

    async def approve(name, args, summary):
        approvals.append((name, args))
        return len(approvals) > 1

    tools = ToolRegistry()
    tools.register(*memory_tools(memory))
    agent = Agent(ChatHistory(conn), tools, PermissionManager(conn, approve), memory)

    async def run():
        args = {"fact": "Prefiro respostas curtas."}
        assert (await agent.run_tool("remember_user_preference", args))[0] == "denied"
        assert not memory.profile
        assert (await agent.run_tool("remember_user_preference", args))[0] == "executed"
        provider = RecordingProvider()
        [event async for event in agent.send(provider, "model", "Primeira pergunta")]
        first_session = agent.conversation_id
        agent.new_conversation()
        [event async for event in agent.send(provider, "model", "Outra pergunta")]
        assert "Prefiro respostas curtas." in provider.inputs[-1][0]
        assert len(provider.inputs[-1][1]) == 1
        agent.select_conversation(first_session)
        assert agent.messages()[0].text == "Primeira pergunta"
        assert len(agent.history.conversations()) == 2
        memory.save(memory.profile, False)
        [event async for event in agent.send(provider, "model", "Sem memória")]
        assert "Prefiro respostas curtas." not in provider.inputs[-1][0]
        assert provider.inputs[-1][2] == []

    asyncio.run(run())
    memory.close()


def test_sessions_have_titles_and_reject_missing_ids():
    history = ChatHistory(sqlite3.connect(":memory:"))
    cid = history.new_conversation()
    history.add(cid, ChatMessage("user", "Planejar minha semana"))
    history.add(cid, ChatMessage("user", "Outra coisa"))
    assert history.conversations() == [(cid, "Planejar minha semana")]
    agent = Agent(history, ToolRegistry(), PermissionManager(history.conn))
    with pytest.raises(ValueError, match="não encontrada"):
        agent.select_conversation(999)


def test_codex_sessions_reset_remote_context_and_replay_local_history():
    from tests.test_providers_agent import FakeAuth, FakeProc
    from ventude.assistant.providers.codex import CodexAppServerProvider

    processes = []

    async def spawn(*args, **kwargs):
        proc = FakeProc(kwargs["env"])
        processes.append(proc)
        return proc

    async def run():
        provider = CodexAppServerProvider(FakeAuth(), which=lambda _: "codex", spawn=spawn)
        await provider.select_context(1, "Perfil: respostas curtas")
        history = [ChatMessage("user", "Primeira"), ChatMessage("user", "Continuação")]
        [event async for event in provider.stream("m", "Perfil: respostas curtas", history, [], [])]
        sent = processes[-1].sent[3]["params"]["input"][0]["text"]
        assert "respostas curtas" in sent and "Primeira" in sent
        await provider.select_context(2, "Perfil: respostas curtas")
        assert provider.thread_id is None and processes[0].returncode == 0
        history = [ChatMessage("user", "Nova sessão")]
        [event async for event in provider.stream("m", "Perfil: respostas curtas", history, [], [])]
        assert len(processes) == 2
        sent = processes[-1].sent[3]["params"]["input"][0]["text"]
        assert "Nova sessão" in sent and "Primeira" not in sent
        await provider.close()

    asyncio.run(run())


def test_assistant_page_sessions_and_busy_controls(qapp, tmp_path):
    from ventude.assistant.service import AssistantService
    from ventude.core.async_worker import AsyncWorker
    from ventude.core.config import Settings
    from ventude.core.events import EventBus
    from ventude.storage.database import Database
    from ventude.ui import themes
    from ventude.ui.pages.assistant_page import AssistantPage

    worker = AsyncWorker()
    db = Database(tmp_path / "app.db")
    bus = EventBus()
    page = AssistantPage(
        lambda approve: AssistantService(
            tmp_path, db, Settings, lambda _: None, lambda: None, approve
        ),
        worker,
        bus,
    )
    try:
        page.setStyleSheet(themes.STYLESHEET)
        page.resize(644, 460)
        page.show()
        first = page.service.agent.conversation_id
        page.service.agent.history.add(first, ChatMessage("user", "Minha primeira sessão"))
        page._new_conversation()
        assert page.sessions.count() == 2
        page.sessions.setCurrentIndex(page.sessions.findData(first))
        assert page.service.agent.conversation_id == first
        assert "Minha primeira sessão" in page.view.toPlainText()
        page._set_busy(True)
        assert not page.sessions.isEnabled() and not page.memory_btn.isEnabled()
        page._set_busy(False)
        assert page.sessions.isEnabled() and page.memory_btn.isEnabled()
        assert page.minimumSizeHint().width() <= 644
    finally:
        page.close()
        page.shutdown()
        worker.stop()
        db.close()
