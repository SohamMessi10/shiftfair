from shiftfair.load import load_schedule
from shiftfair.report import schedule_csv, schedule_lines, write_schedule
from tests.helpers import person, problem, shift


def club():
    import datetime as dt
    return problem([shift("pm", "14:00", "17:00"), shift("am", "09:00", "12:00", needed=2),
                    shift("sun", "22:00", "01:00", date=dt.date(2026, 12, 6))],
                   [person("Ben", am="yes", pm="yes"), person("Ana", am="yes", sun="yes"), person("Cy")])


ASSIGNMENT = {"am": frozenset({"Ben", "Ana"}), "pm": frozenset({"Ben"}), "sun": frozenset()}


def test_schedule_lines_by_day_in_time_order_with_hours():
    assert schedule_lines(club(), ASSIGNMENT) == [
        "Sat 2026-12-05",
        "  09:00–12:00  am   Ana, Ben",
        "  14:00–17:00  pm   Ben",
        "Sun 2026-12-06",
        "  22:00–01:00  sun  (nobody)",
        "hours: Ben 6 h  Ana 3 h  Cy 0 h"]


def test_schedule_csv_is_in_time_order_and_reads_back(tmp_path):
    assert schedule_csv(club(), ASSIGNMENT) == ("shift,date,start,end,person\n"
                                                "am,2026-12-05,09:00,12:00,Ana\n"
                                                "am,2026-12-05,09:00,12:00,Ben\n"
                                                "pm,2026-12-05,14:00,17:00,Ben\n")
    write_schedule(tmp_path / "s.csv", club(), ASSIGNMENT)
    assert load_schedule(tmp_path / "s.csv", club()) == ASSIGNMENT


def test_names_with_commas_and_quotes_survive_the_round_trip(tmp_path):
    p = problem([shift("a")], [person('Lee, "Jo"', a="yes")])
    write_schedule(tmp_path / "s.csv", p, {"a": frozenset({'Lee, "Jo"'})})
    assert load_schedule(tmp_path / "s.csv", p) == {"a": frozenset({'Lee, "Jo"'})}
