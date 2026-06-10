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
    dictation = "dictation"
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
