# modules/__init__.py
# Import semua function dengan nama yang konsisten

try:
    from .compensation import compensation
except ImportError:
    def compensation():
        raise ImportError("compensation module tidak ditemukan")

try:
    from .expertLevel import expertLevel
except ImportError:
    def expertLevel():
        raise ImportError("expertLevel module tidak ditemukan")

try:
    from .learningHour import learningHour
except ImportError:
    def learningHour():
        raise ImportError("learningHour module tidak ditemukan")

try:
    from .newVariation import newVariation
except ImportError:
    def newVariation():
        raise ImportError("newVariation module tidak ditemukan")

# Alias untuk backward compatibility
compensation_page = compensation
expertLevel_page = expertLevel
learningHour_page = learningHour
newVariation_page = newVariation

__all__ = [
    'compensation',
    'expertLevel', 
    'learningHour',
    'newVariation',
    'compensation_page',
    'expertLevel_page',
    'learningHour_page',
    'newVariation_page'
]