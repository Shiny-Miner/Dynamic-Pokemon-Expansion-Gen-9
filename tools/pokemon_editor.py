#!/usr/bin/env python3
import os
import re
import shutil
import subprocess
import tempfile
import tkinter as tk
import wave
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
SRC_DIR = ROOT / "src"
GRAPHICS_DIR = ROOT / "graphics"
INCLUDE_DIR = ROOT / "include"

BASE_STATS_FILE = SRC_DIR / "Base_Stats.c"
BASE_STATS_HEADER = INCLUDE_DIR / "base_stats.h"
FRONT_COORDS_FILE = SRC_DIR / "Front_Pic_Coords_Table.c"
BACK_COORDS_FILE = SRC_DIR / "Back_Pic_Coords_Table.c"
ELEVATION_FILE = SRC_DIR / "Enemy_Elevation_Table.c"
CRY_TABLE_FILES = [SRC_DIR / "Cry_Table.c", SRC_DIR / "Cry_Table_2.c"]
EVOLUTION_FILE = SRC_DIR / "Evolution_Table.c"
ICON_TABLE_FILE = SRC_DIR / "Icon_Table.c"
ICON_PALETTE_TABLE_FILE = SRC_DIR / "Icon_Palette_Table.c"
FRONT_PIC_TABLE_FILE = SRC_DIR / "Front_Pic_Table.c"
BACK_PIC_TABLE_FILE = SRC_DIR / "Back_Pic_Table.c"
PALETTE_TABLE_FILE = SRC_DIR / "Palette_Table.c"
SHINY_PALETTE_TABLE_FILE = SRC_DIR / "Shiny_Palette_Table.c"
SPRITE_DATA_HEADER = INCLUDE_DIR / "sprite_data.h"
POKEDEX_DATA_FILE = SRC_DIR / "Pokedex_Data_Table.c"
SPECIES_TO_DEX_FILE = SRC_DIR / "Species_To_Pokdex_Table.c"
POKEDEX_ORDERS_FILE = SRC_DIR / "Pokedex_Orders.c"
LEARNSETS_FILE = SRC_DIR / "Learnsets.c"
ITEMS_HEADER = INCLUDE_DIR / "items.h"
ABILITIES_HEADER = INCLUDE_DIR / "abilities.h"
MOVES_HEADER = INCLUDE_DIR / "moves.h"
EVOLUTION_HEADER = INCLUDE_DIR / "evolution.h"
BACKGROUND_IMAGE = SCRIPT_DIR / "BattlePreviewBackground.png"
SHADOW_IMAGE = SCRIPT_DIR / "BattlePreviewShadow.png"
SPRITE_TRANSPARENT_COLOR = (0x98, 0xD0, 0xA0, 255)
SPECIES_HEADER = INCLUDE_DIR / "species.h"
POKEDEX_HEADER = INCLUDE_DIR / "pokedex.h"
POKEDEX_STRINGS_FILE = ROOT / "strings" / "Pokedex_Data.string"
POKEMON_NAMES_FILE = ROOT / "strings" / "Pokemon_Name_Table.string"
POKEDEX_HOOKS_FILE = ROOT / "assembly" / "pokedex_hooks.s"
BPRE_ROM = ROOT / "BPRE0.gba"
AUDIO_DIR = ROOT / "audio"


def validate_project_layout():
    required = [SRC_DIR, GRAPHICS_DIR, INCLUDE_DIR, BASE_STATS_FILE, SPECIES_HEADER]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Raiz do projeto DPE invalida ({ROOT}): ausente(s): {joined}")

POKEDEX_ORDER_ARRAYS = [
    "gPokedexOrder_Regional",
    "gPokedexOrder_Alphabetical",
    "gPokedexOrder_Weight",
    "gPokedexOrder_Height",
    "gPokedexOrder_Type",
]

BASE_STAT_FIELDS = [
    "baseHP",
    "baseAttack",
    "baseDefense",
    "baseSpeed",
    "baseSpAttack",
    "baseSpDefense",
]

BASE_INFO_FIELDS = [
    "type1",
    "type2",
    "catchRate",
    "expYield",
    "evYield_HP",
    "evYield_Attack",
    "evYield_Defense",
    "evYield_Speed",
    "evYield_SpAttack",
    "evYield_SpDefense",
    "item1",
    "item2",
    "genderRatio",
    "eggCycles",
    "friendship",
    "growthRate",
    "eggGroup1",
    "eggGroup2",
    "ability1",
    "ability2",
    "hiddenAbility",
    "safariZoneFleeRate",
    "noFlip",
]

COORD_FIELDS = ["size", "y_offset"]
HEX_FIELDS = {"size", "y_offset", "elevation"}
DEFAULT_COORD_VALUES = {"size": "0x88", "y_offset": "0x0"}
DEFAULT_ELEVATION_VALUE = "0x0"
NUMERIC_FIELDS = set(BASE_STAT_FIELDS + ["catchRate", "expYield", "eggCycles", "friendship", "safariZoneFleeRate"])
NUMERIC_FIELDS.update(["evYield_HP", "evYield_Attack", "evYield_Defense", "evYield_Speed", "evYield_SpAttack", "evYield_SpDefense"])
NUMERIC_FIELDS.update(["front_size", "front_y_offset", "back_size", "back_y_offset", "elevation"])


def parse_int(value):
    try:
        return int(str(value).strip(), 0)
    except (TypeError, ValueError):
        return None


def species_display_name(species):
    name = species.replace("SPECIES_", "").replace("_", " ").title()
    return name.replace(" Nidoran F", " Nidoran-F").replace(" Nidoran M", " Nidoran-M")


def species_to_name_symbol(species):
    return "NAME_" + species.replace("SPECIES_", "")


def name_symbol_candidates(species):
    symbol = species_to_name_symbol(species)
    compact = symbol.replace("_F", "F").replace("_M", "M")
    candidates = [symbol]
    if compact != symbol:
        candidates.append(compact)
    return candidates


def decode_string_text(text):
    return (
        text.replace("[B6]", "♀")
        .replace("[B5]", "♂")
        .replace("\\n", "\n")
        .replace("\\l", "\n")
        .replace("\\p", "\n\n")
        .strip()
    )


def encode_string_text(text):
    return text.replace("♀", "[B6]").replace("♂", "[B5]").strip()


def symbol_to_title(symbol, prefix):
    return symbol.replace(prefix, "").replace("_", " ").title().replace(" ", "")


def species_to_sprite_name(species):
    raw = species.replace("SPECIES_", "").title().replace("_", "")
    return raw.replace("NidoranF", "NidoranF").replace("NidoranM", "NidoranM")


def species_to_cry_symbol(species):
    return "gCry" + species_to_sprite_name(species)


def species_to_dex(species):
    return "NATIONAL_DEX_" + species.replace("SPECIES_", "")


def species_to_dex_entry(species):
    return "DEX_ENTRY_" + species.replace("SPECIES_", "")


def normalize_species_name(name):
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name.strip()).strip("_").upper()
    if not cleaned:
        raise ValueError("Nome da especie vazio.")
    return cleaned if cleaned.startswith("SPECIES_") else "SPECIES_" + cleaned


def read_lines(path):
    with Path(path).open("r", encoding="utf-8", errors="ignore") as f:
        return f.readlines()


def write_lines(path, lines):
    path = Path(path)
    ensure_backup(path)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.writelines(lines)


def ensure_backup(path):
    backup_path = path.with_suffix(path.suffix + ".bak")
    if not backup_path.exists():
        shutil.copy2(path, backup_path)


def parse_symbol_names(path, prefix):
    names = []
    seen = set()
    pattern = re.compile(rf"^\s*(?:#define\s+)?({re.escape(prefix)}[A-Z0-9_]+)\b")
    if not Path(path).exists():
        return names
    with Path(path).open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                continue
            match = pattern.match(line)
            if match and match.group(1) not in seen:
                seen.add(match.group(1))
                names.append(match.group(1))
    return names


def encode_category(text):
    tokens = []
    for char in text[:11]:
        if char in TEXT_TOKEN_OVERRIDES:
            tokens.append(TEXT_TOKEN_OVERRIDES[char])
        elif char.isalpha():
            tokens.append("_" + char)
        elif char.isdigit():
            tokens.append("_" + char)
        else:
            tokens.append("_SPACE")
    tokens.append("_END")
    while len(tokens) < 12:
        tokens.append("_SPACE")
    return "{" + ", ".join(tokens[:12]) + "}"


def decode_category(raw):
    tokens = re.findall(r"_[A-Za-z0-9]+", raw or "")
    chars = []
    for token in tokens:
        if token == "_END":
            break
        if token == "_SPACE":
            chars.append(" ")
        elif token == "_HYPHEN":
            chars.append("-")
        elif token == "_PERIOD":
            chars.append(".")
        elif token == "_COMMA":
            chars.append(",")
        elif token == "_APOSTROPHE":
            chars.append("'")
        elif token == "_FEMALE":
            chars.append("♀")
        elif token == "_MALE":
            chars.append("♂")
        else:
            chars.append(token[1:])
    return "".join(chars).rstrip()


TYPE_OPTIONS = parse_symbol_names(BASE_STATS_HEADER, "TYPE_")
ITEM_OPTIONS = parse_symbol_names(ITEMS_HEADER, "ITEM_")
ABILITY_OPTIONS = parse_symbol_names(ABILITIES_HEADER, "ABILITY_")
GROWTH_OPTIONS = parse_symbol_names(BASE_STATS_HEADER, "GROWTH_")
EGG_GROUP_OPTIONS = parse_symbol_names(BASE_STATS_HEADER, "EGG_GROUP_")
BOOL_OPTIONS = ["TRUE", "FALSE"]
MOVE_OPTIONS = [move for move in parse_symbol_names(MOVES_HEADER, "MOVE_") if not move.endswith("_LENGTH")]
EVO_OPTIONS = parse_symbol_names(EVOLUTION_HEADER, "EVO_")

DEX_FIELDS = [
    "categoryName",
    "height",
    "weight",
    "pokemonScale",
    "pokemonOffset",
    "trainerScale",
    "trainerOffset",
]

TEXT_TOKEN_OVERRIDES = {
    " ": "_SPACE",
    "-": "_HYPHEN",
    ".": "_PERIOD",
    ",": "_COMMA",
    "'": "_APOSTROPHE",
    "♀": "_FEMALE",
    "♂": "_MALE",
}


class CArrayEditor:
    def __init__(self, path, array_name, entry_type):
        self.path = Path(path)
        self.array_name = array_name
        self.entry_type = entry_type
        self.lines = []
        self.array_start = None
        self.array_end = None
        self.entries = {}
        self.load()

    def load(self):
        with self.path.open("r", encoding="utf-8", errors="ignore") as f:
            self.lines = f.readlines()
        self.parse_entries()

    def find_array_bounds(self):
        start = None
        brace_depth = 0
        for idx, line in enumerate(self.lines):
            if start is None and self.array_name in line and "=" in line:
                start = idx
                brace_depth = line.count("{") - line.count("}")
                continue
            if start is not None:
                brace_depth += line.count("{") - line.count("}")
                if brace_depth == 0:
                    return start, idx
        return start, len(self.lines) - 1

    def parse_entries(self):
        self.array_start, self.array_end = self.find_array_bounds()
        if self.array_start is None:
            raise RuntimeError(f"Array {self.array_name} nao encontrado em {self.path}")
        raw_lines = self.lines[self.array_start : self.array_end + 1]
        if self.entry_type in {"base_stats", "coords"}:
            self.entries = self.parse_struct_entries(raw_lines)
        elif self.entry_type == "elevation":
            self.entries = self.parse_value_entries(raw_lines)
        else:
            raise RuntimeError(f"Tipo de entrada desconhecido: {self.entry_type}")

    def parse_struct_entries(self, raw_lines):
        entries = {}
        current = None
        pending_species = None
        pending_start_idx = None
        brace_depth = 0
        for rel_idx, line in enumerate(raw_lines):
            idx = self.array_start + rel_idx
            if current is None:
                inline = re.match(r"\s*\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=\s*\{([^}]*)\}", line)
                if inline:
                    entries[inline.group(1)] = {
                        "start_idx": idx,
                        "end_idx": idx,
                        "field_map": {},
                    }
                    continue
                m = re.match(r"\s*\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=\s*\{", line)
                if m:
                    current = {
                        "species": m.group(1),
                        "start_idx": idx,
                        "end_idx": None,
                        "field_map": {},
                    }
                    brace_depth = 1
                    continue
                m = re.match(r"\s*\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=\s*$", line)
                if m:
                    pending_species = m.group(1)
                    pending_start_idx = idx
                    continue
                if pending_species and re.match(r"\s*\{", line):
                    current = {
                        "species": pending_species,
                        "start_idx": pending_start_idx,
                        "end_idx": None,
                        "field_map": {},
                    }
                    pending_species = None
                    pending_start_idx = None
                    brace_depth = line.count("{") - line.count("}")
                    if brace_depth == 0:
                        current["end_idx"] = idx
                        entries[current["species"]] = current
                        current = None
                    continue
                if line.strip():
                    pending_species = None
                    pending_start_idx = None
                continue

            brace_depth += line.count("{") - line.count("}")
            if brace_depth == 0:
                current["end_idx"] = idx
                entries[current["species"]] = current
                current = None
                continue

            indent = re.match(r"\s*", line).group(0)
            field_pattern = re.compile(r"\.(\w+)\s*=\s*(.*?)(?=,\s*\.\w+\s*=|,\s*(?://.*)?$)")
            for field_match in field_pattern.finditer(line):
                current["field_map"][field_match.group(1)] = {
                    "line_idx": idx,
                    "indent": indent,
                    "raw": field_match.group(2).strip(),
                }
        return entries

    def parse_value_entries(self, raw_lines):
        entries = {}
        for rel_idx, line in enumerate(raw_lines):
            idx = self.array_start + rel_idx
            m = re.match(r"(\s*)\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=\s*([^,]+),(.*)$", line)
            if m:
                entries[m.group(2)] = {
                    "line_idx": idx,
                    "indent": m.group(1),
                    "suffix": "," + m.group(4),
                    "raw": m.group(3).strip(),
                }
        return entries

    def get_keys(self):
        return list(self.entries.keys())

    def get_raw(self, species, key):
        entry = self.entries.get(species)
        if not entry:
            return ""
        if self.entry_type == "elevation":
            return entry.get("raw", "")
        field = entry["field_map"].get(key)
        return field.get("raw", "") if field else ""

    def get_int(self, species, key):
        return parse_int(self.get_raw(species, key))

    def has_entry(self, species):
        return species in self.entries

    def has_field(self, species, key):
        entry = self.entries.get(species)
        if not entry:
            return False
        if self.entry_type == "elevation":
            return True
        return key in entry["field_map"]

    def add_missing_entry(self, species):
        if species in self.entries:
            return
        if self.entry_type == "coords":
            self.add_struct_entry(species, DEFAULT_COORD_VALUES)
        elif self.entry_type == "elevation":
            self.add_value_entry(species, DEFAULT_ELEVATION_VALUE)

    def add_struct_entry(self, species, defaults):
        insert_idx = self.array_end
        lines = [
            f"\t[{species}] =\n",
            "\t{\n",
            f"\t\t.size = {defaults['size']},\n",
            f"\t\t.y_offset = {defaults['y_offset']},\n",
            "\t},\n",
        ]
        self.lines[insert_idx:insert_idx] = lines
        self.entries[species] = {
            "species": species,
            "start_idx": insert_idx,
            "end_idx": insert_idx + len(lines) - 1,
            "field_map": {
                "size": {
                    "line_idx": insert_idx + 2,
                    "indent": "\t\t",
                    "suffix": ",",
                    "raw": defaults["size"],
                },
                "y_offset": {
                    "line_idx": insert_idx + 3,
                    "indent": "\t\t",
                    "suffix": ",",
                    "raw": defaults["y_offset"],
                },
            },
        }
        self.array_end += len(lines)

    def add_value_entry(self, species, default):
        insert_idx = self.array_end
        self.lines.insert(insert_idx, f"\t[{species}] = {default},\n")
        self.entries[species] = {
            "line_idx": insert_idx,
            "indent": "\t",
            "suffix": ",",
            "raw": default,
        }
        self.array_end += 1

    def set_raw(self, species, key, value):
        if species not in self.entries:
            self.add_missing_entry(species)
        entry = self.entries.get(species)
        if not entry:
            return False
        raw = str(value).strip()
        if self.entry_type == "elevation":
            field = entry
            self.lines[field["line_idx"]] = f"{field['indent']}[{species}] = {raw}{field['suffix']}\n"
            field["raw"] = raw
            return True

        field = entry["field_map"].get(key)
        if not field:
            insert_idx = entry["end_idx"]
            indent = entry["field_map"].get(next(iter(entry["field_map"]), ""), {}).get("indent", "\t\t")
            self.lines.insert(insert_idx, f"{indent}.{key} = {raw},\n")
            self.parse_entries()
            return True

        line_idx = field["line_idx"]
        pattern = re.compile(rf"(\.{re.escape(key)}\s*=\s*)(.*?)(?=,\s*\.\w+\s*=|,\s*(?://.*)?$)")
        self.lines[line_idx], count = pattern.subn(lambda match: match.group(1) + raw, self.lines[line_idx], count=1)
        if count != 1:
            return False
        field["raw"] = raw
        return True

    def set_value(self, species, key, value):
        raw = format(value, "#x") if key in HEX_FIELDS else str(value)
        return self.set_raw(species, key, raw)

    def save(self):
        ensure_backup(self.path)
        with self.path.open("w", encoding="utf-8", newline="") as f:
            f.writelines(self.lines)


class SpriteTable:
    def __init__(self, path, graphics_subdir):
        self.path = Path(path)
        self.graphics_subdir = GRAPHICS_DIR / graphics_subdir
        self.entries = {}
        self.load()

    def load(self):
        self.entries = {}
        if not self.path.exists():
            return
        pattern = re.compile(r"\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=\s*\{\s*([A-Za-z0-9_]+)Tiles\s*,")
        with self.path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                match = pattern.search(line)
                if not match:
                    continue
                png = self.graphics_subdir / f"{match.group(2)}.png"
                self.entries[match.group(1)] = png

    def get_path(self, species):
        path = self.entries.get(species)
        if path and path.exists():
            return path
        return None


class IconTable:
    def __init__(self, path):
        self.path = Path(path)
        self.graphics_subdir = GRAPHICS_DIR / "pokeicon"
        self.entries = {}
        self.symbols = {}
        self.load()

    def load(self):
        self.entries = {}
        self.symbols = {}
        if not self.path.exists():
            return
        pattern = re.compile(r"\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=\s*([A-Za-z0-9_]+)Tiles\s*,")
        with self.path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                match = pattern.search(line)
                if not match:
                    continue
                symbol = match.group(2)
                self.symbols[match.group(1)] = symbol
                self.entries[match.group(1)] = self.graphics_subdir / f"{symbol}.png"

    def get_symbol(self, species):
        return self.symbols.get(species, "")

    def get_path(self, species):
        path = self.entries.get(species)
        if path and path.exists():
            return path
        return None


class IconPaletteData:
    def __init__(self):
        self.lines = read_lines(ICON_PALETTE_TABLE_FILE) if ICON_PALETTE_TABLE_FILE.exists() else []
        self.entries = {}
        self.array_end = None
        self.parse()

    def parse(self):
        self.entries = {}
        self.array_end = None
        in_array = False
        opened = False
        depth = 0
        for idx, line in enumerate(self.lines):
            if not in_array and "gMonIconPaletteIndices" in line:
                in_array = True
            if not in_array:
                continue
            depth += line.count("{") - line.count("}")
            if "{" in line:
                opened = True
            match = re.match(r"(\s*)\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=\s*([^,]+),(.*)$", line)
            if match:
                self.entries[match.group(2)] = {
                    "line_idx": idx,
                    "indent": match.group(1),
                    "suffix": "," + match.group(4),
                    "raw": match.group(3).strip(),
                }
            if opened and depth == 0:
                self.array_end = idx
                return
        self.array_end = len(self.lines)

    def get_raw(self, species):
        entry = self.entries.get(species)
        return entry["raw"] if entry else ""

    def set_index(self, species, index):
        raw = f"0x{int(index):x}"
        if species in self.entries:
            entry = self.entries[species]
            self.lines[entry["line_idx"]] = f"{entry['indent']}[{species}] = {raw}{entry['suffix']}\n"
            entry["raw"] = raw
            return
        insert_idx = self.array_end if self.array_end is not None else len(self.lines)
        for idx, line in enumerate(self.lines):
            if "//New Species Go Here" in line:
                insert_idx = idx
                break
        self.lines.insert(insert_idx, f"\t[{species}] = {raw},\n")
        self.parse()

    def save(self):
        if ICON_PALETTE_TABLE_FILE.exists():
            write_lines(ICON_PALETTE_TABLE_FILE, self.lines)


class DesignatedStructEditor:
    def __init__(self, path, array_name):
        self.path = Path(path)
        self.array_name = array_name
        self.lines = []
        self.array_start = None
        self.array_end = None
        self.entries = {}
        self.load()

    def load(self):
        self.lines = read_lines(self.path)
        self.array_start, self.array_end = self.find_array_bounds()
        self.entries = self.parse_entries()

    def find_array_bounds(self):
        start = None
        depth = 0
        for idx, line in enumerate(self.lines):
            if start is None and self.array_name in line and "=" in line:
                start = idx
                depth = line.count("{") - line.count("}")
                continue
            if start is not None:
                depth += line.count("{") - line.count("}")
                if depth == 0:
                    return start, idx
        return start, len(self.lines) - 1

    def parse_entries(self):
        entries = {}
        current = None
        pending_key = None
        pending_start = None
        depth = 0
        for idx in range(self.array_start, self.array_end + 1):
            line = self.lines[idx]
            if current is None:
                m = re.match(r"\s*\[\s*([A-Z0-9_]+)\s*\]\s*=\s*\{", line)
                if m:
                    current = {"key": m.group(1), "start_idx": idx, "field_map": {}}
                    depth = 1
                    continue
                m = re.match(r"\s*\[\s*([A-Z0-9_]+)\s*\]\s*=\s*$", line)
                if m:
                    pending_key = m.group(1)
                    pending_start = idx
                    continue
                if pending_key and re.match(r"\s*\{", line):
                    current = {"key": pending_key, "start_idx": pending_start, "field_map": {}}
                    pending_key = None
                    pending_start = None
                    depth = line.count("{") - line.count("}")
                    continue
                if line.strip():
                    pending_key = None
                    pending_start = None
                continue

            depth += line.count("{") - line.count("}")
            if depth == 0:
                current["end_idx"] = idx
                entries[current["key"]] = current
                current = None
                continue
            field_match = re.match(r"(\s*)\.(\w+)\s*=\s*(.+)(,.*)$", line)
            if field_match:
                current["field_map"][field_match.group(2)] = {
                    "line_idx": idx,
                    "indent": field_match.group(1),
                    "raw": field_match.group(3).strip(),
                    "suffix": field_match.group(4).rstrip("\n"),
                }
        return entries

    def get_raw(self, key, field):
        entry = self.entries.get(key)
        if not entry:
            return ""
        data = entry["field_map"].get(field)
        return data["raw"] if data else ""

    def set_raw(self, key, field, value):
        entry = self.entries.get(key)
        if not entry:
            return False
        data = entry["field_map"].get(field)
        if not data:
            return False
        data["raw"] = str(value).strip()
        self.lines[data["line_idx"]] = f"{data['indent']}.{field} = {data['raw']}{data['suffix']}\n"
        return True

    def add_entry(self, key, values):
        if key in self.entries:
            return
        insert_idx = self.array_end
        lines = [
            f"\t[{key}] =\n",
            "\t{\n",
            f"\t\t.categoryName = {values['categoryName']},\n",
            f"\t\t.height = {values['height']},\n",
            f"\t\t.weight = {values['weight']},\n",
            f"\t\t.description = {values['description']},\n",
            "\t\t.unusedDescription = (const u8*) 0x8444cb1,\n",
            f"\t\t.pokemonScale = {values['pokemonScale']},\n",
            f"\t\t.pokemonOffset = {values['pokemonOffset']},\n",
            f"\t\t.trainerScale = {values['trainerScale']},\n",
            f"\t\t.trainerOffset = {values['trainerOffset']},\n",
            "\t},\n",
        ]
        self.lines[insert_idx:insert_idx] = lines
        self.array_end += len(lines)

    def save(self):
        write_lines(self.path, self.lines)


class PokedexData:
    def __init__(self):
        self.entries = DesignatedStructEditor(POKEDEX_DATA_FILE, "gPokedexEntries")
        self.species_to_dex = self.load_species_to_dex()
        self.alternate_descriptions = self.load_alternate_descriptions()
        self.descriptions = self.load_descriptions()
        self.dirty_descriptions = set()

    def load_species_to_dex(self):
        mapping = {}
        if not SPECIES_TO_DEX_FILE.exists():
            return mapping
        for line in read_lines(SPECIES_TO_DEX_FILE):
            m = re.match(r"\s*\[\s*(SPECIES_[A-Z0-9_]+)\s*-\s*1\s*\]\s*=\s*(NATIONAL_DEX_[A-Z0-9_]+)", line)
            if m:
                mapping[m.group(1)] = m.group(2)
        return mapping

    def load_alternate_descriptions(self):
        mapping = {}
        if not POKEDEX_DATA_FILE.exists():
            return mapping
        for line in read_lines(POKEDEX_DATA_FILE):
            macro = re.search(r"ALTERNATE_DEX_ENTRY\(\s*([A-Z0-9_]+)\s*\)", line)
            if macro:
                species_suffix = macro.group(1)
                mapping["SPECIES_" + species_suffix] = "DEX_ENTRY_" + species_suffix
                continue
            explicit = re.search(r"\{\s*(SPECIES_[A-Z0-9_]+)\s*,\s*(DEX_ENTRY_[A-Z0-9_]+)\s*\}", line)
            if explicit:
                mapping[explicit.group(1)] = explicit.group(2)
        return mapping

    def load_descriptions(self):
        descriptions = {}
        if not POKEDEX_STRINGS_FILE.exists():
            return descriptions
        current = None
        chunks = []
        for line in read_lines(POKEDEX_STRINGS_FILE):
            org = re.match(r"#org\s+@(DEX_ENTRY_[A-Z0-9_]+)", line)
            if org:
                if current:
                    descriptions[current] = "".join(chunks).strip("\n")
                current = org.group(1)
                chunks = []
                continue
            if current:
                if line.startswith("#org "):
                    descriptions[current] = "".join(chunks).strip("\n")
                    current = None
                    chunks = []
                else:
                    chunks.append(line)
        if current:
            descriptions[current] = "".join(chunks).strip("\n")
        return descriptions

    def dex_for_species(self, species):
        return self.species_to_dex.get(species, species_to_dex(species))

    def description_for_species(self, species, dex):
        alternate = self.alternate_descriptions.get(species)
        if alternate:
            return alternate
        raw = self.entries.get_raw(dex, "description") or species_to_dex_entry(species)
        symbol = re.search(r"\b(DEX_ENTRY_[A-Z0-9_]+)\b", raw)
        return symbol.group(1) if symbol else raw

    def get_values(self, species):
        dex = self.dex_for_species(species)
        desc_symbol = self.description_for_species(species, dex)
        values = {
            "nationalDex": dex,
            "descriptionSymbol": desc_symbol,
            "descriptionText": self.descriptions.get(desc_symbol, ""),
        }
        for field in DEX_FIELDS:
            raw = self.entries.get_raw(dex, field)
            values[field] = decode_category(raw) if field == "categoryName" else raw
        return values

    def set_values(self, species, values):
        dex = values.get("nationalDex") or self.dex_for_species(species)
        for field in DEX_FIELDS:
            if field not in values:
                continue
            raw = encode_category(values[field]) if field == "categoryName" else values[field]
            self.entries.set_raw(dex, field, raw)
        desc_symbol = values.get("descriptionSymbol", "")
        if desc_symbol:
            if species not in self.alternate_descriptions:
                self.entries.set_raw(dex, "description", desc_symbol)
            if re.match(r"DEX_ENTRY_[A-Z0-9_]+$", desc_symbol):
                description = values.get("descriptionText", "")
                if description != self.descriptions.get(desc_symbol, ""):
                    self.descriptions[desc_symbol] = description
                    self.dirty_descriptions.add(desc_symbol)

    def save(self):
        self.entries.save()
        self.save_descriptions()

    def save_descriptions(self):
        if not self.dirty_descriptions:
            return
        lines = read_lines(POKEDEX_STRINGS_FILE)
        out = []
        written = set()
        idx = 0
        while idx < len(lines):
            line = lines[idx]
            org = re.match(r"#org\s+@(DEX_ENTRY_[A-Z0-9_]+)", line)
            if not org or org.group(1) not in self.dirty_descriptions:
                out.append(line)
                idx += 1
                continue

            symbol = org.group(1)
            out.append(line)
            text = self.descriptions.get(symbol, "").rstrip("\n")
            if text:
                out.append(text + "\n")
            written.add(symbol)
            idx += 1
            while idx < len(lines) and lines[idx].strip() and not lines[idx].startswith(("#org ", "//", "/*")):
                idx += 1

        for symbol in self.dirty_descriptions - written:
            text = self.descriptions.get(symbol, "").rstrip("\n")
            if out and out[-1].strip():
                out.append("\n")
            out.append(f"#org @{symbol}\n")
            if text:
                out.append(text + "\n")
        write_lines(POKEDEX_STRINGS_FILE, out)
        self.dirty_descriptions.clear()


class PokemonNameData:
    def __init__(self):
        self.names = self.load()

    def load(self):
        names = {}
        if not POKEMON_NAMES_FILE.exists():
            return names
        current = None
        chunks = []
        for line in read_lines(POKEMON_NAMES_FILE):
            org = re.match(r"#org\s+@(NAME_[A-Z0-9_]+)", line)
            if org:
                if current:
                    names[current] = decode_string_text("".join(chunks))
                current = org.group(1)
                chunks = []
                continue
            if current:
                if line.startswith("#org "):
                    names[current] = decode_string_text("".join(chunks))
                    current = None
                    chunks = []
                elif not re.match(r"\s*(MAX_LENGTH|FILL_FF)\s*=", line):
                    chunks.append(line)
        if current:
            names[current] = decode_string_text("".join(chunks))
        return names

    def get(self, species):
        for symbol in name_symbol_candidates(species):
            name = self.names.get(symbol)
            if name:
                return name
        return species_display_name(species)

    def append_missing(self, species, name):
        symbol = species_to_name_symbol(species)
        if any(candidate in self.names for candidate in name_symbol_candidates(species)):
            return
        lines = read_lines(POKEMON_NAMES_FILE)
        text = encode_string_text(name) or species_display_name(species)
        if lines and lines[-1].strip():
            lines.append("\n")
        lines.append(f"#org @{symbol}\n{text}\n")
        write_lines(POKEMON_NAMES_FILE, lines)
        self.names[symbol] = text


class PokedexOrdersData:
    def __init__(self):
        self.lines = read_lines(POKEDEX_ORDERS_FILE) if POKEDEX_ORDERS_FILE.exists() else []
        self.bounds = {}
        self.orders = {}
        self.parse()

    def parse(self):
        self.bounds = {}
        self.orders = {}
        for array_name in POKEDEX_ORDER_ARRAYS:
            bounds = self.find_array_bounds(array_name)
            if not bounds:
                self.orders[array_name] = []
                continue
            _start_idx, open_idx, end_idx = bounds
            self.bounds[array_name] = bounds
            entries = []
            for line in self.lines[open_idx + 1 : end_idx]:
                match = re.match(r"\s*(SPECIES_[A-Z0-9_]+)\s*,", line)
                if match:
                    entries.append(match.group(1))
            self.orders[array_name] = entries

    def find_array_bounds(self, array_name):
        start = None
        open_idx = None
        depth = 0
        for idx, line in enumerate(self.lines):
            if start is None and array_name in line and "=" in line:
                start = idx
                continue
            if start is None:
                continue
            if open_idx is None:
                if "{" in line:
                    open_idx = idx
                    depth = line.count("{") - line.count("}")
                    if depth == 0:
                        return start, open_idx, idx
                elif re.match(r"\s*const\s+u16\s+gPokedexOrder_", line):
                    return None
                continue
            depth += line.count("{") - line.count("}")
            if depth == 0:
                return start, open_idx, idx
        return None

    def get_order(self, array_name):
        return list(self.orders.get(array_name, []))

    def set_order(self, array_name, species_list):
        if array_name not in POKEDEX_ORDER_ARRAYS or array_name not in self.bounds:
            return
        start_idx, _open_idx, end_idx = self.bounds[array_name]
        new_lines = [self.lines[start_idx], "{\n"]
        new_lines.extend(f"\t{species},\n" for species in species_list)
        new_lines.append("};\n")
        self.lines[start_idx : end_idx + 1] = new_lines
        self.parse()

    def save(self):
        if POKEDEX_ORDERS_FILE.exists():
            write_lines(POKEDEX_ORDERS_FILE, self.lines)


class LearnsetData:
    def __init__(self):
        self.lines = read_lines(LEARNSETS_FILE) if LEARNSETS_FILE.exists() else []
        self.species_to_array = self.parse_species_table()
        self.learnset_bounds = {}
        self.learnsets = self.parse_learnsets()

    def parse_species_table(self):
        mapping = {}
        for line in self.lines:
            match = re.match(r"\s*\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=\s*([A-Za-z0-9_]+)\s*,", line)
            if match:
                mapping[match.group(1)] = match.group(2)
        return mapping

    def parse_learnsets(self):
        learnsets = {}
        current = None
        entries = []
        start_idx = None
        for idx, line in enumerate(self.lines):
            start = re.match(r"\s*static\s+const\s+struct\s+LevelUpMove\s+([A-Za-z0-9_]+)\[\]\s*=\s*\{", line)
            if start:
                current = start.group(1)
                entries = []
                start_idx = idx
                continue
            if current:
                if "LEVEL_UP_END" in line:
                    learnsets[current] = entries
                    self.learnset_bounds[current] = (start_idx, idx)
                    current = None
                    entries = []
                    start_idx = None
                    continue
                move = re.match(r"\s*LEVEL_UP_MOVE\(\s*([0-9]+)\s*,\s*(MOVE_[A-Z0-9_]+)\s*\)", line)
                if move:
                    entries.append((int(move.group(1)), move.group(2)))
        return learnsets

    def get_for_species(self, species):
        array_name = self.species_to_array.get(species, "")
        return array_name, self.learnsets.get(array_name, [])

    def set_for_species(self, species, entries):
        array_name = self.species_to_array.get(species, "")
        if not array_name:
            array_name = "s" + species_to_sprite_name(species) + "LevelUpLearnset"
            self.add_learnset_array(species, array_name, add_table_entry=True)
        elif array_name not in self.learnset_bounds:
            self.add_learnset_array(species, array_name, add_table_entry=False)
        self.learnsets[array_name] = entries
        self.replace_array_entries(array_name, entries)

    def add_learnset_array(self, species, array_name, add_table_entry=True):
        insert_idx = 0
        for idx, line in enumerate(self.lines):
            if "const struct LevelUpMove* const gLevelUpLearnsets" in line:
                insert_idx = idx
                break
        block = [
            f"static const struct LevelUpMove {array_name}[] = {{\n",
            "\tLEVEL_UP_END\n",
            "};\n\n",
        ]
        self.lines[insert_idx:insert_idx] = block
        self.species_to_array[species] = array_name
        if add_table_entry:
            insert_before_array_end(self.lines, "gLevelUpLearnsets", f"\t[{species}] = {array_name},\n")
        self.species_to_array = self.parse_species_table()
        self.learnset_bounds = {}
        self.learnsets = self.parse_learnsets()

    def replace_array_entries(self, array_name, entries):
        if array_name not in self.learnset_bounds:
            return
        start_idx, end_idx = self.learnset_bounds[array_name]
        new_lines = [self.lines[start_idx]]
        for level, move in entries:
            new_lines.append(f"\tLEVEL_UP_MOVE({int(level):2d}, {move}),\n")
        new_lines.append("\tLEVEL_UP_END\n")
        new_lines.extend(self.lines[end_idx + 1 : end_idx + 2])
        self.lines[start_idx : end_idx + 2] = new_lines
        self.learnset_bounds = {}
        self.learnsets = self.parse_learnsets()

    def save(self):
        write_lines(LEARNSETS_FILE, self.lines)


class EvolutionData:
    def __init__(self):
        self.lines = read_lines(EVOLUTION_FILE) if EVOLUTION_FILE.exists() else []
        self.entry_bounds = {}
        self.evolutions = {}
        self.array_end_idx = None
        self.parse_entries()

    def find_array_end(self):
        in_array = False
        opened = False
        depth = 0
        for idx, line in enumerate(self.lines):
            if not in_array and "gEvolutionTable" in line:
                in_array = True
            if not in_array:
                continue
            depth += line.count("{") - line.count("}")
            if "{" in line:
                opened = True
            if opened and depth == 0:
                return idx
        return len(self.lines)

    def parse_entries(self):
        self.entry_bounds = {}
        self.evolutions = {}
        self.array_end_idx = self.find_array_end()
        starts = []
        entry_start = re.compile(r"\s*\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=")
        for idx, line in enumerate(self.lines[: self.array_end_idx]):
            match = entry_start.match(line)
            if match:
                starts.append((match.group(1), idx))
        for pos, (species, start_idx) in enumerate(starts):
            end_idx = starts[pos + 1][1] if pos + 1 < len(starts) else self.array_end_idx
            block = "".join(self.lines[start_idx:end_idx])
            entries = []
            for raw_tuple in re.findall(r"\{([^{}]+)\}", block):
                fields = self.split_initializer_fields(raw_tuple)
                if len(fields) == 4 and fields[0].startswith("EVO_") and fields[2].startswith("SPECIES_"):
                    entries.append(tuple(fields))
            self.entry_bounds[species] = (start_idx, end_idx)
            self.evolutions[species] = entries

    def split_initializer_fields(self, text):
        fields = []
        current = []
        paren_depth = 0
        for char in text:
            if char == "(":
                paren_depth += 1
            elif char == ")" and paren_depth:
                paren_depth -= 1
            if char == "," and paren_depth == 0:
                fields.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        if current:
            fields.append("".join(current).strip())
        return fields

    def get_for_species(self, species):
        return self.evolutions.get(species, [])

    def set_for_species(self, species, entries):
        if not EVOLUTION_FILE.exists():
            return
        if species in self.entry_bounds:
            start_idx, end_idx = self.entry_bounds[species]
            self.lines[start_idx:end_idx] = self.format_entry(species, entries)
        elif entries:
            insert_idx = self.array_end_idx if self.array_end_idx is not None else len(self.lines)
            self.lines[insert_idx:insert_idx] = self.format_entry(species, entries)
        self.parse_entries()

    def format_entry(self, species, entries):
        if not entries:
            return []
        lines = [f"\t[{species}] =\n", "\t{\n"]
        for method, param, target, extra in entries:
            lines.append(f"\t\t{{{method}, {param}, {target}, {extra}}},\n")
        lines.append("\t},\n")
        return lines

    def save(self):
        if EVOLUTION_FILE.exists():
            write_lines(EVOLUTION_FILE, self.lines)


class CryData:
    def __init__(self):
        self.tables = [DesignatedStructEditor(path, "gCryTable") for path in CRY_TABLE_FILES if path.exists()]

    def get_raw(self, species):
        for table in self.tables:
            raw = table.get_raw(species, "wav")
            if raw:
                return raw
        return ""

    def set_symbol(self, species, symbol):
        for table in self.tables:
            if species not in table.entries:
                self.add_cry_entry(table.path, species, symbol)
                table.load()
            table.set_raw(species, "wav", symbol)

    def add_cry_entry(self, path, species, symbol):
        text = (
            f"\t[{species}] =\n"
            "\t{\n"
            "\t\t.type = 0x20,\n"
            "\t\t.key = 0x3c,\n"
            "\t\t.length = 0x0,\n"
            "\t\t.pan_sweep = 0x0,\n"
            f"\t\t.wav = {symbol},\n"
            "\t\t.attack = 0xff,\n"
            "\t\t.decay = 0x0,\n"
            "\t\t.sustain = 0xff,\n"
            "\t\t.release = 0x0,\n"
            "\t},\n"
        )
        append_before_array_end(path, "gCryTable", text)

    def save(self):
        for table in self.tables:
            table.save()


def cry_symbol_to_wav_path(symbol):
    if not symbol or not re.match(r"gCry[A-Za-z0-9_]+$", symbol):
        return None
    path = AUDIO_DIR / f"{symbol}.wav"
    return path if path.exists() else None


def ensure_cry_extern(symbol):
    lines = read_lines(INCLUDE_DIR / "cry_data.h")
    extern = f"extern u8 {symbol}[];\n"
    if extern in lines:
        return
    insert_idx = len(lines)
    lines.insert(insert_idx, extern)
    write_lines(INCLUDE_DIR / "cry_data.h", lines)


def import_cry_file(species, source_path):
    symbol = species_to_cry_symbol(species)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    target = AUDIO_DIR / f"{symbol}.wav"
    if target.exists():
        ensure_backup(target)
    shutil.copy2(source_path, target)
    ensure_cry_extern(symbol)
    return symbol, target


def parse_pointer_offset(raw):
    match = re.search(r"\((?:u8|u16)\s*\*\)\s*(0x[0-9A-Fa-f]+)", raw or "")
    return parse_int(match.group(1)) if match else None


def read_rom_offset(raw, max_bytes=32):
    pointer = parse_pointer_offset(raw)
    if pointer is None:
        return None, ""
    if not BPRE_ROM.exists():
        return pointer, "BPRE0.gba não identificado; offsets de ROM ignorados."
    rom_offset = pointer - 0x08000000 if pointer >= 0x08000000 else pointer
    try:
        with BPRE_ROM.open("rb") as f:
            f.seek(rom_offset)
            data = f.read(max_bytes)
    except OSError as exc:
        return pointer, f"Falha ao ler BPRE0.gba: {exc}"
    return pointer, f"ROM offset 0x{rom_offset:X}: {data.hex(' ')}"


def play_wav_file(path):
    if not path or not Path(path).exists():
        raise FileNotFoundError("Arquivo .wav nao encontrado.")
    players = [
        ["paplay", str(path)],
        ["aplay", str(path)],
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)],
    ]
    for command in players:
        if shutil.which(command[0]):
            subprocess.Popen(command)
            return
    try:
        with wave.open(str(path), "rb"):
            pass
    except wave.Error as exc:
        raise RuntimeError(f"WAV invalido: {exc}") from exc
    raise RuntimeError("Nenhum player encontrado (paplay, aplay ou ffplay).")


def last_define_value(path, prefix):
    last = None
    for line in read_lines(path):
        m = re.match(rf"\s*#define\s+({re.escape(prefix)}[A-Z0-9_]+)\s+(.+?)(?:\s|$)", line)
        if m:
            value = parse_int(m.group(2))
            if value is not None:
                last = (m.group(1), value)
    return last


def pokedex_define_options():
    return [dex for dex in parse_symbol_names(POKEDEX_HEADER, "NATIONAL_DEX_") if dex not in {"NATIONAL_DEX_NONE", "NATIONAL_DEX_COUNT"}]


def add_define_before_pattern(path, pattern, line):
    lines = read_lines(path)
    for idx, existing in enumerate(lines):
        if re.search(pattern, existing):
            lines.insert(idx, line)
            write_lines(path, lines)
            return
    lines.append(line)
    write_lines(path, lines)


def display_name_from_user_input(raw_name, species):
    name = raw_name.strip()
    if not name or name.upper().startswith("SPECIES_"):
        return species_display_name(species)
    return name[:10]


def increment_expanded_pokedex_size():
    lines = read_lines(POKEDEX_HOOKS_FILE)
    pattern = re.compile(r"(\.ExpandedPokedexSize:\s*\.word\s+)(\d+)(\s*\*\s*8.*)")
    for idx, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            value = int(match.group(2)) + 1
            lines[idx] = f"{match.group(1)}{value}{match.group(3)}\n"
            write_lines(POKEDEX_HOOKS_FILE, lines)
            return value
    raise RuntimeError(f"Nao foi possivel atualizar .ExpandedPokedexSize em {POKEDEX_HOOKS_FILE}")


def add_new_species_files(species, category_name, pokemon_name=None, dex_mode="new", existing_dex=None):
    create_new_dex = dex_mode == "new"
    dex = species_to_dex(species) if create_new_dex else existing_dex
    dex_entry = species_to_dex_entry(species)
    species_last = last_define_value(SPECIES_HEADER, "SPECIES_")
    dex_last = last_define_value(POKEDEX_HEADER, "NATIONAL_DEX_") if create_new_dex else None
    if not species_last or (create_new_dex and not dex_last):
        raise RuntimeError("Nao foi possivel descobrir o ultimo SPECIES/NATIONAL_DEX.")
    if not create_new_dex and not dex:
        raise RuntimeError("Selecione uma entrada NATIONAL_DEX existente.")
    species_value = species_last[1] + 1
    dex_value = dex_last[1] + 1 if dex_last else None

    add_define_before_pattern(SPECIES_HEADER, r"^\s*#define\s+NUM_SPECIES\b", f"#define {species} 0x{species_value:X}\n")
    species_lines = read_lines(SPECIES_HEADER)
    species_lines = [
        re.sub(r"#define\s+NUM_SPECIES\s+\(.+\)", f"#define NUM_SPECIES ({species} + 1)", line)
        for line in species_lines
    ]
    write_lines(SPECIES_HEADER, species_lines)

    if create_new_dex:
        add_define_before_pattern(POKEDEX_HEADER, r"^\s*#define\s+FINAL_DEX_ENTRY\b", f"#define {dex} {dex_value}\n")
        dex_lines = read_lines(POKEDEX_HEADER)
        dex_lines = [
            re.sub(r"#define\s+FINAL_DEX_ENTRY\s+NATIONAL_DEX_[A-Z0-9_]+", f"#define FINAL_DEX_ENTRY {dex}", line)
            for line in dex_lines
        ]
        for idx, line in enumerate(dex_lines):
            if line.startswith("//Category"):
                dex_lines.insert(idx, f"extern const u8 {dex_entry}[];\n")
                break
        write_lines(POKEDEX_HEADER, dex_lines)

        dex_name = species.replace("SPECIES_", "").title().replace("_", " ")
        strings = read_lines(POKEDEX_STRINGS_FILE)
        strings.insert(max(0, len(strings) - 1), f"\n#org @{dex_entry}\n{dex_name} was added with the Pokemon editor.\n")
        write_lines(POKEDEX_STRINGS_FILE, strings)
        append_pokedex_entry(dex, dex_entry, category_name)
        increment_expanded_pokedex_size()

    append_species_to_dex_mapping(species, dex)
    PokemonNameData().append_missing(species, pokemon_name or species_display_name(species))
    append_base_stats_entry(species)
    append_coords_and_elevation_entries(species)
    append_pokedex_order(species)


def insert_before_array_end(lines, array_name, text):
    start = None
    depth = 0
    for idx, line in enumerate(lines):
        if start is None and array_name in line and "=" in line:
            start = idx
            depth = line.count("{") - line.count("}")
            continue
        if start is not None:
            depth += line.count("{") - line.count("}")
            if depth == 0:
                lines.insert(idx, text)
                return
    raise RuntimeError(f"Array {array_name} nao encontrado.")


def append_before_array_end(path, array_name, text):
    lines = read_lines(path)
    try:
        insert_before_array_end(lines, array_name, text)
    except RuntimeError as exc:
        raise RuntimeError(f"Array {array_name} nao encontrado em {path}") from exc
    write_lines(path, lines)


def max_sprite_number():
    highest = 0
    for directory in [GRAPHICS_DIR / "frontspr", GRAPHICS_DIR / "backspr"]:
        for path in directory.glob("*.png"):
            match = re.match(r"g(?:FrontSprite|BackShinySprite)(\d+)", path.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return highest


def max_icon_number():
    highest = 0
    for path in (GRAPHICS_DIR / "pokeicon").glob("*.png"):
        match = re.match(r"gIconSprite(\d+)", path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest


def sprite_symbol_for_species(species, side):
    table = FRONT_PIC_TABLE_FILE if side == "front" else BACK_PIC_TABLE_FILE
    prefix = "gFrontSprite" if side == "front" else "gBackShinySprite"
    pattern = re.compile(rf"\[\s*{re.escape(species)}\s*\]\s*=\s*\{{\s*({prefix}[A-Za-z0-9_]+)Tiles\s*,")
    for line in read_lines(table):
        match = pattern.search(line)
        if match:
            return match.group(1)
    number = max_sprite_number() + 1
    return f"{prefix}{number:03d}{species_to_sprite_name(species)}"


def icon_symbol_for_species(species):
    pattern = re.compile(rf"\[\s*{re.escape(species)}\s*\]\s*=\s*(gIconSprite[A-Za-z0-9_]+)Tiles\s*,")
    for line in read_lines(ICON_TABLE_FILE):
        match = pattern.search(line)
        if match:
            return match.group(1)
    return f"gIconSprite{max_icon_number() + 1:03d}{species_to_sprite_name(species)}"


def ensure_sprite_table_entry(species, side, symbol):
    table = FRONT_PIC_TABLE_FILE if side == "front" else BACK_PIC_TABLE_FILE
    array = "gMonFrontPicTable" if side == "front" else "gMonBackPicTable"
    if re.search(rf"\[\s*{re.escape(species)}\s*\]", "".join(read_lines(table))):
        return
    append_before_array_end(table, array, f"\t[{species}] =            {{{symbol}Tiles, (64 * 64) / 2, {species}}},\n")


def ensure_sprite_palette_table_entry(species, side, symbol):
    table = PALETTE_TABLE_FILE if side == "front" else SHINY_PALETTE_TABLE_FILE
    array = "gMonPaletteTable" if side == "front" else "gMonShinyPaletteTable"
    tag = species if side == "front" else f"{species} + NUM_SPECIES"
    entry = f"\t[{species}] =            {{{symbol}Pal, {tag}, 0x0}},\n"
    lines = read_lines(table)
    pattern = re.compile(rf"(\s*\[\s*{re.escape(species)}\s*\]\s*=\s*)\{{[^}}]+\}}(.*)$")
    for idx, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            lines[idx] = f"{match.group(1)}{{{symbol}Pal, {tag}, 0x0}}{match.group(2)}\n"
            write_lines(table, lines)
            return

    insert_idx = None
    for idx, line in enumerate(lines):
        if "//New Species Go Here" in line:
            insert_idx = idx
            break
    if insert_idx is None:
        append_before_array_end(table, array, entry)
        return
    lines.insert(insert_idx, entry)
    write_lines(table, lines)


def ensure_icon_table_entry(species, symbol):
    lines = read_lines(ICON_TABLE_FILE)
    pattern = re.compile(rf"(\s*\[\s*{re.escape(species)}\s*\]\s*=\s*)([A-Za-z0-9_]+)(Tiles\s*,.*)$")
    for idx, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            lines[idx] = f"{match.group(1)}{symbol}{match.group(3)}\n"
            write_lines(ICON_TABLE_FILE, lines)
            return
    insert_idx = None
    for idx, line in enumerate(lines):
        if "//New Species Go Here" in line:
            insert_idx = idx
            break
    if insert_idx is None:
        start = None
        depth = 0
        for idx, line in enumerate(lines):
            if start is None and "gMonIconTable" in line and "=" in line:
                start = idx
            if start is not None:
                depth += line.count("{") - line.count("}")
                if depth == 0 and "{" in "".join(lines[start : idx + 1]):
                    insert_idx = idx
                    break
    if insert_idx is None:
        raise RuntimeError(f"Array gMonIconTable nao encontrado em {ICON_TABLE_FILE}")
    lines.insert(insert_idx, f"\t[{species}] =                 {symbol}Tiles,\n")
    write_lines(ICON_TABLE_FILE, lines)


def ensure_sprite_extern(symbol):
    lines = read_lines(SPRITE_DATA_HEADER)
    extern = f"extern const u8 {symbol}Tiles[];\n"
    if extern in lines:
        return
    insert_idx = len(lines)
    for idx, line in enumerate(lines):
        if symbol.startswith("gBackShinySprite") and line.startswith("extern const u8 gIconSprite"):
            insert_idx = idx
            break
        if symbol.startswith("gFrontSprite") and line.startswith("extern const u8 gBackShinySprite"):
            insert_idx = idx
            break
    lines.insert(insert_idx, extern)
    write_lines(SPRITE_DATA_HEADER, lines)


def ensure_icon_extern(symbol):
    lines = read_lines(SPRITE_DATA_HEADER)
    extern = f"extern const u8 {symbol}Tiles[];\n"
    if extern in lines:
        return
    insert_idx = len(lines)
    for idx, line in enumerate(lines):
        if line.startswith("extern const u8 gIconSpriteGiga"):
            insert_idx = idx
            break
    if insert_idx == len(lines):
        for idx, line in enumerate(lines):
            if line.startswith("extern const u8 gIconSprite"):
                insert_idx = idx + 1
    lines.insert(insert_idx, extern)
    write_lines(SPRITE_DATA_HEADER, lines)


def ensure_sprite_palette_extern(symbol):
    lines = read_lines(SPRITE_DATA_HEADER)
    extern = f"extern const u8 {symbol}Pal[];\n"
    if extern in lines:
        return
    insert_idx = len(lines)
    sentinel = "extern const u8 gFrontSprite252Pal[]" if symbol.startswith("gFrontSprite") else "extern const u8 gBackShinySprite252Pal[]"
    for idx, line in enumerate(lines):
        if line.startswith(sentinel):
            insert_idx = idx
            break
    lines.insert(insert_idx, extern)
    write_lines(SPRITE_DATA_HEADER, lines)


def palette_to_png_palette(palette):
    flat_palette = []
    for red, green, blue, _alpha in palette[:16]:
        flat_palette.extend([red, green, blue])
    while len(flat_palette) < 16 * 3:
        flat_palette.extend([0, 0, 0])
    flat_palette.extend([0] * (256 * 3 - len(flat_palette)))
    return flat_palette


def frame_palette(frame, label):
    rgba = frame.convert("RGBA")
    color_key = rgba.getpixel((0, 0))
    palette = [SPRITE_TRANSPARENT_COLOR]
    seen = {SPRITE_TRANSPARENT_COLOR}
    for pixel in rgba.getdata():
        key = SPRITE_TRANSPARENT_COLOR if pixel == color_key else pixel
        if key not in seen:
            if len(palette) >= 16:
                raise ValueError(f"{label} tem mais de 16 cores. Reduza a paleta antes de importar.")
            seen.add(key)
            palette.append(key)
    return palette


def derive_shiny_palette(normal_frame, shiny_frame, normal_palette):
    normal_rgba = normal_frame.convert("RGBA")
    shiny_rgba = shiny_frame.convert("RGBA")
    normal_pixels = list(normal_rgba.getdata())
    shiny_pixels = list(shiny_rgba.getdata())
    shiny_palette = [normal_palette[0]]

    for color in normal_palette[1:]:
        counts = {}
        for normal_pixel, shiny_pixel in zip(normal_pixels, shiny_pixels):
            if normal_pixel != color:
                continue
            counts[shiny_pixel] = counts.get(shiny_pixel, 0) + 1
        if counts:
            shiny_palette.append(max(counts.items(), key=lambda item: item[1])[0])
        else:
            shiny_palette.append(color)
    while len(shiny_palette) < 16:
        shiny_palette.append((0, 0, 0, 255))
    return shiny_palette[:16]


def index_frame_with_palette(frame, palette, label, color_key=None):
    rgba = frame.convert("RGBA")
    color_key = color_key if color_key is not None else rgba.getpixel((0, 0))
    color_to_index = {color: idx for idx, color in enumerate(palette)}
    indexed_pixels = []

    for pixel in rgba.getdata():
        key = palette[0] if pixel == color_key else pixel
        if key not in color_to_index:
            if len(palette) >= 16:
                raise ValueError(f"{label} tem cor fora da paleta shiny de 16 cores: {key}.")
            color_to_index[key] = len(palette)
            palette.append(key)
        indexed_pixels.append(color_to_index[key])

    indexed = Image.new("P", frame.size)
    indexed.putdata(indexed_pixels)
    indexed.putpalette(palette_to_png_palette(palette))
    return indexed


def indexed_crop(image, box, label="sprite"):
    frame = image.crop(box)
    palette = frame_palette(frame, label)
    while len(palette) < 16:
        palette.append((0, 0, 0, 255))
    return index_frame_with_palette(frame, palette[:16], label)


def import_external_sprite_sheet(species, source_path):
    if Image is None:
        raise RuntimeError("Pillow nao esta instalado; nao consigo recortar PNG indexado com seguranca.")
    image = Image.open(source_path)
    if image.width < 256 or image.height < 64:
        raise ValueError("A imagem precisa ter pelo menos 256x64 com 4 frames de 64x64.")
    front_normal = image.crop((0, 0, 64, 64))
    front_shiny = image.crop((64, 0, 128, 64))
    back_shiny = image.crop((192, 0, 256, 64))

    front_symbol = sprite_symbol_for_species(species, "front")
    back_symbol = sprite_symbol_for_species(species, "back")
    front_path = GRAPHICS_DIR / "frontspr" / f"{front_symbol}.png"
    back_path = GRAPHICS_DIR / "backspr" / f"{back_symbol}.png"
    front_path.parent.mkdir(parents=True, exist_ok=True)
    back_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_backup(front_path) if front_path.exists() else None
    ensure_backup(back_path) if back_path.exists() else None
    normal_palette = frame_palette(front_normal, "front sprite")
    while len(normal_palette) < 16:
        normal_palette.append((0, 0, 0, 255))
    shiny_palette = derive_shiny_palette(front_normal, front_shiny, normal_palette)

    index_frame_with_palette(front_normal, normal_palette[:16], "front sprite").save(front_path)
    index_frame_with_palette(back_shiny, shiny_palette[:16], "back sprite").save(back_path)

    ensure_sprite_extern(front_symbol)
    ensure_sprite_extern(back_symbol)
    ensure_sprite_palette_extern(front_symbol)
    ensure_sprite_palette_extern(back_symbol)
    ensure_sprite_table_entry(species, "front", front_symbol)
    ensure_sprite_table_entry(species, "back", back_symbol)
    ensure_sprite_palette_table_entry(species, "front", front_symbol)
    ensure_sprite_palette_table_entry(species, "back", back_symbol)
    return front_path, back_path


def import_external_icon(species, source_path, palette_index):
    if Image is None:
        raise RuntimeError("Pillow nao esta instalado; nao consigo importar PNG indexado com seguranca.")
    if int(palette_index) not in {0, 1, 2}:
        raise ValueError("O index da paleta do icone precisa ser 0, 1 ou 2.")

    image = Image.open(source_path).convert("RGBA")
    if image.size == (32, 32):
        combined = Image.new("RGBA", (32, 64), image.getpixel((0, 0)))
        combined.paste(image, (0, 0))
        combined.paste(image, (0, 32))
        image = combined
    elif image.size != (32, 64):
        raise ValueError("O icone precisa ser 32x64 com 2 frames, ou 32x32 para duplicar o frame.")

    symbol = icon_symbol_for_species(species)
    target = GRAPHICS_DIR / "pokeicon" / f"{symbol}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    ensure_backup(target) if target.exists() else None

    palette = frame_palette(image, "pokemon icon")
    while len(palette) < 16:
        palette.append((0, 0, 0, 255))
    index_frame_with_palette(image, palette[:16], "pokemon icon").save(target)

    ensure_icon_extern(symbol)
    ensure_icon_table_entry(species, symbol)
    icon_palettes = IconPaletteData()
    icon_palettes.set_index(species, palette_index)
    icon_palettes.save()
    return target


def append_species_to_dex_mapping(species, dex):
    append_before_array_end(SPECIES_TO_DEX_FILE, "gSpeciesToNationalPokedexNum", f"\t[{species} - 1] = {dex},\n")


def append_pokedex_entry(dex, dex_entry, category_name):
    editor = DesignatedStructEditor(POKEDEX_DATA_FILE, "gPokedexEntries")
    editor.add_entry(dex, {
        "categoryName": encode_category(category_name or "Unknown"),
        "height": "1",
        "weight": "1",
        "description": dex_entry,
        "pokemonScale": "256",
        "pokemonOffset": "0",
        "trainerScale": "256",
        "trainerOffset": "0",
    })
    editor.save()


def append_base_stats_entry(species):
    text = (
        f"\n\t[{species}] =\n"
        "\t{\n"
        "\t\t.baseHP = 1,\n"
        "\t\t.baseAttack = 1,\n"
        "\t\t.baseDefense = 1,\n"
        "\t\t.baseSpAttack = 1,\n"
        "\t\t.baseSpDefense = 1,\n"
        "\t\t.baseSpeed = 1,\n"
        "\t\t.type1 = TYPE_NORMAL,\n"
        "\t\t.type2 = TYPE_NORMAL,\n"
        "\t\t.catchRate = 255,\n"
        "\t\t.expYield = 1,\n"
        "\t\t.evYield_HP = 0,\n"
        "\t\t.evYield_Attack = 0,\n"
        "\t\t.evYield_Defense = 0,\n"
        "\t\t.evYield_SpAttack = 0,\n"
        "\t\t.evYield_SpDefense = 0,\n"
        "\t\t.evYield_Speed = 0,\n"
        "\t\t.item1 = ITEM_NONE,\n"
        "\t\t.item2 = ITEM_NONE,\n"
        "\t\t.genderRatio = MON_GENDERLESS,\n"
        "\t\t.eggCycles = 20,\n"
        "\t\t.friendship = 50,\n"
        "\t\t.growthRate = GROWTH_MEDIUM_FAST,\n"
        "\t\t.eggGroup1 = EGG_GROUP_UNDISCOVERED,\n"
        "\t\t.eggGroup2 = EGG_GROUP_UNDISCOVERED,\n"
        "\t\t.ability1 = ABILITY_NONE,\n"
        "\t\t.ability2 = ABILITY_NONE,\n"
        "\t\t.safariZoneFleeRate = 0,\n"
        "\t\t.hiddenAbility = ABILITY_NONE,\n"
        "\t\t.noFlip = FALSE,\n"
        "\t},\n"
    )
    append_before_array_end(BASE_STATS_FILE, "gBaseStats", text)


def append_coords_and_elevation_entries(species):
    front = CArrayEditor(FRONT_COORDS_FILE, "gMonFrontPicCoords", "coords")
    front.set_raw(species, "size", "0x88")
    front.set_raw(species, "y_offset", "0x0")
    front.save()
    back = CArrayEditor(BACK_COORDS_FILE, "gMonBackPicCoords", "coords")
    back.set_raw(species, "size", "0x88")
    back.set_raw(species, "y_offset", "0x0")
    back.save()
    elevation = CArrayEditor(ELEVATION_FILE, "gEnemyMonElevation", "elevation")
    elevation.set_raw(species, "elevation", "0x0")
    elevation.save()


def append_pokedex_order(species):
    append_before_array_end(POKEDEX_ORDERS_FILE, "gPokedexOrder_Regional", f"\t{species},\n")


class PokemonData:
    def __init__(self):
        self.names = PokemonNameData()
        self.base_stats = CArrayEditor(BASE_STATS_FILE, "gBaseStats", "base_stats")
        self.front_coords = CArrayEditor(FRONT_COORDS_FILE, "gMonFrontPicCoords", "coords")
        self.back_coords = CArrayEditor(BACK_COORDS_FILE, "gMonBackPicCoords", "coords")
        self.elevation = CArrayEditor(ELEVATION_FILE, "gEnemyMonElevation", "elevation")
        self.front_sprites = SpriteTable(FRONT_PIC_TABLE_FILE, "frontspr")
        self.back_sprites = SpriteTable(BACK_PIC_TABLE_FILE, "backspr")
        self.icons = IconTable(ICON_TABLE_FILE)
        self.icon_palettes = IconPaletteData()
        self.pokedex = PokedexData()
        self.pokedex_orders = PokedexOrdersData()
        self.learnsets = LearnsetData()
        self.evolutions = EvolutionData()
        self.cries = CryData()
        self.species_order = self.build_species_order()

    def build_species_order(self):
        # Coordinate tables also contain battle-only objects without base stats
        # (for example Zygarde cells). They cannot be safely edited as Pokemon.
        return [species for species in self.base_stats.get_keys() if species != "SPECIES_NONE"]

    def get_species_list(self):
        return self.species_order

    def display_name(self, species):
        return self.names.get(species)

    def get_values(self, species):
        values = {}
        for field in BASE_STAT_FIELDS + BASE_INFO_FIELDS:
            values[field] = self.base_stats.get_raw(species, field)
        for field in COORD_FIELDS:
            values[f"front_{field}"] = self.front_coords.get_raw(species, field) or DEFAULT_COORD_VALUES[field]
            values[f"back_{field}"] = self.back_coords.get_raw(species, field) or DEFAULT_COORD_VALUES[field]
        values["elevation"] = self.elevation.get_raw(species, "elevation") or DEFAULT_ELEVATION_VALUE
        return values

    def missing_edit_targets(self, species):
        missing = []
        for field in COORD_FIELDS:
            if not self.front_coords.has_field(species, field):
                missing.append(f"front_{field}")
            if not self.back_coords.has_field(species, field):
                missing.append(f"back_{field}")
        if not self.elevation.has_entry(species):
            missing.append("elevation")
        return missing

    def set_values(self, species, values):
        for field in BASE_STAT_FIELDS + BASE_INFO_FIELDS:
            if field in values and values[field] != "":
                self.base_stats.set_raw(species, field, values[field])
        for field in COORD_FIELDS:
            front_key = f"front_{field}"
            back_key = f"back_{field}"
            if front_key in values:
                self.front_coords.set_raw(species, field, values[front_key])
            if back_key in values:
                self.back_coords.set_raw(species, field, values[back_key])
        if "elevation" in values:
            self.elevation.set_raw(species, "elevation", values["elevation"])

    def save(self):
        self.base_stats.save()
        self.front_coords.save()
        self.back_coords.save()
        self.elevation.save()
        self.pokedex.save()
        self.learnsets.save()
        self.evolutions.save()
        self.icon_palettes.save()
        self.pokedex_orders.save()
        self.cries.save()

    def sprite_path(self, species, side):
        return self.front_sprites.get_path(species) if side == "front" else self.back_sprites.get_path(species)

    def icon_path(self, species):
        return self.icons.get_path(species)

    def icon_palette(self, species):
        return self.icon_palettes.get_raw(species)


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)

    def _on_mousewheel(self, event):
        if self.winfo_toplevel().focus_get() and str(self.winfo_toplevel().focus_get()).startswith(str(self)):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class PokemonEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dynamic Pokemon Editor")
        self.root.geometry("1180x760")
        self.data = PokemonData()
        self.current_species = None
        self.current_values = {}
        self.entry_vars = {}
        self.dex_vars = {}
        self.learnset_rows = []
        self.selected_learnset_row = None
        self.evolution_rows = []
        self.selected_evolution_row = None
        self.current_pokedex_order_array = None
        self.photo_refs = {}
        self.icon_frame = 0
        self.icon_animation_job = None
        self.preview_scale = tk.IntVar(value=1)
        self.show_guides = tk.BooleanVar(value=True)
        self.build_ui()
        self.load_species_list()

    def build_ui(self):
        style = ttk.Style(self.root)
        style.configure("SelectedLearnset.TFrame", background="#d8e8ff")
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left = ttk.Frame(self.root, padding=8)
        left.grid(row=0, column=0, sticky="ns")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)
        ttk.Label(left, text="Buscar Pokemon").grid(row=0, column=0, sticky="w")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.filter_species)
        ttk.Entry(left, textvariable=self.search_var, width=30).grid(row=1, column=0, sticky="ew", pady=(2, 8))
        tree_frame = ttk.Frame(left)
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.species_tree = ttk.Treeview(tree_frame, columns=("name",), show="tree headings", height=28, selectmode="browse")
        self.species_tree.heading("#0", text="Species")
        self.species_tree.heading("name", text="Nome")
        self.species_tree.column("#0", width=180, stretch=False)
        self.species_tree.column("name", width=120, stretch=True)
        self.species_tree.grid(row=0, column=0, sticky="nsew")
        self.species_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.species_tree.yview)
        self.species_tree.configure(yscrollcommand=self.species_scrollbar.set)
        self.species_scrollbar.grid(row=0, column=1, sticky="ns")
        self.species_tree.bind("<<TreeviewSelect>>", self.on_species_select)

        left_buttons = ttk.Frame(left)
        left_buttons.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        left_buttons.columnconfigure(0, weight=1)
        left_buttons.columnconfigure(1, weight=1)
        ttk.Button(left_buttons, text="Novo", command=self.open_new_species_dialog).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(left_buttons, text="Recarregar", command=self.reload_data).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(left_buttons, text="Salvar", command=self.save_all).grid(row=0, column=2, sticky="ew", padx=(4, 0))
        left_buttons.columnconfigure(2, weight=1)

        right = ttk.Frame(self.root, padding=(0, 8, 8, 8))
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        self.header_var = tk.StringVar(value="Selecione um Pokemon")
        ttk.Label(right, textvariable=self.header_var, font=("TkDefaultFont", 14, "bold")).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        notebook = ttk.Notebook(right)
        notebook.grid(row=1, column=0, sticky="nsew")

        self.icon_palette_var = tk.StringVar()
        self.create_stats_info_tab(notebook)
        self.create_position_preview_tab(notebook)
        self.create_pokedex_tab(notebook)
        self.create_pokedex_orders_tab(notebook)
        self.create_learnset_tab(notebook)
        self.create_evolution_tab(notebook)
        self.create_cry_tab(notebook)
        self.create_files_tab(notebook)

        self.status_var = tk.StringVar(value="Pronto.")
        ttk.Label(self.root, textvariable=self.status_var, anchor="w").grid(row=1, column=0, columnspan=2, sticky="ew")

    def create_labeled_entry(self, parent, label, key, row, column, width=18, values=None, note=None):
        ttk.Label(parent, text=label).grid(row=row, column=column * 3, sticky="w", padx=(0, 8), pady=4)
        var = tk.StringVar()
        if values:
            entry = ttk.Combobox(parent, textvariable=var, values=values, width=width)
            entry.bind("<<ComboboxSelected>>", self.apply_current_edits)
        else:
            entry = ttk.Entry(parent, textvariable=var, width=width)
        entry.grid(row=row, column=column * 3 + 1, sticky="ew", padx=(0, 6 if note else 18), pady=4)
        entry.bind("<FocusOut>", self.apply_current_edits)
        entry.bind("<Return>", self.apply_current_edits)
        if note:
            ttk.Label(parent, text=note).grid(row=row, column=column * 3 + 2, sticky="w", padx=(0, 18), pady=4)
        parent.columnconfigure(column * 3 + 1, weight=1)
        self.entry_vars[key] = var
        return entry

    def create_nudge_entry(self, parent, label, key, row, column, width=12):
        ttk.Label(parent, text=label).grid(row=row, column=column * 3, sticky="w", padx=(0, 8), pady=4)
        var = tk.StringVar()
        holder = ttk.Frame(parent)
        holder.grid(row=row, column=column * 3 + 1, sticky="ew", padx=(0, 18), pady=4)
        entry = ttk.Entry(holder, textvariable=var, width=width)
        entry.pack(side="left", fill="x", expand=True)
        ttk.Button(holder, text="▲", width=2, command=lambda: self.nudge_value(key, 1)).pack(side="left", padx=(4, 0))
        ttk.Button(holder, text="▼", width=2, command=lambda: self.nudge_value(key, -1)).pack(side="left", padx=(2, 0))
        entry.bind("<FocusOut>", self.apply_current_edits)
        entry.bind("<Return>", self.apply_current_edits)
        parent.columnconfigure(column * 3 + 1, weight=1)
        self.entry_vars[key] = var
        return entry

    def create_stats_info_tab(self, notebook):
        scroll = ScrollableFrame(notebook)
        notebook.add(scroll, text="Base Stats / Dados Gerais")
        tab = scroll.inner

        stats = ttk.LabelFrame(tab, text="Base Stats", padding=10)
        stats.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        for idx, field in enumerate(BASE_STAT_FIELDS):
            self.create_labeled_entry(stats, field, field, idx // 2, idx % 2, width=10)
        ttk.Label(stats, text="BST").grid(row=3, column=0, sticky="w", pady=(10, 4))
        self.bst_var = tk.StringVar(value="0")
        ttk.Label(stats, textvariable=self.bst_var, font=("TkDefaultFont", 18, "bold")).grid(row=3, column=1, sticky="w", pady=(10, 4))

        battle = ttk.LabelFrame(tab, text="Tipos, captura e EXP", padding=10)
        battle.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
        self.create_labeled_entry(battle, "type1", "type1", 0, 0, width=22, values=TYPE_OPTIONS)
        self.create_labeled_entry(battle, "type2", "type2", 0, 1, width=22, values=TYPE_OPTIONS)
        self.create_labeled_entry(battle, "catchRate", "catchRate", 1, 0, width=10)
        self.create_labeled_entry(battle, "expYield", "expYield", 1, 1, width=10)
        self.create_labeled_entry(battle, "growthRate", "growthRate", 2, 0, width=24, values=GROWTH_OPTIONS)
        self.create_labeled_entry(battle, "genderRatio", "genderRatio", 2, 1, width=24)
        self.create_labeled_entry(battle, "eggCycles", "eggCycles", 3, 0, width=10)
        self.create_labeled_entry(battle, "friendship", "friendship", 3, 1, width=10)

        evs = ttk.LabelFrame(tab, text="EV Yield", padding=10)
        evs.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=8)
        ev_fields = ["evYield_HP", "evYield_Attack", "evYield_Defense", "evYield_Speed", "evYield_SpAttack", "evYield_SpDefense"]
        for idx, field in enumerate(ev_fields):
            self.create_labeled_entry(evs, field, field, idx // 2, idx % 2, width=10)

        items = ttk.LabelFrame(tab, text="Itens", padding=10)
        items.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=8)
        self.create_labeled_entry(items, "item1", "item1", 0, 0, width=30, values=ITEM_OPTIONS, note="25%")
        self.create_labeled_entry(items, "item2", "item2", 1, 0, width=30, values=ITEM_OPTIONS, note="5%")

        breeding = ttk.LabelFrame(tab, text="Egg Groups", padding=10)
        breeding.grid(row=2, column=0, sticky="nsew", padx=(0, 8), pady=8)
        self.create_labeled_entry(breeding, "eggGroup1", "eggGroup1", 0, 0, width=28, values=EGG_GROUP_OPTIONS)
        self.create_labeled_entry(breeding, "eggGroup2", "eggGroup2", 1, 0, width=28, values=EGG_GROUP_OPTIONS)

        abilities = ttk.LabelFrame(tab, text="Abilities", padding=10)
        abilities.grid(row=2, column=1, sticky="nsew", padx=(8, 0), pady=8)
        self.create_labeled_entry(abilities, "ability1", "ability1", 0, 0, width=32, values=ABILITY_OPTIONS)
        self.create_labeled_entry(abilities, "ability2", "ability2", 1, 0, width=32, values=ABILITY_OPTIONS)
        self.create_labeled_entry(abilities, "hiddenAbility", "hiddenAbility", 2, 0, width=32, values=ABILITY_OPTIONS)

        misc = ttk.LabelFrame(tab, text="Outros", padding=10)
        misc.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        self.create_labeled_entry(misc, "safariZoneFleeRate", "safariZoneFleeRate", 0, 0, width=10)
        self.create_labeled_entry(misc, "noFlip", "noFlip", 1, 0, width=10, values=BOOL_OPTIONS)

        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)

    def create_position_preview_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text="Coords / Elevacao / Preview")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

        controls = ttk.Frame(tab)
        controls.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        front = ttk.LabelFrame(controls, text="Front sprite", padding=10)
        back = ttk.LabelFrame(controls, text="Back sprite", padding=10)
        enemy = ttk.LabelFrame(controls, text="Enemy elevation", padding=10)
        front.pack(fill="x", pady=(0, 8))
        back.pack(fill="x", pady=8)
        enemy.pack(fill="x", pady=(8, 0))
        for idx, field in enumerate(COORD_FIELDS):
            creator = self.create_nudge_entry if field == "y_offset" else self.create_labeled_entry
            creator(front, field, f"front_{field}", idx, 0, width=12)
            creator(back, field, f"back_{field}", idx, 0, width=12)
        self.create_nudge_entry(enemy, "elevation", "elevation", 0, 0, width=12)
        ttk.Label(enemy, text="Valores aceitam decimal ou hexadecimal, ex.: 12 ou 0xc.").grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        icon_preview = ttk.LabelFrame(controls, text="Icone", padding=10)
        icon_preview.pack(fill="x", pady=(8, 0))
        self.icon_preview_canvas = tk.Canvas(icon_preview, width=72, height=72, bg="#303030", highlightthickness=0)
        self.icon_preview_canvas.pack(side="left")
        self.icon_preview_info_var = tk.StringVar(value="Sem icone")
        icon_details = ttk.Frame(icon_preview)
        icon_details.pack(side="left", fill="x", expand=True, padx=(8, 0))
        ttk.Label(icon_details, textvariable=self.icon_preview_info_var, justify="left").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(icon_details, text="Palette index").grid(row=1, column=0, sticky="w", pady=(8, 0))
        icon_palette_combo = ttk.Combobox(
            icon_details,
            textvariable=self.icon_palette_var,
            values=("0", "1", "2"),
            state="readonly",
            width=4,
        )
        icon_palette_combo.grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(8, 0))
        icon_palette_combo.bind("<<ComboboxSelected>>", self.apply_current_edits)

        self.preview_canvas = tk.Canvas(tab, bg="#202020", highlightthickness=0)
        self.preview_canvas.grid(row=0, column=1, sticky="nsew")
        self.preview_canvas.bind("<Configure>", lambda _event: self.update_preview())

        toolbar = ttk.Frame(tab)
        toolbar.grid(row=1, column=1, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(toolbar, text="Guias", variable=self.show_guides, command=self.update_preview).pack(side="left")
        ttk.Button(toolbar, text="Atualizar", command=self.update_preview).pack(side="right")

    def create_pokedex_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Pokédex")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(8, weight=1)

        fields = [
            ("National Dex", "nationalDex", 0, True),
            ("Description symbol", "descriptionSymbol", 1, False),
            ("Category", "categoryName", 2, False),
            ("Height", "height", 3, False),
            ("Weight", "weight", 4, False),
            ("Pokemon scale", "pokemonScale", 5, False),
            ("Pokemon offset", "pokemonOffset", 6, False),
            ("Trainer scale", "trainerScale", 7, False),
            ("Trainer offset", "trainerOffset", 8, False),
        ]
        for label, key, row, readonly in fields:
            ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
            var = tk.StringVar()
            state = "readonly" if readonly else "normal"
            entry = ttk.Entry(tab, textvariable=var, state=state)
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            entry.bind("<FocusOut>", self.apply_current_edits)
            entry.bind("<Return>", self.apply_current_edits)
            self.dex_vars[key] = var

        ttk.Label(tab, text="Description").grid(row=9, column=0, sticky="nw", padx=(0, 8), pady=(8, 4))
        self.dex_description_text = tk.Text(tab, height=7, wrap="word")
        self.dex_description_text.grid(row=9, column=1, sticky="nsew", pady=(8, 4))
        self.dex_description_text.bind("<FocusOut>", self.apply_current_edits)
        ttk.Button(tab, text="Aplicar Pokédex", command=self.apply_current_edits).grid(row=10, column=1, sticky="e", pady=(8, 0))

    def create_pokedex_orders_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Ordens Pokédex")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        top = ttk.Frame(tab)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(top, text="Ordem").pack(side="left")
        self.pokedex_order_var = tk.StringVar(value=POKEDEX_ORDER_ARRAYS[0])
        order_combo = ttk.Combobox(top, textvariable=self.pokedex_order_var, values=POKEDEX_ORDER_ARRAYS, state="readonly", width=34)
        order_combo.pack(side="left", padx=(8, 16))
        order_combo.bind("<<ComboboxSelected>>", self.on_pokedex_order_changed)
        self.pokedex_order_count_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.pokedex_order_count_var).pack(side="left")

        controls = ttk.Frame(tab)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.pokedex_order_species_var = tk.StringVar()
        self.pokedex_order_species_combo = ttk.Combobox(controls, textvariable=self.pokedex_order_species_var, values=[], width=34)
        self.pokedex_order_species_combo.pack(side="left")
        ttk.Button(controls, text="Adicionar", command=self.add_pokedex_order_species).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Trocar selecionado", command=self.replace_pokedex_order_species).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Remover selecionado", command=self.remove_pokedex_order_species).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Subir", command=lambda: self.move_pokedex_order_species(-1)).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Descer", command=lambda: self.move_pokedex_order_species(1)).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Aplicar ordem", command=self.apply_pokedex_order_edits).pack(side="right")

        tree_frame = ttk.Frame(tab)
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.pokedex_order_tree = ttk.Treeview(
            tree_frame,
            columns=("order", "species", "name"),
            show="headings",
            selectmode="browse",
        )
        self.pokedex_order_tree.heading("order", text="#")
        self.pokedex_order_tree.heading("species", text="Species")
        self.pokedex_order_tree.heading("name", text="Nome")
        self.pokedex_order_tree.column("order", width=70, stretch=False, anchor="e")
        self.pokedex_order_tree.column("species", width=260, stretch=False)
        self.pokedex_order_tree.column("name", width=220, stretch=True)
        self.pokedex_order_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.pokedex_order_tree.yview)
        self.pokedex_order_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.pokedex_order_tree.bind("<<TreeviewSelect>>", self.on_pokedex_order_row_selected)

    def create_learnset_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Learnset")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        self.learnset_header_var = tk.StringVar(value="Selecione um Pokemon")
        ttk.Label(tab, textvariable=self.learnset_header_var).grid(row=0, column=0, sticky="w", pady=(0, 8))

        toolbar = ttk.Frame(tab)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="Adicionar", command=self.add_learnset_row).pack(side="left")
        ttk.Button(toolbar, text="Remover selecionado", command=self.remove_selected_learnset_row).pack(side="left", padx=(8, 0))
        ttk.Label(toolbar, text="Copiar de").pack(side="left", padx=(18, 4))
        self.learnset_copy_species_var = tk.StringVar()
        self.learnset_copy_species_combo = ttk.Combobox(toolbar, textvariable=self.learnset_copy_species_var, values=[], width=30)
        self.learnset_copy_species_combo.pack(side="left")
        ttk.Button(toolbar, text="Copiar", command=self.copy_learnset_from_selected_species).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Aplicar learnset", command=self.apply_current_edits).pack(side="right")

        self.learnset_canvas = tk.Canvas(tab, borderwidth=0, highlightthickness=0)
        self.learnset_rows_frame = ttk.Frame(self.learnset_canvas)
        self.learnset_scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self.learnset_canvas.yview)
        self.learnset_canvas.configure(yscrollcommand=self.learnset_scrollbar.set)
        self.learnset_window = self.learnset_canvas.create_window((0, 0), window=self.learnset_rows_frame, anchor="nw")
        self.learnset_canvas.grid(row=2, column=0, sticky="nsew")
        self.learnset_scrollbar.grid(row=2, column=1, sticky="ns")
        self.learnset_rows_frame.bind("<Configure>", lambda _event: self.learnset_canvas.configure(scrollregion=self.learnset_canvas.bbox("all")))
        self.learnset_canvas.bind("<Configure>", lambda event: self.learnset_canvas.itemconfigure(self.learnset_window, width=event.width))

        header = ttk.Frame(self.learnset_rows_frame)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(header, text="Lv.", width=8).pack(side="left", padx=(0, 8))
        ttk.Label(header, text="Move").pack(side="left", fill="x", expand=True)
        ttk.Label(tab, text=f"{len(MOVE_OPTIONS)} moves carregados de include/moves.h").grid(row=3, column=0, sticky="w", pady=(8, 0))

    def create_evolution_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Evolução")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        self.evolution_header_var = tk.StringVar(value="Selecione um Pokemon")
        ttk.Label(tab, textvariable=self.evolution_header_var).grid(row=0, column=0, sticky="w", pady=(0, 8))

        toolbar = ttk.Frame(tab)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="Adicionar", command=self.add_evolution_row).pack(side="left")
        ttk.Button(toolbar, text="Remover selecionado", command=self.remove_selected_evolution_row).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Aplicar evolução", command=self.apply_current_edits).pack(side="right")

        self.evolution_canvas = tk.Canvas(tab, borderwidth=0, highlightthickness=0)
        self.evolution_rows_frame = ttk.Frame(self.evolution_canvas)
        self.evolution_scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self.evolution_canvas.yview)
        self.evolution_canvas.configure(yscrollcommand=self.evolution_scrollbar.set)
        self.evolution_window = self.evolution_canvas.create_window((0, 0), window=self.evolution_rows_frame, anchor="nw")
        self.evolution_canvas.grid(row=2, column=0, sticky="nsew")
        self.evolution_scrollbar.grid(row=2, column=1, sticky="ns")
        self.evolution_rows_frame.bind("<Configure>", lambda _event: self.evolution_canvas.configure(scrollregion=self.evolution_canvas.bbox("all")))
        self.evolution_canvas.bind("<Configure>", lambda event: self.evolution_canvas.itemconfigure(self.evolution_window, width=event.width))

        header = ttk.Frame(self.evolution_rows_frame)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        header.columnconfigure(0, weight=2)
        header.columnconfigure(1, weight=1)
        header.columnconfigure(2, weight=2)
        header.columnconfigure(3, weight=1)
        ttk.Label(header, text="Método").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(header, text="Parâmetro").grid(row=0, column=1, sticky="w", padx=(0, 8))
        ttk.Label(header, text="Espécie alvo").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Label(header, text="Extra").grid(row=0, column=3, sticky="w")
        ttk.Label(tab, text=f"{len(EVO_OPTIONS)} métodos carregados de include/evolution.h").grid(row=3, column=0, sticky="w", pady=(8, 0))

    def create_cry_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Cry")
        tab.columnconfigure(1, weight=1)

        self.cry_raw_var = tk.StringVar()
        self.cry_file_var = tk.StringVar()
        self.cry_rom_var = tk.StringVar()

        ttk.Label(tab, text="Tabela .wav").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(tab, textvariable=self.cry_raw_var, state="readonly").grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(tab, text="Arquivo").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(tab, textvariable=self.cry_file_var, state="readonly").grid(row=1, column=1, sticky="ew", pady=4)

        buttons = ttk.Frame(tab)
        buttons.grid(row=2, column=1, sticky="w", pady=(8, 4))
        ttk.Button(buttons, text="Play", command=self.play_current_cry).pack(side="left")
        ttk.Button(buttons, text="Adicionar / trocar .wav", command=self.import_current_cry).pack(side="left", padx=(8, 0))

        ttk.Label(tab, text="Offset ROM").grid(row=3, column=0, sticky="nw", padx=(0, 8), pady=(12, 4))
        ttk.Label(tab, textvariable=self.cry_rom_var, wraplength=640, justify="left").grid(row=3, column=1, sticky="ew", pady=(12, 4))

    def update_cry_fields(self):
        if not hasattr(self, "cry_raw_var"):
            return
        raw = self.data.cries.get_raw(self.current_species)
        self.cry_raw_var.set(raw or "Sem entrada em Cry_Table.c")
        wav_path = cry_symbol_to_wav_path(raw)
        self.cry_file_var.set(os.path.relpath(wav_path, ROOT) if wav_path else "Arquivo .wav nao localizado em audio/")
        _pointer, status = read_rom_offset(raw)
        self.cry_rom_var.set(status if status else "Sem offset bruto do tipo (u8*) 0x... ou (u16*) 0x....")

    def create_files_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Sprites / Arquivos")
        self.front_path_var = tk.StringVar()
        self.back_path_var = tk.StringVar()
        self.icon_path_var = tk.StringVar()
        ttk.Label(tab, text="Front PNG").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(tab, textvariable=self.front_path_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(tab, text="Substituir", command=lambda: self.replace_sprite("front")).grid(row=0, column=2, pady=4)
        ttk.Label(tab, text="Back PNG").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(tab, textvariable=self.back_path_var, state="readonly").grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(tab, text="Substituir", command=lambda: self.replace_sprite("back")).grid(row=1, column=2, pady=4)
        ttk.Label(tab, text="Icon PNG").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(tab, textvariable=self.icon_path_var, state="readonly").grid(row=2, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(tab, text="Importar", command=self.import_icon).grid(row=2, column=2, pady=4)
        ttk.Button(tab, text="Importar sheet 64x64", command=self.import_sprite_sheet).grid(row=3, column=1, sticky="w", padx=8, pady=(8, 4))
        tab.columnconfigure(1, weight=1)

        files = [
            BASE_STATS_FILE,
            FRONT_COORDS_FILE,
            BACK_COORDS_FILE,
            ELEVATION_FILE,
            FRONT_PIC_TABLE_FILE,
            BACK_PIC_TABLE_FILE,
            PALETTE_TABLE_FILE,
            SHINY_PALETTE_TABLE_FILE,
            SPRITE_DATA_HEADER,
            BACKGROUND_IMAGE,
            SHADOW_IMAGE,
            SPECIES_HEADER,
            POKEDEX_HEADER,
            POKEDEX_DATA_FILE,
            SPECIES_TO_DEX_FILE,
            POKEMON_NAMES_FILE,
            POKEDEX_STRINGS_FILE,
            POKEDEX_HOOKS_FILE,
            EVOLUTION_FILE,
            EVOLUTION_HEADER,
            ICON_TABLE_FILE,
            ICON_PALETTE_TABLE_FILE,
            INCLUDE_DIR / "cry_data.h",
            *CRY_TABLE_FILES,
        ]
        ttk.Label(tab, text="Arquivos usados pela ferramenta").grid(row=4, column=0, columnspan=3, sticky="w", pady=(18, 4))
        for idx, path in enumerate(files, start=5):
            ttk.Label(tab, text=os.path.relpath(path, ROOT)).grid(row=idx, column=0, columnspan=3, sticky="w", pady=2)

    def load_species_list(self):
        self.species = self.data.get_species_list()
        self.filtered_species = self.species.copy()
        self.refresh_species_listbox()
        if hasattr(self, "pokedex_order_species_combo"):
            self.pokedex_order_species_combo.configure(values=self.species)
            if not self.pokedex_order_species_var.get() and self.species:
                self.pokedex_order_species_var.set(self.species[0])
            self.load_pokedex_order_table(self.pokedex_order_var.get())
        if hasattr(self, "learnset_copy_species_combo"):
            self.learnset_copy_species_combo.configure(values=self.species)
            if not self.learnset_copy_species_var.get() and self.species:
                self.learnset_copy_species_var.set(self.species[0])
        self.status_var.set(f"{len(self.species)} Pokemon carregados.")

    def refresh_species_listbox(self):
        self.species_tree.delete(*self.species_tree.get_children(""))
        for species in self.filtered_species:
            self.species_tree.insert("", tk.END, iid=species, text=species, values=(self.data.display_name(species),))

    def filter_species(self, *_args):
        term = self.search_var.get().strip().upper()
        if not term:
            self.filtered_species = self.species.copy()
        else:
            self.filtered_species = [s for s in self.species if term in s or term in self.data.display_name(s).upper()]
        self.refresh_species_listbox()

    def on_species_select(self, _event=None):
        selection = self.species_tree.selection()
        if selection:
            self.select_species(selection[0])

    def select_species(self, species):
        if self.current_species:
            if not self.apply_current_edits(silent=True):
                return
        self.current_species = species
        self.current_values = self.data.get_values(species)
        for key, var in self.entry_vars.items():
            var.set(self.current_values.get(key, ""))
        self.update_pokedex_fields()
        self.update_learnset_fields()
        self.update_evolution_fields()
        self.update_cry_fields()
        self.update_sprite_paths()
        self.update_bst()
        self.update_preview()
        self.update_icon_preview()
        self.header_var.set(f"{species} - {self.data.display_name(species)}")
        missing = self.data.missing_edit_targets(species)
        if missing:
            self.status_var.set(f"Editando {species}. Entradas ausentes serao criadas ao salvar: {', '.join(missing)}.")
        else:
            self.status_var.set(f"Editando {species}.")

    def collect_values(self):
        return {key: var.get().strip() for key, var in self.entry_vars.items()}

    def update_pokedex_fields(self):
        if not hasattr(self, "dex_description_text"):
            return
        values = self.data.pokedex.get_values(self.current_species)
        for key, var in self.dex_vars.items():
            var.set(values.get(key, ""))
        self.dex_description_text.delete("1.0", tk.END)
        self.dex_description_text.insert("1.0", values.get("descriptionText", ""))

    def collect_dex_values(self):
        if not hasattr(self, "dex_description_text"):
            return {}
        values = {key: var.get().strip() for key, var in self.dex_vars.items()}
        values["descriptionText"] = self.dex_description_text.get("1.0", "end-1c")
        return values

    def current_pokedex_order_entries(self):
        if not hasattr(self, "pokedex_order_tree"):
            return []
        entries = []
        for item in self.pokedex_order_tree.get_children(""):
            values = self.pokedex_order_tree.item(item, "values")
            if len(values) >= 2:
                entries.append(values[1])
        return entries

    def load_pokedex_order_table(self, array_name):
        if not hasattr(self, "pokedex_order_tree"):
            return
        self.pokedex_order_tree.delete(*self.pokedex_order_tree.get_children(""))
        entries = self.data.pokedex_orders.get_order(array_name)
        for idx, species in enumerate(entries, start=1):
            self.pokedex_order_tree.insert("", tk.END, iid=f"{array_name}:{idx}", values=(idx, species, self.data.display_name(species)))
        self.current_pokedex_order_array = array_name
        self.pokedex_order_count_var.set(f"{len(entries)} Pokémon na lista")

    def refresh_pokedex_order_numbers(self):
        if not hasattr(self, "pokedex_order_tree"):
            return
        for idx, item in enumerate(self.pokedex_order_tree.get_children(""), start=1):
            values = list(self.pokedex_order_tree.item(item, "values"))
            if len(values) >= 3:
                values[0] = idx
                self.pokedex_order_tree.item(item, values=values)
        self.pokedex_order_count_var.set(f"{len(self.pokedex_order_tree.get_children(''))} Pokémon na lista")

    def apply_pokedex_order_edits(self):
        if not hasattr(self, "pokedex_order_tree"):
            return True
        array_name = self.current_pokedex_order_array or self.pokedex_order_var.get()
        self.data.pokedex_orders.set_order(array_name, self.current_pokedex_order_entries())
        self.status_var.set(f"Ordem {array_name} aplicada. Clique em Salvar para gravar.")
        return True

    def on_pokedex_order_changed(self, _event=None):
        self.apply_pokedex_order_edits()
        self.load_pokedex_order_table(self.pokedex_order_var.get())

    def on_pokedex_order_row_selected(self, _event=None):
        selection = self.pokedex_order_tree.selection()
        if not selection:
            return
        values = self.pokedex_order_tree.item(selection[0], "values")
        if len(values) >= 2:
            self.pokedex_order_species_var.set(values[1])

    def add_pokedex_order_species(self):
        species = self.pokedex_order_species_var.get().strip()
        if not species:
            return
        if species not in self.species:
            messagebox.showerror("Species inválida", f"{species} não existe na lista carregada.")
            return
        idx = len(self.pokedex_order_tree.get_children("")) + 1
        self.pokedex_order_tree.insert("", tk.END, values=(idx, species, self.data.display_name(species)))
        self.refresh_pokedex_order_numbers()
        self.apply_pokedex_order_edits()

    def replace_pokedex_order_species(self):
        selection = self.pokedex_order_tree.selection()
        if not selection:
            return
        species = self.pokedex_order_species_var.get().strip()
        if species not in self.species:
            messagebox.showerror("Species inválida", f"{species} não existe na lista carregada.")
            return
        item = selection[0]
        values = list(self.pokedex_order_tree.item(item, "values"))
        order_number = values[0] if values else len(self.pokedex_order_tree.get_children(""))
        self.pokedex_order_tree.item(item, values=(order_number, species, self.data.display_name(species)))
        self.apply_pokedex_order_edits()

    def remove_pokedex_order_species(self):
        selection = self.pokedex_order_tree.selection()
        if not selection:
            return
        self.pokedex_order_tree.delete(selection[0])
        self.refresh_pokedex_order_numbers()
        self.apply_pokedex_order_edits()

    def move_pokedex_order_species(self, delta):
        selection = self.pokedex_order_tree.selection()
        if not selection:
            return
        item = selection[0]
        siblings = list(self.pokedex_order_tree.get_children(""))
        current_idx = siblings.index(item)
        new_idx = current_idx + delta
        if new_idx < 0 or new_idx >= len(siblings):
            return
        self.pokedex_order_tree.move(item, "", new_idx)
        self.pokedex_order_tree.selection_set(item)
        self.refresh_pokedex_order_numbers()
        self.apply_pokedex_order_edits()

    def update_learnset_fields(self):
        if not hasattr(self, "learnset_rows_frame"):
            return
        self.clear_learnset_rows()
        array_name, entries = self.data.learnsets.get_for_species(self.current_species)
        if not array_name:
            self.learnset_header_var.set("Learnset nao encontrado.")
            return
        self.learnset_header_var.set(f"{array_name} - {len(entries)} moves")
        for level, move in entries:
            self.add_learnset_row(level, move)

    def clear_learnset_rows(self):
        for row in self.learnset_rows:
            row["frame"].destroy()
        self.learnset_rows = []
        self.selected_learnset_row = None

    def add_learnset_row(self, level=1, move="MOVE_NONE"):
        if not hasattr(self, "learnset_rows_frame"):
            return
        row_index = len(self.learnset_rows) + 1
        frame = ttk.Frame(self.learnset_rows_frame, padding=(2, 2))
        frame.grid(row=row_index, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)
        level_var = tk.StringVar(value=str(level))
        move_var = tk.StringVar(value=move)
        level_entry = ttk.Entry(frame, textvariable=level_var, width=8)
        level_entry.grid(row=0, column=0, sticky="w", padx=(0, 8), pady=2)
        move_combo = ttk.Combobox(frame, textvariable=move_var, values=MOVE_OPTIONS, width=34)
        move_combo.grid(row=0, column=1, sticky="ew", pady=2)
        name_var = tk.StringVar(value=symbol_to_title(move, "MOVE_"))
        ttk.Label(frame, textvariable=name_var, width=24).grid(row=0, column=2, sticky="w", padx=(8, 0))
        row = {"frame": frame, "level": level_var, "move": move_var, "name": name_var}
        self.learnset_rows.append(row)

        def select_row(_event=None, selected=row):
            self.selected_learnset_row = selected
            for item in self.learnset_rows:
                item["frame"].configure(style="TFrame")
            selected["frame"].configure(style="SelectedLearnset.TFrame")

        def update_name(_event=None):
            name_var.set(symbol_to_title(move_var.get(), "MOVE_"))

        frame.bind("<Button-1>", select_row)
        level_entry.bind("<FocusIn>", select_row)
        move_combo.bind("<FocusIn>", select_row)
        move_combo.bind("<<ComboboxSelected>>", update_name)
        move_combo.bind("<FocusOut>", update_name)
        return row

    def remove_selected_learnset_row(self):
        if not self.selected_learnset_row:
            return
        self.selected_learnset_row["frame"].destroy()
        self.learnset_rows.remove(self.selected_learnset_row)
        self.selected_learnset_row = None
        for idx, row in enumerate(self.learnset_rows, start=1):
            row["frame"].grid_configure(row=idx)

    def copy_learnset_from_selected_species(self):
        source = self.learnset_copy_species_var.get().strip()
        if not source:
            return
        if source not in self.species:
            messagebox.showerror("Learnset", f"Pokemon invalido: {source}")
            return
        if source == self.current_species:
            messagebox.showerror("Learnset", "Selecione outro Pokemon para copiar.")
            return
        _array_name, entries = self.data.learnsets.get_for_species(source)
        if not entries:
            if not messagebox.askyesno("Learnset", f"{source} nao tem moves cadastrados. Limpar learnset atual?"):
                return
        self.clear_learnset_rows()
        for level, move in entries:
            self.add_learnset_row(level, move)
        self.status_var.set(f"Learnset copiado de {source}. Clique em Aplicar learnset ou Salvar para gravar.")

    def collect_learnset_values(self):
        if not hasattr(self, "learnset_rows"):
            return []
        entries = []
        for row in self.learnset_rows:
            level = parse_int(row["level"].get())
            move = row["move"].get().strip()
            if level is None:
                raise ValueError(f"Nivel invalido no learnset: {row['level'].get()}")
            if move not in MOVE_OPTIONS:
                raise ValueError(f"Move invalido no learnset: {move}")
            entries.append((level, move))
        return entries

    def update_evolution_fields(self):
        if not hasattr(self, "evolution_rows_frame"):
            return
        self.clear_evolution_rows()
        entries = self.data.evolutions.get_for_species(self.current_species)
        self.evolution_header_var.set(f"{len(entries)} evoluções cadastradas")
        for method, param, target, extra in entries:
            self.add_evolution_row(method, param, target, extra)

    def clear_evolution_rows(self):
        for row in self.evolution_rows:
            row["frame"].destroy()
        self.evolution_rows = []
        self.selected_evolution_row = None

    def add_evolution_row(self, method="EVO_LEVEL", param="1", target="SPECIES_NONE", extra="0"):
        if not hasattr(self, "evolution_rows_frame"):
            return
        row_index = len(self.evolution_rows) + 1
        frame = ttk.Frame(self.evolution_rows_frame, padding=(2, 2))
        frame.grid(row=row_index, column=0, sticky="ew")
        for column in range(4):
            frame.columnconfigure(column, weight=1)

        method_var = tk.StringVar(value=method)
        param_var = tk.StringVar(value=param)
        target_var = tk.StringVar(value=target)
        extra_var = tk.StringVar(value=extra)

        method_combo = ttk.Combobox(frame, textvariable=method_var, values=EVO_OPTIONS, width=26)
        method_combo.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=2)
        param_entry = ttk.Entry(frame, textvariable=param_var, width=18)
        param_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=2)
        target_combo = ttk.Combobox(frame, textvariable=target_var, values=getattr(self, "species", []), width=30)
        target_combo.grid(row=0, column=2, sticky="ew", padx=(0, 8), pady=2)
        extra_entry = ttk.Entry(frame, textvariable=extra_var, width=18)
        extra_entry.grid(row=0, column=3, sticky="ew", pady=2)

        row = {"frame": frame, "method": method_var, "param": param_var, "target": target_var, "extra": extra_var}
        self.evolution_rows.append(row)

        def select_row(_event=None, selected=row):
            self.selected_evolution_row = selected
            for item in self.evolution_rows:
                item["frame"].configure(style="TFrame")
            selected["frame"].configure(style="SelectedLearnset.TFrame")

        frame.bind("<Button-1>", select_row)
        for widget in (method_combo, param_entry, target_combo, extra_entry):
            widget.bind("<FocusIn>", select_row)
        return row

    def remove_selected_evolution_row(self):
        if not self.selected_evolution_row:
            return
        self.selected_evolution_row["frame"].destroy()
        self.evolution_rows.remove(self.selected_evolution_row)
        self.selected_evolution_row = None
        for idx, row in enumerate(self.evolution_rows, start=1):
            row["frame"].grid_configure(row=idx)
        self.evolution_header_var.set(f"{len(self.evolution_rows)} evoluções cadastradas")

    def collect_evolution_values(self):
        if not hasattr(self, "evolution_rows"):
            return []
        entries = []
        species_options = set(getattr(self, "species", []))
        for row in self.evolution_rows:
            method = row["method"].get().strip()
            param = row["param"].get().strip() or "0"
            target = row["target"].get().strip()
            extra = row["extra"].get().strip() or "0"
            if method not in EVO_OPTIONS:
                raise ValueError(f"Método de evolução inválido: {method}")
            if not target:
                raise ValueError("Espécie alvo vazia na evolução.")
            if species_options and target not in species_options:
                raise ValueError(f"Espécie alvo inválida na evolução: {target}")
            entries.append((method, param, target, extra))
        return entries

    def nudge_value(self, key, delta):
        if key not in self.entry_vars:
            return
        raw = self.entry_vars[key].get().strip() or "0"
        value = parse_int(raw)
        if value is None:
            self.status_var.set(f"Valor invalido em {key}: {raw}")
            return
        value = max(0, value + delta)
        self.entry_vars[key].set(format(value, "#x") if raw.lower().startswith("0x") else str(value))
        self.apply_current_edits()

    def validate_values(self, values):
        for key, value in values.items():
            if value == "":
                continue
            if key in NUMERIC_FIELDS and parse_int(value) is None:
                raise ValueError(f"Valor invalido em {key}: {value}")
        return True

    def apply_current_edits(self, _event=None, silent=False):
        if not self.current_species:
            return True
        values = self.collect_values()
        try:
            self.validate_values(values)
            learnset_values = self.collect_learnset_values()
            evolution_values = self.collect_evolution_values()
            icon_palette_index = parse_int(self.icon_palette_var.get())
            if icon_palette_index not in {0, 1, 2}:
                raise ValueError("O palette index do icon precisa ser 0, 1 ou 2.")
        except ValueError as exc:
            if not silent:
                messagebox.showerror("Entrada invalida", str(exc))
            self.status_var.set(str(exc))
            return False
        self.data.set_values(self.current_species, values)
        self.data.pokedex.set_values(self.current_species, self.collect_dex_values())
        self.data.learnsets.set_for_species(self.current_species, learnset_values)
        self.data.evolutions.set_for_species(self.current_species, evolution_values)
        self.data.icon_palettes.set_index(self.current_species, icon_palette_index)
        self.current_values = values
        self.update_bst()
        self.update_preview()
        self.update_icon_preview()
        if not silent:
            self.status_var.set(f"Valores aplicados para {self.current_species}. Clique em Salvar para gravar nos arquivos.")
        return True

    def update_bst(self):
        total = 0
        for field in BASE_STAT_FIELDS:
            value = parse_int(self.entry_vars[field].get())
            total += value or 0
        self.bst_var.set(str(total))

    def update_sprite_paths(self):
        if not self.current_species:
            self.front_path_var.set("")
            self.back_path_var.set("")
            self.icon_path_var.set("")
            self.icon_palette_var.set("")
            return
        front = self.data.sprite_path(self.current_species, "front")
        back = self.data.sprite_path(self.current_species, "back")
        icon = self.data.icon_path(self.current_species)
        self.front_path_var.set(os.path.relpath(front, ROOT) if front else "Nao encontrado")
        self.back_path_var.set(os.path.relpath(back, ROOT) if back else "Nao encontrado")
        self.icon_path_var.set(os.path.relpath(icon, ROOT) if icon else "Nao encontrado")
        palette_index = parse_int(self.data.icon_palette(self.current_species))
        self.icon_palette_var.set(str(palette_index) if palette_index in {0, 1, 2} else "0")

    def replace_sprite(self, side):
        if not self.current_species:
            messagebox.showwarning("Nenhum Pokemon", "Selecione um Pokemon antes.")
            return
        target = self.data.sprite_path(self.current_species, side)
        if not target:
            messagebox.showerror("Sprite nao encontrado", f"Nao encontrei o PNG {side} deste Pokemon.")
            return
        source = filedialog.askopenfilename(
            title=f"Selecionar novo sprite {side}",
            filetypes=[("PNG", "*.png"), ("Todos os arquivos", "*.*")],
        )
        if not source:
            return
        ensure_backup(target)
        shutil.copy2(source, target)
        self.photo_refs.clear()
        self.update_preview()
        self.status_var.set(f"Sprite {side} substituido: {os.path.relpath(target, ROOT)}")

    def import_sprite_sheet(self):
        if not self.current_species:
            messagebox.showwarning("Nenhum Pokemon", "Selecione um Pokemon antes.")
            return
        source = filedialog.askopenfilename(
            title="Selecionar spritesheet 64x64",
            filetypes=[("PNG", "*.png"), ("Todos os arquivos", "*.*")],
        )
        if not source:
            return
        try:
            front_path, back_path = import_external_sprite_sheet(self.current_species, source)
            self.data.front_sprites.load()
            self.data.back_sprites.load()
            self.update_sprite_paths()
            self.photo_refs.clear()
            self.update_preview()
            self.status_var.set(
                "Sprites importados: "
                f"{os.path.relpath(front_path, ROOT)} / {os.path.relpath(back_path, ROOT)}"
            )
        except Exception as exc:
            messagebox.showerror("Erro ao importar spritesheet", str(exc))

    def import_icon(self):
        if not self.current_species:
            messagebox.showwarning("Nenhum Pokemon", "Selecione um Pokemon antes.")
            return
        source = filedialog.askopenfilename(
            title="Selecionar pokemon icon 32x64",
            filetypes=[("PNG", "*.png"), ("Todos os arquivos", "*.*")],
        )
        if not source:
            return
        palette_index = simpledialog.askinteger(
            "Paleta do icon",
            "Digite o index da paleta do icon (0, 1 ou 2):",
            parent=self.root,
            minvalue=0,
            maxvalue=2,
        )
        if palette_index is None:
            return
        try:
            target = import_external_icon(self.current_species, source, palette_index)
            self.data.icons.load()
            self.data.icon_palettes = IconPaletteData()
            self.update_sprite_paths()
            self.photo_refs.clear()
            self.update_icon_preview()
            self.status_var.set(
                f"Icone importado: {os.path.relpath(target, ROOT)} com paleta {palette_index}."
            )
        except Exception as exc:
            messagebox.showerror("Erro ao importar icon", str(exc))

    def play_current_cry(self):
        raw = self.data.cries.get_raw(self.current_species)
        wav_path = cry_symbol_to_wav_path(raw)
        if not wav_path:
            messagebox.showwarning("Cry nao encontrado", "Nao ha arquivo .wav em audio/ para este cry.")
            return
        try:
            play_wav_file(wav_path)
            self.status_var.set(f"Tocando {os.path.relpath(wav_path, ROOT)}")
        except Exception as exc:
            messagebox.showerror("Erro ao tocar cry", str(exc))

    def import_current_cry(self):
        if not self.current_species:
            messagebox.showwarning("Nenhum Pokemon", "Selecione um Pokemon antes.")
            return
        source = filedialog.askopenfilename(
            title="Selecionar cry .wav",
            filetypes=[("WAV", "*.wav"), ("Todos os arquivos", "*.*")],
        )
        if not source:
            return
        try:
            symbol, target = import_cry_file(self.current_species, source)
            self.data.cries.set_symbol(self.current_species, symbol)
            self.update_cry_fields()
            self.status_var.set(f"Cry importado: {os.path.relpath(target, ROOT)}. Clique em Salvar para gravar a tabela.")
        except Exception as exc:
            messagebox.showerror("Erro ao importar cry", str(exc))

    def open_new_species_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Adicionar novo Pokémon")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)
        ttk.Label(dialog, text="Nome / macro").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=36).grid(row=0, column=1, sticky="ew", padx=10, pady=(10, 4))
        ttk.Label(dialog, text="Categoria Pokédex").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        category_var = tk.StringVar(value="Unknown")
        ttk.Entry(dialog, textvariable=category_var, width=36).grid(row=1, column=1, sticky="ew", padx=10, pady=4)

        dex_mode_var = tk.StringVar(value="new")
        existing_dex_var = tk.StringVar()
        dex_options = pokedex_define_options()
        if dex_options:
            existing_dex_var.set(dex_options[0])

        dex_frame = ttk.LabelFrame(dialog, text="Pokédex", padding=8)
        dex_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=4)
        dex_frame.columnconfigure(1, weight=1)
        ttk.Radiobutton(dex_frame, text="Adicionar nova entry", variable=dex_mode_var, value="new").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Radiobutton(dex_frame, text="Usar dex_entry existente", variable=dex_mode_var, value="existing").grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        existing_dex_combo = ttk.Combobox(dex_frame, textvariable=existing_dex_var, values=dex_options, state="readonly", width=34)
        existing_dex_combo.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))

        ttk.Label(dialog, text="Cria entradas padrão em species.h, Base_Stats, coords, elevação e tabelas necessárias.").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=10, pady=(4, 10)
        )

        buttons = ttk.Frame(dialog)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", padx=10, pady=(0, 10))

        def create():
            try:
                raw_name = name_var.get()
                species = normalize_species_name(raw_name)
                if species in self.data.get_species_list():
                    raise ValueError(f"{species} ja existe.")
                add_new_species_files(
                    species,
                    category_var.get().strip() or "Unknown",
                    display_name_from_user_input(raw_name, species),
                    dex_mode_var.get(),
                    existing_dex_var.get().strip(),
                )
                self.reload_data()
                self.search_var.set(species)
                self.select_species(species)
                self.species_tree.selection_set(species)
                self.species_tree.see(species)
                dialog.destroy()
                self.status_var.set(f"{species} criado. Revise stats, Pokédex e sprites antes de compilar.")
            except Exception as exc:
                messagebox.showerror("Erro ao criar Pokémon", str(exc), parent=dialog)

        ttk.Button(buttons, text="Cancelar", command=dialog.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Criar", command=create).pack(side="right")

    def save_all(self):
        if self.current_species and not self.apply_current_edits(silent=True):
            return
        self.apply_pokedex_order_edits()
        try:
            self.data.save()
        except Exception as exc:
            messagebox.showerror("Erro ao salvar", str(exc))
            self.status_var.set("Falha ao salvar.")
            return
        self.status_var.set("Arquivos salvos. Backups .bak foram criados quando necessario.")
        messagebox.showinfo("Salvo", "Arquivos salvos com sucesso.")

    def reload_data(self):
        try:
            selected = self.current_species
            self.data = PokemonData()
            self.load_species_list()
            self.current_species = None
            self.current_values = {}
            if selected in self.species:
                self.select_species(selected)
            else:
                for var in self.entry_vars.values():
                    var.set("")
                self.update_preview()
                self.update_icon_preview()
        except Exception as exc:
            messagebox.showerror("Erro", f"Falha ao recarregar: {exc}")

    def apply_color_key_transparency(self, photo):
        try:
            transparent_color = photo.get(0, 0)
        except tk.TclError:
            return photo
        width = photo.width()
        height = photo.height()
        try:
            for y in range(height):
                for x in range(width):
                    if photo.get(x, y) == transparent_color:
                        try:
                            photo.put("", (x, y))
                        except tk.TclError:
                            pass
        except tk.TclError:
            return photo

        return photo

    def pil_photo_with_color_key(self, path, scale=1, crop_box=None):
        if Image is None or ImageTk is None:
            return None
        try:
            image = Image.open(path).convert("RGBA")
            if crop_box:
                image = image.crop(crop_box)
            transparent_color = image.getpixel((0, 0))
            pixels = []
            for pixel in image.getdata():
                if pixel == transparent_color:
                    pixels.append((pixel[0], pixel[1], pixel[2], 0))
                else:
                    pixels.append(pixel)
            image.putdata(pixels)
            if scale > 1:
                resample = getattr(getattr(Image, "Resampling", Image), "NEAREST")
                image = image.resize((image.width * scale, image.height * scale), resample)
            return ImageTk.PhotoImage(image)
        except Exception:
            return None

    def load_photo(self, key, path, scale=1, color_key=False):
        if not path or not Path(path).exists():
            return None
        cache_key = (key, str(path), scale, color_key, Path(path).stat().st_mtime)
        if cache_key in self.photo_refs:
            return self.photo_refs[cache_key]
        try:
            if color_key:
                photo = self.pil_photo_with_color_key(path, scale=scale)
                if photo is None:
                    photo = tk.PhotoImage(file=str(path))
                    photo = self.apply_color_key_transparency(photo)
                    if scale > 1:
                        photo = photo.zoom(scale, scale)
            else:
                photo = tk.PhotoImage(file=str(path))
                if scale > 1:
                    photo = photo.zoom(scale, scale)
            self.photo_refs[cache_key] = photo
            return photo
        except tk.TclError:
            return None

    def load_icon_frame_photo(self, path, frame_index):
        if not path or not Path(path).exists():
            return None
        cache_key = ("icon_frame", str(path), frame_index, Path(path).stat().st_mtime)
        if cache_key in self.photo_refs:
            return self.photo_refs[cache_key]
        try:
            if Image is not None:
                with Image.open(path) as image:
                    frame_height = 32 if image.height >= 64 else image.height
                    frame_width = min(32, image.width)
                    y0 = frame_height * frame_index if image.height >= frame_height * (frame_index + 1) else 0
                photo = self.pil_photo_with_color_key(path, scale=2, crop_box=(0, y0, frame_width, y0 + frame_height))
                if photo:
                    self.photo_refs[cache_key] = photo
                    return photo

            source = tk.PhotoImage(file=str(path))
            frame_height = 32 if source.height() >= 64 else source.height()
            frame_width = min(32, source.width())
            y0 = frame_height * frame_index if source.height() >= frame_height * (frame_index + 1) else 0
            cropped = tk.PhotoImage(width=frame_width, height=frame_height)
            cropped.tk.call(cropped, "copy", source, "-from", 0, y0, frame_width, y0 + frame_height, "-to", 0, 0)
            cropped = self.apply_color_key_transparency(cropped)
            if frame_width <= 32 and frame_height <= 32:
                cropped = cropped.zoom(2, 2)
            self.photo_refs[cache_key] = cropped
            return cropped
        except tk.TclError:
            return None

    def update_icon_preview(self):
        if not hasattr(self, "icon_preview_canvas"):
            return
        if self.icon_animation_job is not None:
            self.root.after_cancel(self.icon_animation_job)
            self.icon_animation_job = None

        canvas = self.icon_preview_canvas
        canvas.delete("all")
        if not self.current_species:
            self.icon_preview_info_var.set("Sem icone")
            return

        icon_path = self.data.icon_path(self.current_species)
        palette = self.data.icon_palette(self.current_species) or "Sem entrada"
        if not icon_path:
            canvas.create_text(36, 36, text="Icon\nnao encontrado", fill="#ffffff", justify="center")
            self.icon_preview_info_var.set(f"Paleta: {palette}")
            return

        photo = self.load_icon_frame_photo(icon_path, self.icon_frame)
        if photo:
            canvas.create_image(36, 36, image=photo, anchor="center")
        else:
            canvas.create_text(36, 36, text="Erro\nao abrir", fill="#ffffff", justify="center")
        self.icon_preview_info_var.set(f"Paleta: {palette}\nFrame: {self.icon_frame}")
        self.icon_frame = 1 - self.icon_frame
        self.icon_animation_job = self.root.after(500, self.update_icon_preview)

    def coord_parts(self, key):
        raw = self.current_values.get(key, "0")
        value = parse_int(raw) or 0
        return (value >> 4) & 0xF, value & 0xF

    def preview_number(self, key):
        return parse_int(self.current_values.get(key, "0")) or 0

    def update_preview(self):
        if not hasattr(self, "preview_canvas"):
            return
        canvas = self.preview_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)
        scale = max(1, self.preview_scale.get())

        bg = self.load_photo("bg", BACKGROUND_IMAGE, scale=1)
        if bg:
            x = (width - bg.width()) // 2
            y = (height - bg.height()) // 2
            canvas.create_image(x, y, image=bg, anchor="nw")
            origin_x, origin_y = x, y
            bg_w, bg_h = bg.width(), bg.height()
        else:
            origin_x, origin_y = width // 2 - 120, height // 2 - 80
            bg_w, bg_h = 240, 160
            canvas.create_rectangle(origin_x, origin_y, origin_x + bg_w, origin_y + bg_h, fill="#456878", outline="")

        if self.show_guides.get():
            canvas.create_rectangle(origin_x, origin_y, origin_x + bg_w, origin_y + bg_h, outline="#ffffff", dash=(3, 3))
            canvas.create_line(origin_x, origin_y + bg_h - 34, origin_x + bg_w, origin_y + bg_h - 34, fill="#90d090", dash=(2, 4))
            canvas.create_line(origin_x, origin_y + 72, origin_x + bg_w, origin_y + 72, fill="#d0d090", dash=(2, 4))

        if not self.current_species:
            canvas.create_text(width // 2, height // 2, text="Selecione um Pokemon", fill="#ffffff", font=("TkDefaultFont", 16, "bold"))
            return

        front_path = self.data.sprite_path(self.current_species, "front")
        back_path = self.data.sprite_path(self.current_species, "back")
        front = self.load_photo("front", front_path, scale=scale, color_key=True)
        back = self.load_photo("back", back_path, scale=scale, color_key=True)
        shadow = self.load_photo("shadow", SHADOW_IMAGE, scale=scale, color_key=True)

        front_y_offset = self.preview_number("front_y_offset")
        back_y_offset = self.preview_number("back_y_offset")
        elevation = self.preview_number("elevation")
        front_w_tiles, front_h_tiles = self.coord_parts("front_size")
        back_w_tiles, back_h_tiles = self.coord_parts("back_size")

        enemy_top_y = origin_y + 10 * scale
        player_top_y = origin_y + 48 * scale
        enemy_x = origin_x + 176 * scale
        player_x = origin_x + int(bg_w * 0.25)

        if elevation >= 1 and shadow:
            canvas.create_image(enemy_x, origin_y + 64 * scale, image=shadow, anchor="center")

        if front:
            sprite_x = enemy_x - front.width() // 2
            sprite_y = enemy_top_y + (front_y_offset - elevation) * scale
            canvas.create_image(sprite_x, sprite_y, image=front, anchor="nw")
        else:
            canvas.create_text(enemy_x, enemy_top_y + 32, text="Front PNG\nnao encontrado", fill="#ffffff", justify="center")

        if back:
            sprite_x = player_x - back.width() // 2
            sprite_y = player_top_y + back_y_offset * scale
            canvas.create_image(sprite_x, sprite_y, image=back, anchor="nw")
        else:
            canvas.create_text(player_x, player_top_y + 32, text="Back PNG\nnao encontrado", fill="#ffffff", justify="center")

        info = [
            self.current_species,
            f"Front size {front_w_tiles}x{front_h_tiles}, y top+10 {front_y_offset}, elev {elevation}",
            f"Back size {back_w_tiles}x{back_h_tiles}, y top+48 {back_y_offset}",
        ]
        text_x = origin_x + 8
        text_y = max(4, origin_y - 54)
        for line in info:
            canvas.create_text(text_x + 1, text_y + 1, text=line, anchor="nw", fill="#000000", font=("Consolas", 10))
            canvas.create_text(text_x, text_y, text=line, anchor="nw", fill="#ffffff", font=("Consolas", 10))
            text_y += 16


def main():
    try:
        validate_project_layout()
        root = tk.Tk()
        PokemonEditorApp(root)
        root.mainloop()
    except Exception as exc:
        try:
            messagebox.showerror("Erro critico", str(exc))
        except tk.TclError:
            print(f"Erro critico: {exc}")


if __name__ == "__main__":
    main()
