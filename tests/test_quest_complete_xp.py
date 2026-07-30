"""Claiming a template quest with an XP reward.

`POST /api/quests/complete` granted XP by hand: it added straight to
`character.xp` and then ran its own level-up loop against
`combat_service._xp_required` -- **a function that does not exist**, so the
import raised ImportError and the request answered 500. Nothing caught it
because the tested quest endpoints are the daily/weekly pool ones
(`/api/quests/daily/claim`), which are a different handler, and no
`QuestTemplate` rows are seeded anywhere, so the path never ran in a real game.

Had the import succeeded it would have been worse than a 500: the loop
`while character.xp >= required(character.level)` does not terminate once the
requirement stops rising at the level cap.

It now goes through `progression.grant_xp`, the one place that turns XP into
levels -- which respects the cap and grants stat and talent points with it.
"""

import json

import pytest

from app import db
from app.models.models import Character
from app.models.quest import QuestProgress, QuestTemplate
from app.models.xp import MAX_LEVEL, xp_for_level


@pytest.fixture()
def quest_at_target(client, logged_in_user):
    """An accepted template quest whose objective is already satisfied."""
    template = QuestTemplate(
        slug="_test_xp_quest",
        title="A Test Errand",
        description="Kill something.",
        objectives_json=json.dumps([{"id": "kill", "type": "kill", "count": 1}]),
        rewards_json=json.dumps({"xp": 500}),
    )
    db.session.add(template)
    db.session.commit()

    character = Character.query.filter_by(user_id=logged_in_user.id).first()
    if character is None:
        character = Character(
            user_id=logged_in_user.id, name="Questor", stats='{"str":10}', gear="{}", items="[]", level=1, xp=0
        )
        db.session.add(character)
        db.session.commit()

    progress = QuestProgress(
        character_id=character.id,
        quest_template_id=template.id,
        status="active",
        progress_json=json.dumps({"kill": 1}),
    )
    db.session.add(progress)
    db.session.commit()
    return character, template


def test_claiming_a_quest_grants_its_xp(client, test_app, quest_at_target):
    character, template = quest_at_target
    before = int(character.xp or 0)

    resp = client.post("/api/quests/complete", json={"character_id": character.id, "quest_id": template.id})

    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(character)
    assert character.xp == before + 500


def test_quest_xp_cannot_push_a_character_past_the_cap(client, test_app, quest_at_target):
    """The level cap belongs to progression.grant_xp. A second XP path that
    levelled on its own would walk straight through it."""
    character, template = quest_at_target
    character.xp = xp_for_level(MAX_LEVEL)
    character.level = MAX_LEVEL
    db.session.commit()

    resp = client.post("/api/quests/complete", json={"character_id": character.id, "quest_id": template.id})

    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(character)
    assert character.level == MAX_LEVEL, "quest XP levelled a character past the cap"
