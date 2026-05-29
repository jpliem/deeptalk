from deeptalk.cost.tracker import CostTracker


def test_allows_until_cap_then_denies():
    t = CostTracker(max_calls=2)
    assert t.allow("s1") is True
    assert t.allow("s1") is True
    assert t.allow("s1") is False
    assert t.spent("s1") == 2


def test_unlimited_when_negative():
    t = CostTracker(max_calls=-1)
    for _ in range(100):
        assert t.allow("s1") is True


def test_sessions_are_independent():
    t = CostTracker(max_calls=1)
    assert t.allow("s1") is True
    assert t.allow("s2") is True
    assert t.allow("s1") is False
    assert t.allow("s2") is False
