"""AI subsystem for document parsing, embeddings, and job fit evaluation."""

from app.ai.client import BaseAIClient, MockAIClient, OllamaAIClient, OpenAICompatibleClient, get_ai_client
from app.ai.cv_parser import CVParser
from app.ai.embeddings import ProfileEmbedder
from app.ai.evaluator import JobEvaluator, JobFitEvaluation
from app.ai.feedback import FeedbackManager
from app.ai.profile_extractor import ExtractedProfile, extract_profile_from_text, save_profile_to_db

__all__ = [
    "CVParser",
    "ExtractedProfile",
    "extract_profile_from_text",
    "save_profile_to_db",
    "BaseAIClient",
    "OllamaAIClient",
    "OpenAICompatibleClient",
    "MockAIClient",
    "get_ai_client",
    "ProfileEmbedder",
    "JobEvaluator",
    "JobFitEvaluation",
    "FeedbackManager",
]
