"""
Server-side backstop that cuts a reply the moment it looks like programming
code, shared by ai_chat's plain-chat persona and ai_secretary's admin agent
(both surfaces are branded "SchoolDom AI").

Small local models (1B-3B) don't reliably follow a "never write code"
system-prompt rule on their own - this is a hard check on the model's own
output, not a request to the model to police itself.
"""

CODE_SIGNALS = (
    "```",
    "<?php",
    "#!/usr/bin/env",
    "def __init__",
    "console.log(",
    "select * from",
    "insert into",
    "create table",
    "import numpy",
    "import pandas",
    "</html>",
    "<script",
)

CODE_REFUSAL_MESSAGE = (
    "\n\nI can't help with writing or explaining code — I'm here for Schooldom "
    "admin tasks like lesson plans, letters, and messages. What can I help you "
    "with on the platform?"
)


def looks_like_code(text: str) -> bool:
    lowered = text.lower()
    return any(signal in lowered for signal in CODE_SIGNALS)
