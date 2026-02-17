from app.services.solve.local_final_solver import try_solve_final_with_sympy_numpy


def test_critical_points_generic_prompt():
    text = (
        "Question 6 (Final answer only)\n"
        "Find the critical points of f(x)=x^3 - 6x^2 + 9x.\n"
        "Final answer: x = ____"
    )
    solved = try_solve_final_with_sympy_numpy(text)
    assert solved is not None
    assert solved.classification_topic == "critical_points"
    assert "(1, 3)" in solved.answer_text


def test_laplace_generic_prompt():
    text = (
        "Question 10 (Final answer only)\n"
        "Compute the Laplace transform:\n"
        "L{ t e^{3t} }(s)\n"
        "Final answer: ____"
    )
    solved = try_solve_final_with_sympy_numpy(text)
    assert solved is not None
    assert solved.classification_topic == "laplace_transform"
    assert "(s - 3)**(-2)" in solved.answer_text
