from app.seed_items import _augment_item_level_default


def test_insert_without_level_gets_default_zero():
    line = "('potion-x','Potion X','potion','desc',10),"
    out = _augment_item_level_default(line, has_level=False)
    assert ", 0, 'common', 1.0)" in out


def test_insert_with_level_untouched():
    line = "('weapon-x','Sword','weapon','desc',10,5,'rare',2.0),"
    out = _augment_item_level_default(line, has_level=True)
    assert out == line
