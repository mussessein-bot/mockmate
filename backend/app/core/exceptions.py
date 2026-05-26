class SessionNotFoundError(Exception):
    pass

class InvalidStateTransitionError(Exception):
    pass

class ProbeQuotaExceededError(Exception):
    pass

class LLMError(Exception):
    pass

class TTSError(Exception):
    pass
