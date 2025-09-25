"""Test data factories to reduce boilerplate in tests.

Usage examples:
    from tests.factories import create_user, create_character, create_instance, ensure_item

    def test_something(test_app):
        with test_app.app_context():
            user = create_user('alice')
            char = create_character(user, name='Hero', char_class='fighter')
            inst = create_instance(user, seed=1234)
            sword = ensure_item('short-sword')
"""
from __future__ import annotations
from typing import Optional
from app import db
from app.models.models import User, Character, Item
from app.models.dungeon_instance import DungeonInstance
import json
from werkzeug.security import generate_password_hash

BASE_STATS = {
    'fighter': {'str':12,'dex':10,'int':8,'wis':8,'con':12,'cha':8,'hp':12,'mana':4,'class':'fighter'},
    'mage':    {'str':8,'dex':10,'int':12,'wis':10,'con':8,'cha':8,'hp':8,'mana':12,'class':'mage'},

}
STARTER_ITEMS = {
    'fighter': ['short-sword','wooden-shield'],
    'mage': ['oak-staff','potion-mana'],

}

def create_user(username: str, password: str = 'pass', role: str = 'user') -> User:
    user = User.query.filter_by(username=username).first()
    if user:
        return user
    user = User(username=username, password=generate_password_hash(password), role=role)
    db.session.add(user)
    db.session.commit()
    return user

def create_character(user: User, name: str, char_class: str = 'fighter', items: Optional[list[str]] = None) -> Character:
    stats = BASE_STATS.get(char_class, BASE_STATS['fighter'])
    bag = items if items is not None else STARTER_ITEMS.get(char_class, [])
    c = Character(user_id=user.id, name=name, stats=json.dumps(stats), gear=json.dumps({}), items=json.dumps(bag))
    db.session.add(c)
    db.session.commit()
    return c

def ensure_item(slug: str) -> Item:
    it = Item.query.filter_by(slug=slug).first()
    if it:
        return it
    # Minimal default item creation if missing
    it = Item(slug=slug, name=slug.replace('-', ' ').title(), type='weapon', description='', value_copper=100, level=1, rarity='common', weight=1.0)
    db.session.add(it)
    db.session.commit()
    return it

def create_instance(user: User, seed: int = 9999) -> DungeonInstance:
    inst = DungeonInstance.query.filter_by(user_id=user.id, seed=seed).first()
    if inst:
        return inst
    inst = DungeonInstance(user_id=user.id, seed=seed, pos_x=0, pos_y=0, pos_z=0)
    db.session.add(inst)
    db.session.commit()
    return inst
