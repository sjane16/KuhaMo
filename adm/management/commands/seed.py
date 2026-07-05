import shutil
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from adm.models import Building, Floor, Room




class Command(BaseCommand):
    help = 'Seed buildings, floors and rooms'


    def copy_floor_images(self):
        src = os.path.join(settings.BASE_DIR, 'adm', 'static', 'adm', 'floor_maps')
        dst = os.path.join(settings.MEDIA_ROOT, 'floor_maps')
        os.makedirs(dst, exist_ok=True)
        if os.path.exists(src):
            for f in os.listdir(src):
                shutil.copy2(os.path.join(src, f), os.path.join(dst, f))
            self.stdout.write(self.style.SUCCESS('Floor map images copied!'))
        else:
            self.stdout.write(self.style.WARNING('No floor map images found in static folder.'))


    def handle(self, *args, **kwargs):
        self.copy_floor_images()


        # ── Prevent duplicates ──────────────────────────────
        if Building.objects.exists():
            self.stdout.write(self.style.WARNING('Existing data found! Clearing and reseeding...'))
            Room.objects.all().delete()
            Floor.objects.all().delete()
            Building.objects.all().delete()


        # ── Buildings ───────────────────────────────────────
        mb  = Building.objects.create(name='Main Building', code='MB')
        nb  = Building.objects.create(name='New Building', code='NB')
        llb = Building.objects.create(name='Library and Laboratory Building', code='LLB')


        # ── LLB Floors ──────────────────────────────────────
        llb_f1 = Floor.objects.create(
            building=llb, floor_number=1,
            label='Ground Floor',
            map_image='floor_maps/llb_f1.png',
            image_width=1920, image_height=1080
        )
        llb_f2 = Floor.objects.create(
            building=llb, floor_number=2,
            label='Second Floor',
            map_image='floor_maps/llb_f2.png',
            image_width=1920, image_height=1080
        )


        # ── NB Floors ───────────────────────────────────────
        nb_f1 = Floor.objects.create(
            building=nb, floor_number=1,
            label='Ground Floor',
            map_image='floor_maps/NB-Ground-Floor.png',
            image_width=1920, image_height=1080
        )
        nb_f2 = Floor.objects.create(
            building=nb, floor_number=2,
            label='Second Floor',
            map_image='floor_maps/NB-2nd-Floor.png',
            image_width=1920, image_height=1080
        )
        nb_f3 = Floor.objects.create(
            building=nb, floor_number=3,
            label='Third Floor',
            map_image='floor_maps/NB-3rd-Floor.png',
            image_width=1920, image_height=1080
        )
        nb_f4 = Floor.objects.create(
            building=nb, floor_number=4,
            label='Fourth Floor',
            map_image='floor_maps/NB-4th-Floor.png',
            image_width=1920, image_height=1080
        )


        # ── MB Floors ───────────────────────────────────────
        mb_f1 = Floor.objects.create(
            building=mb, floor_number=1,
            label='Ground Floor',
            map_image='floor_maps/mb_f1.png',
            image_width=1920, image_height=1080
        )
        mb_f2 = Floor.objects.create(
            building=mb, floor_number=2,
            label='Second Floor',
            map_image='floor_maps/mb_f2.png',
            image_width=1920, image_height=1080
        )
        mb_f3 = Floor.objects.create(
            building=mb, floor_number=3,
            label='Third Floor',
            map_image='floor_maps/mb_f3.png',
            image_width=1920, image_height=1080
        )
        mb_f4 = Floor.objects.create(
            building=mb, floor_number=4,
            label='Fourth Floor',
            map_image='floor_maps/mb_f4.png',
            image_width=1920, image_height=1080
        )


        # ════════════════════════════════════════════════════
        # LLB ROOMS
        # ════════════════════════════════════════════════════


        # Ground Floor
        Room.objects.create(floor=llb_f1, name='Clinic', code='LLB_CLINIC', x=0, y=0)
        Room.objects.create(floor=llb_f1, name='Maintenance and Engineering Office', code='LLB_MEO', x=0, y=0)
        Room.objects.create(floor=llb_f1, name='Supply and Equipment Office', code='LLB_SEO', x=0, y=0)
        Room.objects.create(floor=llb_f1, name='Registrar', code='LLB_REG', x=0, y=0)
        Room.objects.create(floor=llb_f1, name='Cash Management Division', code='LLB_CMD', x=0, y=0)
        Room.objects.create(floor=llb_f1, name='Administrative Offices', code='LLB_ADMIN', x=0, y=0)


        # Second Floor
        Room.objects.create(floor=llb_f2, name='Library', code='LLB_LIB', x=0, y=0)


        # ════════════════════════════════════════════════════
        # NEW BUILDING ROOMS
        # ════════════════════════════════════════════════════


        # Ground Floor
        Room.objects.create(floor=nb_f1, name='Faculty Comfort Room', code='NB_FCR', x=200, y=430)
        Room.objects.create(floor=nb_f1, name='Storage Room', code='NB_STORAGE', x=445, y=470)
        Room.objects.create(floor=nb_f1, name='Office of the VP for Administration', code='NB_VPA', x=675, y=470)
        Room.objects.create(floor=nb_f1, name='Office of the VP for Comptrollership', code='NB_VPC', x=915, y=470)
        Room.objects.create(floor=nb_f1, name='Human Resources Management and Development Division', code='NB_HRMDD', x=1155, y=470)
        Room.objects.create(floor=nb_f1, name='Planning and Budget Division', code='NB_PBD', x=1395, y=470)
        Room.objects.create(floor=nb_f1, name='Accounting Division', code='NB_ACCTG', x=1665, y=470)


        # Second Floor
        Room.objects.create(floor=nb_f2, name='NB201', code='NB201', x=1535, y=595)
        Room.objects.create(floor=nb_f2, name='NB202', code='NB202', x=1320, y=595)
        Room.objects.create(floor=nb_f2, name='NB203', code='NB203', x=1085, y=595)
        Room.objects.create(floor=nb_f2, name='NB204', code='NB204', x=845, y=595)
        Room.objects.create(floor=nb_f2, name='NB205', code='NB205', x=605, y=595)


        # Third Floor
        Room.objects.create(floor=nb_f3, name='NB | ICT Office', code='NB_ICTO', x=465, y=610)
        Room.objects.create(floor=nb_f3, name='NB301', code='NB301', x=1755, y=610)
        Room.objects.create(floor=nb_f3, name='NB302', code='NB302', x=1545, y=610)
        Room.objects.create(floor=nb_f3, name='NB303', code='NB303', x=1330, y=610)
        Room.objects.create(floor=nb_f3, name='NB304', code='NB304', x=1105, y=610)
        Room.objects.create(floor=nb_f3, name='NB305', code='NB305', x=875, y=610)
        Room.objects.create(floor=nb_f3, name='NB306', code='NB306', x=650, y=610)


        # Fourth Floor
        Room.objects.create(floor=nb_f4, name='NB | Storage Room Floor 4', code='NB_STORAGE4', x=465, y=610)
        Room.objects.create(floor=nb_f4, name='NB401', code='NB401', x=1755, y=610)
        Room.objects.create(floor=nb_f4, name='NB402', code='NB402', x=1545, y=610)
        Room.objects.create(floor=nb_f4, name='NB403', code='NB403', x=1330, y=610)
        Room.objects.create(floor=nb_f4, name='NB404', code='NB404', x=1105, y=610)
        Room.objects.create(floor=nb_f4, name='NB405', code='NB405', x=875, y=610)
        Room.objects.create(floor=nb_f4, name='NB406', code='NB406', x=650, y=610)


        # ════════════════════════════════════════════════════
        # MAIN BUILDING ROOMS
        # ════════════════════════════════════════════════════


        # Ground Floor — offices keep MB_ prefix
        Room.objects.create(floor=mb_f1, name='Office of the VP for Student Success', code='MB_VPSS', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='Manny Villar Wing', code='MB_MVW', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='College of Arts and Sciences', code='MB_CAS', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='College of Business and Management', code='MB_CBM', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='College of Criminal Justice', code='MB_CCJ', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='College of Education', code='MB_CED', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='College of Computer Studies', code='MB_CCS', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='College of Health Sciences', code='MB_CHS', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='Institute of Graduate and Professional Studies', code='MB_IGPS', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='University Research Extension Linkages', code='MB_URELA', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='Admission Office', code='MB_ADMIT', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='Guidance Counseling and Psychological Services', code='MB_GCPS', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='Security Office', code='MB_SEC', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='Office of the University President', code='MB_PRES', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='Office of the VP for Academic Affairs', code='MB_VPAA', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='Accreditation Room', code='MB_ACCRED', x=0, y=0)
        Room.objects.create(floor=mb_f1, name='Quality Assurance and Accreditation', code='MB_QAA', x=0, y=0)


        # Second Floor — classrooms use M prefix
        Room.objects.create(floor=mb_f2, name='Palma Hall', code='MB_PALMA', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M201', code='M201', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M202', code='M202', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M203', code='M203', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M204', code='M204', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M205', code='M205', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M206', code='M206', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M207', code='M207', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M208', code='M208', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M209', code='M209', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M210', code='M210', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M211', code='M211', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M212', code='M212', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M213', code='M213', x=0, y=0)
        Room.objects.create(floor=mb_f2, name='M214', code='M214', x=0, y=0)


        # Third Floor
        Room.objects.create(floor=mb_f3, name='Psychology Laboratory', code='MB_PSYLAB', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='Office of Student Internship and Placement', code='MB_OSIPP', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='F302', code='F302', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='F309', code='F309', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='College of Law Library', code='MB_LAWLIB', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='Function Hall B', code='MB_FHB', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='Entrepreneurship Laboratory', code='MB_ENTLAB', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='Office of Legal Aid', code='MB_OLA', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='Moot Court', code='MB_MOOT', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='FI Room', code='MB_FI', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M301', code='M301', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M302', code='M302', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M303', code='M303', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M304', code='M304', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M305', code='M305', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M306', code='M306', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M307', code='M307', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M308', code='M308', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M309', code='M309', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M310', code='M310', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M311', code='M311', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M312', code='M312', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M313', code='M313', x=0, y=0)
        Room.objects.create(floor=mb_f3, name='M314', code='M314', x=0, y=0)


        # Fourth Floor
        Room.objects.create(floor=mb_f4, name='NRL CHS Skills Laboratory', code='MB_SKILLSLAB', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='Physical Therapy Laboratory', code='MB_PTLAB', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='La Universidad Official Student Publication', code='MB_OSP', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='Function Hall F', code='MB_FHF', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='Faculty Association', code='MB_FA', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='Laboratory Area', code='MB_LABAREA', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='Forensic Science Laboratory', code='MB_FORENSIC', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M401', code='M401', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M402', code='M402', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M403', code='M403', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M404', code='M404', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M405', code='M405', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M406', code='M406', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M407', code='M407', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M408', code='M408', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M409', code='M409', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M410', code='M410', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M411', code='M411', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M412', code='M412', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M413', code='M413', x=0, y=0)
        Room.objects.create(floor=mb_f4, name='M414', code='M414', x=0, y=0)


        self.stdout.write(self.style.SUCCESS('Seed data created successfully!'))



