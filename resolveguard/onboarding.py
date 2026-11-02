"""Customer-facing entry copy. Greetings require no model, retrieval or account access."""
import re

WELCOME_MESSAGE="Hello! I'm your ResolveGuard assistant. How can I help you today?"
ONBOARDING_SYSTEM_RULE=(
    'Use a short, welcoming tone for onboarding. Never present execution logs, '
    'internal states or telemetry as customer guidance. Public questions do not '
    'require sign-in; ask for secure authentication only for protected requests. '
    'Do not add a technical details preamble to a greeting. '
    'The application supplies the welcome message; do not invent account context.'
)


def is_greeting(message):
    return bool(re.fullmatch(r'\s*(?:hi|hello|hey|good morning|good afternoon|good evening)[!.\s]*',message,re.I))
