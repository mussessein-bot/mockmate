from typing import AsyncGenerator
from app.agents.base import BaseAgent
from app.core.models import InterviewSession, InterviewState
from app.llm.client import chat_completion, chat_completion_stream
from app.llm.prompts.interviewer_prompts import (
    build_interviewer_prompt,
    OPENING_ZH,
    OPENING_EN,
)


class InterviewerAgent(BaseAgent):
    async def generate_opening(self) -> str:
        opening_map = OPENING_ZH if self.language == "zh" else OPENING_EN
        return opening_map[self.session.persona.value]

    async def generate_closing(self) -> str:
        messages = build_interviewer_prompt(
            persona=self.session.persona.value,
            language=self.language,
            next_action="close",
            topic="",
            is_probe=False,
            probe_reason=None,
            candidate_name=self.session.profile.name,
            target_role=self.session.profile.target_role,
            interview_type=self.session.interview_type.value,
            recent_messages=self.recent_messages,
            is_closing=True,
        )
        return await chat_completion(messages, temperature=0.7)

    async def generate_response(
        self,
        next_action: str,
        topic: str,
        is_probe: bool,
        probe_reason: str | None,
        question_type: str = "behavioral",
    ) -> str:
        messages = build_interviewer_prompt(
            persona=self.session.persona.value,
            language=self.language,
            next_action=next_action,
            topic=topic,
            is_probe=is_probe,
            probe_reason=probe_reason,
            candidate_name=self.session.profile.name,
            target_role=self.session.profile.target_role,
            interview_type=self.session.interview_type.value,
            recent_messages=self.recent_messages,
            question_type=question_type,
        )
        return await chat_completion(messages, temperature=0.75)

    async def stream_response(
        self,
        next_action: str,
        topic: str,
        is_probe: bool,
        probe_reason: str | None,
        question_type: str = "behavioral",
    ) -> AsyncGenerator[str, None]:
        messages = build_interviewer_prompt(
            persona=self.session.persona.value,
            language=self.language,
            next_action=next_action,
            topic=topic,
            is_probe=is_probe,
            probe_reason=probe_reason,
            candidate_name=self.session.profile.name,
            target_role=self.session.profile.target_role,
            interview_type=self.session.interview_type.value,
            recent_messages=self.recent_messages,
            question_type=question_type,
        )
        async for chunk in chat_completion_stream(messages, temperature=0.75):
            yield chunk
