import pytest

from app import app
from app.models.theme import Theme
from app.seed_themes import seed_themes


@pytest.mark.db_isolation
def test_seed_themes_creates_cold_steel_and_classic_dungeon():
    with app.app_context():
        count = seed_themes(verbose=False)
        assert count == 2

        cold_steel = Theme.query.filter_by(name="Cold Steel").first()
        assert cold_steel is not None
        assert cold_steel.is_active is True
        assert cold_steel.primary == "#5ad1c9"
        assert cold_steel.body_bg == "#0c0e12"

        classic = Theme.query.filter_by(name="Classic Dungeon").first()
        assert classic is not None
        assert classic.is_active is False
        assert classic.primary == "#d4a574"


@pytest.mark.db_isolation
def test_seed_themes_is_idempotent():
    with app.app_context():
        seed_themes(verbose=False)
        first_count = Theme.query.count()
        seed_themes(verbose=False)
        second_count = Theme.query.count()
        assert first_count == second_count
