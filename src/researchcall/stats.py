"""Descriptive statistics and a first inferential test, standard library only.

The dependency question decides the design. A statistics stack would bring
correctness for free but cost the one property this application sells: that
the command line runs with nothing installed. A Welch t-test is small enough
to implement and check by hand — so it is implemented, checked against known
values in the tests, and stops there. Anything bigger (ANOVA, regression)
should be done where researchers do it anyway: in R or SPSS, via the exports.

The p-value comes from the regularized incomplete beta function, computed with
the continued-fraction expansion from Numerical Recipes — the standard route
when SciPy is not on the table.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


# -- descriptives ----------------------------------------------------------


@dataclass(frozen=True)
class Descriptives:
    n: int
    mean: float
    sd: float
    minimum: float
    median: float
    maximum: float


def describe(values: Sequence[float]) -> Descriptives:
    if not values:
        raise ValueError("Nothing to describe: the value list is empty")
    ordered = sorted(float(v) for v in values)
    n = len(ordered)
    mean = sum(ordered) / n
    # Sample standard deviation (n-1): these are drawn people, not a population.
    sd = math.sqrt(sum((v - mean) ** 2 for v in ordered) / (n - 1)) if n > 1 else 0.0
    middle = n // 2
    median = ordered[middle] if n % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return Descriptives(
        n=n, mean=mean, sd=sd, minimum=ordered[0], median=median, maximum=ordered[-1]
    )


# -- the incomplete beta function ------------------------------------------


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Numerical Recipes)."""
    max_iterations = 200
    epsilon = 3.0e-12
    tiny = 1.0e-300

    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iterations + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < epsilon:
            return h
    raise ArithmeticError("Incomplete beta continued fraction did not converge")


def _incomplete_beta(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_survival(t_value: float, df: float) -> float:
    """P(T > t) for Student's t — one tail."""
    x = df / (df + t_value * t_value)
    tail = 0.5 * _incomplete_beta(df / 2.0, 0.5, x)
    return tail if t_value >= 0 else 1.0 - tail


# -- the Welch t-test ------------------------------------------------------


@dataclass(frozen=True)
class TTestResult:
    group_a: str
    group_b: str
    n_a: int
    n_b: int
    mean_a: float
    mean_b: float
    t: float
    df: float
    p_two_sided: float

    def to_dict(self) -> dict:
        return {
            "test": "welch_t",
            "groups": [self.group_a, self.group_b],
            "n": [self.n_a, self.n_b],
            "means": [round(self.mean_a, 6), round(self.mean_b, 6)],
            "t": round(self.t, 6),
            "df": round(self.df, 4),
            "p_two_sided": round(self.p_two_sided, 6),
            "note": (
                "Welch's t-test (unequal variances assumed). Descriptive study "
                "data: a p-value is not a license for a causal claim."
            ),
        }


def welch_t_test(
    values_a: Sequence[float],
    values_b: Sequence[float],
    label_a: str = "A",
    label_b: str = "B",
) -> TTestResult:
    """Two groups, unequal variances assumed — the default that does not flatter.

    Student's classic test assumes equal variances and rewards the assumption
    with smaller p-values; Welch does not need it and loses almost nothing
    when it happens to hold. For field data nobody has checked, Welch is the
    honest default.
    """
    if len(values_a) < 2 or len(values_b) < 2:
        raise ValueError("Each group needs at least two values for a t-test")
    a = describe(values_a)
    b = describe(values_b)
    if a.sd == 0.0 and b.sd == 0.0:
        raise ValueError("Both groups are constant; a t-test says nothing here")
    se_a = (a.sd**2) / a.n
    se_b = (b.sd**2) / b.n
    t_value = (a.mean - b.mean) / math.sqrt(se_a + se_b)
    df = (se_a + se_b) ** 2 / (
        (se_a**2) / (a.n - 1) + (se_b**2) / (b.n - 1)
    )
    p = 2.0 * t_survival(abs(t_value), df)
    return TTestResult(
        group_a=label_a,
        group_b=label_b,
        n_a=a.n,
        n_b=b.n,
        mean_a=a.mean,
        mean_b=b.mean,
        t=t_value,
        df=df,
        p_two_sided=min(1.0, p),
    )
