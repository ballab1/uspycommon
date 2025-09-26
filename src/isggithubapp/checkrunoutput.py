from typing import Any, Dict


class CheckRunOutput:
    def __init__(self, data: Dict[str, Any]):
        self.summary = None
        self.text = None
        self.title = None
        self._useAttributes(data)

    def _useAttributes(self, attributes: Dict[str, Any]) -> None:
        if "summary" in attributes:
            self.summary = attributes["summary"]
        if "text" in attributes:
            self.text = attributes["text"]
        if "title" in attributes:
            self.title = attributes["title"]
