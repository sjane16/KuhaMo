from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.test import TestCase

from adm.models import Building, Floor, Room
from adm.views import _build_dashboard_data
from .forms import ReportForm
from .models import Report


class ReportLocationTests(TestCase):
    def setUp(self):
        self.building = Building.objects.create(name='Original Building', code='OB')
        self.floor = Floor.objects.create(building=self.building, floor_number=1, label='First Floor')
        self.room = Room.objects.create(floor=self.floor, name='Original Room', code='OR')

    def create_report(self, key, **kwargs):
        return Report.objects.create(job_order_id=key, category='electrical', description='Test', **kwargs)

    def backfill(self):
        migration = import_module('user.migrations.0034_backfill_report_rooms')
        migration.backfill_report_rooms(apps, SimpleNamespace(connection=SimpleNamespace(alias='default')))

    def test_new_reports_capture_location_and_survive_room_rename_and_deletion(self):
        report = self.create_report('ROOM-LINK', room=self.room)
        original = report.location
        self.room.name = 'Renamed Room'
        self.room.save()
        self.building.name = 'Renamed Building'
        self.building.save()
        report.save()
        report.refresh_from_db()
        self.assertEqual(report.location, original)
        self.assertEqual(report.room_location, 'Original Room')
        self.assertEqual(report.building_name, 'Original Building')
        self.room.delete()
        report.refresh_from_db()
        self.assertIsNone(report.room_id)
        self.assertEqual(report.location, original)
        dashboard = _build_dashboard_data('all')
        index = dashboard['building_labels'].index('Original Building')
        self.assertEqual(dashboard['building_status_data']['pending'][index], 1)

    def test_backfill_links_unique_matches_but_not_ambiguous_or_missing_rooms(self):
        label = 'Original Building, First Floor, Original Room'
        report = self.create_report('BACKFILL', location=label)
        self.backfill()
        self.backfill()
        report.refresh_from_db()
        self.assertEqual(report.room_id, self.room.pk)
        self.assertEqual(report.location, label)
        self.assertEqual(report.history.first().room_id, self.room.pk)
        Room.objects.create(floor=self.floor, name=self.room.name, code='DUP')
        ambiguous = self.create_report('AMBIGUOUS', location=label)
        unknown = self.create_report('UNKNOWN', location='Old Building, Old Floor, Old Room')
        self.backfill()
        for row in (ambiguous, unknown):
            row.refresh_from_db()
            self.assertIsNone(row.room_id)
        self.assertEqual(unknown.room_location, 'Old Room')
        self.assertEqual(unknown.building_name, 'Old Building')

    def test_room_selector_accepts_only_rooms_on_selected_floor(self):
        form = ReportForm(data={'building': self.building.pk, 'floor': self.floor.pk})
        self.assertEqual(list(form.fields['location'].queryset), [self.room])
        other_floor = Floor.objects.create(building=self.building, floor_number=2, label='Second')
        other_room = Room.objects.create(floor=other_floor, name='Other', code='OTHER')
        self.assertFalse(form.fields['location'].queryset.filter(pk=other_room.pk).exists())
