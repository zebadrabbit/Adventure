from app.dungeon import Dungeon

def _door_chain_violations(d):
    grid = d.grid
    x = len(grid); y = len(grid[0])
    violations = []
    # Check horizontal chains
    for iy in range(y):
        run = []
        for ix in range(x):
            if grid[ix][iy][0].cell_type == 'door':
                run.append((ix,iy))
            else:
                if len(run) > 1:
                    # A chain is only a violation if all doors in chain have room on same side (wall-hug)
                    if _is_linear_wall_hug(run, grid):
                        violations.append(list(run))
                run = []
        if len(run) > 1 and _is_linear_wall_hug(run, grid):
            violations.append(list(run))
    # Check vertical chains
    for ix in range(x):
        run = []
        for iy in range(y):
            if grid[ix][iy][0].cell_type == 'door':
                run.append((ix,iy))
            else:
                if len(run) > 1 and _is_linear_wall_hug(run, grid):
                    violations.append(list(run))
                run = []
        if len(run) > 1 and _is_linear_wall_hug(run, grid):
            violations.append(list(run))
    return violations

def _is_linear_wall_hug(run, grid):
    # Determine if all doors in run have the same room-adjacent direction and also at least two corridor sides inline.
    if len(run) < 2:
        return False
    dirs = []
    xlen = len(grid); ylen = len(grid[0])
    for (x,y) in run:
        room_sides = []
        for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx,ny = x+dx,y+dy
            if 0 <= nx < xlen and 0 <= ny < ylen and grid[nx][ny][0].cell_type == 'room':
                room_sides.append((dx,dy))
        if len(room_sides) != 1:
            return False
        dirs.append(room_sides[0])
    # All same direction?
    first = dirs[0]
    if not all(d == first for d in dirs):
        return False
    return True

def test_no_linear_door_chains():
    seeds = [11, 222, 3333, 4444]
    for s in seeds:
        d = Dungeon(seed=s, size=(60,60,1))
        violations = _door_chain_violations(d)
        assert not violations, f"Seed {s} produced door chain(s): {violations[:2]}"
