"""Regression checks using the preserved campus pathway image."""
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from .campus_nav import get_pathfinder
from .intents import navigation_destinations
from .views import calculate_campus_route


class CampusNavigationTests(SimpleTestCase):
    def test_science_and_new_locations_return_drawable_walkable_routes(self):
        pathfinder = get_pathfinder()
        width, height = pathfinder.orig_size
        for destination in ((63, 21.9), (7.2, 64.6), (87.6, 47.4), (87, 60.3)):
            with self.subTest(destination=destination):
                response = calculate_campus_route(APIRequestFactory().post(
                    '/api/navigation/route/',
                    dict(start_x=10.1, start_y=23.8,
                         end_x=destination[0], end_y=destination[1]),
                    format='json',
                ))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['status'], 'success')
                self.assertGreater(len(response.data['path']), 1)
                for point in response.data['path']:
                    x = round(point['x'] * width / 100 / pathfinder.scale)
                    y = round(point['y'] * height / 100 / pathfinder.scale)
                    self.assertEqual(pathfinder.grid[y, x], 1)
                end = response.data['path'][-1]
                snapped = pathfinder.snap_coordinate(
                    int(destination[0] * width / 100),
                    int(destination[1] * height / 100),
                )
                self.assertAlmostEqual(end['x'], snapped[0] * pathfinder.scale / width * 100)
                self.assertAlmostEqual(end['y'], snapped[1] * pathfinder.scale / height * 100)

    def test_new_locations_can_be_requested_in_chat(self):
        for text, expected in (
            ('Where is the College of Business Management and Accountancy?', 'cbma'),
            ('Where is the College of Health Sciences?', 'chs'),
            ('Where is MacLab?', 'maclab'),
            ('Where is the Science Building?', 'science_building'),
        ):
            with self.subTest(text=text):
                self.assertEqual(navigation_destinations(text), [expected])
