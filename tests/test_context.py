from core.context import PipelineContext


class TestPipelineContext:
    def test_default_values(self):
        ctx = PipelineContext()
        assert ctx.run_id is not None
        assert ctx.created_at is not None
        assert ctx.raw_transcript is None
        assert ctx.stages_completed == []
        assert ctx.errors == []

    def test_mark_stage(self):
        ctx = PipelineContext()
        ctx.mark_stage("transcription")
        assert "transcription" in ctx.stages_completed

    def test_add_error(self):
        ctx = PipelineContext()
        ctx.add_error("analysis", "something went wrong")
        assert len(ctx.errors) == 1
        assert "[analysis] something went wrong" in ctx.errors[0]

    def test_cost_fields(self):
        ctx = PipelineContext()
        assert ctx.provider_name is None
        assert ctx.input_tokens == 0
        assert ctx.cost_usd == 0.0
