import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from data_sources.wtt import WTTDataSource
from data_sources.wtt_time import offset_for_event, venue_to_local
from services.calendar_export import start_utc


class WTTTimeTests(unittest.TestCase):
    def test_official_event_timezone_ids_and_unknown(self):
        self.assertEqual(offset_for_event({"timeZoneId": 73}), timedelta(hours=5))
        self.assertEqual(offset_for_event({"timeZoneId": 45}), timedelta(hours=1))
        self.assertEqual(offset_for_event({"timeZoneId": 53}), timedelta(hours=2))
        self.assertIsNone(offset_for_event({"timeZoneId": 9999}))
        self.assertIsNone(offset_for_event({}))

    def test_astana_venue_time_matches_official_utc_result(self):
        venue = datetime(2026, 9, 20, 17, 0)
        local = venue_to_local(venue, timedelta(hours=5))
        self.assertEqual(local.astimezone(timezone.utc),
                         datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc))

    def test_schedule_time_and_calendar_use_same_instant(self):
        source = WTTDataSource()
        try:
            unit = {
                "Code": "MATCH--", "StartDate": "2026-09-20T17:45:00",
                "ScheduleStatus": "Scheduled", "SubEvent": "Men's Singles",
                "StartList": {"Start": [
                    {"Competitor": {"Description": {"TeamName": "A"}}},
                    {"Competitor": {"Description": {"TeamName": "B"}}},
                ]},
            }
            offset = timedelta(hours=5)
            now = venue_to_local(datetime(2026, 9, 20, 17, 0), offset)
            match = source._build_match("Astana", unit, set(), {}, None, None, now, offset)
            self.assertIsNotNone(match)
            self.assertEqual(start_utc(match),
                             datetime(2026, 9, 20, 12, 45, tzinfo=timezone.utc))
        finally:
            source._client.close()

    def test_unknown_timezone_prevents_publishing_wrong_schedule(self):
        source = WTTDataSource()
        try:
            source._get_json = Mock(return_value=[{"eventId": 9000, "timeZoneId": 9999}])
            self.assertIsNone(source._event_offset(9000))
            with self.assertRaisesRegex(ValueError, "时区未核实"):
                source._event_matches(9000, "Unknown")
        finally:
            source._client.close()


if __name__ == "__main__":
    unittest.main()
