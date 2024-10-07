import re
from collections import Counter
from typing import NamedTuple, Protocol, runtime_checkable
from math import gcd

from aider.coders.cedar_parser import Marker, RelativeMarker, RelativePositionType, Segment, MarkerType, BodyOrWhole

MATCH_TYPES = ('exact', 'stripped', 'normalized', 'partial')

class MarkerMatchResult(NamedTuple):
    match_type: str
    index: int
    indent: int

    def __str__(self):
        return f"{self.match_type.lower()} @ {self.index} ({self.indent})"


class IndexBoundaries(NamedTuple):
    start: MarkerMatchResult
    end: MarkerMatchResult


class SearchRange(NamedTuple):
    start: int
    end: int
    indent: int = 0


class FunctionBoundaries(NamedTuple):
    whole: SearchRange
    body: SearchRange
    # TODO Derive these 3 attrs from search ranges below

    @property
    def start_line(self) -> int:
        return self.whole.start + 1

    @property
    def body_start_line(self) -> int:
        return self.body.start + 1

    @property
    def end_line(self) -> int:
        return self.whole.end


def read_file(file_path: str) -> str:
    with open(file_path, 'r') as file:
        return file.read()


def write_file(file_path: str, lines: list[str]):
    with open(file_path, 'w') as file:
        file.writelines([line + '\n' for line in lines])

class IndentationInfo(NamedTuple):
    char_count: int
    char: str
    min_indent_level: int
    consistency: bool = True
    message: str | None = None

    def level_difference(self, base_indentation_count: int):
        return self.char_count_to_level(base_indentation_count) - self.min_indent_level

    def char_count_to_level(self, char_count: int) -> int:
        return char_count // self.char_count

    def level_to_chars(self, level: int) -> str:
        return level * self.char_count * self.char

    def adjust_indentation(self, lines: list[str], base_indentation_count: int) -> list[str]:
        line_adjuster = self._adjust_indentation_fun(base_indentation_count)
        # Return the transformed lines
        return [line_adjuster(line) for line in lines]

    def _adjust_indentation_fun(self, base_indentation_count: int):
        # Calculate the indentation difference
        level_difference = self.level_difference(base_indentation_count)

        def adjust_line(line: str) -> str:
            if not line.strip():
                # Handle empty lines or lines with only whitespace
                return line

            current_indent = get_line_indent_count(line)
            current_level = self.char_count_to_level(current_indent)
            new_level = max(0, current_level + level_difference)
            new_indent = self.level_to_chars(new_level)

            return new_indent + line.lstrip()
        return adjust_line

def get_line_indent_count(line: str):
    return len(line) - len(line.lstrip())

def count_leading_chars(line: str, char: str) -> int:
    return len(line) - len(line.lstrip(char))


def normalize_line(line: str):
    return re.sub(r'[^\w]', '.', line.strip(), flags=re.UNICODE)


def bow_to_search_range(bow: BodyOrWhole, searh_range: FunctionBoundaries | SearchRange | None = None, lines: list[str] | None = None) -> SearchRange:
    match searh_range:

        case SearchRange() | None:
            return searh_range or SearchRange(0, -1, 0)

        case FunctionBoundaries() as function_boundaries:
            match bow:
                case BodyOrWhole.BODY:
                    return function_boundaries.body
                case BodyOrWhole.WHOLE:
                    return function_boundaries.whole
                case _ as invalid:
                    raise ValueError(f"Invalid: {invalid}")

        case _ as invalid:
            raise ValueError(f"Invalid: {invalid}")


# MarkerOrSegment

# class MarkerOrSegmentProtocol(Protocol):
#     def marker_or_segment_to_index_range(self) -> str:
#         ...


@runtime_checkable
class MarkerOrSegmentProtocol(Protocol):
    def marker_or_segment_to_index_range(
        self,
        lines: list[str],
        search_start_index: int = 0, search_end_index: int = -1
    ) -> SearchRange:
        ...


def marker_or_segment_to_index_range_impl(
    self,
    lines: list[str],
    search_start_index: int = 0, search_end_index: int = -1
) -> SearchRange | None:
    match self:
        case Marker(type=MarkerType.LINE):
            result = find_line_index_and_indent(lines, self, search_start_index, search_end_index)
            assert result, f"Unable to find `{self}`; Try: 1) Double-checking the marker (maybe you specified the the wrong one); or 2) using *exactly* the same characters from source; or 3) using another marker"
            return SearchRange(result.index, result.index + 1, result.indent)
        case Segment(start=s, end=e):
            result = segment_to_indexes(lines, s, e, search_start_index, search_end_index)
            return SearchRange(result.start.index, result.end.index, result.start.indent)
        case _ as invalid:
            raise ValueError(f"Unexpected type: {invalid}")


Marker.marker_or_segment_to_index_range = marker_or_segment_to_index_range_impl
Segment.marker_or_segment_to_index_range = marker_or_segment_to_index_range_impl


def find_line_index_and_indent(
    lines: list[str],
    search_term: Marker | RelativeMarker,
    search_start_index: int = 0, search_end_index: int = -1
) -> MarkerMatchResult | None:
    """
    Find the index of a specified line within a list of strings, considering different match types and an offset.

    This function searches for a given line within a list, considering 4 types of matches in order of priority:
    1. Exact match
    2. Stripped match (ignoring leading and trailing whitespace)
    3. Normalized match (ignoring non-alphanumeric characters)
    4. Partial (Searching for a substring, using `casefold` to ignore upper- and lower-case differences.

    The function applies the offset across all match types while maintaining the priority order.

    :Args:
        :param lines: The list of strings to search through.
        :param search_term:
            search_marker.value: The line to search for.
            search_marker.offset: The number of matches to skip before returning a result.
                      0 skips no match and returns the first match, 1 returns the second match, and so on.
        :param search_start_index: The index to start the search from. Defaults to 0.
        :param search_end_index: The index to end the search at (exclusive).
                                          Defaults to -1, which means search to the end of the list.

    :returns:
        MarkerMatchResult: The index for the desired line in the 'lines' list.
             Returns None if no match is found or if the offset exceeds the number of matches within each category.

    :Example:
        >> lines = ["Hello, world!", "  Hello, world!  ", "Héllo, wörld?", "Another line", "Hello, world!"]
        >> _find_line_index(lines, "Hello, world!", 1)
        4  # Returns the index of the second exact match

    Note:
        - The function prioritizes match types in the order: exact, stripped, normalized, partial.
        - The offset is considered separately for each type.
    """
    search_line = search_term.value
    assert search_line, "Empty marker"
    assert search_term.type == MarkerType.LINE, f"Invalid marker type: {search_term.type}"

    matches = {t: [] for t in MATCH_TYPES}

    stripped_search = search_line.strip()
    normalized_search_line = normalize_line(stripped_search)

    if search_start_index < 0:
        search_start_index = 0
    if search_end_index < 0:
        search_end_index = len(lines)

    assert search_start_index < len(lines), f"search start index ({search_start_index}) must be less than line count ({len(lines)})"
    assert search_end_index <= len(lines), f"search end index ({search_end_index}) must be less than or equal to line count ({len(lines)})"

    for i in range(search_start_index, search_end_index):
        line = lines[i]
        reference_indent = get_line_indent_count(line)

        # Check for exact match
        if search_line == line:
            matches['exact'].append((i, reference_indent))

        # Check for stripped match
        elif stripped_search == line.strip():
            matches['stripped'].append((i, reference_indent))

        # Check for normalized match
        elif normalized_search_line == normalize_line(line):
            matches['normalized'].append((i, reference_indent))

        # Last resort!
        elif normalized_search_line.casefold() in normalize_line(line).casefold():
            matches['partial'].append((i, reference_indent))

    offset = search_term.offset or 0
    for match_type in MATCH_TYPES:
        if offset < len(matches[match_type]):
            index, reference_indent = matches[match_type][offset]
            match match_type:
                case 'normalized':
                    print(f'Note: using {match_type} match for {search_term}')
                case 'partial':
                    print(f"Note: Won't accept {match_type} match at index {index} for {search_term}")
                    continue
            if isinstance(search_term, RelativeMarker):
                match search_term.qualifier:
                    case RelativePositionType.BEFORE:
                        index += -1
                    case RelativePositionType.AFTER:
                        index += 1
                    case RelativePositionType.AT:
                        pass
                    case _ as invalid:
                        raise ValueError(f"Not implemented: {invalid}")
            return MarkerMatchResult(match_type, index, reference_indent)

    return None


def segment_to_indexes(
    lines: list[str],
    start_relpos: RelativeMarker, end_relpos: RelativeMarker,
    search_start_index: int = 0, search_end_index: int = -1
) -> IndexBoundaries:
    assert len(lines), "`lines` is empty"

    start_match_result = find_line_index_and_indent(lines, start_relpos, search_start_index, search_end_index)
    assert start_match_result, f"Unable to find segment start \"{start_relpos}\"; Try: 1) Double-checking the marker (maybe you specified the the wrong one); or 2) using *exactly* the same characters from source; or 3) using a marker from above"

    end_match_result = find_line_index_and_indent(lines, end_relpos, start_match_result.index, search_end_index)
    if end_match_result:
        if end_match_result.index > -1:
            end_match_result = end_match_result._replace(index=end_match_result.index+1)
    assert end_match_result, f"Unable to find segment end \"{end_relpos}\" - Try: 1) using *exactly* the same characters from source; or 2) using a marker from below"
    return IndexBoundaries(start_match_result, end_match_result)


def normalize_indent(content: str, context_indent_count: int = 0, indentation_info: IndentationInfo | None = None) -> list[str]:
    # TODO Always send str?
    lines = [line.lstrip() for line in content.splitlines() if line.strip()] if isinstance(content, str) else content

    context_indent_level = indentation_info.char_count_to_level(context_indent_count)
    for i in range(len(lines)):
        line = lines[i]
        parts = line.split(':', 1)
        if len(parts) == 2 and parts[0].startswith('@'):
            relative_indent_level = int(parts[0][1:])
            absolute_indent_level = context_indent_level + relative_indent_level
            assert absolute_indent_level >= 0, f"Final indentation for line `{line.strip()}` cannot be negative ({absolute_indent_level})"
            lines[i] = indentation_info.level_to_chars(absolute_indent_level) + parts[1].lstrip()
        else:
            absolute_indent_level = context_indent_level
            lines[i] = indentation_info.level_to_chars(absolute_indent_level) + line.lstrip()

    return lines

def analyze_indentation(lines: list[str]) -> IndentationInfo:

    def extract_indentation(line: str) -> str:
        return re.match(r'^\s*', line).group(0)

    indentations = [extract_indentation(line) for line in lines if line.strip()]

    if not indentations:
        return IndentationInfo(4, ' ', 0, True, "No indentation found. Assuming 4 spaces (PEP 8).")

    indent_chars = Counter(indent[0] for indent in indentations if indent)
    dominant_char = ' ' if indent_chars.get(' ', 0) >= indent_chars.get('\t', 0) else '\t'

    indent_lengths = [len(indent) for indent in indentations]

    if dominant_char == '\t':
        char_count = 1
    else:
        # For spaces, determine the most likely char_count
        space_counts = [len for len in indent_lengths if len % 2 == 0 and len > 0]
        if not space_counts:
            char_count = 2  # Default to 2 if no even space counts
        else:
            # Sort top 5 space counts and find the largest GCD
            sorted_counts = sorted([c[0] for c in Counter(space_counts).most_common(5)], reverse=True)
            char_count = sorted_counts[0]
            for i in range(1, len(sorted_counts)):
                new_gcd = gcd(char_count, sorted_counts[i])
                if new_gcd <= 1:
                    break
                char_count = new_gcd

    min_indent_chars = min(indent_lengths) if indent_lengths else 0
    min_indent_level = min_indent_chars // char_count

    consistency = all(len(indent) % char_count == 0 for indent in indentations if indent)
    match dominant_char:
        case ' ':
            domcharstr = 'space'
        case '\t':
            domcharstr = 'tab'
        case _:
            domcharstr = dominant_char
    message = f"Found {char_count}-{domcharstr} indentation"
    if not consistency:
        message += " (inconsistent)"

    return IndentationInfo(char_count, dominant_char, min_indent_level, consistency, message)
