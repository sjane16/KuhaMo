import sqlite3
from django.db import transaction
from adm.models import Building, Floor, Room

BACKUP = "db_before_progress_rollback.sqlite3"

if Building.objects.exists() or Floor.objects.exists() or Room.objects.exists():
    print("ABORT: may laman na ang Building/Floor/Room. Walang binago.")
else:
    src = sqlite3.connect(f"file:{BACKUP}?mode=ro", uri=True)
    buildings = src.execute("SELECT id, name, code FROM adm_building ORDER BY id").fetchall()
    floors = src.execute(
        "SELECT id, building_id, floor_number, label FROM adm_floor ORDER BY id"
    ).fetchall()
    rooms = src.execute(
        "SELECT id, floor_id, name, code FROM adm_room ORDER BY id"
    ).fetchall()
    src.close()

    with transaction.atomic():
        for b_id, name, code in buildings:
            Building.objects.create(id=b_id, name=name, code=code, has_floors=True)
        for f_id, b_id, number, label in floors:
            Floor.objects.create(id=f_id, building_id=b_id, floor_number=number, label=label)
        order_by_floor = {}
        for r_id, f_id, name, code in rooms:
            order_by_floor[f_id] = order_by_floor.get(f_id, 0) + 1
            Room.objects.create(
                id=r_id,
                floor_id=f_id,
                name=name,
                code=code,
                order=order_by_floor[f_id],
            )

    print(Building.objects.count(), Floor.objects.count(), Room.objects.count())