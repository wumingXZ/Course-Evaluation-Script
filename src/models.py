from enum import Enum
from pydantic import BaseModel, Field


class Sentiment(str, Enum):
    LIKE = "like"
    NEUTRAL = "neutral"
    DISLIKE = "dislike"


class QuestionType(str, Enum):
    FORWARD = "forward"
    REVERSE = "reverse"
    YESNO = "yesno"
    CHECKBOX = "checkbox"


class Option(BaseModel):
    index: int
    label: str
    has_text_input: bool = False


class Question(BaseModel):
    index: int
    title: str
    options: list[Option] = []
    detected_type: QuestionType = QuestionType.FORWARD
    is_reverse: bool = False
    is_yesno: bool = False
    has_textfill: bool = False
    was_reversed: bool = False  # True if JS normalization reversed option order
    # overrides from term.yaml
    skip: bool = False
    force_option: int | None = None


class Selection(BaseModel):
    question_index: int
    option_index: int
    text: str | None = None


class QuestionOverride(BaseModel):
    type: QuestionType | None = None
    force: str | None = None  # "positive" | "negative" | "neutral"
    skip: bool = False


class CourseConfig(BaseModel):
    name: str
    overrides: dict[str, QuestionOverride] = {}


class BehaviorConfig(BaseModel):
    confirm_before_submit: bool = True


class AIConfig(BaseModel):
    enabled: bool = False
    provider: str = "claude"
    model: str = "claude-haiku-4-5-20251001"
    api_key_env: str = "ANTHROPIC_API_KEY"
    base_url: str | None = None
    opinionated: bool = False


class SelectorsConfig(BaseModel):
    course_list_container: str = ""       # 空 = 自动检测
    question_container: str = ""          # 空 = 自动检测
    radio_group: str = 'input[type="radio"]'


class DefaultPresetsConfig(BaseModel):
    forward_scale_size: int = 5
    neutral_allowed_under_like: list[int] = [4]
    max_negative_under_neutral: int = 1


class TermConfig(BaseModel):
    semester: str
    app_base_url: str = "https://ce.fudan.edu.cn/index.html?v=3.41.0"
    evaluation_route: str = "#/my-task/details/UnFinished/0/1/Final/undefined/4"
    selectors: SelectorsConfig = SelectorsConfig()
    default_presets: DefaultPresetsConfig = DefaultPresetsConfig()
    behavior: BehaviorConfig = BehaviorConfig()
    ai: AIConfig = AIConfig()
    courses: list[CourseConfig] = []
    text_presets: dict[str, list[str]] = {}


class Distribution(BaseModel):
    weights: list[float]
    description: str = ""


class SentimentDistributions(BaseModel):
    like: Distribution
    neutral: Distribution
    dislike: Distribution


class TextfillTriggerRates(BaseModel):
    like: float = 0.3
    neutral: float = 0.6
    dislike: float = 0.3


class DistributionsConfig(BaseModel):
    forward: SentimentDistributions
    reverse: SentimentDistributions
    yesno: SentimentDistributions
    textfill: TextfillTriggerRates = TextfillTriggerRates()


class PresetsConfig(BaseModel):
    distributions: DistributionsConfig
