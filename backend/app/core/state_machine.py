from app.core.models import InterviewSession, InterviewState, InterviewMode
from app.core.exceptions import InvalidStateTransitionError

MAX_PROBES = 2

# question_count thresholds for preset mode state transitions
OPENING_END   = 1   # after 1 question → BEHAVIORAL
BEHAVIORAL_END = 6  # after 6 questions → TECHNICAL
TECHNICAL_END  = 8  # after 8 questions → CLOSING


def can_probe(session: InterviewSession) -> bool:
    """True if a probe can be triggered after the current answer."""
    if session.probe_count >= MAX_PROBES:
        return False
    # Cannot probe an answer that was itself a probe question
    if session.last_was_probe:
        return False
    return True


def transition_after_answer(session: InterviewSession, next_action: str) -> InterviewState:
    """
    Determine the next InterviewState after the candidate answers.
    next_action is Strategy Agent output: "probe" | "continue" | "close"
    """
    state = session.state
    mode  = session.interview_mode

    if state == InterviewState.INIT:
        return InterviewState.OPENING

    if state == InterviewState.OPENING:
        if next_action == "probe" and can_probe(session):
            return InterviewState.DEEP_DIVE
        return _advance_from_opening(session, mode)

    if state == InterviewState.BEHAVIORAL:
        if next_action == "probe" and can_probe(session):
            return InterviewState.DEEP_DIVE
        return _advance_from_behavioral(session, mode)

    if state == InterviewState.DEEP_DIVE:
        # Always return to wherever we came from; probe cannot trigger another probe
        return _return_from_probe(session, mode)

    if state == InterviewState.TECHNICAL:
        if next_action == "probe" and can_probe(session):
            return InterviewState.DEEP_DIVE
        return _advance_from_technical(session, mode)

    if state == InterviewState.CLOSING:
        return InterviewState.COMPLETED

    return state


def _advance_from_opening(session: InterviewSession, mode: InterviewMode) -> InterviewState:
    if mode == InterviewMode.PRESET:
        return InterviewState.BEHAVIORAL if session.question_count >= OPENING_END else InterviewState.OPENING
    return InterviewState.BEHAVIORAL


def _advance_from_behavioral(session: InterviewSession, mode: InterviewMode) -> InterviewState:
    if mode == InterviewMode.PRESET:
        return InterviewState.TECHNICAL if session.question_count >= BEHAVIORAL_END else InterviewState.BEHAVIORAL
    return InterviewState.BEHAVIORAL


def _advance_from_technical(session: InterviewSession, mode: InterviewMode) -> InterviewState:
    if mode == InterviewMode.PRESET:
        return InterviewState.CLOSING if session.question_count >= TECHNICAL_END else InterviewState.TECHNICAL
    return InterviewState.TECHNICAL


def _return_from_probe(session: InterviewSession, mode: InterviewMode) -> InterviewState:
    """After a probe, figure out which state to return to."""
    if session.question_count < OPENING_END:
        return InterviewState.OPENING
    if mode == InterviewMode.PRESET:
        if session.question_count < BEHAVIORAL_END:
            return InterviewState.BEHAVIORAL
        if session.question_count < TECHNICAL_END:
            return InterviewState.TECHNICAL
        return InterviewState.CLOSING
    # Dynamic: stay in whatever substantive state we were in
    return InterviewState.BEHAVIORAL


def apply_probe(session: InterviewSession) -> None:
    """Increment probe counter and mark last question as probe."""
    session.probe_count += 1
    session.last_was_probe = True


def apply_question(session: InterviewSession) -> None:
    """Increment main question counter and clear probe flag."""
    session.question_count += 1
    session.last_was_probe = False
