from django.core.management.base import BaseCommand
from adm.models import Building, Floor, Room


class Command(BaseCommand):
    help = 'Seed buildings, floors and rooms'

    def handle(self, *args, **kwargs):
        # ── Buildings ──────────────────────────────────────
        mb  = Building.objects.create(name='Main Building', code='MB')
        nb  = Building.objects.create(name='New Building', code='NB')
        llb = Building.objects.create(name='Library and Laboratory Building', code='LLB')

        # ── Main Building Floors ────────────────────────────
        mb_f1 = Floor.objects.create(building=mb, floor_number=1, label='Main Building - Floor 1', map_image='floor_maps/mb_f1.png', image_width=1100, image_height=450)
        mb_f2 = Floor.objects.create(building=mb, floor_number=2, label='Main Building - Floor 2', map_image='floor_maps/mb_f2.png', image_width=1100, image_height=450)
        mb_f3 = Floor.objects.create(building=mb, floor_number=3, label='Main Building - Floor 3', map_image='floor_maps/mb_f3.png', image_width=1100, image_height=450)
        mb_f4 = Floor.objects.create(building=mb, floor_number=4, label='Main Building - Floor 4', map_image='floor_maps/mb_f4.png', image_width=1100, image_height=450)

        # ── New Building Floors ─────────────────────────────
        nb_f1 = Floor.objects.create(building=nb, floor_number=1, label='New Building - Floor 1', map_image='floor_maps/nb_f1.png', image_width=1100, image_height=450)
        nb_f2 = Floor.objects.create(building=nb, floor_number=2, label='New Building - Floor 2', map_image='floor_maps/nb_f2.png', image_width=1100, image_height=450)
        nb_f3 = Floor.objects.create(building=nb, floor_number=3, label='New Building - Floor 3', map_image='floor_maps/nb_f3.png', image_width=1100, image_height=450)
        nb_f4 = Floor.objects.create(building=nb, floor_number=4, label='New Building - Floor 4', map_image='floor_maps/nb_f4.png', image_width=1100, image_height=450)

        # ── LLB Floors ──────────────────────────────────────
        llb_f1 = Floor.objects.create(building=llb, floor_number=1, label='LLB - Floor 1', map_image='floor_maps/llb_f1.png', image_width=1100, image_height=450)
        llb_f2 = Floor.objects.create(building=llb, floor_number=2, label='LLB - Floor 2', map_image='floor_maps/llb_f2.png', image_width=1100, image_height=450)

        # ── Main Building Rooms ─────────────────────────────
        # Floor 1
        Room.objects.create(floor=mb_f1, name='MB | Lobby', code='MB_LOBBY', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='MB | Clinic', code='MB_CLINIC', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='MB | Guidance Office', code='MB_GUIDANCE', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='MB | Finance Office', code='MB_FINANCE', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='MB | Registrar', code='MB_REGISTRAR', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='MB | Cashier', code='MB_CASHIER', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='MB | Chapel', code='MB_CHAPEL', x=0, y=0)
        # Floor 2
        Room.objects.create(floor=mb_f2, name='M201', code='MB201', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M202', code='MB202', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M203', code='MB203', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M204', code='MB204', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M205', code='MB205', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='MB | Faculty Room', code='MB_FACULTY', x=0, y=0)
        Room.objects.create(floor=mb_f2, name="MB | Dean's Office", code='MB_DEAN', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='MB | Conference Room', code='MB_CONF', x=0, y=0)
        # Floor 3
        Room.objects.create(floor=mb_f3, name='Amba M301', code='AMB301', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='Amba M302', code='AMB302', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='Amba M303', code='AMB303', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='Amba M304', code='AMB304', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='Amba M305', code='AMB305', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='Amba M306', code='AMB306', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='Amba M307', code='AMB307', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='MB | AVR', code='MB_AVR', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='MB | Storage Room', code='MB_STORAGE', x=0, y=0)
        # Floor 4
        Room.objects.create(floor=mb_f4, name='M401', code='MB401', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M402', code='MB402', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M403', code='MB403', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M404', code='MB404', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M405', code='MB405', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='MB | Server Room', code='MB_SERVER', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='MB | CICT Office', code='MB_CICT', x=0, y=0)

        # ── New Building Rooms ──────────────────────────────
        # Floor 1
        Room.objects.create(floor=nb_f1, name='NB | Lobby', code='NB_LOBBY', x=0, y=0)
        Room.objects.create(floor=nb_f1, name='NB | Security Office', code='NB_SECURITY', x=0, y=0)
        Room.objects.create(floor=nb_f1, name='NB | Canteen', code='NB_CANTEEN', x=0, y=0)
        Room.objects.create(floor=nb_f1, name='NB | Bookstore', code='NB_BOOKSTORE', x=0, y=0)
        # Floor 2
        Room.objects.create(floor=nb_f2, name='NB201', code='NB201', x=0, y=0)
        Room.objects.create(floor=nb_f2, name='NB202', code='NB202', x=0, y=0)
        Room.objects.create(floor=nb_f2, name='NB203', code='NB203', x=0, y=0)
        Room.objects.create(floor=nb_f2, name='NB204', code='NB204', x=0, y=0)
        Room.objects.create(floor=nb_f2, name='NB205', code='NB205', x=0, y=0)
        Room.objects.create(floor=nb_f2, name='NB | Male Toilet Floor 2', code='NB_MT2', x=0, y=0)
        Room.objects.create(floor=nb_f2, name='NB | Female Toilet Floor 2', code='NB_FT2', x=0, y=0)
        Room.objects.create(floor=nb_f2, name='NB | Hallway Floor 2', code='NB_HW2', x=0, y=0)
        # Floor 3
        Room.objects.create(floor=nb_f3, name='NB301', code='NB301', x=0, y=0)
        Room.objects.create(floor=nb_f3, name='NB302', code='NB302', x=0, y=0)
        Room.objects.create(floor=nb_f3, name='NB303', code='NB303', x=0, y=0)
        Room.objects.create(floor=nb_f3, name='NB304', code='NB304', x=0, y=0)
        Room.objects.create(floor=nb_f3, name='NB305', code='NB305', x=0, y=0)
        Room.objects.create(floor=nb_f3, name='NB | Male Toilet Floor 3', code='NB_MT3', x=0, y=0)
        Room.objects.create(floor=nb_f3, name='NB | Female Toilet Floor 3', code='NB_FT3', x=0, y=0)
        Room.objects.create(floor=nb_f3, name='NB | Hallway Floor 3', code='NB_HW3', x=0, y=0)
        # Floor 4
        Room.objects.create(floor=nb_f4, name='NB401', code='NB401', x=0, y=0)
        Room.objects.create(floor=nb_f4, name='NB402', code='NB402', x=0, y=0)
        Room.objects.create(floor=nb_f4, name='NB403', code='NB403', x=0, y=0)
        Room.objects.create(floor=nb_f4, name='NB404', code='NB404', x=0, y=0)
        Room.objects.create(floor=nb_f4, name='NB405', code='NB405', x=0, y=0)
        Room.objects.create(floor=nb_f4, name='NB | Male Toilet Floor 4', code='NB_MT4', x=0, y=0)
        Room.objects.create(floor=nb_f4, name='NB | Female Toilet Floor 4', code='NB_FT4', x=0, y=0)
        Room.objects.create(floor=nb_f4, name='NB | Hallway Floor 4', code='NB_HW4', x=0, y=0)

        # ── LLB Rooms ───────────────────────────────────────
        # Floor 1
        Room.objects.create(floor=llb_f1, name='LLB | Library', code='LLB_LIB', x=0, y=0)
        Room.objects.create(floor=llb_f1, name='LLB | Reading Area', code='LLB_READ', x=0, y=0)
        Room.objects.create(floor=llb_f1, name='LLB | Librarian Office', code='LLB_LIBR', x=0, y=0)
        # Floor 2
        Room.objects.create(floor=llb_f2, name='LLB | Electronics Lab', code='LLB_LAB1', x=0, y=0)
        Room.objects.create(floor=llb_f2, name='LLB | Lab 2', code='LLB_LAB2', x=0, y=0)
        Room.objects.create(floor=llb_f2, name='LLB | Lab 3', code='LLB_LAB3', x=0, y=0)

        self.stdout.write(self.style.SUCCESS('Seed data created successfully!'))