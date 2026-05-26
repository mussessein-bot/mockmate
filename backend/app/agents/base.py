from app.core.models import InterviewSession


class BaseAgent:
    def __init__(self, session: InterviewSession):
        self.session = session
        self.language = session.profile.language.value

    @property
    def recent_messages(self) -> list[dict]:
        return [
            {"role": m.role.value, "content": m.content}
            for m in self.session.messages[-10:]
        ]
