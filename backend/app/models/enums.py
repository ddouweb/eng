import enum


class WordType(str, enum.Enum):
    word = "word"
    sentence = "sentence"


class TagType(str, enum.Enum):
    favorite = "favorite"
    high_freq = "high_freq"
    exam_focus = "exam_focus"
    excluded = "excluded"
    memorized = "memorized"


class MasteryLevel(str, enum.Enum):
    unlearned = "unlearned"
    learning = "learning"
    familiar = "familiar"
    permanent = "permanent"


class PracticeMode(str, enum.Enum):
    flashcard = "flashcard"
    spelling = "spelling"
    choice = "choice"
    cn2en_choice = "cn2en_choice"
    en2cn_write = "en2cn_write"
    dictation = "dictation"
    matching = "matching"
    timed_challenge = "timed_challenge"
    scramble = "scramble"
    memory_flash = "memory_flash"
    flip_match = "flip_match"
    dialogue = "dialogue"


class PlanStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    paused = "paused"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    skipped = "skipped"


class TaskType(str, enum.Enum):
    learn = "learn"
    weekly_review = "weekly_review"
    monthly_review = "monthly_review"
    wrong_word_drill = "wrong_word_drill"


class PlanType(str, enum.Enum):
    """forward = 学新词（首轮）；review_only = 不学新词，纯滚动复习（二轮）；
    wrong_word_drill = 错题优先刷（三轮冲刺）。"""
    forward = "forward"
    review_only = "review_only"
    wrong_word_drill = "wrong_word_drill"
