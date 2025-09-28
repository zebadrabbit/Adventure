from app import app, db
from app.models.models import Item
from app.server import _configure_logging, seed_items


def test_configure_logging_and_seed_items(tmp_path, monkeypatch):
    # Redirect instance path to a temp directory to exercise logging setup
    monkeypatch.setattr(app, "instance_path", str(tmp_path))
    with app.app_context():
        db.create_all()
        # Run logging config twice to ensure idempotence (handler replace path)
        _configure_logging()
        _configure_logging()
        # Seed items and verify at least one known slug
        seed_items()
        assert Item.query.filter_by(slug="short-sword").first() is not None
        # Re-run to ensure no duplicates
        count_before = Item.query.count()
        seed_items()
        assert Item.query.count() == count_before
    # Confirm log file created
    log_file = tmp_path / "app.log"
    assert log_file.exists()
