import unittest      # Python's built-in framework for writing and running unit tests
import os            # For creating and removing temporary test files during teardown
from datetime import datetime, timedelta  # For building explicit date fixtures used in streak tests

# Import every public symbol needed from the single application module
from hobby_tracker import (
    Hobby,              # Data model: one personal hobby record
    HobbyStore,         # Persistence layer: JSON file load and save
    HobbyAnalytics,     # Functional analytics: filter, map, max, reduce, sorted
    HobbyTracker,       # Application controller: 4-option menu and sub-menus
    _rebuild_streak,    # Module-level streak engine tested directly with known dates
    _entries_in_window, # Module-level window-counting helper tested with exact ranges
    _progress_bar       # Module-level ASCII bar generator tested with known values
)

"""
Test suite for the Hobby Tracker application.

Each test builds explicit hobby data with fixed dates and asserts exact
expected values so the reader can clearly see what is being tested and why
the assertion should hold.

    TestHobby          — Construction, serialisation, and round-trip restoration.
    TestHobbyAnalytics — Functional methods with exact numeric assertions.
    TestHobbyStore     — File persistence: save-then-reload round-trips.
    TestHobbyTracker   — Streak engine, progress bar, and controller state.
"""


# ===========================================================================
# Tests for the Hobby data model
# ===========================================================================
class TestHobby(unittest.TestCase):
    """Verify that Hobby objects are constructed and serialised correctly."""

    def setUp(self):
        """Create a Hobby with known values that every test in this class will inspect."""
        # Build a daily hobby with specific values so assertions are unambiguous
        self.hobby = Hobby(
            title="Morning Journaling",     # Title used in equality checks below
            cycle="daily",                  # Daily cycle used in label checks below
            frequency=1,                    # Frequency=1 used in dict checks below
            description="Write one page"   # Description used in dict checks below
        )

    def test_title_stored_correctly(self):
        """Title passed to the constructor must be stored exactly as given."""
        # Expect the title attribute to equal the string passed in
        self.assertEqual(self.hobby.title, "Morning Journaling")  # Must match constructor arg

    def test_cycle_and_frequency_stored_correctly(self):
        """Cycle and frequency must be stored without modification."""
        self.assertEqual(self.hobby.cycle, "daily")   # Must match constructor arg
        self.assertEqual(self.hobby.frequency, 1)     # Must match constructor arg

    def test_description_stored_correctly(self):
        """Description must be stored without modification."""
        self.assertEqual(self.hobby.description, "Write one page")  # Must match constructor arg

    def test_log_dates_starts_empty(self):
        """A brand-new Hobby must have an empty log_dates list before any session is logged."""
        self.assertEqual(self.hobby.log_dates, [])    # No sessions recorded yet

    def test_streak_and_best_streak_start_at_zero(self):
        """Both streak values must be zero for a hobby that has never been logged."""
        self.assertEqual(self.hobby.streak, 0)        # No consecutive cycles completed yet
        self.assertEqual(self.hobby.best_streak, 0)   # No personal best established yet

    def test_created_on_is_set_automatically(self):
        """created_on must be a non-empty string stamped at construction time."""
        self.assertIsInstance(self.hobby.created_on, str)      # Must always be a string
        self.assertGreater(len(self.hobby.created_on), 0)      # Must not be blank

    def test_cycle_label_daily_returns_Daily(self):
        """cycle_label() must return 'Daily' for a hobby whose cycle is 'daily'."""
        self.assertEqual(self.hobby.cycle_label(), "Daily")    # 'daily' maps to 'Daily'

    def test_cycle_label_weekly_returns_Weekly(self):
        """cycle_label() must return 'Weekly' for a hobby whose cycle is 'weekly'."""
        weekly = Hobby("Chess", "weekly", 2, "Two puzzles per week")  # Build a weekly hobby
        self.assertEqual(weekly.cycle_label(), "Weekly")       # 'weekly' maps to 'Weekly'

    def test_target_label_daily_shows_per_day(self):
        """target_label() must return '1x / day' for any daily hobby."""
        self.assertEqual(self.hobby.target_label(), "1x / day")  # Daily always shows this

    def test_target_label_weekly_shows_frequency(self):
        """target_label() must include the frequency number for a weekly hobby."""
        weekly = Hobby("Chess", "weekly", 3, "Three sessions a week")  # frequency=3
        self.assertEqual(weekly.target_label(), "3x / we")     # '3x / we' for weekly

    def test_to_dict_produces_correct_title_and_cycle(self):
        """to_dict must produce a dict whose title and cycle match the Hobby's attributes."""
        result = self.hobby.to_dict()                          # Serialise to a plain dict
        self.assertEqual(result["title"], "Morning Journaling")  # Title must survive serialisation
        self.assertEqual(result["cycle"], "daily")             # Cycle must survive serialisation
        self.assertEqual(result["frequency"], 1)               # Frequency must survive serialisation

    def test_to_dict_contains_all_eight_keys(self):
        """to_dict must produce a dictionary that has exactly the eight required keys."""
        result = self.hobby.to_dict()                          # Serialise the hobby
        required_keys = {
            "title", "cycle", "frequency", "description",     # Identity fields
            "created_on", "log_dates", "streak", "best_streak"  # Tracking fields
        }
        self.assertEqual(set(result.keys()), required_keys)   # All eight keys must be present

    def test_from_dict_restores_title_cycle_and_frequency(self):
        """from_dict must restore the core identity fields exactly as stored."""
        record = {                                             # Build a representative dict
            "title": "Chess Puzzles",
            "cycle": "weekly",
            "frequency": 2,
            "description": "Solve two puzzles per week",
            "created_on": "2026-04-06 19:00",
            "log_dates": ["2026-04-07", "2026-04-09"],        # Two stored dates
            "streak": 1,
            "best_streak": 2
        }
        restored = Hobby.from_dict(record)                    # Reconstruct from the dict
        self.assertEqual(restored.title, "Chess Puzzles")     # Title correctly restored
        self.assertEqual(restored.cycle, "weekly")            # Cycle correctly restored
        self.assertEqual(restored.frequency, 2)               # Frequency correctly restored

    def test_from_dict_restores_log_dates_and_streaks(self):
        """from_dict must restore log_dates, streak, and best_streak exactly."""
        record = {
            "title": "Screenless Morning",
            "cycle": "daily",
            "frequency": 1,
            "description": "No screens for one hour",
            "created_on": "2026-04-20 06:30",
            "log_dates": ["2026-05-07", "2026-05-08", "2026-05-09"],  # Three known dates
            "streak": 3,                                       # Known streak value
            "best_streak": 20                                  # Known best value
        }
        restored = Hobby.from_dict(record)                    # Reconstruct from the dict
        self.assertEqual(len(restored.log_dates), 3)          # All three dates must be present
        self.assertIn("2026-05-08", restored.log_dates)       # Specific date must be in the list
        self.assertEqual(restored.streak, 3)                  # Streak must match stored value
        self.assertEqual(restored.best_streak, 20)            # Best must match stored value

    def test_roundtrip_preserves_log_dates_and_streaks(self):
        """Converting a Hobby to dict and back must leave all data unchanged."""
        self.hobby.log_dates = ["2026-05-07", "2026-05-08", "2026-05-09"]  # Attach 3 dates
        self.hobby.streak = 3                                 # Set a known streak
        self.hobby.best_streak = 10                           # Set a known best
        restored = Hobby.from_dict(self.hobby.to_dict())      # Full serialise → deserialise
        self.assertEqual(restored.log_dates, ["2026-05-07", "2026-05-08", "2026-05-09"])
        self.assertEqual(restored.streak, 3)                  # Streak value unchanged
        self.assertEqual(restored.best_streak, 10)            # Best value unchanged


# ===========================================================================
# Tests for the HobbyAnalytics functional layer
# ===========================================================================
class TestHobbyAnalytics(unittest.TestCase):
    """Verify every analytics function with exact numeric assertions."""

    def setUp(self):
        """Build four Hobby objects with known streak values for all analytics tests."""
        # Daily hobby A — highest streak, used to verify max() behaviour
        self.daily_a = Hobby("Journaling", "daily", 1, "Write daily")
        self.daily_a.streak = 10           # Current streak value used in average calculation
        self.daily_a.best_streak = 15      # Highest best — must be returned by longest_streak_overall

        # Daily hobby B — lower values, used to verify filter and sorting behaviour
        self.daily_b = Hobby("Screenless", "daily", 1, "No screens in morning")
        self.daily_b.streak = 5            # Lower than daily_a for average/sort checks
        self.daily_b.best_streak = 8       # Lower than daily_a for sort checks

        # Weekly hobby — used to verify list_by_cycle filter
        self.weekly_a = Hobby("Chess", "weekly", 2, "Solve chess puzzles")
        self.weekly_a.streak = 4           # Distinct value for average calculation
        self.weekly_a.best_streak = 4

        # Monthly hobby — used to verify list_by_cycle filter for monthly
        self.monthly_a = Hobby("Deep Clean", "monthly", 1, "Clean apartment")
        self.monthly_a.streak = 3          # Lowest streak in the collection
        self.monthly_a.best_streak = 3

        # Full list used by most tests
        self.hobbies = [self.daily_a, self.daily_b, self.weekly_a, self.monthly_a]

    def test_list_all_returns_all_four_hobbies(self):
        """list_all must return every hobby — none omitted, none duplicated."""
        result = HobbyAnalytics.list_all(self.hobbies)            # Calls map() internally
        self.assertEqual(len(result), 4)                           # Exactly four must be returned
        self.assertIn(self.daily_a, result)                        # Journaling must be present
        self.assertIn(self.monthly_a, result)                      # Deep Clean must be present

    def test_list_by_cycle_daily_returns_two_hobbies(self):
        """list_by_cycle('daily') must return exactly the two daily hobbies."""
        daily_group = HobbyAnalytics.list_by_cycle(self.hobbies, "daily")  # filter() internally
        self.assertEqual(len(daily_group), 2)                      # Two daily hobbies in collection
        titles = [h.title for h in daily_group]                    # Extract titles for inspection
        self.assertIn("Journaling", titles)                        # Journaling is daily
        self.assertIn("Screenless", titles)                        # Screenless is daily

    def test_list_by_cycle_weekly_returns_one_hobby(self):
        """list_by_cycle('weekly') must return exactly the one weekly hobby."""
        weekly_group = HobbyAnalytics.list_by_cycle(self.hobbies, "weekly")
        self.assertEqual(len(weekly_group), 1)                     # Only Chess is weekly
        self.assertEqual(weekly_group[0].title, "Chess")           # Must be the Chess hobby

    def test_list_by_cycle_yearly_returns_empty_list(self):
        """list_by_cycle('yearly') must return an empty list when no yearly hobbies exist."""
        yearly_group = HobbyAnalytics.list_by_cycle(self.hobbies, "yearly")
        self.assertEqual(len(yearly_group), 0)                     # No yearly hobbies in collection

    def test_longest_streak_overall_returns_journaling_with_best_15(self):
        """longest_streak_overall must return the hobby whose best_streak is 15."""
        top = HobbyAnalytics.longest_streak_overall(self.hobbies)  # Calls max() internally
        self.assertEqual(top.title, "Journaling")                  # Journaling has best_streak=15
        self.assertEqual(top.best_streak, 15)                      # Exact value must be 15

    def test_longest_streak_overall_returns_none_for_empty_list(self):
        """longest_streak_overall must return None without raising when given an empty list."""
        result = HobbyAnalytics.longest_streak_overall([])         # Empty list edge case
        self.assertIsNone(result)                                   # Must be None, not an error

    def test_longest_streak_for_journaling_returns_15(self):
        """longest_streak_for must return 15 for Journaling which has best_streak=15."""
        result = HobbyAnalytics.longest_streak_for(self.daily_a)   # Named accessor function
        self.assertEqual(result, 15)                               # Exact best_streak value

    def test_longest_streak_for_chess_returns_4(self):
        """longest_streak_for must return 4 for Chess which has best_streak=4."""
        result = HobbyAnalytics.longest_streak_for(self.weekly_a)  # Named accessor function
        self.assertEqual(result, 4)                                # Exact best_streak value

    def test_sorted_by_streak_order_is_15_8_4_3(self):
        """sorted_by_streak must return hobbies in descending best_streak order: 15,8,4,3."""
        ranked = HobbyAnalytics.sorted_by_streak(self.hobbies)     # Calls sorted() internally
        best_values = [h.best_streak for h in ranked]              # Extract best_streak per hobby
        self.assertEqual(best_values, [15, 8, 4, 3])              # Exact descending order expected

    def test_average_streak_of_10_5_4_3_equals_5_5(self):
        """average_streak must return exactly 5.5 for streaks [10, 5, 4, 3]."""
        # streaks are: daily_a=10, daily_b=5, weekly_a=4, monthly_a=3 → mean = 22/4 = 5.5
        avg = HobbyAnalytics.average_streak(self.hobbies)          # Calls reduce() internally
        self.assertAlmostEqual(avg, 5.5, places=5)                 # Exact mean: (10+5+4+3)/4=5.5

    def test_average_streak_returns_zero_for_empty_list(self):
        """average_streak must return 0.0 without raising when the list is empty."""
        result = HobbyAnalytics.average_streak([])                 # Edge case: no hobbies
        self.assertEqual(result, 0.0)                              # Must be 0.0, not an error

    def test_total_sessions_sums_3_plus_2_equals_5(self):
        """total_sessions must return 5 when one hobby has 3 dates and another has 2."""
        self.daily_a.log_dates = ["2026-05-07", "2026-05-08", "2026-05-09"]  # 3 sessions
        self.weekly_a.log_dates = ["2026-05-05", "2026-05-07"]               # 2 sessions
        # daily_b and monthly_a have no log_dates → contribute 0 each
        total = HobbyAnalytics.total_sessions(self.hobbies)        # Calls reduce() internally
        self.assertEqual(total, 5)                                 # 3 + 2 + 0 + 0 = 5

    def test_total_sessions_returns_zero_for_empty_list(self):
        """total_sessions must return 0 without raising when the list is empty."""
        result = HobbyAnalytics.total_sessions([])                 # Edge case: no hobbies
        self.assertEqual(result, 0)                                # Must be 0, not an error


# ===========================================================================
# Tests for the HobbyStore persistence layer
# ===========================================================================
class TestHobbyStore(unittest.TestCase):
    """Verify that hobbies survive a complete save-then-reload cycle without data loss."""

    TEST_FILE = "test_hobbies_store.json"  # Isolated file used only by this test class

    def setUp(self):
        """Redirect HobbyStore to the isolated test file before each test method."""
        HobbyStore.DATA_FILE = self.TEST_FILE              # Avoid touching the real data file

    def tearDown(self):
        """Delete the temporary test file and restore the default file name after each test."""
        if os.path.exists(self.TEST_FILE):
            os.remove(self.TEST_FILE)                      # Remove the leftover test artifact
        HobbyStore.DATA_FILE = "hobbies.json"              # Restore the production default name

    def test_save_and_load_restores_title_and_cycle(self):
        """Title and cycle of a saved hobby must be identical after a reload."""
        h = Hobby("Reading", "daily", 1, "Read 20 pages every day")  # Build the test hobby
        HobbyStore.save([h])                               # Write to the isolated test file
        loaded = HobbyStore.load()                         # Read back from the same file
        self.assertEqual(loaded[0].title, "Reading")       # Title must be identical after reload
        self.assertEqual(loaded[0].cycle, "daily")         # Cycle must be identical after reload

    def test_save_and_load_restores_log_dates_exactly(self):
        """All three log dates must be present and identical after a save-load round-trip."""
        h = Hobby("Reading", "daily", 1, "Read 20 pages every day")
        h.log_dates = ["2026-05-07", "2026-05-08", "2026-05-09"]  # Three specific dates
        HobbyStore.save([h])                               # Persist to the test file
        loaded = HobbyStore.load()                         # Reload from the test file
        self.assertEqual(len(loaded[0].log_dates), 3)      # Count must be exactly three
        self.assertEqual(loaded[0].log_dates[0], "2026-05-07")  # First date must match
        self.assertEqual(loaded[0].log_dates[2], "2026-05-09")  # Last date must match

    def test_save_and_load_restores_streak_values(self):
        """streak and best_streak must be identical after a save-load round-trip."""
        h = Hobby("Reading", "daily", 1, "Read daily")
        h.streak = 7                                       # Set a known streak value
        h.best_streak = 14                                 # Set a known best_streak value
        HobbyStore.save([h])                               # Write to the test file
        loaded = HobbyStore.load()                         # Reload from the test file
        self.assertEqual(loaded[0].streak, 7)              # streak must be exactly 7
        self.assertEqual(loaded[0].best_streak, 14)        # best_streak must be exactly 14

    def test_save_three_hobbies_all_reload_correctly(self):
        """All three hobbies in a list must survive a save-then-load round-trip intact."""
        first = Hobby("Yoga", "daily", 1, "Morning yoga")
        second = Hobby("Chess", "weekly", 2, "Two puzzles per week")
        third = Hobby("Clean", "monthly", 1, "Full apartment clean")
        HobbyStore.save([first, second, third])            # Save all three at once
        loaded = HobbyStore.load()                         # Reload all three from the file
        self.assertEqual(len(loaded), 3)                   # All three must be present
        titles = [h.title for h in loaded]                 # Collect titles for inspection
        self.assertIn("Yoga", titles)                      # First hobby present
        self.assertIn("Chess", titles)                     # Second hobby present
        self.assertIn("Clean", titles)                     # Third hobby present

    def test_load_returns_empty_list_when_file_absent(self):
        """HobbyStore.load must return [] rather than raising when no file exists."""
        if os.path.exists(self.TEST_FILE):
            os.remove(self.TEST_FILE)                      # Ensure the file is genuinely absent
        result = HobbyStore.load()                         # Attempt load with no file on disk
        self.assertEqual(result, [])                       # Must return exactly an empty list


# ===========================================================================
# Tests for the streak engine, progress bar, and HobbyTracker controller
# ===========================================================================
class TestHobbyTracker(unittest.TestCase):
    """Verify streak calculations with explicit dates, progress-bar output, and controller state."""

    TEST_FILE = "test_hobbies_app.json"  # Separate file isolated from HobbyStore tests

    def setUp(self):
        """Boot a fresh HobbyTracker instance backed by an empty isolated test file."""
        HobbyStore.DATA_FILE = self.TEST_FILE              # Redirect persistence to the test file
        HobbyStore.save([])                                # Write an empty hobbies list to disk
        self.tracker = HobbyTracker()                      # Instantiate the application controller

    def tearDown(self):
        """Remove the test file and restore the production data file path after each test."""
        if os.path.exists(self.TEST_FILE):
            os.remove(self.TEST_FILE)                      # Clean up the leftover test artifact
        HobbyStore.DATA_FILE = "hobbies.json"              # Restore the production default name

    def test_initial_hobbies_list_is_empty(self):
        """A freshly created HobbyTracker backed by an empty file must hold no hobbies."""
        self.assertEqual(len(self.tracker.hobbies), 0)     # List must start completely empty

    def test_adding_one_hobby_makes_length_one(self):
        """After appending one Hobby and saving, the reloaded list must have exactly one entry."""
        h = Hobby("Running", "daily", 1, "Evening 5 km run")  # Build a test hobby
        self.tracker.hobbies.append(h)                     # Add it to the controller's list
        HobbyStore.save(self.tracker.hobbies)              # Persist to the test file
        reloaded = HobbyStore.load()                       # Reload from disk
        self.assertEqual(len(reloaded), 1)                 # Count must be exactly one
        self.assertEqual(reloaded[0].title, "Running")     # Must be the hobby we added

    def test_entries_in_window_counts_only_may_1_and_may_5(self):
        """_entries_in_window must count 2 when window is May 1–7 and list spans Apr–May."""
        # Dates: Apr 30 is before the window, May 1 and May 5 are inside, May 10 is after
        log = ["2026-04-30", "2026-05-01", "2026-05-05", "2026-05-10", "2026-05-12"]
        win_open = datetime(2026, 5, 1).date()             # Window opens on May 1st
        win_close = datetime(2026, 5, 7).date()            # Window closes on May 7th
        count = _entries_in_window(log, win_open, win_close)
        self.assertEqual(count, 2)                         # Only May 1 and May 5 qualify

    def test_daily_streak_three_consecutive_days(self):
        """_rebuild_streak must return streak=3 for three consecutive daily log dates."""
        h = Hobby("Meditation", "daily", 1, "Morning meditation")
        today = datetime.now().date()
        # Use the last three days relative to today so no past window is ever missed
        h.log_dates = [
            (today - timedelta(days=2)).strftime("%Y-%m-%d"),
            (today - timedelta(days=1)).strftime("%Y-%m-%d"),
            today.strftime("%Y-%m-%d"),
        ]
        streak, best = _rebuild_streak(h)                  # Run the streak engine
        self.assertEqual(streak, 3)                        # Three consecutive days → streak = 3
        self.assertEqual(best, 3)                          # Best must also be 3

    def test_daily_streak_resets_to_one_after_missed_day(self):
        """_rebuild_streak must reset streak to 1 when one day is skipped in the past."""
        h = Hobby("Meditation", "daily", 1, "Morning meditation")
        today = datetime.now().date()
        # today-3 and today-2 done, today-1 MISSED (past closed window), today done again
        h.log_dates = [
            (today - timedelta(days=3)).strftime("%Y-%m-%d"),
            (today - timedelta(days=2)).strftime("%Y-%m-%d"),
            today.strftime("%Y-%m-%d"),                    # Gap on today-1
        ]
        h.best_streak = 2                                  # Previous best before the miss
        streak, best = _rebuild_streak(h)                  # Run the streak engine
        self.assertEqual(streak, 1)                        # Only today in the current run
        self.assertEqual(best, 2)                          # Best is preserved from before the gap

    def test_weekly_streak_three_satisfied_weeks(self):
        """_rebuild_streak must return streak=3 for three weeks each with 2 sessions."""
        h = Hobby("Chess Puzzles", "weekly", 2, "Two puzzles per week")
        today = datetime.now().date()
        this_monday = today - timedelta(days=today.weekday())  # Start of the current open week
        # Use the three most recent fully closed weeks — the current open week has no entries
        # so it will not reset the streak (win_close >= today guard)
        w1 = this_monday - timedelta(weeks=3)  # Oldest of the three complete weeks
        w2 = this_monday - timedelta(weeks=2)
        w3 = this_monday - timedelta(weeks=1)  # Most recent complete week
        h.log_dates = [
            (w1 + timedelta(days=1)).strftime("%Y-%m-%d"),  # Week 1: session 1
            (w1 + timedelta(days=3)).strftime("%Y-%m-%d"),  # Week 1: session 2
            (w2 + timedelta(days=1)).strftime("%Y-%m-%d"),  # Week 2: session 1
            (w2 + timedelta(days=3)).strftime("%Y-%m-%d"),  # Week 2: session 2
            (w3 + timedelta(days=1)).strftime("%Y-%m-%d"),  # Week 3: session 1
            (w3 + timedelta(days=3)).strftime("%Y-%m-%d"),  # Week 3: session 2
        ]
        streak, best = _rebuild_streak(h)                  # Run the streak engine
        self.assertEqual(streak, 3)                        # Three consecutive weeks met → 3
        self.assertEqual(best, 3)                          # Best must match

    def test_weekly_streak_broken_by_one_session_below_target(self):
        """_rebuild_streak must reset streak when a past week has only 1 of 2 required."""
        h = Hobby("Chess Puzzles", "weekly", 2, "Two puzzles per week")
        today = datetime.now().date()
        this_monday = today - timedelta(days=today.weekday())
        # Three complete weeks: week 1 met, week 2 only 1 session (fails), week 3 met
        w1 = this_monday - timedelta(weeks=3)
        w2 = this_monday - timedelta(weeks=2)
        w3 = this_monday - timedelta(weeks=1)
        h.log_dates = [
            (w1 + timedelta(days=1)).strftime("%Y-%m-%d"),  # Week 1: session 1 — streak=1
            (w1 + timedelta(days=3)).strftime("%Y-%m-%d"),  # Week 1: session 2
            (w2 + timedelta(days=1)).strftime("%Y-%m-%d"),  # Week 2: only 1 session — resets streak
            (w3 + timedelta(days=1)).strftime("%Y-%m-%d"),  # Week 3: session 1 — streak back to 1
            (w3 + timedelta(days=3)).strftime("%Y-%m-%d"),  # Week 3: session 2
        ]
        h.best_streak = 1                                  # Stored best before the test
        streak, best = _rebuild_streak(h)                  # Run the streak engine
        self.assertEqual(streak, 1)                        # Only week 3 contributes to current run
        self.assertEqual(best, 1)                          # Best stays at 1 (set in week 1)

    def test_progress_bar_is_all_filled_when_streak_equals_best(self):
        """_progress_bar must produce 10 filled blocks when streak equals best_streak."""
        bar = _progress_bar(streak=10, best=10, width=10)  # 100% — all filled
        self.assertEqual(bar, "██████████")                # Ten filled blocks expected

    def test_progress_bar_is_all_empty_when_streak_is_zero(self):
        """_progress_bar must produce 10 empty blocks when streak is zero."""
        bar = _progress_bar(streak=0, best=10, width=10)   # 0% — all empty
        self.assertEqual(bar, "░░░░░░░░░░")               # Ten empty blocks expected

    def test_progress_bar_is_half_filled_when_streak_is_half_of_best(self):
        """_progress_bar must produce 5 filled and 5 empty blocks for streak=5, best=10."""
        bar = _progress_bar(streak=5, best=10, width=10)   # 50% — half filled
        self.assertEqual(bar.count("█"), 5)                # Five filled blocks
        self.assertEqual(bar.count("░"), 5)                # Five empty blocks

    def test_three_hobbies_all_persist_and_reload(self):
        """All three hobbies added to HobbyTracker must be recoverable after save and load."""
        h1 = Hobby("Yoga", "daily", 1, "Morning stretch")
        h2 = Hobby("Reading", "weekly", 3, "30 pages three times a week")
        h3 = Hobby("Budget", "monthly", 1, "Review monthly finances")
        self.tracker.hobbies.extend([h1, h2, h3])          # Add all three to the controller
        HobbyStore.save(self.tracker.hobbies)              # Persist all three to disk
        reloaded = HobbyStore.load()                       # Reload from the test file
        self.assertEqual(len(reloaded), 3)                 # All three must survive
        titles = [h.title for h in reloaded]               # Extract titles for inspection
        self.assertIn("Yoga", titles)                      # Yoga must be present
        self.assertIn("Reading", titles)                   # Reading must be present
        self.assertIn("Budget", titles)                    # Budget must be present

    def test_render_table_displays_all_hobbies(self):
        """_render_table must print a formatted table row for each registered hobby."""
        # Build three hobbies with known values and inject them into the tracker
        h1 = Hobby("Morning Journaling", "daily", 1, "Write one page every morning")
        h1.streak = 28                                     # Set a known streak for display
        h1.best_streak = 28                                # Set a known best for display
        h2 = Hobby("Chess Puzzles", "weekly", 2, "Solve two puzzles per week")
        h2.streak = 5                                      # Set a known streak for display
        h2.best_streak = 5                                 # Set a known best for display
        h3 = Hobby("Apartment Deep Clean", "monthly", 1, "Full cleaning session")
        h3.streak = 4                                      # Set a known streak for display
        h3.best_streak = 4                                 # Set a known best for display
        self.tracker.hobbies = [h1, h2, h3]               # Load directly into the tracker
        result = self.tracker._render_table()              # Call the real display method
        self.assertTrue(result)                            # Must return True (table was printed)
        self.assertEqual(len(self.tracker.hobbies), 3)    # All three rows must be in the table

    def test_stats_screen_displays_progress_bars_and_analytics(self):
        """_stats_screen must print ASCII bars and analytics for all registered hobbies."""
        # Build two hobbies with log dates so the stats screen has real data to display
        h1 = Hobby("Morning Journaling", "daily", 1, "Write one page every morning")
        h1.log_dates = ["2026-05-09", "2026-05-10", "2026-05-11"]  # Three recent sessions
        h1.streak = 3                                      # Known streak shown in the bars
        h1.best_streak = 28                                # Known best shown in the bars
        h2 = Hobby("Chess Puzzles", "weekly", 2, "Solve two puzzles per week")
        h2.log_dates = ["2026-05-05", "2026-05-07"]       # Two sessions in the last week
        h2.streak = 5                                      # Known streak shown in the bars
        h2.best_streak = 5                                 # Known best shown in the bars
        self.tracker.hobbies = [h1, h2]                   # Load directly into the tracker
        self.tracker._stats_screen()                       # Call the real display method
        self.assertEqual(len(self.tracker.hobbies), 2)    # Both hobbies must still be present


# ===========================================================================
# Custom runner for cleaner terminal output
# ===========================================================================
class _CleanResult(unittest.TextTestResult):
    """Replace Python 3.11+ redundant paths with concise docstrings and class section headers."""

    _current_class = None  # Tracks the active class so headers print exactly once per class

    def getDescription(self, test):
        """Return the first line of the method docstring, or a prettified method name."""
        doc = test.shortDescription()                              # First line of method's docstring
        return doc if doc else test._testMethodName.replace("_", " ")  # Fallback to method name

    def startTest(self, test):
        """Print a section header when the test class changes, then hand off to the parent."""
        cls_name = type(test).__name__                            # Name of the current test class
        if cls_name != _CleanResult._current_class:              # Entering a new class
            _CleanResult._current_class = cls_name               # Remember it for the next test
            cls_doc = (type(test).__doc__ or "").strip().split("\n")[0]  # First line of class doc
            self.stream.writeln("")                               # Blank line before the header
            rule = "─" * 72                                      # Horizontal divider line
            self.stream.writeln(rule)                            # Top rule
            label = f"  {cls_name}  —  {cls_doc}" if cls_doc else f"  {cls_name}"
            self.stream.writeln(label)                           # Class name and one-line summary
            self.stream.writeln(rule)                            # Bottom rule
        super().startTest(test)                                  # Delegate to standard handler


class _CleanRunner(unittest.TextTestRunner):
    """TextTestRunner that plugs in _CleanResult for section-headed, non-redundant output."""
    resultclass = _CleanResult                                   # Replace the default result class


if __name__ == "__main__":
    unittest.main(testRunner=_CleanRunner(verbosity=2))  # Section-headed output, no duplicate names
