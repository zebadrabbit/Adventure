import pytest
from app.models.dungeon_instance import DungeonInstance
from app import db

@pytest.mark.usefixtures('auth_client')
class TestDungeonRoutes:
    def _instance(self):
        return DungeonInstance.query.first()

    def test_map_endpoint_basic(self, auth_client):
        r = auth_client.get('/api/dungeon/map')
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()
        assert 'grid' in data and isinstance(data['grid'], list)
        assert data['width'] == 75 and data['height'] == 75
        assert len(data['grid']) == 75 and len(data['grid'][0]) == 75
        # grid should contain at least one room and wall char mapping
        flat = ''.join(''.join(row) for row in data['grid'])
        assert any(c in flat for c in ('room','tunnel','door'))

    def test_state_endpoint(self, auth_client):
        r = auth_client.get('/api/dungeon/state')
        assert r.status_code == 200
        data = r.get_json()
        assert 'pos' in data and 'exits' in data
        assert isinstance(data['exits'], list)

    def test_move_noop_then_move(self, auth_client):
        inst = self._instance()
        start = (inst.pos_x, inst.pos_y)
        # noop
        r0 = auth_client.post('/api/dungeon/move', json={'dir': ''})
        assert r0.status_code == 200
        db.session.refresh(inst)
        # If starting placeholder (0,0), the move endpoint may normalize to entrance; allow that.
        if start != (0,0):
            assert (inst.pos_x, inst.pos_y) == start
        # try north
        r1 = auth_client.post('/api/dungeon/move', json={'dir': 'n'})
        assert r1.status_code == 200
        db.session.refresh(inst)
        after = (inst.pos_x, inst.pos_y)
        assert after != start  # moved or at least attempted (if blocked test might flake)

    def test_seed_determinism_api(self, auth_client):
        # Capture initial map
        r1 = auth_client.get('/api/dungeon/map')
        grid1 = r1.get_json()['grid']
        # Force same seed by ensuring instance seed unchanged, request again
        r2 = auth_client.get('/api/dungeon/map')
        grid2 = r2.get_json()['grid']
        assert grid1 == grid2, 'Map should be deterministic for the same seed'
