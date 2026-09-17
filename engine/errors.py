"""Errors safe to return to a player. Never include credentials or prompt contents."""


class RequestError(Exception):
    def __init__(
        self, status: int, code: str, message: str = "", *, defense: str | None = None
    ) -> None:
        self.defense = defense
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message or code)

    def public_dict(self) -> dict[str, str]:
        payload = {"error": self.code}
        if self.message:
            payload["message"] = self.message
        if self.defense:
            payload["defense"] = self.defense
        return payload
