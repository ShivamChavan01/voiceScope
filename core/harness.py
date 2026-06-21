import json
from pathlib import Path
from core.assertions import AssertionEngine
from utils.logger import logger


class TestHarness:
    def __init__(self, test_cases_path: str = "tests/test_cases.json"):
        self.test_cases_path = test_cases_path
        self.engine = AssertionEngine()

    def load_cases(self) -> dict:
        path = Path(self.test_cases_path)
        if not path.exists():
            return {"test_suite": "unknown", "test_cases": []}
        data: dict = json.loads(path.read_text())
        return data

    async def run_single(self, case: dict) -> dict:
        test_id = case.get("test_id", "unknown")
        audio_file = case.get("audio_file", "")
        expected = case.get("expected", {})

        try:
            audio_path = Path(audio_file)
            if not audio_path.exists():
                return {
                    "test_id": test_id,
                    "passed": False,
                    "run_id": None,
                    "assertions": [
                        {
                            "field": "file_exists",
                            "expected": audio_file,
                            "actual": None,
                            "passed": False,
                            "message": f"Audio file not found: {audio_file}",
                        }
                    ],
                }

            audio_bytes = audio_path.read_bytes()
            from api.routes import get_pipeline

            result = await get_pipeline().run(audio_bytes, audio_path.name)

            assertions = self.engine.evaluate(expected, result)
            all_passed = all(a.passed for a in assertions) if assertions else False

            return {
                "test_id": test_id,
                "passed": all_passed,
                "run_id": result.get("run_id"),
                "assertions": [a.to_dict() for a in assertions],
            }

        except Exception as e:
            logger.error(f"[Harness] test {test_id} failed — {e}")
            return {
                "test_id": test_id,
                "passed": False,
                "run_id": None,
                "assertions": [
                    {
                        "field": "pipeline",
                        "expected": "success",
                        "actual": "exception",
                        "passed": False,
                        "message": f"Pipeline error: {e}",
                    }
                ],
            }

    async def run_all(self) -> dict:
        data = self.load_cases()
        test_suite = data.get("test_suite", "unknown")
        cases = data.get("test_cases", [])

        results = []
        for case in cases:
            result = await self.run_single(case)
            results.append(result)

        total = len(results)
        passed = sum(1 for r in results if r["passed"])
        failed = total - passed
        pass_rate = f"{(passed / total * 100):.1f}%" if total else "0.0%"

        return {
            "test_suite": test_suite,
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate,
            "results": results,
        }
