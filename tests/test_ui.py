"""Run the real Streamlit app headless (streamlit.testing.AppTest) and click through it like a user."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parent.parent / "app.py")


@pytest.fixture
def at(monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)  # use the committed data/ folder
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    assert not app.exception, app.exception
    return app


def test_every_tab_renders_without_errors(at):
    assert at.tabs[0].label == "🔍 Search"
    assert len(at.tabs) == 5
    assert not at.error


def test_search_shows_details_and_burn_off(at):
    at.text_input[0].set_value("oat").run()
    assert not at.exception
    assert any("Found" in s.value for s in at.success)
    assert any("To burn" in m.value for m in at.markdown)


def test_add_to_plate_updates_totals(at):
    add = next(b for b in at.button if "Add to my plate" in b.label)
    add.click().run()
    assert not at.exception
    assert at.tabs[1].label == "🍽️ My plate (1)"
    assert any(m.label == "Calories" for m in at.tabs[1].metric)


def test_weight_changes_the_calorie_target(at):
    before = next(m.value for m in at.sidebar.metric)
    at.sidebar.number_input[2].set_value(90).run()  # weight
    after = next(m.value for m in at.sidebar.metric)
    assert before != after
