from enum import StrEnum


class SourceType(StrEnum):
    RSS = "rss"
    API = "api"
    WEBHOOK = "webhook"


class StoryStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    SCORED = "scored"
    APPROVED = "approved"
    POSTED = "posted"
    REJECTED = "rejected"


class TweetStatus(StrEnum):
    PENDING_POST = "pending_post"
    POSTED = "posted"
    FAILED = "failed"
    DRY_RUN_POSTED = "dry_run_posted"


class RejectionStage(StrEnum):
    DEDUP = "dedup"
    VERIFICATION = "verification"
    IMPORTANCE = "importance"
    COUNCIL = "council"
    STALENESS = "staleness"
    FREQUENCY_GATE = "frequency_gate"
    TWEET_GENERATION = "tweet_generation"
    POSTING = "posting"


class RejectionReason(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    LOW_IMPORTANCE = "low_importance"
    COUNCIL_REJECTED = "council_rejected"
    STORY_TOO_OLD = "story_too_old"
    DUPLICATE = "duplicate"
    DAILY_CAP_REACHED = "daily_cap_reached"
    MIN_INTERVAL_NOT_MET = "min_interval_not_met"
    LLM_REFUSED = "llm_refused"
    X_API_ERROR = "x_api_error"
    OTHER = "other"


class PipelineRunType(StrEnum):
    POLL = "poll"
    PROCESS = "process"
    POST = "post"


class PipelineRunStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
