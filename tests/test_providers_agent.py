import asyncio
import json
import sqlite3

import httpx

from ventude.assistant.agent import Agent
from ventude.assistant.history import ChatHistory
from ventude.assistant.permissions import Level, PermissionManager
from ventude.assistant.providers.base import Provider
from ventude.assistant.providers.codex import INSTALL_HELP, CodexAppServerProvider, build_command
from ventude.assistant.providers.responses import ApiKeyProvider, to_input
from ventude.assistant.tools.base import Tool, ToolRegistry, obj
from ventude.assistant.types import (
    ChatMessage,
    Completed,
    Failed,
    TextDelta,
    ToolCall,
    ToolCallsRequested,
    ToolUsed,
)


def sse(*events):
    return "".join(f"data: {json.dumps(e)}\n\n" for e in events).encode()


class Store(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def collect(agen):
    async def run():
        return [e async for e in agen]

    return asyncio.run(run())


def api_provider(handler):
    return ApiKeyProvider(
        Store(openai_api_key="sk-test"), httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )


def test_responses_text_stream():
    bodies = []

    def handler(req):
        bodies.append(json.loads(req.content))
        assert req.headers["authorization"] == "Bearer sk-test"
        return httpx.Response(
            200,
            content=sse(
                {"type": "response.output_text.delta", "delta": "Ol"},
                {"type": "response.output_text.delta", "delta": "á"},
                {"type": "response.completed", "response": {}},
            ),
        )

    evs = collect(api_provider(handler).stream("m", "inst", [ChatMessage("user", "oi")], [], []))
    assert [e.text for e in evs if isinstance(e, TextDelta)] == ["Ol", "á"]
    assert isinstance(evs[-1], Completed) and evs[-1].text == "Olá"
    assert bodies[0]["store"] is False and bodies[0]["stream"] is True


def test_responses_function_call_and_failure():
    def handler(req):
        return httpx.Response(
            200,
            content=sse(
                {
                    "type": "response.output_item.done",
                    "item": {
                        "type": "function_call",
                        "call_id": "c1",
                        "name": "t",
                        "arguments": '{"a": 1}',
                    },
                },
                {"type": "response.completed"},
            ),
        )

    evs = collect(api_provider(handler).stream("m", "", [], [{"x": 1}], []))
    assert evs[-1].calls == [ToolCall("c1", "t", {"a": 1})]

    fail = api_provider(
        lambda r: httpx.Response(
            200,
            content=sse(
                {"type": "response.failed", "response": {"error": {"code": "usage_limit"}}}
            ),
        )
    )
    assert "usage_limit" in collect(fail.stream("m", "", [], [], []))[-1].message
    cut = api_provider(
        lambda r: httpx.Response(
            200, content=sse({"type": "response.output_text.delta", "delta": "x"})
        )
    )
    assert isinstance(collect(cut.stream("m", "", [], [], []))[-1], Failed)


def test_missing_key_unavailable():
    p = ApiKeyProvider(Store())
    assert not p.availability()[0]
    assert isinstance(collect(p.stream("m", "", [], [], []))[-1], Failed)


def test_to_input_with_image():
    items = to_input([ChatMessage("user", "veja", ["data:image/png;base64,AA"])])
    assert items[0]["content"][1] == {
        "type": "input_image",
        "image_url": "data:image/png;base64,AA",
    }


def test_list_models_chatgpt_catalog():
    p = api_provider(
        lambda r: httpx.Response(
            200,
            json={
                "models": [
                    {"slug": "a", "display_name": "A", "visibility": "list"},
                    {"slug": "h", "visibility": "hide"},
                ]
            },
        )
    )
    assert asyncio.run(p.list_models()) == [("a", "A")]


class FakeAuth:
    def __init__(self, connected=True):
        self.connected = connected

    def credentials(self):
        return {"access_token": "tok"} if self.connected else None

    async def access_token(self):
        return "tok"


def test_codex_unavailable_without_cli():
    p = CodexAppServerProvider(FakeAuth(), which=lambda _n: None)
    ok, msg = p.availability()
    assert not ok and msg == INSTALL_HELP
    assert not CodexAppServerProvider(FakeAuth(False), which=lambda _n: "codex").availability()[0]


def test_codex_command_matches_docs():
    cmd = build_command("codex")
    assert cmd[:4] == ["codex", "app-server", "--listen", "stdio://"]
    assert 'model_providers.openai_chatgpt_plan.env_key="ACCESS_TOKEN"' in cmd


class FakeProc:
    """Simula o codex app-server respondendo JSON-RPC por stdio."""

    def __init__(self, env):
        self.env = env
        self.returncode = None
        self.stdout = asyncio.StreamReader()
        self.sent = []
        outer = self

        class Stdin:
            def write(self, data):
                msg = json.loads(data)
                outer.sent.append(msg)
                outer._reply(msg)

            async def drain(self):
                pass

        self.stdin = Stdin()

    def _out(self, obj):
        self.stdout.feed_data((json.dumps(obj) + "\n").encode())

    def _reply(self, msg):
        m, rid = msg.get("method"), msg.get("id")
        if m == "initialize":
            self._out({"id": rid, "result": {}})
        elif m == "thread/start":
            self._out({"id": rid, "result": {"thread": {"id": "th1"}}})
        elif m == "turn/start":
            self._out({"id": rid, "result": {"turn": {"id": "tu1"}}})
            self._out({"method": "item/agentMessage/delta", "params": {"delta": "oi"}})
            self._out({"id": 99, "method": "item/commandExecution/requestApproval", "params": {}})
            self._out({"method": "turn/completed", "params": {"turn": {"status": "completed"}}})

    def terminate(self):
        self.returncode = 0
        self.stdout.feed_eof()

    async def wait(self):
        return 0


def test_codex_jsonrpc_flow():
    procs = []

    async def spawn(*cmd, **kw):
        p = FakeProc(kw["env"])
        procs.append(p)
        return p

    async def run():
        prov = CodexAppServerProvider(FakeAuth(), which=lambda _n: "codex", spawn=spawn)
        evs = [e async for e in prov.stream("gpt-x", "", [ChatMessage("user", "olá")], [], [])]
        await prov.close()
        return prov, evs

    prov, evs = asyncio.run(run())
    proc = procs[0]
    assert proc.env["ACCESS_TOKEN"] == "tok"
    methods = [m.get("method") for m in proc.sent]
    assert methods[:4] == ["initialize", "initialized", "thread/start", "turn/start"]
    assert proc.sent[0]["params"]["clientInfo"]["name"] == "ventude"
    assert proc.sent[3]["params"]["input"] == [{"type": "text", "text": "olá"}]
    assert {"jsonrpc": "2.0", "id": 99, "result": {"decision": "decline"}} in proc.sent
    assert [e.text for e in evs if isinstance(e, TextDelta)] == ["oi"]
    assert isinstance(evs[-1], Completed) and prov.thread_id == "th1"


class ScriptedProvider(Provider):
    id = "fake"
    supports_tools = True

    def __init__(self):
        self.calls = 0
        self.extra_seen = []

    def availability(self):
        return True, ""

    async def list_models(self):
        return []

    async def stream(self, model, instructions, history, tools, extra_input):
        self.calls += 1
        self.extra_seen.append(list(extra_input))
        if self.calls == 1:
            yield ToolCallsRequested([ToolCall("c1", "danger", {"x": 1})])
        else:
            yield TextDelta("feito")
            yield Completed()


def make_agent(answer):
    conn = sqlite3.connect(":memory:")
    ran = []

    async def approver(tool, args, summary):
        return answer

    reg = ToolRegistry()
    reg.register(
        Tool(
            "danger",
            "d",
            obj({"x": {"type": "integer"}}, ["x"]),
            lambda a: ran.append(a) or "ok",
            Level.AUTO,
            destructive=True,
        )
    )
    agent = Agent(ChatHistory(conn), reg, PermissionManager(conn, approver))
    return agent, ran


def test_agent_tool_loop_with_approval():
    agent, ran = make_agent(True)
    prov = ScriptedProvider()
    evs = collect(agent.send(prov, "m", "faça"))
    used = [e for e in evs if isinstance(e, ToolUsed)]
    assert used[0].status == "executed" and ran == [{"x": 1}]
    assert prov.extra_seen[1][1]["type"] == "function_call_output"
    assert [m.role for m in agent.messages()] == ["user", "assistant"]
    stages = [s for _t, s, _d in reversed(agent.permissions.history())]
    assert stages == ["requested", "approved", "executed"]


def test_agent_denied_tool_not_executed():
    agent, ran = make_agent(False)
    evs = collect(agent.send(ScriptedProvider(), "m", "faça"))
    assert [e.status for e in evs if isinstance(e, ToolUsed)] == ["denied"] and ran == []


def test_agent_invalid_args_rejected():
    agent, ran = make_agent(True)
    status, _ = asyncio.run(agent.run_tool("danger", {"x": "não"}))
    assert status == "error" and ran == []
