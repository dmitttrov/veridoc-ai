from decimal import Decimal

from veridoc_ft.realeval.normalize import (
    canonical_period,
    parse_number,
    periods_match,
    to_base,
    values_match,
)


def test_parse_number_variants() -> None:
    assert parse_number("383,285") == Decimal(383285)
    assert parse_number("$1.2 billion") == Decimal(1_200_000_000)
    assert parse_number("(1,234)") == Decimal(-1234)
    assert parse_number("$(1,234)") == Decimal(-1234)  # currency before parenthesis
    assert parse_number("-500") == Decimal(-500)
    assert parse_number("27%") == Decimal(27)
    assert parse_number("n/a") is None


def test_accounting_negative_with_currency_and_unit() -> None:
    # "$(42,012) million" must equal the raw negative XBRL integer.
    assert values_match("$(42,012)", "USD millions", "-42012000000", None)


def test_to_base_scales_from_value_and_unit() -> None:
    assert to_base("383,285", "USD millions") == Decimal(383_285_000_000)
    assert to_base("383.285", "billion") == Decimal(383_285_000_000)
    assert to_base("383285000000", None) == Decimal(383_285_000_000)


def test_values_match_across_scales() -> None:
    # millions vs raw integer
    assert values_match("383,285", "USD millions", "383285000000", None)
    # billions-with-decimals vs millions
    assert values_match("383.285", "billion", "383,285", "million")
    # accounting negative vs signed
    assert values_match("(500)", "USD millions", "-500", "USD millions")


def test_values_match_rounding_tolerance() -> None:
    # 383.3 billion rounds within 0.5% of the exact filing figure
    assert values_match("383.3", "billion", "383285000000", None)
    # but a clearly different number does not match
    assert not values_match("400", "billion", "383285000000", None)


def test_percent_vs_money_never_matches() -> None:
    assert values_match("27", "percent", "27%", None)
    assert not values_match("27", "percent", "27", "USD millions")


def test_canonical_period() -> None:
    assert canonical_period("FY2023") == (2023, None)
    assert canonical_period("fiscal 2023") == (2023, None)
    assert canonical_period("Q2 2024") == (2024, 2)
    assert canonical_period("year ended September 30, 2023") == (2023, None)
    assert canonical_period("no year here") is None


def test_periods_match() -> None:
    assert periods_match("FY2023", "fiscal 2023")
    assert not periods_match("Q1 2024", "Q2 2024")
    assert not periods_match("FY2023", "FY2024")
