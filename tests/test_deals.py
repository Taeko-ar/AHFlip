import unittest

from ahflip.deals import find_deals
from ahflip.sources.blizzard import lowest


class FindDeals(unittest.TestCase):
    cur = {1: (50, 5), 2: (100, 1), 3: (90, 2)}
    hist = {2: [200, 210, 190], 3: [100, 100, 100]}

    def test_vendor_and_flip(self):
        d = find_deals(self.cur, self.hist, {1: 80}, 0.05, 0.75, 3)
        self.assertEqual([(k, i) for k, i, *_ in d], [("flip", 2), ("vendor", 1)])
        self.assertEqual(d[0][4], 90)  # 200 * 0.95 - 100

    def test_needs_enough_history(self):
        self.assertEqual(find_deals(self.cur, self.hist, {}, 0.05, 0.75, 4), [])


class Lowest(unittest.TestCase):
    def test_unit_price_quantity_and_bids(self):
        self.assertEqual(
            lowest(
                [
                    {"item": {"id": 7}, "buyout": 100, "quantity": 4},
                    {"item": {"id": 7}, "unit_price": 20, "quantity": 2},
                    {"item": {"id": 8}, "bid": 5, "quantity": 1},  # bid only
                    {"item": {"id": 9}, "bid": 100, "buyout": 100, "quantity": 1},  # bid reached buyout: can't buy out
                    {"item": {"id": 9}, "bid": 50, "buyout": 300, "quantity": 1},
                ]
            ),
            {7: (20, 6), 9: (300, 1)},
        )
