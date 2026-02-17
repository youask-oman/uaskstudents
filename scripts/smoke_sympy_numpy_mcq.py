import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import sympy as sp


@dataclass
class MCQCase:
    name: str
    choices: Dict[str, sp.Expr]
    result: sp.Expr


def match_choices(result: sp.Expr, choices: Dict[str, sp.Expr]) -> Tuple[List[str], str]:
    matched: List[str] = []
    h = sp.Heaviside(sp.Symbol("t", real=True))
    normalized = sp.simplify(result / h) if result.has(sp.Heaviside) else result
    for key, val in choices.items():
        if sp.simplify(result - val) == 0 or sp.simplify(normalized - val) == 0:
            matched.append(key)
    nval = sp.N(result)
    if getattr(result, "free_symbols", set()):
        rendered = str(nval)
    elif getattr(nval, "is_real", False):
        rendered = f"{float(nval):.10g}"
    else:
        rendered = str(nval)
    return matched, rendered


def main() -> None:
    t = sp.symbols("t", real=True)
    a = sp.symbols("a", positive=True, real=True)
    z = sp.symbols("z")
    x = sp.symbols("x", positive=True, real=True)
    theta = sp.symbols("theta", real=True)

    # 1) contour integral
    f1 = sp.exp(z) / (z**2 * (z - 1))
    res1 = sp.simplify(2 * sp.pi * sp.I * (sp.residue(f1, z, 0) + sp.residue(f1, z, 1)))

    # 2) determinant
    A = sp.Matrix([[2, 1, 1], [1, 2, 1], [1, 1, 2]])
    res2 = sp.simplify(A.det())

    # 3) improper integral
    # Use Gamma-Zeta identity: ∫_0^∞ x^(s-1)/(e^x-1) dx = Γ(s)ζ(s), s=4
    res3 = sp.simplify(sp.gamma(4) * sp.zeta(4))

    # 4) P(X^2+Y^2<=2), chi-square(2)
    res4 = sp.simplify(1 - sp.exp(-1))

    # 5) order 2 elements in Z8 x Z2
    def ord_mod(n: int, m: int) -> int:
        if n % m == 0:
            return 1
        k = 1
        v = n % m
        while v != 0:
            k += 1
            v = (v + n) % m
        return k

    count = 0
    for u in range(8):
        for v in range(2):
            o = math.lcm(ord_mod(u, 8), ord_mod(v, 2))
            if o == 2:
                count += 1
    res5 = sp.Integer(count)

    # 6) double integral on unit disk
    r = sp.symbols("r", nonnegative=True, real=True)
    res6 = sp.simplify(sp.integrate(sp.integrate(r**2 * r, (r, 0, 1)), (theta, 0, 2 * sp.pi)))

    # 7) image of imaginary axis under w=(z-1)/(z+1)
    y = sp.symbols("y", real=True)
    w = sp.simplify((sp.I * y - 1) / (sp.I * y + 1))
    res7 = sp.simplify(sp.Abs(w) ** 2)  # equals 1 for all real y

    # 8) maximize xyz with x^2+y^2+z^2=1, x,y,z>0
    res8 = sp.simplify(1 / (3 * sp.sqrt(3)))

    # 9) inverse Laplace
    s = sp.symbols("s", positive=True, real=True)
    res9 = sp.simplify(sp.inverse_laplace_transform(1 / (s**2 + 1) ** 2, s, t))

    # 10) projection on span(1,1,1)
    v10 = sp.Matrix([1, 0, -1])
    u10 = sp.Matrix([1, 1, 1])
    res10_vec = sp.simplify((v10.dot(u10) / u10.dot(u10)) * u10)
    res10 = sp.Matrix(res10_vec)

    # 11) integral 0..2pi 1/(5-4cosθ)
    res11 = sp.simplify(sp.integrate(1 / (5 - 4 * sp.cos(theta)), (theta, 0, 2 * sp.pi)))

    # 12) stationary distribution
    P = np.array([[0.7, 0.3], [0.4, 0.6]], dtype=float)
    wvals, wvecs = np.linalg.eig(P.T)
    idx = int(np.argmin(np.abs(wvals - 1.0)))
    vec = np.real(wvecs[:, idx])
    vec = vec / np.sum(vec)
    res12 = (sp.nsimplify(vec[0]), sp.nsimplify(vec[1]))

    # 13) operator norm
    res13 = sp.Integer(1)

    # 14) cosine transform
    res14 = sp.simplify(sp.integrate(sp.cos(a * x) / (x**2 + 1), (x, 0, sp.oo)))

    # 15) tr(e^{tA})
    ev = A.eigenvals()
    res15 = sp.simplify(sum(mult * sp.exp(val * t) for val, mult in ev.items()))

    cases: List[MCQCase] = [
        MCQCase("1 contour integral", {
            "A": 2 * sp.pi * sp.I * (sp.E - 2),
            "B": 2 * sp.pi * sp.I * (sp.E + 2),
            "C": 2 * sp.pi * sp.I * (2 - sp.E),
            "D": 2 * sp.pi * (sp.E - 2),
            "E": sp.Integer(0),
        }, res1),
        MCQCase("2 det(A)", {"A": 0, "B": 1, "C": 2, "D": 4, "E": 8}, res2),
        MCQCase("3 improper integral", {
            "A": sp.pi**4 / 90, "B": sp.pi**4 / 30, "C": sp.pi**4 / 15, "D": 2 * sp.pi**4 / 15, "E": 6 * sp.pi**4 / 15
        }, res3),
        MCQCase("4 normal probability", {
            "A": sp.exp(-1), "B": 1 - sp.exp(-1), "C": 1 - sp.exp(-2), "D": sp.Rational(1, 2), "E": 1 - 1 / sp.E**2
        }, res4),
        MCQCase("5 order in Z8xZ2", {"A": 1, "B": 2, "C": 3, "D": 4, "E": 7}, res5),
        MCQCase("6 disk integral", {"A": sp.pi, "B": sp.pi / 2, "C": sp.pi / 3, "D": sp.Rational(1, 2), "E": 2 * sp.pi}, res6),
        MCQCase("7 mobius image", {"A": 0, "B": 1, "C": 2, "D": sp.Rational(1, 2), "E": -1}, res7),
        MCQCase("8 constrained maximum", {
            "A": sp.Rational(1, 3),
            "B": 1 / (3 * sp.sqrt(3)),
            "C": sp.sqrt(3) / 9,
            "D": 1 / sp.sqrt(3),
            "E": sp.Rational(1, 9),
        }, res8),
        MCQCase("9 inverse laplace", {
            "A": sp.Rational(1, 2) * (sp.sin(t) - t * sp.cos(t)),
            "B": sp.Rational(1, 2) * (sp.sin(t) + t * sp.cos(t)),
            "C": sp.Rational(1, 2) * (sp.cos(t) - t * sp.sin(t)),
            "D": sp.sin(t),
            "E": t * sp.sin(t),
        }, res9),
        MCQCase("10 projection", {
            "A": sp.Matrix([1, 0, -1]),
            "B": sp.Matrix([sp.Rational(1, 3)] * 3),
            "C": sp.Matrix([0, 0, 0]),
            "D": sp.Matrix([sp.Rational(2, 3)] * 3),
            "E": sp.Matrix([-sp.Rational(1, 3)] * 3),
        }, res10),
        MCQCase("11 trig integral", {"A": 2 * sp.pi / 5, "B": sp.pi / 2, "C": 2 * sp.pi / 3, "D": sp.pi / 3, "E": 2 * sp.pi}, res11),
        MCQCase("12 stationary distribution", {
            "A": (sp.Rational(3, 7), sp.Rational(4, 7)),
            "B": (sp.Rational(4, 7), sp.Rational(3, 7)),
            "C": (sp.Rational(1, 2), sp.Rational(1, 2)),
            "D": (sp.Rational(2, 3), sp.Rational(1, 3)),
            "E": (sp.Rational(7, 10), sp.Rational(3, 10)),
        }, sp.Tuple(*res12)),
        MCQCase("13 operator norm", {"A": 0, "B": sp.Rational(1, 2), "C": 1, "D": 2, "E": sp.oo}, res13),
        MCQCase("14 cosine/(x^2+1)", {"A": sp.pi * sp.exp(-a) / 2, "B": sp.pi * sp.exp(a) / 2, "C": sp.pi * sp.exp(-a), "D": sp.pi / (2 * a), "E": 1 / (1 + a**2)}, res14),
        MCQCase("15 tr(exp(tA))", {"A": 3 * sp.exp(2 * t), "B": sp.exp(4 * t) + 2 * sp.exp(t), "C": 2 * sp.exp(4 * t) + sp.exp(t), "D": sp.exp(3 * t), "E": sp.exp(t) + 2 * sp.exp(2 * t)}, res15),
    ]

    print("SymPy/NumPy MCQ smoke test")
    print("-" * 80)
    for case in cases:
        if isinstance(case.result, sp.Matrix):
            matches = [k for k, v in case.choices.items() if isinstance(v, sp.Matrix) and (case.result - v) == sp.zeros(*case.result.shape)]
            print(f"{case.name}: result={case.result.tolist()} matches={matches}")
        elif isinstance(case.result, sp.Tuple):
            matches = [k for k, v in case.choices.items() if isinstance(v, tuple) and case.result == sp.Tuple(*v)]
            print(f"{case.name}: result={tuple(case.result)} matches={matches}")
        else:
            matched, numeric = match_choices(sp.simplify(case.result), {k: sp.sympify(v) for k, v in case.choices.items()})
            print(f"{case.name}: result={sp.simplify(case.result)} numeric~{numeric} matches={matched}")


if __name__ == "__main__":
    main()
