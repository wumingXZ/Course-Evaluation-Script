import math
import random

from .models import (
    Question,
    Selection,
    Sentiment,
    QuestionType,
    PresetsConfig,
    TermConfig,
    CourseConfig,
)


def generate_selections(
    questions: list[Question],
    sentiment: Sentiment,
    presets: PresetsConfig,
    term: TermConfig,
    course: CourseConfig | None = None,
) -> list[Selection]:
    selections: list[Selection] = []
    negative_count = 0
    neutral_count = 0
    max_negative = term.default_presets.max_negative_under_neutral
    max_neutral_under_like = 2  # 喜欢模式下"一般"最多2题

    # Fixed rules (independent of sentiment, applies to all courses):
    # - Q1: always option index 2 (约等于 Approximately Equal to)
    # - Q12: always "非常不同意" (index 0)
    # - Q15: for neutral/dislike, always "一般" (index 1)
    # - Q16, Q17: always only "无 None" option
    FIXED_OPTIONS = {1: 2}  # question_index → option_index (Q1=约等于)
    FIXED_REVERSE_INDEX = 12
    FIXED_NEUTRAL_RECOMMEND_INDEX = 15  # Q15 = recommend question
    FIXED_NONE_INDICES = {16, 17}

    for q in questions:
        # --- Fixed rule: specific option index ---
        if q.index in FIXED_OPTIONS:
            selections.append(Selection(
                question_index=q.index,
                option_index=FIXED_OPTIONS[q.index],
            ))
            continue

        # --- Fixed rule: Q12 always 非常不同意 ---
        if q.index == FIXED_REVERSE_INDEX:
            q.detected_type = QuestionType.REVERSE
            q.is_reverse = True
            selections.append(Selection(
                question_index=q.index,
                option_index=0,  # 非常不同意 (worst = disagree with negative statement = positive)
            ))
            continue

        # --- Fixed rule: Q15 = 一般 for neutral/dislike ---
        if q.index == FIXED_NEUTRAL_RECOMMEND_INDEX and sentiment in (Sentiment.NEUTRAL, Sentiment.DISLIKE):
            selections.append(Selection(
                question_index=q.index,
                option_index=1,  # 一般 Neutral (middle option)
            ))
            continue

        # --- Fixed rule: Q16/Q17 always only "无 None" ---
        if q.index in FIXED_NONE_INDICES:
            for i, opt in enumerate(q.options):
                if "无" in opt.label or "None" in opt.label:
                    selections.append(Selection(
                        question_index=q.index,
                        option_index=i,
                    ))
            # Ensure at least one selection
            if not any(s.question_index == q.index for s in selections):
                # If no "无" found, skip this question (select nothing)
                pass
            continue

        # Apply course-level overrides
        if course and q.title in course.overrides:
            override = course.overrides[q.title]
            if override.skip:
                continue
            if override.type:
                q.detected_type = override.type
                q.is_reverse = (override.type == QuestionType.REVERSE)
                q.is_yesno = (override.type == QuestionType.YESNO)
            if override.force == "positive" and q.options:
                # Forward: positive = highest index. Reverse: positive = lowest.
                idx = 0 if q.is_reverse else len(q.options) - 1
                selections.append(Selection(
                    question_index=q.index,
                    option_index=idx,
                ))
                continue
            if override.force == "negative" and q.options:
                # Forward: negative = lowest index. Reverse: negative = highest.
                idx = len(q.options) - 1 if q.is_reverse else 0
                selections.append(Selection(
                    question_index=q.index,
                    option_index=idx,
                ))
                continue
            if override.force == "neutral" and q.options:
                mid = len(q.options) // 2
                selections.append(Selection(
                    question_index=q.index,
                    option_index=mid,
                ))
                continue

        if q.skip:
            continue

        # --- Checkbox questions: multi-select ---
        if q.detected_type == QuestionType.CHECKBOX:
            _generate_checkbox_selections(q, sentiment, selections, presets, term)
            continue

        # Determine distribution key
        if q.is_yesno:
            scale_key = "yesno"
        elif q.is_reverse:
            scale_key = "reverse"
        else:
            scale_key = "forward"

        dists = getattr(presets.distributions, scale_key)
        weights = getattr(dists, sentiment.value).weights

        if len(q.options) != len(weights):
            # Mismatch: adjust weights to match option count
            weights = _normalize_weights(len(q.options), scale_key, sentiment)

        # Constraint: no negative for "like" on forward scale
        if sentiment == Sentiment.LIKE and scale_key == "forward":
            negative_cutoff = max(1, math.floor(len(weights) * 0.4))
            for i in range(negative_cutoff):
                weights[i] = 0
            # 一般 (neutral) at most 2 questions
            if neutral_count >= max_neutral_under_like:
                neutral_idx = len(weights) // 2
                weights[neutral_idx] = 0
                # Renormalize: if all weights zero, fallback
                if sum(weights) == 0:
                    weights[-1] = 0.7
                    weights[-2] = 0.3

        # Constraint: at most max_negative for "neutral" on forward scale
        if sentiment == Sentiment.NEUTRAL and scale_key == "forward":
            if negative_count >= max_negative:
                for i in range(len(weights)):
                    if i < math.floor(len(weights) * 0.4):
                        weights[i] = 0

        # Normalize to ensure at least one non-zero weight
        if sum(weights) == 0:
            # Fallback: uniform weights
            weights = [1.0] * len(weights)

        chosen = random.choices(range(len(weights)), weights=weights, k=1)[0]

        # Track negative count for neutral constraint
        if sentiment == Sentiment.NEUTRAL and scale_key == "forward":
            negative_cutoff = max(1, math.floor(len(weights) * 0.4))
            if chosen < negative_cutoff:
                negative_count += 1

        # Track neutral count for like constraint
        if sentiment == Sentiment.LIKE and scale_key == "forward":
            neutral_idx = len(weights) // 2
            if chosen == neutral_idx:
                neutral_count += 1

        # Text fill
        text = None
        if q.has_textfill and q.options and chosen < len(q.options):
            rate = getattr(presets.distributions.textfill, sentiment.value)
            if random.random() < rate:
                preset_list = term.text_presets.get(sentiment.value, [])
                if preset_list:
                    text = random.choice(preset_list)

        selections.append(Selection(
            question_index=q.index,
            option_index=chosen,
            text=text,
        ))

    return selections


def _generate_checkbox_selections(
    q: Question,
    sentiment: Sentiment,
    selections: list[Selection],
    presets: PresetsConfig | None = None,
    term: TermConfig | None = None,
) -> None:
    """Generate multi-select choices for checkbox questions."""
    n = len(q.options)
    if n == 0:
        return

    if sentiment == Sentiment.LIKE:
        probs = [0.3] * n
    elif sentiment == Sentiment.DISLIKE:
        probs = [0.7] * n
    else:
        probs = [0.5] * n

    for i in range(n):
        if random.random() < probs[i]:
            text = None
            if q.options[i].has_text_input and presets and term:
                rate = getattr(presets.distributions.textfill, sentiment.value)
                if random.random() < rate:
                    preset_list = term.text_presets.get(sentiment.value, [])
                    if preset_list:
                        text = random.choice(preset_list)
            selections.append(Selection(
                question_index=q.index,
                option_index=i,
                text=text,
            ))

    # Ensure at least one selection
    if not any(s.question_index == q.index for s in selections):
        idx = random.randrange(n)
        selections.append(Selection(
            question_index=q.index,
            option_index=idx,
        ))


def _normalize_weights(num_options: int, scale_key: str, sentiment: Sentiment) -> list[float]:
    """Generate default weights when option count doesn't match preset."""
    is_reverse = (scale_key == "reverse")

    if num_options == 2:
        # Yes/No style
        if sentiment == Sentiment.LIKE:
            return [0.2, 0.8] if is_reverse else [0.8, 0.2]
        elif sentiment == Sentiment.DISLIKE:
            return [0.8, 0.2] if is_reverse else [0.2, 0.8]
        else:
            return [0.5, 0.5]

    # Likert: index 0 = worst, num_options-1 = best (after normalization)
    # For reverse scale, swap like ↔ dislike semantics
    effective_sentiment = sentiment
    if is_reverse and sentiment == Sentiment.LIKE:
        effective_sentiment = Sentiment.DISLIKE
    elif is_reverse and sentiment == Sentiment.DISLIKE:
        effective_sentiment = Sentiment.LIKE

    if effective_sentiment == Sentiment.LIKE:
        weights = [0.0] * num_options
        weights[-1] = 0.6
        weights[-2] = 0.3
        if num_options >= 3:
            weights[-3] = 0.1
    elif effective_sentiment == Sentiment.DISLIKE:
        weights = [0.0] * num_options
        weights[0] = 0.6
        weights[1] = 0.3
        if num_options >= 3:
            weights[2] = 0.1
    else:
        # Neutral: peak in the middle
        mid = num_options // 2
        weights = [0.05] * num_options
        weights[mid] = 0.6
        if mid - 1 >= 0:
            weights[mid - 1] = 0.15
        if mid + 1 < num_options:
            weights[mid + 1] = 0.15

    return weights
