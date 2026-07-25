import asyncio
import unittest
from dataclasses import dataclass

from schemas import ReviewResult, VerificationResult
from workflow import DevelopmentWorkflow, ReviewLimitExceeded


@dataclass
class FakeEngineer:
    """记录工程师收到的任务，模拟实现和返工。"""

    calls: list[str]

    async def implement(self, task: str) -> None:
        self.calls.append(task)


@dataclass
class FakeReviewer:
    """按顺序返回预设审查结果。"""

    results: list[ReviewResult]
    calls: int = 0

    async def review(self, requirements: str) -> ReviewResult:
        result = self.results[self.calls]
        self.calls += 1
        return result


@dataclass
class FakeVerifier:
    """记录自动验证是否执行。"""

    calls: int = 0

    async def verify(self) -> VerificationResult:
        self.calls += 1
        return VerificationResult(passed=True, summary="检查通过", details=[])


@dataclass
class SequentialVerifier:
    """按顺序返回预设自动检查结果。"""

    results: list[VerificationResult]
    calls: int = 0

    async def verify(self) -> VerificationResult:
        result = self.results[self.calls]
        self.calls += 1
        return result


class DevelopmentWorkflowTest(unittest.TestCase):
    """验证审查返工状态机。"""

    def test_returns_to_engineer_until_review_passes(self) -> None:
        engineer = FakeEngineer(calls=[])
        reviewer = FakeReviewer(
            results=[
                ReviewResult(approved=False, summary="需要修改", issues=["缺少错误处理"]),
                ReviewResult(approved=True, summary="通过", issues=[]),
            ]
        )
        verifier = FakeVerifier()
        workflow = DevelopmentWorkflow(engineer, reviewer, verifier, max_review_attempts=3)

        result = asyncio.run(workflow.develop("开发价格应用"))

        self.assertTrue(result.verification.passed)
        self.assertEqual(reviewer.calls, 2)
        self.assertEqual(verifier.calls, 1)
        self.assertEqual(len(engineer.calls), 2)
        self.assertIn("缺少错误处理", engineer.calls[1])

    def test_does_not_verify_when_review_limit_is_exceeded(self) -> None:
        engineer = FakeEngineer(calls=[])
        reviewer = FakeReviewer(
            results=[ReviewResult(approved=False, summary="拒绝", issues=["仍有问题"])] * 2
        )
        verifier = FakeVerifier()
        workflow = DevelopmentWorkflow(engineer, reviewer, verifier, max_review_attempts=2)

        with self.assertRaises(ReviewLimitExceeded):
            asyncio.run(workflow.develop("开发价格应用"))

        self.assertEqual(verifier.calls, 0)

    def test_returns_to_engineer_when_automated_checks_fail(self) -> None:
        engineer = FakeEngineer(calls=[])
        reviewer = FakeReviewer(
            results=[
                ReviewResult(approved=True, summary="审查通过", issues=[]),
                ReviewResult(approved=True, summary="复审通过", issues=[]),
            ]
        )
        verifier = SequentialVerifier(
            results=[
                VerificationResult(passed=False, summary="语法检查失败", details=["app.py:1"]),
                VerificationResult(passed=True, summary="检查通过", details=[]),
            ]
        )
        workflow = DevelopmentWorkflow(engineer, reviewer, verifier, max_review_attempts=3)

        result = asyncio.run(workflow.develop("开发价格应用"))

        self.assertTrue(result.verification.passed)
        self.assertEqual(len(engineer.calls), 2)
        self.assertIn("语法检查失败", engineer.calls[1])


if __name__ == "__main__":
    unittest.main()
