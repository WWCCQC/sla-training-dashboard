import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

with patch.dict(os.environ, {'SUPABASE_URL': 'https://example.supabase.co',
                             'SUPABASE_KEY': 'test-key'}):
    import app


class TrainingTable:
    """In-memory Data API with the same server-side response cap."""

    def __init__(self, rows, cap=1000, fail_after=None):
        self.rows = rows
        self.cap = cap
        self.fail_after = fail_after

    def table(self, name):
        if name != 'training_sla':
            raise AssertionError(name)
        return TrainingQuery(self)


class TrainingQuery:
    def __init__(self, table):
        self.table = table
        self.start = 0
        self.end = table.cap - 1
        self.sort_column = None

    def select(self, columns):
        return self

    def order(self, column):
        self.sort_column = column
        return self

    def range(self, start, end):
        self.start, self.end = start, end
        return self

    def execute(self):
        if self.table.fail_after is not None and self.start >= self.table.fail_after:
            raise RuntimeError('Data API unavailable')
        rows = self.table.rows
        if self.sort_column:
            rows = sorted(rows, key=lambda row: row[self.sort_column])
        return SimpleNamespace(data=rows[self.start:min(self.end + 1, self.start + self.table.cap)])


class LoadDataTests(unittest.TestCase):
    def test_loads_all_rows_and_counts_onprocess_beyond_first_page(self):
        rows = [dict(row_id=i, training_month='Nov26',
                     result='Onprocess' if i >= 1000 else 'Completed',
                     created_at='2026-11-18T00:00:00Z' if i == 1055 else None)
                for i in range(1056)]
        with patch.object(app, 'supabase', TrainingTable(list(reversed(rows)))):
            df = app.load_data()
        self.assertEqual(len(df), 1056)
        self.assertEqual(df['row_id'].tolist(), list(range(1056)))
        self.assertEqual(app.get_summary_stats(df)['onprocess'], 56)
        self.assertEqual(app.LATEST_DATA_UPDATED_AS, '18 November 2026 07:00')

    def test_handles_empty_table_and_exact_page_boundary(self):
        for total in (0, 2000):
            with self.subTest(total=total):
                rows = [dict(row_id=i) for i in range(total)]
                with patch.object(app, 'supabase', TrainingTable(rows)):
                    self.assertEqual(len(app.load_data()), total)

    def test_continues_when_server_cap_is_smaller_than_requested_page(self):
        rows = [dict(row_id=i) for i in range(1056)]
        with patch.object(app, 'supabase', TrainingTable(rows, cap=200)):
            self.assertEqual(len(app.load_data()), 1056)

    def test_page_failure_does_not_return_partial_database_data(self):
        rows = [dict(row_id=i) for i in range(1056)]
        fallback = app.pd.DataFrame([dict(row_id=-1)])
        with patch.object(app, 'supabase', TrainingTable(rows, fail_after=1000)), \
                patch.object(app.pd, 'read_csv', return_value=fallback):
            df = app.load_data()
        self.assertEqual(df['row_id'].tolist(), [-1])


if __name__ == '__main__':
    unittest.main()
