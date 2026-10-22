from typing import Dict, List, Tuple, Optional, Any
from sqlalchemy.orm import Session
from backend.app.models.examination import Examination
from backend.app.models.submission import Submission, DetectedResponse, FinalScore, SubmissionStatus
from backend.app.models.audit import AuditLog


class ScoringEngine:
    @staticmethod
    def calculate_score(
        responses: Dict[int, str],
        answer_key: Dict[str, str],
        positive_marks: float = 1.0,
        negative_marks: float = 0.25,
        blank_marks: float = 0.0,
        multiple_penalty: float = 0.25,
        total_questions: int = 100,
    ) -> Dict[str, Any]:
        """Calculates exact test scores and question breakdown."""
        correct_count = 0
        incorrect_count = 0
        blank_count = 0
        multiple_count = 0
        review_count = 0
        total_score = 0.0

        for q_num in range(1, total_questions + 1):
            user_ans = responses.get(q_num, "BLANK")
            correct_ans = answer_key.get(str(q_num))

            if user_ans == "REVIEW":
                review_count += 1
            elif user_ans == "BLANK":
                blank_count += 1
                total_score += blank_marks
            elif user_ans == "MULTIPLE":
                multiple_count += 1
                total_score -= multiple_penalty
            elif correct_ans is not None:
                if user_ans == correct_ans:
                    correct_count += 1
                    total_score += positive_marks
                else:
                    incorrect_count += 1
                    total_score -= negative_marks
            else:
                # If question not in answer key, treat as unpenalized blank or review
                blank_count += 1

        max_possible_score = float(total_questions * positive_marks)
        percentage = 0.0
        if max_possible_score > 0:
            percentage = round(max(0.0, (total_score / max_possible_score) * 100.0), 2)

        return {
            "total_score": round(total_score, 2),
            "max_score": round(max_possible_score, 2),
            "percentage": percentage,
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "blank_count": blank_count,
            "multiple_count": multiple_count,
            "review_count": review_count,
            "can_finalize": review_count == 0,
        }

    @staticmethod
    def update_submission_score(
        submission: Submission,
        examination: Examination,
        answer_key: Dict[str, str],
        db: Session,
    ) -> Submission:
        """Evaluates all responses for a submission and updates its score fields in the DB."""
        resp_map = {r.question_number: r.final_option for r in submission.responses}
        
        score_res = ScoringEngine.calculate_score(
            responses=resp_map,
            answer_key=answer_key,
            positive_marks=examination.positive_marks,
            negative_marks=examination.negative_marks,
            blank_marks=examination.blank_marks,
            multiple_penalty=examination.multiple_penalty,
            total_questions=examination.question_count,
        )

        submission.total_score = score_res["total_score"]
        submission.max_score = score_res["max_score"]
        submission.percentage = score_res["percentage"]
        submission.correct_count = score_res["correct_count"]
        submission.incorrect_count = score_res["incorrect_count"]
        submission.blank_count = score_res["blank_count"]
        submission.multiple_count = score_res["multiple_count"]
        submission.review_count = score_res["review_count"]

        if score_res["review_count"] > 0:
            submission.status = SubmissionStatus.NEEDS_REVIEW
        else:
            submission.status = SubmissionStatus.PROVISIONAL

        db.commit()
        db.refresh(submission)
        return submission

    @staticmethod
    def rescore_examination(
        examination: Examination,
        new_answer_key: Dict[str, str],
        user_id: int,
        reason: str,
        db: Session,
    ) -> int:
        """Rescores all submissions for an examination following an answer key update."""
        submissions = db.query(Submission).filter(Submission.examination_id == examination.id).all()
        rescored_count = 0

        for sub in submissions:
            old_score = sub.total_score
            ScoringEngine.update_submission_score(
                submission=sub,
                examination=examination,
                answer_key=new_answer_key,
                db=db
            )
            rescored_count += 1

        # Record audit log for rescoring
        audit = AuditLog(
            user_id=user_id,
            action="RESCORE_EXAMINATION",
            resource_type="EXAMINATION",
            resource_id=str(examination.id),
            details={
                "submissions_rescored": rescored_count,
                "reason": reason,
                "new_key_version": len(examination.answer_keys) + 1,
            }
        )
        db.add(audit)
        db.commit()
        return rescored_count
