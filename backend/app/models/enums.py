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
