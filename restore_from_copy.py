import sqlite3
from django.db import transaction
from adm.models import Building, Floor, Room

SOURCE = "db_copy_check.sqlite3"

src = sqlite3.connect(f"file:{SOURCE}?mode=ro", uri=True)
buildings = src.execute("SELECT id, name, code, has_floors FROM adm_building ORDER BY id").fetchall()
floors = src.execute(
    "SELECT id, building_id, floor_number, label FROM adm_floor ORDER BY id"
).fetchall()
rooms = src.execute(
    'SELECT id, floor_id, name, code, "order" FROM adm_room ORDER BY id'
).fetchall()
src.close()

if (len(buildings), len(floors), len(rooms)) != (7, 16, 146):
    print("ABORT: hindi 7/16/146 ang laman ng source:", len(buildings), len(floors), len(rooms))
else:
    with transaction.atomic():
        Room.objects.all().delete()
        Floor.objects.all().delete()
        Building.objects.all().delete()
        for b_id, name, code, has_floors in buildings:
            Building.objects.create(id=b_id, name=name, code=code, has_floors=bool(has_floors))
        for f_id, b_id, number, label in floors:
            Floor.objects.create(id=f_id, building_id=b_id, floor_number=number, label=label)
        for r_id, f_id, name, code, order in rooms:
            Room.objects.create(id=r_id, floor_id=f_id, name=name, code=code, order=order)
    print(Building.objects.count(), Floor.objects.count(), Room.objects.count())