from .message import Message


class Memory:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.history: list[Message] = []

    def add_message(self, message: Message | None):
        if message is None:
            return
        if not isinstance(message, Message):
            raise TypeError("Memory only accepts smart_bot Message instances")
        self.history.append(message)

    def get_history(self) -> list[Message]:
        return self._fileter_history(self.history)
    
    def _fileter_history(self, messages: list[Message]) -> list[Message]:
        filtered_history = messages
        return filtered_history
    def clear_history(self):
        self.history = []
    def __repr__(self):
        return f"session_id: {self.session_id}, history: {self.history}"
    
    