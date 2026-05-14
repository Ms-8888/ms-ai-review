from dataclasses import dataclass

TOOL = {
    "name": "report_finding",
    "description": "Report a code review finding with severity, line number, message, and optional fix.",
    "input_schema": {
        "type": "object",
        "properties": {
            "severity": {
                "type": "string",
                "enum": ["CRITICAL", "WARNING", "INFO"],
                "description": "Severity level of the finding",
            },
            "line": {
                "type": "integer",
                "description": "Line number where the issue occurs",
            },
            "message": {
                "type": "string",
                "description": "Clear description of the issue",
            },
            "fix": {
                "type": "string",
                "description": "Suggested fix for the issue",
            },
        },
        "required": ["severity", "line", "message"],
    },
}


@dataclass
class Finding:
    severity: str
    line: int
    message: str
    fix: str | None = None
