import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

from ventude.services.media import MediaService, MediaState, build_state, format_time


def _controls(**kw):
    base = dict(
        is_play_pause_toggle_enabled=True,
        is_next_enabled=True,
        is_previous_enabled=False,
        is_playback_position_enabled=True,
    )
    base.update(kw)
    return NS(**base)


class FakeSession:
    def __init__(self, title="Song", status=4):
        self.props = NS(title=title, artist="Artist", album_title="Album", thumbnail="THUMB")
        self.playback = NS(playback_status=status, controls=_controls())
        self.timeline = NS(
            start_time=timedelta(0),
            end_time=timedelta(seconds=200),
            position=timedelta(seconds=50),
            last_updated_time=datetime.now(UTC),
        )
        self.handlers: dict[str, object] = {}
        self.removed: list[str] = []
        self.calls: list[object] = []
        self.source_app_user_model_id = "Spotify.exe"

    def __getattr__(self, name):
        if name.startswith("add_"):
            return lambda h, n=name[4:]: self.handlers.setdefault(n, h) and n
        if name.startswith("remove_"):
            return lambda tok: self.removed.append(tok)
        raise AttributeError(name)

    async def try_get_media_properties_async(self):
        return self.props

    def get_playback_info(self):
        return self.playback

    def get_timeline_properties(self):
        return self.timeline

    async def try_change_playback_position_async(self, ticks):
        self.calls.append(("seek", ticks))


class FakeManager:
    def __init__(self, session):
        self.session = session
        self.handler = None

    def add_current_session_changed(self, h):
        self.handler = h
        return "tok"

    def remove_current_session_changed(self, tok):
        pass

    def get_current_session(self):
        return self.session


def make_service(manager, thumbs=None):
    async def factory():
        return manager

    async def reader(ref):
        if thumbs is not None:
            thumbs.append(ref)
        return b"PNG"

    svc = MediaService(factory, reader)
    states, images = [], []
    svc.state_changed.connect(states.append)
    svc.thumbnail_changed.connect(images.append)
    return svc, states, images


def test_format_time():
    assert format_time(0) == "0:00"
    assert format_time(65) == "1:05"
    assert format_time(3725) == "1:02:05"


def test_build_state_none_without_title():
    assert build_state(NS(title=""), NS(playback_status=4), NS()) is None


def test_build_state_values():
    s = FakeSession()
    st = build_state(s.props, s.playback, s.timeline)
    assert st and st.title == "Song" and st.is_playing
    assert st.duration_s == 200 and 50 <= st.position_s < 52
    assert st.can_seek and not st.can_previous


def test_interpolation_only_while_playing():
    st = MediaState("t", "a", "", "playing", 10, 100, 0.0, True, True, True, True)
    assert st.position_at(5.0) == 15
    assert st.position_at(500.0) == 100  # limitado à duração
    paused = MediaState("t", "a", "", "paused", 10, 100, 0.0, True, True, True, True)
    assert paused.position_at(5.0) == 10


def test_service_connect_emits_state_and_thumbnail(qapp):
    session = FakeSession()
    thumbs: list = []
    svc, states, images = make_service(FakeManager(session), thumbs)
    asyncio.run(svc.connect())
    assert states[-1].title == "Song"
    assert images == [b"PNG"] and thumbs == ["THUMB"]
    assert set(session.handlers) == {
        "media_properties_changed",
        "playback_info_changed",
        "timeline_properties_changed",
    }
    # mesma faixa: não relê a capa
    asyncio.run(svc.refresh("playback"))
    assert images == [b"PNG"]


def test_service_no_session_emits_empty(qapp):
    svc, states, images = make_service(FakeManager(None))
    asyncio.run(svc.connect())
    assert states == [None] and images == []


def test_session_change_detaches_old_handlers(qapp):
    old = FakeSession()
    mgr = FakeManager(old)
    svc, states, _ = make_service(mgr)
    asyncio.run(svc.connect())
    mgr.session = None
    asyncio.run(svc.refresh("session"))
    assert len(old.removed) == 3
    assert states[-1] is None


def test_manager_failure_reports_unavailable(qapp):
    async def boom():
        raise OSError("sem WinRT")

    svc = MediaService(boom)
    msgs, states = [], []
    svc.unavailable.connect(msgs.append)
    svc.state_changed.connect(states.append)
    asyncio.run(svc.connect())
    assert msgs and states == [None]


def test_seek_uses_ticks_and_respects_permission(qapp):
    session = FakeSession()
    svc, _, _ = make_service(FakeManager(session))
    svc.start()
    try:
        import time

        for _ in range(100):
            if svc.state:
                break
            time.sleep(0.02)
        svc.seek(30)
        for _ in range(100):
            if session.calls:
                break
            time.sleep(0.02)
        assert session.calls == [("seek", 300_000_000)]
    finally:
        svc.stop()


def test_media_card_empty_and_filled(qapp):
    from ventude.ui.media_card import MediaCard

    svc = MediaService()
    card = MediaCard(svc)
    assert card.empty.isVisibleTo(card) and not card.media_box.isVisibleTo(card)
    st = MediaState("Song", "Artist", "", "playing", 10, 100, 0.0, True, False, True, True)
    svc.state = st
    card.set_state(st)
    assert card.title.text() == "Song" and card.tick.isActive()
    assert not card.next_btn.isEnabled()
    card.set_state(None)
    assert not card.tick.isActive() and card.empty.isVisibleTo(card)
