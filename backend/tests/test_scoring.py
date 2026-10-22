import pytest
from backend.app.services.scoring import ScoringEngine


def test_scoring_calculation():
    # 5 questions:
    # Q1: Correct (+1.0)
    # Q2: Incorrect (-0.25)
    # Q3: Blank (0.0)
    # Q4: Multiple (-0.25)
    # Q5: Review (0.0, review_count=1)
    responses = {
        1: "A",
        2: "C",
        3: "BLANK",
        4: "MULTIPLE",
        5: "REVIEW"
    }
    answer_key = {
        "1": "A",
        "2": "B",
        "3": "C",
        "4": "D",
        "5": "A"
    }

    res = ScoringEngine.calculate_score(
        responses=responses,
        answer_key=answer_key,
        positive_marks=1.0,
        negative_marks=0.25,
        blank_marks=0.0,
        multiple_penalty=0.25,
        total_questions=5
    )

    assert res["correct_count"] == 1
    assert res["incorrect_count"] == 1
    assert res["blank_count"] == 1
    assert res["multiple_count"] == 1
    assert res["review_count"] == 1
    assert res["can_finalize"] is False

    # Score = 1.0 (Q1) - 0.25 (Q2) + 0.0 (Q3) - 0.25 (Q4) = 0.50
    assert res["total_score"] == 0.50
    assert res["max_score"] == 5.0
    assert res["percentage"] == 10.0


def test_perfect_score():
    responses = {i: "A" for i in range(1, 11)}
    answer_key = {str(i): "A" for i in range(1, 11)}

    res = ScoringEngine.calculate_score(
        responses=responses,
        answer_key=answer_key,
        positive_marks=2.0,
        negative_marks=0.5,
        blank_marks=0.0,
        multiple_penalty=0.5,
        total_questions=10
    )

    assert res["correct_count"] == 10
    assert res["incorrect_count"] == 0
    assert res["total_score"] == 20.0
    assert res["max_score"] == 20.0
    assert res["percentage"] == 100.0
    assert res["can_finalize"] is True
