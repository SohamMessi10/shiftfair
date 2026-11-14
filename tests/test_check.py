from shiftfair.check import Rule, Score, check, minutes_worked, score
from tests.helpers import person, problem, shift


def club():
    return problem(
        [shift("am", "09:00", "12:00", needed=2), shift("mid", "11:00", "14:00"), shift("pm", "14:00", "17:00")],
        [person("Ana", 6, am="prefer", mid="yes", pm="yes"), person("Ben", 3, am="yes", pm="avoid"),
         person("Cy", 6, am="yes", mid="yes", pm="prefer")])


def assign(**shifts):
    return {k: frozenset(v) for k, v in shifts.items()}


def test_a_valid_schedule_has_no_violations_and_its_score():
    p = club()
    a = assign(am={"Ana", "Ben"}, mid={"Cy"}, pm={"Ana"})
    assert check(p, a) == []
    assert minutes_worked(p, a) == {"Ana": 360, "Ben": 180, "Cy": 180}
    assert score(p, a) == Score(360**2 + 180**2 + 180**2, prefer=1, avoid=0)


def rules(p, a):
    return [(v.rule, v.message) for v in check(p, a)]


def test_each_rule_is_reported():
    p = club()
    assert rules(p, assign(am={"Ana", "Ben"}, mid={"Ben"}, pm={"Cy"})) == [
        (Rule.AVAILABILITY, "Ben isn't available for mid (Sat 2026-12-05 11:00–14:00)"),
        (Rule.MAX_HOURS, "Ben works 6 h, over their limit of 3 h"),
        (Rule.OVERLAP, "Ben is on am (Sat 2026-12-05 09:00–12:00) and mid (Sat 2026-12-05 11:00–14:00), "
                       "which overlap")]
    assert rules(p, assign(am={"Ana"}, mid={"Cy"}, pm={"Ana", "Cy"})) == [
        (Rule.STAFFING, "am (Sat 2026-12-05 09:00–12:00) has 1 of the 2 people it needs"),
        (Rule.STAFFING, "pm (Sat 2026-12-05 14:00–17:00) has 2 people but needs 1")]


def test_a_missing_shift_counts_as_unstaffed_and_unknowns_are_reported():
    p = club()
    assert rules(p, assign(am={"Ana", "Ben"}, mid={"Cy"})) == [
        (Rule.STAFFING, "pm (Sat 2026-12-05 14:00–17:00) has 0 of the 1 people it needs")]
    assert rules(p, assign(am={"Ana", "Zed"}, mid={"Cy"}, pm={"Ana"}, night={"Ana"})) == [
        (Rule.UNKNOWN, "'Zed' on am isn't anyone in the problem"),
        (Rule.UNKNOWN, "'night' isn't a shift in the problem")]


def test_working_exactly_the_limit_is_allowed_and_back_to_back_is_not_an_overlap():
    p = problem([shift("a", "09:00", "12:00"), shift("b", "12:00", "15:00")], [person("Ana", 6, a="yes", b="yes")])
    assert check(p, assign(a={"Ana"}, b={"Ana"})) == []
    assert score(p, assign(a={"Ana"}, b={"Ana"})) == Score(360**2, 0, 0)
