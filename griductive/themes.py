"""Chủ đề nhân vật (Themes): lớp hiển thị thuần túy thay đổi dàn nhân vật cho bất kỳ câu đố nào.

Chủ đề chỉ thay thế tên hiển thị, nghề nghiệp, ảnh chân dung và cách gọi hai trạng thái;
không bao giờ thay đổi tọa độ ô, cấu trúc manh mối hay đáp án ẩn nên toàn bộ logic
(KB, phép kéo theo, tác tử) vẫn giữ nguyên hoàn toàn.

Mặc định trò chơi sử dụng chủ đề Bóng đá (``football``) gồm 30 cầu thủ với ảnh thật từ
Wikimedia Commons (``web/portraits/``, nguồn lưu tại ``CREDITS.md``). Chủ đề ``classic``
giữ nguyên dàn nhân vật lưu trong tệp câu đố (tự động dùng khi bàn cờ lớn hơn 30 ô).
Vai trò Red card / Fair play hoàn toàn là trạng thái ngẫu nhiên của trò chơi.
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .puzzle import Character, Puzzle, name_key

DEFAULT_THEME = "football"
FILE_CAST = "classic"  # Giữ nguyên dàn nhân vật lưu sẵn trong tệp câu đố
PORTRAIT_DIR = Path(__file__).resolve().parents[1] / "web" / "portraits"


def portrait_slug(name: str) -> str:
    """Chuyển tên cầu thủ thành tên tệp ảnh chuẩn ASCII: "Văn Hậu" -> "van-hau", "Ødegaard" -> "odegaard"."""
    text = name.translate(str.maketrans({"Ø": "O", "ø": "o", "Đ": "D", "đ": "d"}))
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _with_photo(theme_id: str, persona: "Persona") -> "Persona":
    """Gắn đường dẫn ``web/portraits/<theme>/<slug>.jpg`` nếu tồn tại, ngược lại dùng avatar SVG áo đấu."""
    rel = f"portraits/{theme_id}/{portrait_slug(persona.name)}.jpg"
    if (PORTRAIT_DIR.parent / rel).is_file():
        return Persona(persona.name, persona.profession, {**persona.avatar, "photo": rel})
    return persona


@dataclass(frozen=True)
class Persona:
    """Hồ sơ hiển thị của một nhân vật trong chủ đề."""

    name: str
    profession: str
    avatar: dict


# Nhãn từ vựng hiển thị cho hai trạng thái (tầng logic bên dưới vẫn luôn dùng criminal/innocent)
DEFAULT_TERMS = {
    "criminal": {"label": "Criminal", "adj": "a criminal", "one": "criminal", "many": "criminals"},
    "innocent": {"label": "Innocent", "adj": "innocent", "one": "innocent", "many": "innocents"},
}
FOOTBALL_TERMS = {
    "criminal": {"label": "Red card", "adj": "red-carded", "one": "red-carded player", "many": "red-carded players"},
    "innocent": {"label": "Fair play", "adj": "fair-play", "one": "fair-play player", "many": "fair-play players"},
}


@dataclass(frozen=True)
class Theme:
    """Cấu hình một chủ đề hiển thị (tên, bộ nhân vật, từ khóa đặt tên vụ án, thuật ngữ trạng thái)."""

    theme_id: str
    label: str
    description: str
    cast: tuple[Persona, ...]
    title_words: tuple[tuple[str, ...], tuple[str, ...]] = ((), ())
    terms: dict = field(default_factory=lambda: DEFAULT_TERMS, compare=False, hash=False)

    def title_for(self, puzzle_id: str) -> Optional[str]:
        """Sinh tiêu đề vụ án tất định theo ``puzzle_id`` và bộ từ khóa của chủ đề."""
        first, second = self.title_words
        if not first:
            return None
        rng = random.Random(f"{self.theme_id}:title:{puzzle_id}")
        return f"{rng.choice(first)} {rng.choice(second)}"


# ---------------------------------------------------------------- Chủ đề Bóng đá
# 30 cầu thủ nổi tiếng kèm màu áo đội tuyển quốc gia (dùng cho fallback SVG nếu thiếu ảnh)
# nation: (tên đội tuyển, màu chính, màu phụ, họa tiết áo, màu nền avatar)
NATIONS = {
    "ARG": ("Argentina", "#7dd3fc", "#f8fafc", "stripes", "#e0f2fe"),
    "POR": ("Portugal", "#b91c1c", "#15803d", "solid", "#fecaca"),
    "FRA": ("France", "#1e3a8a", "#f8fafc", "solid", "#bfdbfe"),
    "NOR": ("Norway", "#dc2626", "#1e3a8a", "solid", "#fecaca"),
    "BRA": ("Brazil", "#facc15", "#15803d", "solid", "#fef9c3"),
    "EGY": ("Egypt", "#dc2626", "#f8fafc", "solid", "#fee2e2"),
    "BEL": ("Belgium", "#b91c1c", "#111827", "solid", "#fecaca"),
    "CRO": ("Croatia", "#f8fafc", "#dc2626", "checks", "#fee2e2"),
    "ENG": ("England", "#f8fafc", "#1e3a8a", "solid", "#e0e7ff"),
    "POL": ("Poland", "#f8fafc", "#dc2626", "solid", "#fee2e2"),
    "KOR": ("South Korea", "#dc2626", "#111827", "solid", "#fecaca"),
    "ESP": ("Spain", "#c81e1e", "#facc15", "solid", "#fef3c7"),
    "GER": ("Germany", "#f8fafc", "#111827", "solid", "#e5e7eb"),
    "NED": ("Netherlands", "#f97316", "#111827", "solid", "#ffedd5"),
    "URU": ("Uruguay", "#38bdf8", "#111827", "solid", "#e0f2fe"),
    "NGA": ("Nigeria", "#16a34a", "#f8fafc", "solid", "#dcfce7"),
    "VIE": ("Vietnam", "#dc2626", "#facc15", "solid", "#fef3c7"),
}
GOALKEEPER_KIT = ("#a3e635", "#14532d")

# Bảng dữ liệu cầu thủ: (tên, mã quốc gia, vị trí, số áo, tông da, kiểu tóc, màu tóc, râu, phụ kiện)
_FOOTBALLERS = [
    ("Messi", "ARG", "Forward", 10, 1, "slick", "#4a3326", "beard", "armband"),
    ("Ronaldo", "POR", "Forward", 7, 2, "fade", "#1b1512", "none", "armband"),
    ("Mbappé", "FRA", "Forward", 10, 4, "buzz", "#1b1512", "none", ""),
    ("Haaland", "NOR", "Striker", 9, 0, "bun", "#e2c27a", "none", ""),
    ("Neymar", "BRA", "Forward", 10, 2, "mohawk", "#d8b06a", "stubble", ""),
    ("Salah", "EGY", "Winger", 10, 3, "afro", "#1b1512", "beard", ""),
    ("De Bruyne", "BEL", "Midfielder", 7, 0, "slick", "#c2410c", "stubble", ""),
    ("Modrić", "CRO", "Midfielder", 10, 0, "long", "#a16207", "none", "armband"),
    ("Kane", "ENG", "Striker", 9, 0, "slick", "#7a4b2a", "none", "armband"),
    ("Bellingham", "ENG", "Midfielder", 10, 4, "buzz", "#1b1512", "stubble", ""),
    ("Saka", "ENG", "Winger", 7, 5, "fade", "#1b1512", "none", ""),
    ("Vinícius", "BRA", "Winger", 7, 5, "curly", "#1b1512", "none", ""),
    ("Lewandowski", "POL", "Striker", 9, 0, "slick", "#4a3326", "stubble", "armband"),
    ("Son", "KOR", "Forward", 7, 1, "slick", "#1b1512", "none", "armband"),
    ("Yamal", "ESP", "Winger", 19, 3, "curly", "#1b1512", "none", ""),
    ("Pedri", "ESP", "Midfielder", 20, 1, "fade", "#1b1512", "none", ""),
    ("Rodri", "ESP", "Midfielder", 16, 1, "buzz", "#4a3326", "beard", ""),
    ("Musiala", "GER", "Midfielder", 10, 3, "curly", "#2b2220", "none", ""),
    ("Kimmich", "GER", "Midfielder", 6, 0, "slick", "#7a4b2a", "none", "armband"),
    ("Van Dijk", "NED", "Defender", 4, 4, "buzz", "#1b1512", "beard", "armband"),
    ("Alisson", "BRA", "Goalkeeper", 1, 0, "long", "#4a3326", "beard", "gloves"),
    ("Courtois", "BEL", "Goalkeeper", 1, 0, "fade", "#4a3326", "stubble", "gloves"),
    ("Griezmann", "FRA", "Forward", 7, 0, "slick", "#d8b06a", "stubble", ""),
    ("Valverde", "URU", "Midfielder", 15, 1, "long", "#1b1512", "beard", ""),
    ("Ødegaard", "NOR", "Midfielder", 10, 0, "slick", "#7a4b2a", "none", "armband"),
    ("Osimhen", "NGA", "Striker", 9, 5, "mohawk", "#facc15", "none", ""),
    ("Quang Hải", "VIE", "Midfielder", 19, 1, "slick", "#1b1512", "none", ""),
    ("Văn Hậu", "VIE", "Defender", 5, 1, "fade", "#2b2220", "none", ""),
    ("Tiến Linh", "VIE", "Striker", 22, 1, "buzz", "#1b1512", "none", ""),
    ("Hoàng Đức", "VIE", "Midfielder", 14, 1, "curly", "#2b2220", "none", ""),
]


def _footballer(row) -> Persona:
    """Chuyển một dòng dữ liệu cầu thủ thành Persona kèm đặc tả áo đấu."""
    name, nation, position, number, skin, hair, hair_color, facial, extra = row
    nation_name, primary, secondary, pattern, bg = NATIONS[nation]
    if position == "Goalkeeper":
        primary, secondary, pattern = GOALKEEPER_KIT[0], GOALKEEPER_KIT[1], "solid"
    avatar = {"kind": "football", "bg": bg, "kit": primary, "trim": secondary, "pattern": pattern,
              "number": number, "skin": skin, "hair": hair, "hairColor": hair_color, "facial": facial,
              "extra": extra}
    return Persona(name, f"{position} · {nation_name}", avatar)


THEMES: dict[str, Theme] = {
    FILE_CAST: Theme(FILE_CAST, "Case file", "The characters stored in the puzzle file.", ()),
    "football": Theme(
        "football", "Football", "Thirty star players in their national-team colours (photos: Wikimedia Commons).",
        tuple(_with_photo("football", _footballer(r)) for r in _FOOTBALLERS),
        (("The Midnight", "The Derby Day", "The Golden Boot", "The Locker Room", "The Penalty",
          "The Transfer Window", "The Final Whistle", "The Offside"),
         ("Affair", "Mystery", "Scandal", "Heist", "Conspiracy", "Riddle")),
        FOOTBALL_TERMS),
}


def themed_characters(puzzle: Puzzle, base: dict[str, Character], theme_id: str) -> dict[str, Character]:
    """Áp dụng chủ đề ``theme_id`` lên ``puzzle`` (chọn tất định theo puzzle_id và xếp theo tên row-major)."""
    if theme_id not in THEMES:
        raise ValueError(f"unknown theme {theme_id!r}")
    theme = THEMES[theme_id]
    if not theme.cast:
        return dict(base)
    cells = puzzle.board.cells
    if len(cells) > len(theme.cast):
        raise ValueError(f"the {theme.label} theme has only {len(theme.cast)} characters")
    rng = random.Random(f"{theme_id}:{puzzle.puzzle_id}:{len(cells)}")
    cast = sorted(rng.sample(theme.cast, len(cells)), key=lambda p: name_key(p.name))
    return {c: Character(c, p.name, p.profession, p.avatar) for c, p in zip(cells, cast)}


__all__ = ["THEMES", "DEFAULT_THEME", "FILE_CAST", "Theme", "Persona", "themed_characters"]
