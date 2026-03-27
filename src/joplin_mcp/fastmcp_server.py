"""FastMCP-based Joplin MCP Server Implementation.

📝 FINDING NOTES:
- find_notes(query, limit, offset, task, completed) - Find notes by text OR list all notes with pagination ⭐ MAIN FUNCTION FOR TEXT SEARCHES AND LISTING ALL NOTES!
- find_notes_with_tag(tag_name, limit, offset, task, completed) - Find all notes with a specific tag with pagination ⭐ MAIN FUNCTION FOR TAG SEARCHES!
- find_notes_in_notebook(notebook_name, limit, offset, task, completed) - Find all notes in a specific notebook with pagination ⭐ MAIN FUNCTION FOR NOTEBOOK SEARCHES!
- get_all_notes() - Get all notes, most recent first (simple version without pagination)

📋 MANAGING NOTES:
- create_note(title, notebook_name, body) - Create a new note
- get_note(note_id) - Get a specific note by ID with smart display (sections, line ranges, TOC)
- get_links(note_id) - Extract all links to other notes from a note
- update_note(note_id, title, body) - Update an existing note
- delete_note(note_id) - Delete a note

📖 SEQUENTIAL READING (for long notes):
- get_note(note_id, start_line=1) - Start reading from line 1 (default: 50 lines)
- get_note(note_id, start_line=51) - Continue from line 51
- get_note(note_id, start_line=1, line_count=100) - Get specific number of lines

🏷️ MANAGING TAGS:
- list_tags() - List all available tags
- tag_note(note_id, tag_name) - Add a tag to a note
- untag_note(note_id, tag_name) - Remove a tag from a note
- bulk_tag_notes(note_ids, tag_names) - Apply multiple tags to multiple notes
- get_tags_by_note(note_id) - See what tags a note has

📁 MANAGING NOTEBOOKS:
- list_notebooks() - List all available notebooks
- create_notebook(title) - Create a new notebook
"""

import os
import logging
import datetime
import time
import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, TypeVar, Union, Annotated
from enum import Enum
from functools import wraps

import diff_match_patch as dmp_module

# FastMCP imports
from fastmcp import FastMCP, Context

# Pydantic imports for proper Field annotations
from pydantic import Field
from typing_extensions import Annotated

from joppy.client_api import ClientApi
import joppy.data_types

# Import our existing configuration for compatibility
from joplin_mcp.config import JoplinMCPConfig
from joplin_mcp import __version__ as MCP_VERSION

# Configure logging
logger = logging.getLogger(__name__)

# Create FastMCP server instance with session configuration
mcp = FastMCP(
    name="Joplin MCP Server",
    version=MCP_VERSION
)

# Type for generic functions
T = TypeVar('T')

# Global config instance for tool registration
_config: Optional[JoplinMCPConfig] = None

# Load configuration at module level for tool filtering
def _load_module_config() -> JoplinMCPConfig:
    """Load configuration at module level for tool registration filtering."""
    from pathlib import Path
    
    # Use the built-in auto-discovery that checks standard global config locations
    # This includes: ~/.joplin-mcp.json, ~/.config/joplin-mcp/config.json, etc.
    logger.info("Auto-discovering Joplin MCP configuration...")
    
    try:
        config = JoplinMCPConfig.auto_discover()
        
        # Check if a config file was actually found vs. using defaults
        for path in JoplinMCPConfig.get_default_config_paths():
            if path.exists():
                logger.info(f"Successfully loaded configuration from: {path}")
                break
        else:
            # Also check current directory (for development)
            cwd = Path.cwd()
            local_paths = [
                cwd / "joplin-mcp.json",
                cwd / "joplin-mcp.yaml",
                cwd / "joplin-mcp.yml"
            ]
            
            for path in local_paths:
                if path.exists():
                    logger.info(f"Successfully loaded configuration from: {path}")
                    break
            else:
                logger.warning("No configuration file found. Using environment variables and defaults.")
        
        return config
        
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        logger.warning("Falling back to default configuration.")
        return JoplinMCPConfig()

# Load config for tool registration filtering
_module_config = _load_module_config()

# Enums for type safety
class SortBy(str, Enum):
    title = "title"
    created_time = "created_time"
    updated_time = "updated_time"
    relevance = "relevance"

class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"

class ItemType(str, Enum):
    note = "note"
    notebook = "notebook"
    tag = "tag"

# === PYDANTIC VALIDATION TYPES ===

def flexible_bool_converter(value: Union[bool, str, None]) -> Optional[bool]:
    """Convert various string representations to boolean for API compatibility."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        value_lower = value.lower().strip()
        if value_lower in ('true', '1', 'yes', 'on'):
            return True
        elif value_lower in ('false', '0', 'no', 'off'):
            return False
        else:
            raise ValueError("Must be a boolean value or string representation (true/false, 1/0, yes/no, on/off)")
    # Handle other truthy/falsy values
    return bool(value)

def convert_todo_completed(value: Union[bool, str, int, None]) -> tuple[Optional[int], Optional[str]]:
    """Convert todo_completed input to Joplin API epoch-ms timestamp.

    Accepts: True/False, epoch milliseconds, ISO datetime string ('YYYY-MM-DD HH:MM' or 'YYYY-MM-DD').
    Returns: (api_value, warning_message) tuple.
    """
    if value is None:
        return (None, None)

    # Boolean: True = now, False = not completed
    if isinstance(value, bool):
        return (int(time.time() * 1000) if value else 0, None)

    # String: check for bool strings first, then ISO datetime
    if isinstance(value, str):
        value_stripped = value.strip()
        value_lower = value_stripped.lower()
        if value_lower in ('true', 'yes', 'on'):
            return (int(time.time() * 1000), None)
        if value_lower in ('false', 'no', 'off'):
            return (0, None)
        # Try ISO datetime parse
        try:
            dt = datetime.datetime.fromisoformat(value_stripped)
            return (int(dt.timestamp() * 1000), None)
        except ValueError:
            raise ValueError(
                f"Unrecognized todo_completed format: '{value}'. "
                "Accepts: True/False, epoch milliseconds, or ISO datetime 'YYYY-MM-DD HH:MM' / 'YYYY-MM-DD'"
            )

    # Integer: large = epoch ms passthrough, small = warn
    if isinstance(value, (int, float)):
        int_value = int(value)
        if int_value == 0:
            return (0, None)
        if int_value >= 1_000_000_000_000:
            return (int_value, None)
        # Small positive int — likely a mistake
        return (int_value, f"WARNING: todo_completed={int_value} interpreted as {int_value}ms since epoch (1970-01-01). Did you mean True?")

    raise ValueError(
        f"Invalid todo_completed type: {type(value).__name__}. "
        "Accepts: True/False, epoch milliseconds, or ISO datetime 'YYYY-MM-DD HH:MM' / 'YYYY-MM-DD'"
    )

def validate_joplin_id(note_id: str) -> str:
    """Validate that a string is a proper Joplin note ID (32 hex characters)."""
    import re
    if not isinstance(note_id, str):
        raise ValueError("Note ID must be a string")
    if not re.match(r"^[a-f0-9]{32}$", note_id):
        raise ValueError("Note ID must be exactly 32 hexadecimal characters (Joplin UUID format)")
    return note_id

# Validation types - simplified for MCP client compatibility but with runtime validation
LimitType = Annotated[int, Field(ge=1, le=100)]         # Range validation + automatic string-to-int conversion
OffsetType = Annotated[int, Field(ge=0)]                # Minimum validation + automatic string-to-int conversion
RequiredStringType = Annotated[str, Field(min_length=1)]  # Simplified: just min length, runtime validation for complex patterns
JoplinIdType = Annotated[str, Field(min_length=32, max_length=32)]  # Length constraints, runtime regex validation
OptionalBoolType = Optional[Union[bool, str]]  # Accepts both bool and string, runtime conversion handles strings

# === UTILITY FUNCTIONS ===

def get_joplin_client() -> ClientApi:
    """Get a configured joppy client instance."""
    try:
        config = JoplinMCPConfig.load()
        if config.token:
            return ClientApi(token=config.token, url=config.base_url)
        else:
            token = os.getenv("JOPLIN_TOKEN")
            if not token:
                raise ValueError("No token found in config file or JOPLIN_TOKEN environment variable")
            return ClientApi(token=token, url=config.base_url)
    except Exception:
        token = os.getenv("JOPLIN_TOKEN")
        if not token:
            raise ValueError("JOPLIN_TOKEN environment variable is required")
        url = os.getenv("JOPLIN_URL", "http://localhost:41184")
        return ClientApi(token=token, url=url)



def apply_pagination(notes: List[Any], limit: int, offset: int) -> tuple[List[Any], int]:
    """Apply pagination to a list of notes and return paginated results with total count."""
    total_count = len(notes)
    start_index = offset
    end_index = offset + limit
    paginated_notes = notes[start_index:end_index]
    return paginated_notes, total_count

def build_search_filters(task: Optional[bool], completed: Optional[bool]) -> List[str]:
    """Build search filter parts for task and completion status."""
    search_parts = []
    
    # Add task filter if specified
    if task is not None:
        if task:
            search_parts.append("type:todo")
        else:
            search_parts.append("type:note")
    
    # Add completion filter if specified (only relevant for tasks)
    if completed is not None and task is True:
        if completed:
            search_parts.append("iscompleted:1")
        else:
            search_parts.append("iscompleted:0")
    
    return search_parts

def build_general_search_filters(**params) -> List[str]:
    """Build search filter parts from *_filter parameters using field registry.
    
    Uses alondmnt's build_search_filters() for todo fields, simple concatenation for others.
    
    Args:
        **params: All function parameters (will extract *_filter fields automatically)
        
    Returns:
        List of search filter strings
    """
    # Apply field converters first for proper type handling (includes lowercase conversion)
    converted_params = apply_field_converters(**params)
    
    # Get fields that have filter values
    field_pars = generate_field_pars(**converted_params)
    filter_fields = field_pars['filter_fields']
    
    search_parts = []
    
    # Handle special todo fields using alondmnt's existing function
    is_todo_filter = converted_params.get('is_todo_filter')
    todo_completed_filter = converted_params.get('todo_completed_filter')
    
    if is_todo_filter is not None or todo_completed_filter is not None:
        todo_filters = build_search_filters(is_todo_filter, todo_completed_filter)
        search_parts.extend(todo_filters)
    
    # Handle other fields with simple concatenation (exclude the special todo fields)
    special_fields = {'is_todo', 'todo_completed'}
    
    for field_name in filter_fields:
        if field_name not in special_fields:
            filter_value = converted_params.get(f"{field_name}_filter")
            search_parts.append(f'{field_name}:"{filter_value}"')
    
    return search_parts

def format_search_criteria(base_criteria: str, task: Optional[bool], completed: Optional[bool]) -> str:
    """Format search criteria description with filters."""
    criteria_parts = [base_criteria]
    
    if task is True:
        criteria_parts.append("(tasks only)")
    elif task is False:
        criteria_parts.append("(regular notes only)")
    
    if completed is True:
        criteria_parts.append("(completed)")
    elif completed is False:
        criteria_parts.append("(uncompleted)")
    
    return " ".join(criteria_parts)

def format_no_results_with_pagination(item_type: str, criteria: str, offset: int, limit: int) -> str:
    """Format no results message with pagination info."""
    if offset > 0:
        page_info = f" - Page {(offset // limit) + 1} (offset {offset})"
        return format_no_results_message(item_type, criteria + page_info)
    else:
        return format_no_results_message(item_type, criteria)

# Common fields list for note operations
COMMON_NOTE_FIELDS = "id,title,body,created_time,updated_time,parent_id,is_todo,todo_completed"

# Centralized registry for all accessible Joplin note fields
# Each field definition includes: field_name, type_converter, in_common_fields
JOPLIN_NOTE_FIELDS = {
    'title': {
        'type_converter': lambda x: x,
        'in_common_fields': True,
        'description': 'Note title'
    },
    'body': {
        'type_converter': lambda x: x, 
        'in_common_fields': True,
        'description': 'Note content'
    },
    'is_todo': {
        'type_converter': flexible_bool_converter,
        'in_common_fields': True,
        'description': 'Todo status'
    },
    'todo_completed': {
        'type_converter': lambda x: convert_todo_completed(x)[0],
        'in_common_fields': True,
        'description': 'Todo completion status'
    },
    'parent_id': {
        'type_converter': lambda x: x,
        'in_common_fields': True,
        'description': 'Notebook ID'
    },
    'author': {
        'type_converter': lambda x: x,
        'in_common_fields': False,
        'description': 'Note author'
    },
    'source_url': {
        'type_converter': lambda x: x,
        'in_common_fields': False,
        'description': 'Source URL'
    },
    'latitude': {
        'type_converter': lambda x: x,
        'in_common_fields': False,
        'description': 'GPS latitude coordinate'
    },
    'longitude': {
        'type_converter': lambda x: x,
        'in_common_fields': False,
        'description': 'GPS longitude coordinate'
    },
    'altitude': {
        'type_converter': lambda x: x,
        'in_common_fields': False,
        'description': 'GPS altitude coordinate'
    },
    'markup_language': {
        'type_converter': lambda x: x,
        'in_common_fields': False,
        'description': 'Note markup format: 1=Markdown, 2=HTML'
    },
    'user_created_time': {
        'type_converter': lambda x: x,
        'in_common_fields': False,
        'description': 'Custom creation timestamp in milliseconds'
    },
    'user_updated_time': {
        'type_converter': lambda x: x,
        'in_common_fields': False,
        'description': 'Custom update timestamp in milliseconds'
    }
}

def parse_markdown_headings(body: str, start_line: int = 0) -> List[Dict[str, Any]]:
    """Parse markdown headings from content, skipping those in code blocks.
    
    Args:
        body: The markdown content to parse
        start_line: Starting line index (for offset calculations)
        
    Returns:
        List of heading dictionaries with keys:
        - level: Heading level (1-6)
        - title: Heading text (cleaned)
        - line_idx: Absolute line index in original content
        - relative_line_idx: Line index relative to start_line
        - original_line: Full original line text
        - markdown: Original markdown heading (e.g., "## Title")
    """
    if not body:
        return []
    
    import re
    
    lines = body.split('\n')
    headings = []
    
    # Regex patterns
    heading_pattern = r'^(#{1,6})\s+(.+)$'
    code_block_pattern = r'^(```|~~~)'
    in_code_block = False
    
    for rel_line_idx, line in enumerate(lines):
        line_stripped = line.strip()
        abs_line_idx = start_line + rel_line_idx
        
        # Check for code block delimiters
        if re.match(code_block_pattern, line_stripped):
            in_code_block = not in_code_block
            continue
            
        # Only process headings outside code blocks
        if not in_code_block:
            match = re.match(heading_pattern, line_stripped)
            if match:
                hashes = match.group(1)
                title = match.group(2).strip()
                level = len(hashes)
                
                headings.append({
                    'level': level,
                    'title': title,
                    'line_idx': abs_line_idx,
                    'relative_line_idx': rel_line_idx,
                    'original_line': line,
                    'markdown': f"{hashes} {title}"
                })
    
    return headings

def extract_section_content(body: str, section_identifier: str) -> tuple[str, str]:
    """Extract a specific section from note content.
    
    Args:
        body: The note content to extract from
        section_identifier: Can be:
            - Section number (1-based): "1", "2", etc. (highest priority)
            - Heading text (case insensitive): "Introduction" (exact match)
            - Slug format: "introduction" or "my-section" (intentional format)
            - Partial text: "config" matches "Configuration" (fuzzy fallback)
            
    Priority order: Number → Exact → Slug → Partial
            
    Returns:
        tuple: (extracted_content, section_title) or ("", "") if not found
    """
    if not body or not section_identifier:
        return "", ""
    
    import re
    
    # Parse headings using helper function
    headings = parse_markdown_headings(body)
    
    if not headings:
        return "", ""
    
    # Split body into lines for content extraction
    lines = body.split('\n')
    
    # Find target section
    target_heading = None
    
    # Try to parse as section number first
    try:
        section_num = int(section_identifier)
        if 1 <= section_num <= len(headings):
            target_heading = headings[section_num - 1]
        else:
            # Number out of range, fall back to text matching
            target_heading = None
    except ValueError:
        # Not a number, will try text matching below
        target_heading = None
    
    # If no valid section number found, try text/slug matching
    if target_heading is None:
        identifier_lower = section_identifier.lower().strip()
        
        # Priority 1: Try exact matches first (case insensitive)
        for heading in headings:
            title_lower = heading['title'].lower()
            if title_lower == identifier_lower:
                target_heading = heading
                break
        
        # Priority 2: Try slug matches only if no exact match found
        if not target_heading:
            # Convert identifier to slug format
            identifier_slug = re.sub(r'[^\w\s-]', '', identifier_lower)
            identifier_slug = re.sub(r'[-\s_]+', '-', identifier_slug).strip('-')
            
            for heading in headings:
                title_lower = heading['title'].lower()
                
                # Convert title to slug and compare
                title_slug = re.sub(r'[^\w\s-]', '', title_lower)  # Remove special chars
                title_slug = re.sub(r'[-\s]+', '-', title_slug).strip('-')  # Normalize spaces/hyphens
                
                # Only exact slug matches, not partial slug matches
                if title_slug == identifier_slug:
                    target_heading = heading
                    break
        
        # Priority 3: Try partial matches only if no slug match found
        if not target_heading:
            for heading in headings:
                title_lower = heading['title'].lower()
                if identifier_lower in title_lower:
                    target_heading = heading
                    break
    
    if not target_heading:
        return "", ""
    
    # Find content boundaries based on hierarchy
    start_line = target_heading['line_idx']
    end_line = len(lines)
    target_level = target_heading['level']
    
    # Find end of section: next heading at same level or higher
    for heading in headings:
        if heading['line_idx'] > start_line and heading['level'] <= target_level:
            end_line = heading['line_idx']
            break
    
    # Extract the section content
    section_lines = lines[start_line:end_line]
    section_content = '\n'.join(section_lines).strip()
    
    return section_content, target_heading['title']

def create_content_preview(body: str, max_length: int) -> str:
    """Create a content preview that preserves front matter if present.
    
    If the content starts with front matter (delimited by ---), includes the entire
    front matter in the preview, followed by regular content preview.
    
    Args:
        body: The note content to create a preview for
        max_length: Maximum length for the preview (excluding front matter)
    
    Returns:
        str: The content preview with front matter and content preview
    """
    if not body:
        return ""
    
    import re
    
    lines = body.split('\n')
    preview_parts = []
    
    # Extract frontmatter using utility function
    front_matter, content_start_index = extract_frontmatter(body, max_lines=20)
    
    if front_matter:
        preview_parts.append(front_matter)
    
    # Get remaining content after front matter
    remaining_lines = lines[content_start_index:]
    remaining_content = '\n'.join(remaining_lines)
    
    # Calculate remaining space for content preview
    used_space = sum(len(part) + 1 for part in preview_parts)  # +1 for newlines between parts
    remaining_space = max(50, max_length - used_space)  # Ensure at least 50 chars for content
    
    # Add content preview with remaining space
    if remaining_content:
        content_preview = remaining_content.strip()
        if len(content_preview) > remaining_space:
            content_preview = content_preview[:remaining_space] + "..."
        
        # Only add content preview if it's meaningful (more than just "...")
        if len(content_preview.replace("...", "").strip()) > 10:
            preview_parts.append(content_preview)
    
    # If no meaningful content remains and no front matter, show regular preview
    if not preview_parts:
        preview = body[:max_length]
        if len(body) > max_length:
            preview += "..."
        return preview
    
    return '\n\n'.join(preview_parts)

def create_toc_only(body: str) -> str:
    """Create a table of contents with line numbers from note content.
    
    Args:
        body: The note content to extract TOC from
        
    Returns:
        str: Table of contents with heading structure and line numbers, or empty string if no headings
    """
    if not body:
        return ""
    
    headings = parse_markdown_headings(body)
    
    if not headings:
        return ""
    
    # Create TOC entries with line numbers
    toc_entries = []
    for i, heading in enumerate(headings, 1):
        level = heading['level']
        title = heading['title']
        line_num = heading['line_idx']  # 1-based line number
        
        # Create indentation based on heading level (level 1 = no indent, level 2 = 2 spaces, etc.)
        indent = '  ' * (level - 1)
        toc_entries.append(f"{indent}{i}. {title} (line {line_num})")
    
    toc_header = "TABLE_OF_CONTENTS:"
    toc_content = '\n'.join(toc_entries)
    
    return f"{toc_header}\n{toc_content}"

def extract_frontmatter(body: str, max_lines: int = 20) -> tuple[str, int]:
    """Extract frontmatter from note content if present.
    
    Args:
        body: The note content to extract frontmatter from
        max_lines: Maximum number of frontmatter lines to include
        
    Returns:
        tuple: (frontmatter_content, content_start_index)
    """
    if not body or not body.startswith('---'):
        return "", 0
    
    lines = body.split('\n')
    
    # Find the closing front matter delimiter
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == '---':
            front_matter_end = i
            break
    else:
        return "", 0  # No closing delimiter found
    
    # Get frontmatter lines with limit
    front_matter_lines = lines[:front_matter_end + 1]
    
    if len(front_matter_lines) > max_lines:
        # Truncate front matter if it exceeds max_lines
        # Keep opening --- + (max_lines-2) lines of content + closing ---
        front_matter_lines = lines[:max_lines - 1]  # Opening --- + content lines
        front_matter_lines.append('---')  # Add back the closing delimiter
    
    front_matter = '\n'.join(front_matter_lines)
    content_start_index = front_matter_end + 1
    
    return front_matter, content_start_index

def extract_text_terms_from_query(query: str) -> List[str]:
    """Extract text search terms from a Joplin search query, removing operators.
    
    Removes Joplin search operators like tag:, notebook:, type:, iscompleted:, etc.
    and extracts the actual text terms for content matching.
    
    Args:
        query: The search query that may contain operators and text terms
        
    Returns:
        List of text terms for content matching
    """
    import re
    
    if not query or query.strip() == "*":
        return []
    
    # Known Joplin search operators to remove
    operator_patterns = [
        r'tag:\S+',          # tag:work
        r'notebook:\S+',     # notebook:project
        r'type:\S+',         # type:todo
        r'iscompleted:\d+',  # iscompleted:1
        r'created:\S+',      # created:20231201
        r'updated:\S+',      # updated:20231201
        r'latitude:\S+',     # latitude:123.456
        r'longitude:\S+',    # longitude:123.456
        r'altitude:\S+',     # altitude:123.456
        r'resource:\S+',     # resource:image
        r'sourceurl:\S+',    # sourceurl:http
        r'any:\d+',          # any:1
    ]
    
    # Remove all operators
    cleaned_query = query
    for pattern in operator_patterns:
        cleaned_query = re.sub(pattern, '', cleaned_query, flags=re.IGNORECASE)
    
    # Handle quoted phrases - extract them as single terms
    phrase_pattern = r'"([^"]+)"'
    phrases = re.findall(phrase_pattern, cleaned_query)
    
    # Remove quoted phrases from the query to avoid double processing
    for phrase in phrases:
        cleaned_query = cleaned_query.replace(f'"{phrase}"', '')
    
    # Split remaining text into individual words
    individual_words = cleaned_query.split()
    
    # Combine phrases and individual words, filtering out empty strings
    all_terms = phrases + [word.strip() for word in individual_words if word.strip()]
    
    return all_terms

def _find_matching_lines(content_lines: List[str], search_terms: List[str], content_start_index: int) -> tuple[List[tuple[int, str]], List[tuple[int, str]]]:
    """Find lines matching search terms, separated by AND vs OR logic."""
    search_terms_lower = [term.lower() for term in search_terms]
    
    and_matches = []
    or_matches = []
    and_indices = set()
    
    for i, line in enumerate(content_lines):
        line_index = i + content_start_index
        line_lower = line.lower()
        
        # Check for AND matches (all terms present)
        if all(term in line_lower for term in search_terms_lower):
            and_matches.append((line_index, line))
            and_indices.add(line_index)
        # Check for OR matches (any terms present), excluding AND matches
        elif any(term in line_lower for term in search_terms_lower):
            or_matches.append((line_index, line))
    
    return and_matches, or_matches

def create_matching_lines_preview(body: str, search_terms: List[str], max_length: int = 300, max_lines: int = 10, context_lines: int = 0) -> tuple[str, List[int], int, int]:
    """Create a preview showing only lines that match search terms with priority system.
    
    Priority system:
    1. Lines matching ALL search terms (AND logic) - highest priority
    2. Lines matching any search terms (OR logic) - lower priority
    3. Builds incrementally while respecting max_length limit
    
    Args:
        body: The note content to search in
        search_terms: List of terms to search for
        max_length: Maximum length for the preview content
        max_lines: Maximum number of matching lines to include
        context_lines: Number of context lines to show around matches
        
    Returns:
        tuple: (preview_content, list_of_displayed_line_numbers, and_matches_count, or_matches_count)
    """
    if not body or not search_terms:
        return "", [], 0, 0
    
    lines = body.split('\n')
    _, content_start_index = extract_frontmatter(body)
    content_lines = lines[content_start_index:]
    
    # Find all matching lines
    and_matches, or_matches = _find_matching_lines(content_lines, search_terms, content_start_index)
    and_count, or_count = len(and_matches), len(or_matches)
    
    # Combine matches with priority (AND first, then OR)
    all_matches = and_matches + or_matches
    if not all_matches:
        return "", [], 0, 0
    
    # Build preview incrementally
    preview_parts = []
    included_line_numbers = []
    used_indices = set()
    current_length = 0
    
    for line_index, _ in all_matches:
        if len(included_line_numbers) >= max_lines:
            break
            
        # Calculate what this match would add to the preview
        context_block = []
        block_indices = []
        
        # Calculate context range
        start_context = max(content_start_index, line_index - context_lines)
        end_context = min(len(lines), line_index + context_lines + 1)
        
        # Build context block for this match
        for ctx_i in range(start_context, end_context):
            if ctx_i not in used_indices:
                block_indices.append(ctx_i)
                line_num = ctx_i + 1  # 1-based
                line_content = lines[ctx_i]
                
                # Mark the actual matching line vs context
                if ctx_i == line_index:
                    context_block.append(f"[L{line_num}] {line_content}")
                else:
                    context_block.append(f" L{line_num}  {line_content}")
        
        if context_block:
            block_content = '\n'.join(context_block)
            separator_length = 1 if preview_parts else 0  # Newline separator
            block_length = len(block_content) + separator_length
            
            # Check length limit
            if current_length + block_length > max_length and preview_parts:
                break
            
            # Add block with separator
            if preview_parts:
                preview_parts.append("")
            preview_parts.extend(context_block)
            
            current_length += block_length
            used_indices.update(block_indices)
            included_line_numbers.append(line_index + 1)  # 1-based
    
    preview_content = '\n'.join(preview_parts) if preview_parts else ""
    return preview_content, included_line_numbers, and_count, or_count

def create_content_preview_with_search(body: str, max_length: int, search_query: str = "") -> str:
    """Create a content preview that shows matching lines for search queries, with fallback.
    
    Enhancement to create_content_preview that prioritizes showing lines matching
    the search query instead of just the first lines of content.
    
    Args:
        body: The note content to create a preview for
        max_length: Maximum length for the preview (excluding front matter)
        search_query: The search query to extract terms from
    
    Returns:
        str: The content preview with matching lines or fallback to regular preview
    """
    if not body:
        return ""
    
    search_terms = extract_text_terms_from_query(search_query)
    if not search_terms:
        return create_content_preview(body, max_length)
    
    # Extract frontmatter and calculate available space
    front_matter, _ = extract_frontmatter(body, max_lines=10)
    available_length = max(50, max_length - len(front_matter))
    
    matching_preview, line_numbers, and_matches, or_matches = create_matching_lines_preview(
        body, search_terms, max_length=available_length, max_lines=8, context_lines=0
    )
    
    if not matching_preview:
        return create_content_preview(body, max_length)
    
    # Build preview with metadata
    preview_parts = []
    
    if front_matter:
        preview_parts.append(front_matter)
    
    # Build match quality description
    displayed_matches = len(line_numbers)
    total_matches = and_matches + or_matches
    
    if and_matches > 0 and or_matches > 0:
        quality_info = f"({and_matches} match all terms, {or_matches} match any terms)"
    elif and_matches > 0:
        quality_info = "(all match all search terms)"
    else:
        quality_info = "(all match some search terms)"
    
    # Build main message with truncation info
    if displayed_matches < total_matches:
        match_info = f"MATCHING_LINES: {total_matches} total lines match search terms {quality_info} - showing first {displayed_matches}"
    else:
        match_info = f"MATCHING_LINES: {total_matches} lines match search terms {quality_info}"
    
    # Add search terms info
    if search_terms:
        terms_str = ", ".join(f'"{term}"' for term in search_terms[:3])
        if len(search_terms) > 3:
            terms_str += f" (+{len(search_terms)-3} more)"
        match_info += f" [{terms_str}]"
    
    preview_parts.append(match_info)
    preview_parts.append("")
    preview_parts.append(matching_preview)
    
    return '\n'.join(preview_parts)



def format_timestamp(timestamp: Optional[Union[int, datetime.datetime]], format_str: str = "%Y-%m-%d %H:%M:%S") -> Optional[str]:
    """Format a timestamp safely."""
    if not timestamp:
        return None
    try:
        if isinstance(timestamp, datetime.datetime):
            return timestamp.strftime(format_str)
        elif isinstance(timestamp, int):
            return datetime.datetime.fromtimestamp(timestamp / 1000).strftime(format_str)
        else:
            return None
    except:
        return None

def calculate_content_stats(body: str) -> Dict[str, int]:
    """Calculate content statistics for a note body.
    
    Args:
        body: The note content to analyze
        
    Returns:
        Dict with keys: 'characters', 'words', 'lines'
    """
    if not body:
        return {'characters': 0, 'words': 0, 'lines': 0}
    
    # Character count (including whitespace and special characters)
    char_count = len(body)
    
    # Line count
    line_count = len(body.split('\n'))
    
    # Word count (split by whitespace and filter empty strings)
    words = [word for word in body.split() if word.strip()]
    word_count = len(words)
    
    return {
        'characters': char_count,
        'words': word_count, 
        'lines': line_count
    }

def process_search_results(results: Any) -> List[Any]:
    """Process search results from joppy client into a consistent list format."""
    if hasattr(results, 'items'):
        return results.items or []
    elif isinstance(results, list):
        return results
    else:
        return [results] if results else []

def filter_items_by_title(items: List[Any], query: str) -> List[Any]:
    """Filter items by title using case-insensitive search."""
    return [
        item for item in items 
        if query.lower() in getattr(item, 'title', '').lower()
    ]

def format_no_results_message(item_type: str, context: str = "") -> str:
    """Format a standardized no results message optimized for LLM comprehension."""
    return f"ITEM_TYPE: {item_type}\nTOTAL_ITEMS: 0\nCONTEXT: {context}\nSTATUS: No {item_type}s found"

def with_client_error_handling(operation_name: str):
    """Decorator to handle client operations with standardized error handling."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if "parameter is required" in str(e) or "must be between" in str(e):
                    raise e  # Re-raise validation errors as-is
                raise ValueError(f"{operation_name} failed: {str(e)}")
        return wrapper
    return decorator

def conditional_tool(tool_name: str):
    """Decorator to conditionally register tools based on configuration."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Check if tool is enabled in configuration
        if _module_config.tools.get(tool_name, True):  # Default to True if not specified
            # Tool is enabled - register it with FastMCP
            return mcp.tool()(func)
        else:
            # Tool is disabled - return function without registering
            logger.info(f"Tool '{tool_name}' disabled in configuration - not registering")
            return func
    return decorator

def get_notebook_id_by_name(name: str) -> str:
    """Get notebook ID by name with helpful error messages.
    
    Args:
        name: The notebook name to search for
        
    Returns:
        str: The notebook ID
        
    Raises:
        ValueError: If notebook not found or multiple matches
    """
    client = get_joplin_client()
    
    # Find notebook by name
    fields_list = "id,title,created_time,updated_time,parent_id"
    all_notebooks = client.get_all_notebooks(fields=fields_list)
    matching_notebooks = [nb for nb in all_notebooks if getattr(nb, 'title', '').lower() == name.lower()]
    
    if not matching_notebooks:
        available_notebooks = [getattr(nb, 'title', 'Untitled') for nb in all_notebooks]
        raise ValueError(f"Notebook '{name}' not found. Available notebooks: {', '.join(available_notebooks)}")
    
    if len(matching_notebooks) > 1:
        notebook_details = [f"'{getattr(nb, 'title', 'Untitled')}' (ID: {getattr(nb, 'id', 'unknown')})" for nb in matching_notebooks]
        raise ValueError(f"Multiple notebooks found with name '{name}': {', '.join(notebook_details)}. Please be more specific.")
    
    notebook_id = getattr(matching_notebooks[0], 'id', None)
    if not notebook_id:
        raise ValueError(f"Could not get ID for notebook '{name}'")
    
    return notebook_id

def get_tag_id_by_name(name: str) -> str:
    """Get tag ID by name with helpful error messages.
    
    Args:
        name: The tag name to search for
        
    Returns:
        str: The tag ID
        
    Raises:
        ValueError: If tag not found or multiple matches
    """
    client = get_joplin_client()
    
    # Find tag by name
    tag_fields_list = "id,title,created_time,updated_time"
    all_tags = client.get_all_tags(fields=tag_fields_list)
    matching_tags = [tag for tag in all_tags if getattr(tag, 'title', '').lower() == name.lower()]
    
    if not matching_tags:
        available_tags = [getattr(tag, 'title', 'Untitled') for tag in all_tags]
        raise ValueError(f"Tag '{name}' not found. Available tags: {', '.join(available_tags)}. Use create_tag to create a new tag.")
    
    if len(matching_tags) > 1:
        tag_details = [f"'{getattr(tag, 'title', 'Untitled')}' (ID: {getattr(tag, 'id', 'unknown')})" for tag in matching_tags]
        raise ValueError(f"Multiple tags found with name '{name}': {', '.join(tag_details)}. Please be more specific.")
    
    tag_id = getattr(matching_tags[0], 'id', None)
    if not tag_id:
        raise ValueError(f"Could not get ID for tag '{name}'")
    
    return tag_id

# === FORMATTING UTILITIES ===

def get_item_emoji(item_type: ItemType) -> str:
    """Get emoji for item type."""
    emoji_map = {
        ItemType.note: "📝",
        ItemType.notebook: "📁",
        ItemType.tag: "🏷️"
    }
    return emoji_map.get(item_type, "📄")

def format_creation_success(item_type: ItemType, title: str, item_id: str) -> str:
    """Format a standardized success message for creation operations optimized for LLM comprehension."""
    return f"""OPERATION: CREATE_{item_type.value.upper()}
STATUS: SUCCESS
ITEM_TYPE: {item_type.value}
ITEM_ID: {item_id}
TITLE: {title}
MESSAGE: {item_type.value} created successfully in Joplin"""

def format_update_success(item_type: ItemType, item_id: str) -> str:
    """Format a standardized success message for update operations optimized for LLM comprehension."""
    return f"""OPERATION: UPDATE_{item_type.value.upper()}
STATUS: SUCCESS
ITEM_TYPE: {item_type.value}
ITEM_ID: {item_id}
MESSAGE: {item_type.value} updated successfully in Joplin"""

def format_delete_success(item_type: ItemType, item_id: str, soft_delete: bool = True) -> str:
    """Format a standardized success message for delete operations optimized for LLM comprehension."""
    if soft_delete:
        message = f"{item_type.value} moved to trash in Joplin (restorable from Joplin Desktop)"
    else:
        message = f"{item_type.value} deleted permanently from Joplin"
    return f"""OPERATION: DELETE_{item_type.value.upper()}
STATUS: SUCCESS
ITEM_TYPE: {item_type.value}
ITEM_ID: {item_id}
MESSAGE: {message}"""

def format_relation_success(operation: str, item1_type: ItemType, item1_id: str, item2_type: ItemType, item2_id: str) -> str:
    """Format a standardized success message for relationship operations optimized for LLM comprehension."""
    return f"""OPERATION: {operation.upper().replace(' ', '_')}
STATUS: SUCCESS
ITEM1_TYPE: {item1_type.value}
ITEM1_ID: {item1_id}
ITEM2_TYPE: {item2_type.value}
ITEM2_ID: {item2_id}
MESSAGE: {operation} completed successfully"""

def format_item_list(items: List[Any], item_type: ItemType) -> str:
    """Format a list of items (notebooks, tags, etc.) for display optimized for LLM comprehension."""
    if not items:
        return f"ITEM_TYPE: {item_type.value}\nTOTAL_ITEMS: 0\nSTATUS: No {item_type.value}s found in Joplin instance"
    
    count = len(items)
    result_parts = [
        f"ITEM_TYPE: {item_type.value}",
        f"TOTAL_ITEMS: {count}",
        ""
    ]
    
    for i, item in enumerate(items, 1):
        title = getattr(item, 'title', 'Untitled')
        item_id = getattr(item, 'id', 'unknown')
        
        # Structured item entry
        result_parts.extend([
            f"ITEM_{i}:",
            f"  {item_type.value}_id: {item_id}",
            f"  title: {title}",
        ])
        
        # Add parent folder ID if available (for notebooks)
        parent_id = getattr(item, 'parent_id', None)
        if parent_id:
            result_parts.append(f"  parent_id: {parent_id}")
        
        # Add creation time if available
        created_time = getattr(item, 'created_time', None)
        if created_time:
            created_date = format_timestamp(created_time, "%Y-%m-%d %H:%M")
            if created_date:
                result_parts.append(f"  created: {created_date}")
        
        # Add update time if available
        updated_time = getattr(item, 'updated_time', None)
        if updated_time:
            updated_date = format_timestamp(updated_time, "%Y-%m-%d %H:%M")
            if updated_date:
                result_parts.append(f"  updated: {updated_date}")
        
        result_parts.append("")
    
    return "\n".join(result_parts)

def format_item_details(item: Any, item_type: ItemType) -> str:
    """Format a single item (notebook, tag, etc.) for detailed display."""
    emoji = get_item_emoji(item_type)
    title = getattr(item, 'title', 'Untitled')
    item_id = getattr(item, 'id', 'unknown')
    
    result_parts = [f"{emoji} **{title}**", f"ID: {item_id}", ""]
    
    # Add metadata
    metadata = []
    
    # Timestamps
    created_time = getattr(item, 'created_time', None)
    if created_time:
        created_date = format_timestamp(created_time)
        if created_date:
            metadata.append(f"Created: {created_date}")
    
    updated_time = getattr(item, 'updated_time', None)
    if updated_time:
        updated_date = format_timestamp(updated_time)
        if updated_date:
            metadata.append(f"Updated: {updated_date}")
    
    # Parent (for notebooks)
    parent_id = getattr(item, 'parent_id', None)
    if parent_id:
        metadata.append(f"Parent: {parent_id}")
    
    if metadata:
        result_parts.append("**Metadata:**")
        result_parts.extend(f"- {m}" for m in metadata)
    
    return "\n".join(result_parts)

def format_note_details(note: Any, include_body: bool = True, context: str = "individual_notes", original_body: Optional[str] = None) -> str:
    """Format a note for detailed display optimized for LLM comprehension."""
    title = getattr(note, 'title', 'Untitled')
    note_id = getattr(note, 'id', 'unknown')
    
    # Check content exposure settings
    config = _module_config
    should_show_content = config.should_show_content(context)
    should_show_full_content = config.should_show_full_content(context)
    
    # Structured note details - metadata first
    result_parts = [
        f"NOTE_ID: {note_id}",
        f"TITLE: {title}",
    ]
    
    # Add structured metadata first
    created_time = getattr(note, 'created_time', None)
    if created_time:
        created_date = format_timestamp(created_time)
        if created_date:
            result_parts.append(f"CREATED: {created_date}")
    
    updated_time = getattr(note, 'updated_time', None)
    if updated_time:
        updated_date = format_timestamp(updated_time)
        if updated_date:
            result_parts.append(f"UPDATED: {updated_date}")
    
    # Notebook reference
    parent_id = getattr(note, 'parent_id', None)
    if parent_id:
        result_parts.append(f"NOTEBOOK_ID: {parent_id}")
    
    # Todo status
    is_todo = getattr(note, 'is_todo', 0)
    if is_todo:
        result_parts.append("IS_TODO: true")
        todo_completed = getattr(note, 'todo_completed', 0)
        result_parts.append(f"TODO_COMPLETED: {'true' if todo_completed else 'false'}")
    else:
        result_parts.append("IS_TODO: false")
    
    # Add content size statistics (use original_body for stats if provided)
    body = getattr(note, 'body', '')
    stats_body = original_body if original_body is not None else body
    content_stats = calculate_content_stats(stats_body)
    result_parts.append(f"CONTENT_SIZE_CHARS: {content_stats['characters']}")
    result_parts.append(f"CONTENT_SIZE_WORDS: {content_stats['words']}")
    result_parts.append(f"CONTENT_SIZE_LINES: {content_stats['lines']}")
    
    # Add content last to avoid breaking metadata flow
    if include_body:
        body = getattr(note, 'body', '')
        if should_show_content:
            if body:
                if should_show_full_content:
                    # Standard full content display
                    result_parts.append(f"CONTENT: {body}")
                else:
                    # Show preview only (for search results context)
                    max_length = config.get_max_preview_length()
                    preview = create_content_preview(body, max_length)
                    result_parts.append(f"CONTENT_PREVIEW: {preview}")
            else:
                result_parts.append("CONTENT: (empty)")
        else:
            # Content hidden due to privacy settings, but show status
            if body:
                result_parts.append("CONTENT: (hidden by privacy settings)")
            else:
                result_parts.append("CONTENT: (empty)")
    
    return "\n".join(result_parts)

def _build_pagination_header(query: str, total_count: int, limit: int, offset: int) -> List[str]:
    """Build pagination header with search and pagination info."""
    count = min(limit, total_count - offset) if total_count > offset else 0
    current_page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
    start_result = offset + 1 if count > 0 else 0
    end_result = offset + count
    
    header = [
        f"SEARCH_QUERY: {query}",
        f"TOTAL_RESULTS: {total_count}",
        f"SHOWING_RESULTS: {start_result}-{end_result}",
        f"CURRENT_PAGE: {current_page}",
        f"TOTAL_PAGES: {total_pages}",
        f"LIMIT: {limit}",
        f"OFFSET: {offset}",
        ""
    ]
    
    # Add next page guidance
    if total_count > end_result:
        next_offset = offset + limit
        header.extend([f"NEXT_PAGE: Use offset={next_offset} to get the next {limit} results", ""])
    
    return header

def _format_note_entry(note: Any, index: int, config: Any, context: str, original_query: Optional[str], query: str) -> List[str]:
    """Format a single note entry for search results."""
    title = getattr(note, 'title', 'Untitled')
    note_id = getattr(note, 'id', 'unknown')
    body = getattr(note, 'body', '')
    
    # Start with basic info
    entry = [
        f"RESULT_{index}:",
        f"  note_id: {note_id}",
        f"  title: {title}",
    ]
    
    # Add timestamps
    for time_field, label in [('created_time', 'created'), ('updated_time', 'updated')]:
        timestamp = getattr(note, time_field, None)
        if timestamp:
            formatted_date = format_timestamp(timestamp, "%Y-%m-%d %H:%M")
            if formatted_date:
                entry.append(f"  {label}: {formatted_date}")
    
    # Add notebook reference
    parent_id = getattr(note, 'parent_id', None)
    if parent_id:
        entry.append(f"  notebook_id: {parent_id}")
    
    # Add todo status
    is_todo = getattr(note, 'is_todo', 0)
    if is_todo:
        todo_completed = getattr(note, 'todo_completed', 0)
        entry.extend([
            "  is_todo: true",
            f"  todo_completed: {'true' if todo_completed else 'false'}"
        ])
    else:
        entry.append("  is_todo: false")
    
    # Add content statistics
    content_stats = calculate_content_stats(body)
    entry.extend([
        f"  content_size_chars: {content_stats['characters']}",
        f"  content_size_words: {content_stats['words']}",
        f"  content_size_lines: {content_stats['lines']}"
    ])
    
    # Add content based on privacy settings
    should_show_content = config.should_show_content(context)
    if should_show_content and body:
        if config.should_show_full_content(context):
            entry.append(f"  content: {body}")
        else:
            search_query_for_terms = original_query if original_query is not None else query
            preview = create_content_preview_with_search(body, config.get_max_preview_length(), search_query_for_terms)
            entry.append(f"  content_preview: {preview}")
    elif should_show_content:
        entry.append("  content: (empty)")
    else:
        content_status = "(hidden by privacy settings)" if body else "(empty)"
        entry.append(f"  content: {content_status}")
    
    entry.append("")  # Empty line separator
    return entry

def _build_pagination_summary(total_count: int, limit: int, offset: int) -> List[str]:
    """Build pagination summary footer."""
    count = min(limit, total_count - offset) if total_count > offset else 0
    current_page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
    start_result = offset + 1 if count > 0 else 0
    end_result = offset + count
    
    if total_pages <= 1:
        return []
    
    summary = [
        "PAGINATION_SUMMARY:",
        f"  showing_page: {current_page} of {total_pages}",
        f"  showing_results: {start_result}-{end_result} of {total_count}",
        f"  results_per_page: {limit}",
    ]
    
    if current_page < total_pages:
        summary.append(f"  next_page_offset: {offset + limit}")
    
    if current_page > 1:
        summary.append(f"  prev_page_offset: {max(0, offset - limit)}")
    
    return summary

def format_search_results_with_pagination(query: str, results: List[Any], total_count: int, limit: int, offset: int, context: str = "search_results", original_query: Optional[str] = None) -> str:
    """Format search results with pagination information for display optimized for LLM comprehension."""
    config = _module_config
    
    # Build all parts
    result_parts = _build_pagination_header(query, total_count, limit, offset)
    
    # Add note entries
    for i, note in enumerate(results, 1):
        result_parts.extend(_format_note_entry(note, i, config, context, original_query, query))
    
    # Add pagination summary
    result_parts.extend(_build_pagination_summary(total_count, limit, offset))
    
    return "\n".join(result_parts)

def format_tag_list_with_counts(tags: List[Any], client: Any) -> str:
    """Format a list of tags with note counts for display optimized for LLM comprehension."""
    if not tags:
        return "ITEM_TYPE: tag\nTOTAL_ITEMS: 0\nSTATUS: No tags found in Joplin instance"
    
    count = len(tags)
    result_parts = [
        "ITEM_TYPE: tag",
        f"TOTAL_ITEMS: {count}",
        ""
    ]
    
    for i, tag in enumerate(tags, 1):
        title = getattr(tag, 'title', 'Untitled')
        tag_id = getattr(tag, 'id', 'unknown')
        
        # Get note count for this tag
        try:
            notes_result = client.get_notes(tag_id=tag_id, fields=COMMON_NOTE_FIELDS)
            notes = process_search_results(notes_result)
            note_count = len(notes)
        except Exception:
            note_count = 0
        
        # Structured tag entry
        result_parts.extend([
            f"ITEM_{i}:",
            f"  tag_id: {tag_id}",
            f"  title: {title}",
            f"  note_count: {note_count}",
        ])
        
        # Add creation time if available
        created_time = getattr(tag, 'created_time', None)
        if created_time:
            created_date = format_timestamp(created_time, "%Y-%m-%d %H:%M")
            if created_date:
                result_parts.append(f"  created: {created_date}")
        
        # Add update time if available
        updated_time = getattr(tag, 'updated_time', None)
        if updated_time:
            updated_date = format_timestamp(updated_time, "%Y-%m-%d %H:%M")
            if updated_date:
                result_parts.append(f"  updated: {updated_date}")
        
        result_parts.append("")
    
    return "\n".join(result_parts)

# === GENERIC CRUD OPERATIONS ===

def create_tool(tool_name: str, operation_name: str):
    """Create a tool decorator with consistent error handling."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        return conditional_tool(tool_name)(
            with_client_error_handling(operation_name)(func)
        )
    return decorator

# === CORE TOOLS ===

# Add health check endpoint for better compatibility
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request) -> dict:
    """Health check endpoint for load balancers and monitoring."""
    from starlette.responses import JSONResponse
    return JSONResponse({
        "status": "healthy",
        "server": "Joplin MCP Server", 
        "version": MCP_VERSION,
        "transport": "ready"
    }, status_code=200)

@create_tool("ping_joplin", "Ping Joplin")
async def ping_joplin() -> str:
    """Test connection to Joplin server.
    
    Verifies connectivity to the Joplin application. Use to troubleshoot connection issues.
    
    Returns:
        str: Connection status information.
    """
    try:
        client = get_joplin_client()
        client.ping()
        return """OPERATION: PING_JOPLIN
STATUS: SUCCESS
CONNECTION: ESTABLISHED
MESSAGE: Joplin server connection successful"""
    except Exception as e:
        return f"""OPERATION: PING_JOPLIN
STATUS: FAILED
CONNECTION: FAILED
ERROR: {str(e)}
MESSAGE: Unable to reach Joplin server - check connection settings"""

# === NOTE OPERATIONS ===

def _create_note_object(note: Any, body_override: str = None) -> Any:
    """Create a note object with optional body override."""
    class ModifiedNote:
        def __init__(self, original_note, body_override=None):
            for attr in ['id', 'title', 'created_time', 'updated_time', 'parent_id', 'is_todo', 'todo_completed']:
                setattr(self, attr, getattr(original_note, attr, None))
            self.body = body_override if body_override is not None else getattr(original_note, 'body', '')
    
    return ModifiedNote(note, body_override)

def _handle_section_extraction(note: Any, section: str, note_id: str, include_body: bool) -> Optional[str]:
    """Handle section extraction logic, returning formatted result or None if no section handling needed."""
    if not (section and include_body):
        return None
    
    body = getattr(note, 'body', '')
    if not body:
        return None
    
    section_content, section_title = extract_section_content(body, section)
    if section_content:
        modified_note = _create_note_object(note, section_content)
        result = format_note_details(modified_note, include_body, "individual_notes")
        return f"EXTRACTED_SECTION: {section_title}\nSECTION_QUERY: {section}\n{result}"
    
    # Section not found - show available sections with line numbers
    headings = parse_markdown_headings(body)
    section_list = [
        f"{'  ' * (heading['level'] - 1)}{i}. {heading['title']} (line {heading['line_idx']})"
        for i, heading in enumerate(headings, 1)
    ]
    available_sections = "\n".join(section_list) if section_list else "No sections found"
    
    return f"""SECTION_NOT_FOUND: {section}
NOTE_ID: {note_id}
NOTE_TITLE: {getattr(note, 'title', 'Untitled')}
AVAILABLE_SECTIONS:
{available_sections}
ERROR: Section '{section}' not found in note"""

def _handle_toc_display(note: Any, note_id: str, display_mode: str, original_body: str = None) -> str:
    """Handle TOC display with metadata and navigation info."""
    toc = create_toc_only(original_body or getattr(note, 'body', ''))
    if not toc:
        return None
    
    # Create note with empty body for metadata-only display
    toc_note = _create_note_object(note, "")
    metadata_result = format_note_details(toc_note, include_body=False, context="individual_notes", original_body=original_body)
    
    # Build navigation steps based on display mode
    if display_mode == "explicit":
        steps = f"""NEXT_STEPS: 
- To get specific section: get_note("{note_id}", section="1") or get_note("{note_id}", section="Introduction")
- To jump to line number: get_note("{note_id}", start_line=45) (using line numbers from TOC above)
- To get full content: get_note("{note_id}", force_full=True)"""
    else:  # smart_toc_auto
        steps = f"""NEXT_STEPS:
- To get specific section: get_note("{note_id}", section="1") or get_note("{note_id}", section="Introduction")
- To jump to line number: get_note("{note_id}", start_line=45) (using line numbers from TOC above)
- To force full content: get_note("{note_id}", force_full=True)"""
    
    toc_info = f"DISPLAY_MODE: {display_mode}\n\n{toc}\n\n{steps}"
    return f"{metadata_result}\n\n{toc_info}"

def _handle_line_extraction(note: Any, start_line: int, line_count: Optional[int], note_id: str, include_body: bool) -> Optional[str]:
    """Handle line-based extraction for sequential reading."""
    if not include_body:
        return None
    
    body = getattr(note, 'body', '')
    if not body:
        return None
    
    lines = body.split('\n')
    total_lines = len(lines)
    
    # Validate start_line (1-based)
    if start_line < 1 or start_line > total_lines:
        return f"""LINE_EXTRACTION_ERROR: Invalid start_line
NOTE_ID: {note_id}
NOTE_TITLE: {getattr(note, 'title', 'Untitled')}
START_LINE: {start_line}
TOTAL_LINES: {total_lines}
ERROR: start_line must be between 1 and {total_lines}"""
    
    # Determine end line
    if line_count is not None:
        if line_count < 1:
            return f"""LINE_EXTRACTION_ERROR: Invalid line_count
NOTE_ID: {note_id}
LINE_COUNT: {line_count}
ERROR: line_count must be >= 1"""
        actual_end_line = min(start_line + line_count - 1, total_lines)
    else:
        # Default to 50 lines if line_count not specified
        actual_end_line = min(start_line + 49, total_lines)
    
    # Extract lines (convert to 0-based indexing)
    start_idx = start_line - 1
    end_idx = actual_end_line  # end_line is inclusive, so we don't subtract 1
    extracted_lines = lines[start_idx:end_idx]
    extracted_content = '\n'.join(extracted_lines)
    
    # Create modified note with extracted content
    modified_note = _create_note_object(note, extracted_content)
    result = format_note_details(modified_note, include_body, "individual_notes", original_body=body)
    
    # Add extraction metadata
    lines_extracted = len(extracted_lines)
    next_line = actual_end_line + 1 if actual_end_line < total_lines else None
    
    extraction_info = f"""EXTRACTED_LINES: {start_line}-{actual_end_line} ({lines_extracted} lines)
TOTAL_LINES: {total_lines}
EXTRACTION_TYPE: sequential_reading"""
    
    if next_line:
        extraction_info += f"\nNEXT_CHUNK: get_note(\"{note_id}\", start_line={next_line}) for continuation"
    else:
        extraction_info += f"\nSTATUS: End of note reached"
    
    return f"{extraction_info}\n\n{result}"

def _handle_smart_toc_behavior(note: Any, note_id: str, config: Any) -> Optional[str]:
    """Handle smart TOC behavior for long notes."""
    if not config.is_smart_toc_enabled():
        return None
    
    body = getattr(note, 'body', '')
    if not body:
        return None
    
    body_length = len(body)
    toc_threshold = config.get_smart_toc_threshold()
    
    if body_length <= toc_threshold:
        return None  # Not long enough for smart TOC
    
    # Try TOC first
    toc_result = _handle_toc_display(note, note_id, "smart_toc_auto", body)
    if toc_result:
        return toc_result
    
    # No headings found - show truncated content with warning
    truncated_content = body[:toc_threshold] + ("..." if body_length > toc_threshold else "")
    truncated_note = _create_note_object(note, truncated_content)
    result = format_note_details(truncated_note, True, "individual_notes", original_body=body)
    
    truncation_info = f"CONTENT_TRUNCATED: Note is long ({body_length} chars) but has no headings for navigation\nNEXT_STEPS: To force full content: get_note(\"{note_id}\", force_full=True) or start sequential reading: get_note(\"{note_id}\", start_line=1)\n"
    return f"{truncation_info}{result}"

@create_tool("get_note", "Get note")
async def get_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to retrieve")], 
    section: Annotated[Optional[str], Field(description="Extract specific section (heading text, slug, or number)")] = None,
    start_line: Annotated[Optional[int], Field(description="Start line for sequential reading (1-based)")] = None,
    line_count: Annotated[Optional[int], Field(description="Number of lines to extract from start_line (default: 50)")] = None,
    toc_only: Annotated[OptionalBoolType, Field(description="Show only table of contents (default: False)")] = False,
    force_full: Annotated[OptionalBoolType, Field(description="Force full content even for long notes (default: False)")] = False,
    metadata_only: Annotated[OptionalBoolType, Field(description="Show only metadata without content (default: False)")] = False
) -> str:
    """Retrieve a note with smart content display and sequential reading support.
    
    Smart behavior: Short notes show full content, long notes show TOC only.
    Sequential reading: Extract specific line ranges for progressive consumption.
    
    Args:
        note_id: Note identifier
        section: Extract specific section (heading text, slug, or number)
        start_line: Start line for sequential reading (1-based, line numbers)
        line_count: Number of lines to extract (default: 50 if start_line specified)
        toc_only: Show only TOC and metadata  
        force_full: Force full content even for long notes
        metadata_only: Show only metadata without content
    
    Examples:
        get_note("id") - Smart display (full if short, TOC if long)
        get_note("id", section="1") - Get first section
        get_note("id", start_line=1) - Start sequential reading from line 1 (50 lines)
        get_note("id", start_line=51, line_count=30) - Continue reading from line 51 (30 lines)
        get_note("id", toc_only=True) - TOC only
        get_note("id", force_full=True) - Force full content
    """
    
    # Runtime validation for Jan AI compatibility while preserving functionality
    note_id = validate_joplin_id(note_id)
    toc_only = flexible_bool_converter(toc_only)
    force_full = flexible_bool_converter(force_full)
    metadata_only = flexible_bool_converter(metadata_only)
    
    include_body = not metadata_only
    
    # Validate line extraction parameters
    if start_line is not None:
        if start_line < 1:
            raise ValueError("start_line must be >= 1 (line numbers are 1-based)")
        if line_count is not None and line_count < 1:
            raise ValueError("line_count must be >= 1")
    
    # If start_line is provided but we're extracting sections, that's an error
    if start_line is not None and section is not None:
        raise ValueError("Cannot specify both start_line and section - use one extraction method")
    
    client = get_joplin_client()
    note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
    
    # Handle line extraction first (for sequential reading)
    if start_line is not None:
        line_result = _handle_line_extraction(note, start_line, line_count, note_id, include_body)
        if line_result:
            return line_result
    
    # Handle section extraction second
    section_result = _handle_section_extraction(note, section, note_id, include_body)
    if section_result:
        return section_result
    
    # Handle explicit TOC-only mode
    if toc_only and include_body:
        body = getattr(note, 'body', '')
        if body:
            toc_result = _handle_toc_display(note, note_id, "toc_only", body)
            if toc_result:
                return toc_result
    
    # Handle smart TOC behavior (only if not forcing full content)
    if include_body and not force_full:
        smart_toc_result = _handle_smart_toc_behavior(note, note_id, _module_config)
        if smart_toc_result:
            return smart_toc_result
    
    # Default: return full note details
    return format_note_details(note, include_body, "individual_notes")

@create_tool("get_links", "Get links")
async def get_links(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to extract links from")]
) -> str:
    """Extract all links to other notes from a given note and find backlinks from other notes.
    
    Scans the note's content for links in the format [text](:/noteId) or [text](:/noteId#section-slug)
    and searches for backlinks (other notes that link to this note). Returns link text, target/source 
    note info, section slugs (if present), and line context.
    
    Returns:
        str: Formatted list of outgoing links and backlinks with titles, IDs, section slugs, and line context.
        
    Link formats: 
    - [link text](:/targetNoteId) - Link to note
    - [link text](:/targetNoteId#section-slug) - Link to specific section in note
    """
    # Runtime validation for Jan AI compatibility while preserving functionality
    note_id = validate_joplin_id(note_id)
    
    client = get_joplin_client()
    
    # Get the note
    note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
    
    note_title = getattr(note, 'title', 'Untitled')
    body = getattr(note, 'body', '')
    
    # Parse outgoing links using regex (with optional section slugs)
    import re
    link_pattern = r'\[([^\]]+)\]\(:/([a-zA-Z0-9]+)(?:#([^)]+))?\)'
    
    outgoing_links = []
    if body:
        lines = body.split('\n')
        for line_num, line in enumerate(lines, 1):
            matches = re.finditer(link_pattern, line)
            for match in matches:
                link_text = match.group(1)
                target_note_id = match.group(2)
                section_slug = match.group(3) if match.group(3) else None
                
                # Try to get the target note title
                try:
                    target_note = client.get_note(target_note_id, fields="id,title")
                    target_title = getattr(target_note, 'title', 'Unknown Note')
                    target_exists = True
                except:
                    target_title = "Note not found"
                    target_exists = False
                
                link_data = {
                    'text': link_text,
                    'target_id': target_note_id,
                    'target_title': target_title,
                    'target_exists': target_exists,
                    'line_number': line_num,
                    'line_context': line.strip()
                }
                
                # Add section slug if present
                if section_slug:
                    link_data['section_slug'] = section_slug
                
                outgoing_links.append(link_data)
    
    # Search for backlinks - notes that link to this note
    backlinks = []
    try:
        # Search for notes containing this note's ID in link format
        search_query = f":/{note_id}"
        backlink_results = client.search_all(query=search_query, fields=COMMON_NOTE_FIELDS)
        backlink_notes = process_search_results(backlink_results)
        
        # Filter out the current note and parse backlinks
        for source_note in backlink_notes:
            source_note_id = getattr(source_note, 'id', '')
            source_note_title = getattr(source_note, 'title', 'Untitled')
            source_body = getattr(source_note, 'body', '')
            
            # Skip if it's the same note
            if source_note_id == note_id:
                continue
                
            # Parse links in the source note that point to our note
            if source_body:
                lines = source_body.split('\n')
                for line_num, line in enumerate(lines, 1):
                    matches = re.finditer(link_pattern, line)
                    for match in matches:
                        link_text = match.group(1)
                        target_note_id = match.group(2)
                        section_slug = match.group(3) if match.group(3) else None
                        
                        # Only include if this link points to our note
                        if target_note_id == note_id:
                            backlink_data = {
                                'text': link_text,
                                'source_id': source_note_id,
                                'source_title': source_note_title,
                                'line_number': line_num,
                                'line_context': line.strip()
                            }
                            
                            # Add section slug if present
                            if section_slug:
                                backlink_data['section_slug'] = section_slug
                            
                            backlinks.append(backlink_data)
    except Exception as e:
        # If backlink search fails, continue without backlinks
        logger.warning(f"Failed to search for backlinks: {e}")
    
    # Format output optimized for LLM comprehension
    result_parts = [
        f"SOURCE_NOTE: {note_title}",
        f"NOTE_ID: {note_id}",
        f"TOTAL_OUTGOING_LINKS: {len(outgoing_links)}",
        f"TOTAL_BACKLINKS: {len(backlinks)}",
        ""
    ]
    
    # Add outgoing links section
    if outgoing_links:
        result_parts.append("OUTGOING_LINKS:")
        for i, link in enumerate(outgoing_links, 1):
            status = "VALID" if link['target_exists'] else "BROKEN"
            link_details = [
                f"  LINK_{i}:",
                f"    link_text: {link['text']}",
                f"    target_note_id: {link['target_id']}",
                f"    target_note_title: {link['target_title']}",
                f"    link_status: {status}",
            ]
            
            # Add section slug if present
            if 'section_slug' in link:
                link_details.append(f"    section_slug: {link['section_slug']}")
            
            link_details.extend([
                f"    line_number: {link['line_number']}",
                f"    line_context: {link['line_context']}",
                ""
            ])
            
            result_parts.extend(link_details)
    else:
        result_parts.extend([
            "OUTGOING_LINKS: None",
            ""
        ])
    
    # Add backlinks section
    if backlinks:
        result_parts.append("BACKLINKS:")
        for i, backlink in enumerate(backlinks, 1):
            backlink_details = [
                f"  BACKLINK_{i}:",
                f"    link_text: {backlink['text']}",
                f"    source_note_id: {backlink['source_id']}",
                f"    source_note_title: {backlink['source_title']}",
            ]
            
            # Add section slug if present
            if 'section_slug' in backlink:
                backlink_details.append(f"    section_slug: {backlink['section_slug']}")
            
            backlink_details.extend([
                f"    line_number: {backlink['line_number']}",
                f"    line_context: {backlink['line_context']}",
                ""
            ])
            
            result_parts.extend(backlink_details)
    else:
        result_parts.extend([
            "BACKLINKS: None",
            ""
        ])
    
    # Add status message
    if not outgoing_links and not backlinks:
        if not body:
            result_parts.append("STATUS: No content found in this note and no backlinks found")
        else:
            result_parts.append("STATUS: No note links found in this note and no backlinks found")
    else:
        result_parts.append("STATUS: Links and backlinks retrieved successfully")
    
    return "\n".join(result_parts)

@create_tool("create_note", "Create note")
async def create_note(
    title: Annotated[RequiredStringType, Field(description="Note title")], 
    notebook_name: Annotated[RequiredStringType, Field(description="Notebook name")], 
    body: Annotated[str, Field(description="Note content")] = "",
    is_todo: Annotated[OptionalBoolType, Field(description="Create as todo (default: False)")] = False,
    todo_completed: Annotated[Optional[Union[bool, str, int]], Field(description="Mark todo completed. Accepts: True/False (uses current time), epoch milliseconds (e.g. 1740700800000), or ISO datetime string 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD' (default: False)")] = False
) -> str:
    """Create a new note in a specified notebook in Joplin.

    Creates a new note with the specified title, content, and properties. Uses notebook name
    for easier identification instead of requiring notebook IDs.

    Returns:
        str: Success message with the created note's title and unique ID.

    Examples:
        - create_note("Shopping List", "Personal Notes", "- Milk\n- Eggs", True, False) - Create uncompleted todo
        - create_note("Meeting Notes", "Work Projects", "# Meeting with Client") - Create regular note
    """

    # Runtime validation for Jan AI compatibility while preserving functionality
    is_todo = flexible_bool_converter(is_todo)
    todo_completed_value, todo_warning = convert_todo_completed(todo_completed)

    # Use helper function to get notebook ID
    parent_id = get_notebook_id_by_name(notebook_name)

    client = get_joplin_client()
    note = client.add_note(
        title=title, body=body, parent_id=parent_id,
        is_todo=1 if is_todo else 0, todo_completed=todo_completed_value or 0
    )
    result = format_creation_success(ItemType.note, title, str(note))
    if todo_warning:
        result = f"{todo_warning}\n{result}"
    return result

@create_tool("update_note", "Update note")
async def update_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to update")],
    title: Annotated[Optional[str], Field(description="New title (optional)")] = None,
    body: Annotated[Optional[str], Field(description="New content (optional)")] = None,
    is_todo: Annotated[OptionalBoolType, Field(description="Convert to/from todo (optional)")] = None,
    todo_completed: Annotated[Optional[Union[bool, str, int]], Field(description="Mark todo completed. Accepts: True/False (uses current time), epoch milliseconds (e.g. 1740700800000), or ISO datetime string 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD' (optional)")] = None,
    parent_id: Annotated[Optional[str], Field(description="Move to different notebook (notebook ID, optional)")] = None,
    parent_notebook: Annotated[Optional[str], Field(description="Move to different notebook (notebook name, optional)")] = None,
    author: Annotated[Optional[str], Field(description="Note author (optional)")] = None,
    source_url: Annotated[Optional[str], Field(description="Source URL for web clips (optional)")] = None,
    latitude: Annotated[Optional[float], Field(description="GPS latitude coordinate (optional)")] = None,
    longitude: Annotated[Optional[float], Field(description="GPS longitude coordinate (optional)")] = None,
    altitude: Annotated[Optional[float], Field(description="GPS altitude coordinate (optional)")] = None,
    markup_language: Annotated[Optional[int], Field(description="Note markup format: 1=Markdown, 2=HTML (optional)")] = None,
    user_created_time: Annotated[Optional[int], Field(description="Custom creation timestamp in milliseconds (optional)")] = None,
    user_updated_time: Annotated[Optional[int], Field(description="Custom update timestamp in milliseconds (optional)")] = None
) -> str:
    """Update an existing note in Joplin.

    Updates one or more properties of an existing note. At least one field must be provided.
    Can update content and move between notebooks in a single operation.

    For moving notebooks: use either parent_id (notebook ID) OR parent_notebook (notebook name).
    For move-only operations: use move_note() or bulk_move_notes() for clearer intent.

    Returns:
        str: Success message confirming the note was updated.

    Examples:
        - update_note("note123", title="New Title") - Update only the title
        - update_note("note123", body="New content", is_todo=True) - Update content and convert to todo
        - update_note("note123", title="Archive Note", parent_notebook="Archive") - Update title AND move to Archive notebook
        - update_note("note123", title="Archive Note", parent_id="abc123def456") - Update title AND move using notebook ID
        - update_note("note123", latitude=40.7128, longitude=-74.0060) - Add GPS coordinates
    """

    # Runtime validation for Jan AI compatibility while preserving functionality
    note_id = validate_joplin_id(note_id)
    is_todo = flexible_bool_converter(is_todo)
    todo_completed_value, todo_warning = convert_todo_completed(todo_completed)

    # Handle parent_notebook → parent_id conversion
    if parent_notebook is not None and parent_id is not None:
        raise ValueError("Cannot specify both parent_id and parent_notebook. Use one or the other.")

    if parent_notebook is not None:
        parent_id = get_notebook_id_by_name(parent_notebook)

    # Setting todo_completed requires is_todo=True. Joplin silently accepts
    # todo_completed on non-todos but won't render a checkbox.
    if todo_completed_value and todo_completed_value > 0:
        if is_todo is not None and not is_todo:
            raise ValueError("Cannot set todo_completed on a non-todo note. Remove is_todo=False or set is_todo=True.")
        is_todo = True

    update_data = {}
    if title is not None: update_data["title"] = title
    if body is not None: update_data["body"] = body
    if is_todo is not None: update_data["is_todo"] = 1 if is_todo else 0
    if todo_completed_value is not None: update_data["todo_completed"] = todo_completed_value
    if parent_id is not None: update_data["parent_id"] = parent_id
    if author is not None: update_data["author"] = author
    if source_url is not None: update_data["source_url"] = source_url
    if latitude is not None: update_data["latitude"] = latitude
    if longitude is not None: update_data["longitude"] = longitude
    if altitude is not None: update_data["altitude"] = altitude
    if markup_language is not None: update_data["markup_language"] = markup_language
    if user_created_time is not None: update_data["user_created_time"] = user_created_time
    if user_updated_time is not None: update_data["user_updated_time"] = user_updated_time
    
    if not update_data:
        raise ValueError("At least one field must be provided for update")
    
    client = get_joplin_client()

    # Save revision before destructive content changes (title/body overwrite)
    if body is not None or title is not None:
        _save_note_revision(client, note_id)

    converted_update_data = apply_field_converters(**update_data)
    client.modify_note(note_id, **converted_update_data)
    result = format_update_success(ItemType.note, note_id)
    if todo_warning:
        result = f"{todo_warning}\n{result}"
    return result

@create_tool("move_note", "Move note to different notebook")
async def move_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to move")],
    target_notebook: Annotated[Optional[str], Field(description="Target notebook name to move note to")] = None,
    target_notebook_id: Annotated[Optional[str], Field(description="Target notebook ID (alternative to notebook name, optional)")] = None
) -> str:
    """Move a single note to a different notebook.
    
    Changes the parent notebook of a note by updating its parent_id field.
    Specify either target_notebook (name) OR target_notebook_id (ID) - one is required.
    
    Returns:
        str: Success message confirming the note was moved.
    
    Examples:
        - move_note("note123", target_notebook="Archive") - Move note123 to Archive notebook
        - move_note("note123", target_notebook_id="abc123def456") - Move using notebook ID
    """
    
    # Validate parameters
    note_id = validate_joplin_id(note_id)
    
    # Handle target_notebook → target_notebook_id conversion
    if target_notebook is None and target_notebook_id is None:
        raise ValueError("Must specify either target_notebook (name) or target_notebook_id (ID)")
    
    if target_notebook is not None and target_notebook_id is not None:
        raise ValueError("Cannot specify both target_notebook and target_notebook_id. Use one or the other.")
    
    if target_notebook is not None:
        target_notebook_id = get_notebook_id_by_name(target_notebook)
    
    target_notebook_id = validate_joplin_id(target_notebook_id)
    
    client = get_joplin_client()
    
    # Move the note (let Joplin API handle validation like update_note does)
    try:
        client.modify_note(note_id, parent_id=target_notebook_id)
        return f"✅ Note moved successfully to target notebook"
    except Exception as e:
        raise RuntimeError(f"Failed to move note: {e}")

@create_tool("bulk_move_notes", "Bulk move notes")
async def bulk_move_notes(
    note_ids: Annotated[List[str], Field(description="List of note IDs to move")],
    target_notebook: Annotated[Optional[str], Field(description="Target notebook name to move notes to")] = None,
    target_notebook_id: Annotated[Optional[str], Field(description="Target notebook ID (alternative to notebook name, optional)")] = None
) -> str:
    """Move multiple notes to a target notebook in a single operation.
    
    Efficiently moves multiple notes between notebooks by updating their parent_id field.
    Specify either target_notebook (name) OR target_notebook_id (ID) - one is required.
    
    Returns:
        str: Success message with details of the bulk move operation.
    
    Examples:
        - bulk_move_notes(["note1", "note2", "note3"], target_notebook="Archive") - Move 3 notes to Archive
        - bulk_move_notes(["note1", "note2"], target_notebook_id="abc123def456") - Move using notebook ID
    """
    
    # Handle target_notebook → target_notebook_id conversion
    if target_notebook is None and target_notebook_id is None:
        raise ValueError("Must specify either target_notebook (name) or target_notebook_id (ID)")
    
    if target_notebook is not None and target_notebook_id is not None:
        raise ValueError("Cannot specify both target_notebook and target_notebook_id. Use one or the other.")
    
    if target_notebook is not None:
        target_notebook_id = get_notebook_id_by_name(target_notebook)
    
    # Validate target notebook ID
    target_notebook_id = validate_joplin_id(target_notebook_id)
    
    # Validate all note IDs
    validated_note_ids = []
    for note_id in note_ids:
        validated_note_ids.append(validate_joplin_id(note_id))
    
    if not validated_note_ids:
        raise ValueError("At least one note ID must be provided")

    # Auto-backup database before bulk operation (once per day)
    _backup_joplin_database()

    client = get_joplin_client()
    
    # Perform bulk move operations (let Joplin API handle validation like update_note does)
    success_count = 0
    failed_moves = []
    
    for note_id in validated_note_ids:
        try:
            client.modify_note(note_id, parent_id=target_notebook_id)
            success_count += 1
        except Exception as e:
            failed_moves.append(f"Note {note_id}: {str(e)}")
    
    # Format response
    result_lines = [
        f"operation: bulk_move_notes",
        f"status: {'partial_success' if failed_moves else 'success'}",
        f"total_notes: {len(validated_note_ids)}",
        f"moved_successfully: {success_count}",
        f"target_notebook_id: {target_notebook_id}"
    ]
    
    if failed_moves:
        result_lines.append(f"failed_moves: {len(failed_moves)}")
        result_lines.extend([f"  - {error}" for error in failed_moves])
    
    return "\n".join(result_lines)

def extract_query_fields(query: str) -> List[str]:
    """Extract field names from query string (e.g. 'title:Example author:Albert' -> ['title', 'author'])"""
    import re
    pattern = r'(?:^|\s)(\w+):'
    fields = re.findall(pattern, query)
    return list(set(fields))  # Uniquify

def build_conditional_fields_list(**filter_params) -> List[str]:
    """Build list of fields needed for conditional checks from *_filter parameters"""
    conditional_fields = []
    
    # Use centralized field registry instead of hardcoded mapping
    for field_name in JOPLIN_NOTE_FIELDS.keys():
        filter_param_name = f"{field_name}_filter"
        if filter_params.get(filter_param_name) is not None:
            conditional_fields.append(field_name)
    
    return list(set(conditional_fields))  # Uniquify

def build_enhanced_field_list(base_fields: str, additional_fields: List[str]) -> str:
    """Combine base fields with additional fields, removing duplicates"""
    base_list = [f.strip() for f in base_fields.split(',')]
    all_fields = base_list + additional_fields
    unique_fields = list(dict.fromkeys(all_fields))  # Preserve order while uniquifying
    return ','.join(unique_fields)

def generate_field_pars(**params) -> dict:
    """Extract non-None field lists from parameters using registry.
    
    Returns:
        {
            'update_fields': [field_names with non-None update values],
            'filter_fields': [field_names with non-None filter values],
            'all_field_names': [all field names from registry]
        }
    """
    update_fields = []
    filter_fields = []
    all_field_names = list(JOPLIN_NOTE_FIELDS.keys())
    
    for field_name in all_field_names:
        if params.get(field_name) is not None:
            update_fields.append(field_name)
        if params.get(f"{field_name}_filter") is not None:
            filter_fields.append(field_name)
    
    return {
        'update_fields': update_fields,
        'filter_fields': filter_fields, 
        'all_field_names': all_field_names
    }

def generate_field_checks(notes, **params) -> bool:
    """Check if filter conditions match note values.
    
    Args:
        notes: The note object to check
        **params: Parameter values including filter values
        
    Returns:
        bool: True if all filter conditions match (or no conditions), False otherwise
    """
    field_pars = generate_field_pars(**params)
    filter_fields = field_pars['filter_fields']
    
    if not filter_fields:
        return True  # No conditions to check
    
    # Build lists for comparison using list operations
    filter_values_required = [params.get(f"{field}_filter") for field in filter_fields]
    filter_values_found = [getattr(notes, field, None) for field in filter_fields]
    
    return filter_values_required == filter_values_found

def get_conditional_fetch_fields(filter_fields) -> str:
    """Build comma-separated field string for fetching conditional check fields.
    
    Args:
        filter_fields: List of field names that need to be fetched
        
    Returns:
        str: Comma-separated field string (always includes 'id')
    """
    # Use list operations to build field list, ensuring 'id' is first
    fetch_fields = ['id'] + filter_fields
    unique_fields = list(dict.fromkeys(fetch_fields))  # Remove duplicates while preserving order
    return ','.join(unique_fields)

def apply_field_converters(**params) -> dict:
    """Apply type converters to field parameters using registry.
    
    Args:
        **params: All function parameters
        
    Returns:
        dict: Updated parameters with converted values
    """
    updated_params = params.copy()
    
    for field_name, field_info in JOPLIN_NOTE_FIELDS.items():
        converter = field_info['type_converter']
        
        # Apply converter to main field parameter
        if field_name in updated_params and updated_params[field_name] is not None:
            updated_params[field_name] = converter(updated_params[field_name])
        
        # Apply converter to filter parameter  
        filter_param = f"{field_name}_filter"
        if filter_param in updated_params and updated_params[filter_param] is not None:
            updated_params[filter_param] = converter(updated_params[filter_param])
    
    return updated_params

def extract_note_ids_from_result(formatted_result: str, limit: int) -> List[str]:
    """Extract note IDs from formatted search results, limited to specified count.
    
    Parses the formatted output from find_notes() to extract note IDs.
    Expected format contains lines like "  note_id: abc123def456..."
    
    Args:
        formatted_result: Formatted string output from find_notes()
        limit: Maximum number of note IDs to extract
        
    Returns:
        List of note IDs (up to limit count)
    """
    import re
    note_ids = []
    
    # Look for lines containing "note_id: " followed by the ID
    pattern = r'^\s*note_id:\s*([a-f0-9]{32})'
    
    for line in formatted_result.split('\n'):
        match = re.match(pattern, line)
        if match and len(note_ids) < limit:
            note_ids.append(match.group(1))
    
    return note_ids


# --- Database backup for bulk operations ---

_JOPLIN_DB_PATH = Path.home() / ".config" / "joplin-desktop" / "database.sqlite"
_BACKUP_DIR = Path.home() / "JoplinBackup" / "default" / "mcp-backups"
_BACKUP_RETENTION = 10  # keep last N backups


def _backup_joplin_database(force: bool = False) -> Optional[str]:
    """Create a SQLite backup of the Joplin database.

    Uses sqlite3's .backup command for a safe, consistent snapshot even
    while Joplin Desktop is running.

    By default (force=False): creates auto-backup with once-per-day guard,
    subject to automatic retention cleanup (last 10 kept).

    With force=True: creates manual backup that is never auto-deleted,
    requiring explicit user cleanup.

    Args:
        force: If True, create manual backup (no daily guard, no auto-cleanup)

    Returns:
        Backup file path on success, None on skip or failure
    """
    if not _JOPLIN_DB_PATH.exists():
        logger.warning(f"Joplin database not found at {_JOPLIN_DB_PATH}")
        return None

    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if force:
        # Manual backup — never auto-deleted
        backup_path = _BACKUP_DIR / f"joplin_manual_backup_{timestamp}.sqlite"
    else:
        # Auto backup — once-per-day guard
        today = datetime.date.today().strftime("%Y%m%d")
        existing = list(_BACKUP_DIR.glob(f"joplin_auto_backup_{today}_*.sqlite"))
        if existing:
            logger.info(f"Daily auto-backup already exists: {existing[0].name}")
            return str(existing[0])
        backup_path = _BACKUP_DIR / f"joplin_auto_backup_{timestamp}.sqlite"

    try:
        result = subprocess.run(
            ["sqlite3", str(_JOPLIN_DB_PATH), f".backup '{backup_path}'"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            logger.warning(f"SQLite backup failed: {result.stderr}")
            return None

        logger.info(f"Database backup created: {backup_path}")

        # Enforce retention on auto-backups only (manual backups never auto-deleted)
        if not force:
            auto_backups = sorted(_BACKUP_DIR.glob("joplin_auto_backup_*.sqlite"), reverse=True)
            for old_backup in auto_backups[_BACKUP_RETENTION:]:
                old_backup.unlink()
                logger.info(f"Removed old auto-backup: {old_backup.name}")

        return str(backup_path)

    except Exception as e:
        logger.warning(f"Database backup failed: {e}")
        return None


# diff-match-patch instance and patch class for revision creation/reading
_dmp = dmp_module.diff_match_patch()
_PatchObj = type(_dmp.patch_make('', 'x')[0])  # diff_match_patch.patch_obj


def _save_note_revision(client: ClientApi, note_id: str) -> Optional[str]:
    """Save current note content as a Joplin revision before overwriting.

    Creates a revision snapshot using Joplin's native revision system.
    Follows Joplin's createNoteRevision_ algorithm:
    - If prior revisions exist: reconstructs previous state, diffs sequentially,
      sets parent_id to chain with existing revisions
    - If no prior revisions: diffs from empty string (first revision)

    Uses client.add_revision() with corrected millisecond timestamps
    (joppy bug: uses seconds internally — our kwargs override via **data).

    Args:
        client: Configured joppy ClientApi instance
        note_id: ID of the note to snapshot

    Returns:
        Revision ID string on success, None on failure (logs warning)
    """
    try:
        note = client.get_note(note_id, fields="id,parent_id,title,body,is_todo,todo_completed")

        title = getattr(note, 'title', '') or ''
        body = getattr(note, 'body', '') or ''
        notebook_id = getattr(note, 'parent_id', '') or ''
        is_todo = getattr(note, 'is_todo', 0) or 0
        todo_completed = getattr(note, 'todo_completed', 0) or 0

        # Find the latest existing revision for this note
        prev_title = ''
        prev_body = ''
        parent_rev_id = ''

        try:
            all_revs = client.get_all_revisions(fields="id,item_id,created_time")
            note_revs = [r for r in all_revs if getattr(r, 'item_id', '') == note_id]
            if note_revs:
                note_revs.sort(key=lambda r: getattr(r, 'created_time', 0), reverse=True)
                latest_rev = note_revs[0]
                parent_rev_id = latest_rev.id
                # Reconstruct previous state from the revision chain
                prev_content = _reconstruct_revision_content(client, parent_rev_id)
                prev_title = prev_content['title']
                prev_body = prev_content['body']
        except Exception as e:
            logger.debug(f"Could not find parent revision for note {note_id}: {e}")

        # Create diffs from previous state to current content
        title_diff = _dmp.patch_toText(_dmp.patch_make(prev_title, title))
        body_diff = _dmp.patch_toText(_dmp.patch_make(prev_body, body))

        # Build metadata_diff: track what changed from previous metadata
        new_metadata = {
            "id": note_id,
            "parent_id": notebook_id,
            "is_todo": is_todo,
            "todo_completed": todo_completed,
            "title": title,
        }
        metadata_diff = json.dumps({
            "new": new_metadata,
            "deleted": []
        })

        now_ms = int(time.time() * 1000)

        revision_data = {
            "item_updated_time": now_ms,
            "item_created_time": now_ms,
            "title_diff": title_diff,
            "body_diff": body_diff,
            "metadata_diff": metadata_diff,
        }
        if parent_rev_id:
            revision_data["parent_id"] = parent_rev_id

        rev_id = client.add_revision(
            item_id=note_id,
            item_type=joppy.data_types.ItemType.NOTE,
            **revision_data,
        )
        logger.info(f"Saved revision {rev_id} for note {note_id} (parent: {parent_rev_id or 'none'})")
        return rev_id

    except Exception as e:
        logger.warning(f"Failed to save revision for note {note_id}: {e}")
        return None


@create_tool("search_and_bulk_update_preview", "Search and bulk update preview")
async def search_and_bulk_update_preview(
    query: Annotated[str, Field(description="Search text or '*' for all notes")],
    preview_limit: Annotated[int, Field(description="Number of notes to show in preview (default: 5)")] = 5,
    inspect_count: Annotated[int, Field(description="Number of notes to show full content for (default: 2)")] = 2,
    get_conditional_update_counts: Annotated[bool, Field(description="Gets affected vs skipped counts based on filters for conditional updates (slower but more accurate)")] = False,
    condition_search_on_TODOs: Annotated[bool, Field(description="Add filters to search query to match current_is_todo and current_todo_completed (default: False)")] = False,
    # Update-parameters (optional)
    title: Annotated[Optional[str], Field(description="New title to simulate (optional)")] = None,
    body: Annotated[Optional[str], Field(description="New content to simulate (optional)")] = None,
    is_todo: Annotated[OptionalBoolType, Field(description="Convert to/from todo to simulate (optional)")] = None,
    todo_completed: Annotated[Optional[Union[bool, str, int]], Field(description="Mark todo completed to simulate. Accepts: True/False (uses current time), epoch milliseconds, or ISO datetime 'YYYY-MM-DD HH:MM' / 'YYYY-MM-DD' (optional)")] = None,
    parent_id: Annotated[Optional[str], Field(description="Move notes to different notebook to simulate (notebook ID, optional)")] = None,
    parent_notebook: Annotated[Optional[str], Field(description="Move notes to different notebook to simulate (notebook name, optional)")] = None,
    author: Annotated[Optional[str], Field(description="Note author to simulate (optional)")] = None,
    source_url: Annotated[Optional[str], Field(description="Source URL to simulate (optional)")] = None,
    latitude: Annotated[Optional[float], Field(description="GPS latitude coordinate to simulate (optional)")] = None,
    longitude: Annotated[Optional[float], Field(description="GPS longitude coordinate to simulate (optional)")] = None,
    altitude: Annotated[Optional[float], Field(description="GPS altitude coordinate to simulate (optional)")] = None,
    markup_language: Annotated[Optional[int], Field(description="Note markup format: 1=Markdown, 2=HTML to simulate (optional)")] = None,
    user_created_time: Annotated[Optional[int], Field(description="Custom creation timestamp in milliseconds to simulate (optional)")] = None,
    user_updated_time: Annotated[Optional[int], Field(description="Custom update timestamp in milliseconds to simulate (optional)")] = None,
    # Filter-parameters for Conditional updates
    title_filter: Annotated[Optional[str], Field(description="Only update if current title matches this (optional)")] = None,
    body_filter: Annotated[Optional[str], Field(description="Only update if current body matches this (optional)")] = None,
    is_todo_filter: Annotated[OptionalBoolType, Field(description="Only update if current is_todo matches this (optional)")] = None,
    todo_completed_filter: Annotated[OptionalBoolType, Field(description="Only update if current todo_completed matches this (optional)")] = None,
    parent_id_filter: Annotated[Optional[str], Field(description="Only update if current parent_id matches this (optional)")] = None,
    author_filter: Annotated[Optional[str], Field(description="Only update if current author matches this (optional)")] = None,
    source_url_filter: Annotated[Optional[str], Field(description="Only update if current source_url matches this (optional)")] = None,
    latitude_filter: Annotated[Optional[float], Field(description="Only update if current latitude matches this (optional)")] = None,
    longitude_filter: Annotated[Optional[float], Field(description="Only update if current longitude matches this (optional)")] = None,
    altitude_filter: Annotated[Optional[float], Field(description="Only update if current altitude matches this (optional)")] = None,
    markup_language_filter: Annotated[Optional[int], Field(description="Only update if current markup_language matches this (optional)")] = None,
    user_created_time_filter: Annotated[Optional[int], Field(description="Only update if current user_created_time matches this (optional)")] = None,
    user_updated_time_filter: Annotated[Optional[int], Field(description="Only update if current user_updated_time matches this (optional)")] = None
) -> str:
    """Preview search results for bulk update operations.
    
    Shows three levels of information:
    1a. Total count of matching notes
    (faster: obtained from search query return from pagination header)
    1b. Total notes to be updated or skipped based on filters 
    (slower: only returned if get_conditional_update_counts = True)
    2. Preview of first N notes with metadata (titles, IDs, dates)
    3. Full content inspection of first few notes for verification
    
    This function helps verify what notes would be affected before executing bulk updates.
    
    Returns:
        str: Complete preview with count, metadata, and content samples
        
    Examples:
        - search_and_bulk_update_preview("project") - Preview notes containing "project"
        - search_and_bulk_update_preview("*", task=True, preview_limit=10) - Preview 10 todos
    """
    
    # NOTE: todo_completed is handled by convert_todo_completed() in the registry type_converter,
    # which preserves timestamp information. No early bool conversion needed.
    
    # Handle parent_notebook → parent_id conversion
    if parent_notebook is not None and parent_id is not None:
        raise ValueError("Cannot specify both parent_id and parent_notebook. Use one or the other.")
    
    if parent_notebook is not None:
        parent_id = get_notebook_id_by_name(parent_notebook)
    
    client = get_joplin_client()
    
    # Build enhanced field list for search phase (to verify query success)
    query_fields = extract_query_fields(query)
    search_fields = build_enhanced_field_list(COMMON_NOTE_FIELDS, query_fields)
    
    # Build conditional field list for GET phase (only fields needed for conditional checks)
    field_pars = generate_field_pars(**locals())
    filter_fields = field_pars['filter_fields']
    get_fields = get_conditional_fetch_fields(filter_fields)
    
    # Get notes using conditional search logic
    try:
        if condition_search_on_TODOs:
            # Use alondmnt's query building logic with *_filter parameters
            if query.strip() == "*":
                # List all notes with filters
                search_filters = build_general_search_filters(**locals())
                
                if search_filters:
                    # Use search with filters
                    search_query = " ".join(search_filters)
                    results = client.search_all(query=search_query, fields=search_fields)
                    notes = process_search_results(results)
                else:
                    # No filters, get all notes
                    results = client.get_all_notes(fields=search_fields)
                    notes = process_search_results(results)
                    # Sort by updated time, newest first
                    notes = sorted(notes, key=lambda x: getattr(x, 'updated_time', 0), reverse=True)
            else:
                # Build search query with text and filters
                search_parts = [query]
                search_parts.extend(build_general_search_filters(**locals()))
                
                search_query = " ".join(search_parts)
                results = client.search_all(query=search_query, fields=search_fields)
                notes = process_search_results(results)
        else:
            # Just use user's raw query string directly
            if query.strip() == "*":
                results = client.get_all_notes(fields=search_fields)
                notes = process_search_results(results)
                # Sort by updated time, newest first
                notes = sorted(notes, key=lambda x: getattr(x, 'updated_time', 0), reverse=True)
            else:
                results = client.search_all(query=query, fields=search_fields)
                notes = process_search_results(results)
        
        # Apply pagination for preview
        paginated_notes, total_count = apply_pagination(notes, preview_limit, 0)
        
        if not paginated_notes:
            return f"No notes found matching query: {query}"
        
        # Format preview result using the same function as find_notes
        if query.strip() == "*":
            search_description = "all notes"
        else:
            search_description = f'text search: {query}'
        
        preview_result = format_search_results_with_pagination(
            search_description, paginated_notes, total_count, preview_limit, 0, "search_results", original_query=query
        )
        
        # Simulate conditional updates if requested
        affected_count = 0
        skipped_count = 0
        conditional_simulation_result = ""
        
        if get_conditional_update_counts:
            # Use same conditional logic as search_and_bulk_update_execute
            def should_update_field(note, field_name, new_value, current_required_value):
                if new_value is None:
                    return False
                if current_required_value is None:
                    return True
                current_value = getattr(note, field_name, None)
                return current_value == current_required_value
            
            # Use helper functions to replace hardcoded field enumeration
            field_pars = generate_field_pars(**locals())
            update_fields = field_pars['update_fields']
            update_fields_provided = len(update_fields) > 0
            
            if update_fields_provided:
                # Simulate updates on all found notes (not just paginated preview)
                for search_note in notes:
                    note_id = getattr(search_note, 'id')
                    
                    # Fetch individual note with only needed fields for conditional checks
                    if filter_fields:
                        note_fields = client.get_note(note_id, fields=get_fields)  # get_fields already includes 'id'
                    else:
                        # Convert search_note to same structure as client.get_note for consistency
                        note_fields = search_note
                    
                    # Use helper functions to replace hardcoded field enumeration
                    field_pars = generate_field_pars(**locals())
                    has_updates = len(field_pars['update_fields']) > 0
                    conditions_match = generate_field_checks(note_fields, **locals())
                    
                    if has_updates and conditions_match:
                        affected_count += 1
                    else:
                        skipped_count += 1
                
                conditional_simulation_result = f"\n\n=== CONDITIONAL UPDATE SIMULATION ===\nTotal notes found: {total_count}\nNotes that would be updated: {affected_count}\nNotes that would be skipped: {skipped_count}\n"
        
        # Extract note IDs for content inspection
        note_ids = extract_note_ids_from_result(preview_result, inspect_count)
        
        # Get full content for specified notes using direct API calls
        full_content_parts = []
        if note_ids:
            for note_id in note_ids:
                try:
                    # Use client.get_note directly (following alondmnt's pattern)
                    note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
                    if note and hasattr(note, 'body') and hasattr(note, 'title'):
                        content_preview = note.body[:500] + "..." if len(note.body) > 500 else note.body
                        full_content_parts.append(f"--- NOTE {note_id} ({note.title}) ---\n{content_preview}\n")
                    else:
                        full_content_parts.append(f"--- NOTE {note_id} ERROR ---\nNote not found or incomplete data\n")
                except Exception as e:
                    full_content_parts.append(f"--- NOTE {note_id} ERROR ---\nCould not retrieve: {str(e)}\n")
    
    except Exception as e:
        return f"Error during preview: {str(e)}"
    
    # Combine preview with conditional simulation and content inspection
    result_parts = [preview_result]
    
    # Add conditional simulation results if performed
    if conditional_simulation_result:
        result_parts.append(conditional_simulation_result)
    
    if full_content_parts:
        result_parts.extend([
            "\n=== FULL CONTENT INSPECTION ===",
            f"Showing full content for first {len(note_ids)} notes for verification:\n"
        ])
        result_parts.extend(full_content_parts)
    
    return "\n".join(result_parts)

@create_tool("search_and_bulk_update_execute", "Search and bulk update execute")
async def search_and_bulk_update_execute(
    query: Annotated[str, Field(description="Search text or '*' for all notes (must match preview)")],
    expected_count: Annotated[int, Field(description="Expected number of notes from preview")],
    first_title: Annotated[str, Field(description="Title of first note from preview")],
    # All possible update parameters from update_note function
    title: Annotated[Optional[str], Field(description="New title (optional)")] = None,
    body: Annotated[Optional[str], Field(description="New content (optional)")] = None,
    is_todo: Annotated[OptionalBoolType, Field(description="Convert to/from todo (optional)")] = None,
    todo_completed: Annotated[Optional[Union[bool, str, int]], Field(description="Mark todo completed. Accepts: True/False (uses current time), epoch milliseconds, or ISO datetime 'YYYY-MM-DD HH:MM' / 'YYYY-MM-DD' (optional)")] = None,
    parent_id: Annotated[Optional[str], Field(description="Move notes to different notebook (notebook ID, optional)")] = None,
    parent_notebook: Annotated[Optional[str], Field(description="Move notes to different notebook (notebook name, optional)")] = None,
    author: Annotated[Optional[str], Field(description="Note author (optional)")] = None,
    source_url: Annotated[Optional[str], Field(description="Source URL for web clips (optional)")] = None,
    latitude: Annotated[Optional[float], Field(description="GPS latitude coordinate (optional)")] = None,
    longitude: Annotated[Optional[float], Field(description="GPS longitude coordinate (optional)")] = None,
    altitude: Annotated[Optional[float], Field(description="GPS altitude coordinate (optional)")] = None,
    markup_language: Annotated[Optional[int], Field(description="Note markup format: 1=Markdown, 2=HTML (optional)")] = None,
    user_created_time: Annotated[Optional[int], Field(description="Custom creation timestamp in milliseconds (optional)")] = None,
    user_updated_time: Annotated[Optional[int], Field(description="Custom update timestamp in milliseconds (optional)")] = None,
    # Filter parameters - only update if current value matches (consistent with preview function)
    title_filter: Annotated[Optional[str], Field(description="Only update if current title matches this (optional)")] = None,
    body_filter: Annotated[Optional[str], Field(description="Only update if current body matches this (optional)")] = None,
    is_todo_filter: Annotated[OptionalBoolType, Field(description="Only update if current is_todo matches this (optional)")] = None,
    todo_completed_filter: Annotated[OptionalBoolType, Field(description="Only update if current todo_completed matches this (optional)")] = None,
    parent_id_filter: Annotated[Optional[str], Field(description="Only update if current parent_id matches this (optional)")] = None,
    author_filter: Annotated[Optional[str], Field(description="Only update if current author matches this (optional)")] = None,
    source_url_filter: Annotated[Optional[str], Field(description="Only update if current source_url matches this (optional)")] = None,
    latitude_filter: Annotated[Optional[float], Field(description="Only update if current latitude matches this (optional)")] = None,
    longitude_filter: Annotated[Optional[float], Field(description="Only update if current longitude matches this (optional)")] = None,
    altitude_filter: Annotated[Optional[float], Field(description="Only update if current altitude matches this (optional)")] = None,
    markup_language_filter: Annotated[Optional[int], Field(description="Only update if current markup_language matches this (optional)")] = None,
    user_created_time_filter: Annotated[Optional[int], Field(description="Only update if current user_created_time matches this (optional)")] = None,
    user_updated_time_filter: Annotated[Optional[int], Field(description="Only update if current user_updated_time matches this (optional)")] = None
) -> str:
    """Execute bulk update operation on notes matching search criteria.
    
    Performs bulk updates on all notes matching the search query after safety verification.
    The query and expected results must match what was shown in the preview.
    
    Returns:
        str: Detailed results of the bulk update operation including success/failure counts
        
    Examples:
        - search_and_bulk_update_execute("project", 15, "Project Meeting", parent_id="archive_id")
        - search_and_bulk_update_execute("*", 200, "Daily Notes", is_todo=True, task=True)
    """
    
    # Runtime validation for Jan AI compatibility
    is_todo = flexible_bool_converter(is_todo)
    # Note: todo_completed is NOT converted here — the registry type_converter
    # (convert_todo_completed) handles it during per-note update to write proper timestamps
    task = flexible_bool_converter(task)
    completed = flexible_bool_converter(completed)

    # Handle parent_notebook → parent_id conversion
    if parent_notebook is not None and parent_id is not None:
        raise ValueError("Cannot specify both parent_id and parent_notebook. Use one or the other.")

    if parent_notebook is not None:
        parent_id = get_notebook_id_by_name(parent_notebook)

    # Validate conditional parameters
    is_todo_filter = flexible_bool_converter(is_todo_filter)
    todo_completed_filter = flexible_bool_converter(todo_completed_filter)
    
    def should_update_field(note, field_name, new_value, current_required_value):
        """Check if a field should be updated based on conditions"""
        if new_value is None:                    # Not updating this field
            return False
        if current_required_value is None:       # No condition - update unconditionally  
            return True
        
        # Check if note's current value matches required current value
        current_value = getattr(note, field_name, None)
        return current_value == current_required_value
    
    # Check if any update fields are provided using helper function
    field_pars = generate_field_pars(**locals())
    update_fields = field_pars['update_fields']
    
    if not update_fields:
        raise ValueError("At least one update field must be provided")

    # Auto-backup database before bulk operation (once per day)
    _backup_joplin_database()

    # Re-run search to get current results (bypass pagination to get all results)
    client = get_joplin_client()
    
    # Handle special case for listing all notes with filters
    if query.strip() == "*":
        search_filters = build_general_search_filters(**locals())
        if search_filters:
            search_query = " ".join(search_filters)
            results = client.search_all(query=search_query, fields=COMMON_NOTE_FIELDS)
            notes = process_search_results(results)
        else:
            results = client.get_all_notes(fields=COMMON_NOTE_FIELDS)
            notes = process_search_results(results)
    else:
        # Regular text search with filters
        search_filters = build_general_search_filters(**locals())
        if search_filters:
            combined_query = f"{query} {' '.join(search_filters)}"
            results = client.search_all(query=combined_query, fields=COMMON_NOTE_FIELDS)
        else:
            results = client.search_all(query=query, fields=COMMON_NOTE_FIELDS)
        notes = process_search_results(results)
    
    # Safety verification
    if len(notes) != expected_count:
        raise ValueError(f"Search results have changed: expected {expected_count} notes, found {len(notes)}")
    
    if notes and getattr(notes[0], 'title', '') != first_title:
        actual_first = getattr(notes[0], 'title', 'Unknown')
        raise ValueError(f"First note has changed: expected '{first_title}', found '{actual_first}'")
    
    # Perform bulk updates using registry-based approach (matches preview function)
    field_pars = generate_field_pars(**locals())
    update_fields = field_pars['update_fields']
    
    success_count = 0
    failed_updates = []
    skipped_count = 0
    
    for note in notes:
        note_id = getattr(note, 'id')
        try:
            # Build update_data with conditional logic using registry
            update_data = {}
            for field_name in update_fields:
                new_value = locals().get(field_name)
                filter_value = locals().get(f"{field_name}_filter")
                type_converter = JOPLIN_NOTE_FIELDS[field_name]['type_converter']
                
                if should_update_field(note, field_name, new_value, filter_value):
                    update_data[field_name] = type_converter(new_value)
            
            # Only update if some fields passed conditions
            if update_data:
                # Save revision before destructive content changes (title/body)
                if 'body' in update_data or 'title' in update_data:
                    _save_note_revision(client, note_id)
                client.modify_note(note_id, **update_data)
                success_count += 1
            else:
                skipped_count += 1
                
        except Exception as e:
            failed_updates.append(f"Note {note_id} ({getattr(note, 'title', 'Unknown')}): {str(e)}")
    
    # Format response - show all fields that had update values provided using registry
    attempted_updates = []
    for field_name in update_fields:
        new_value = locals().get(field_name)
        filter_value = locals().get(f"{field_name}_filter")
        condition_text = f" (if current={filter_value})" if filter_value is not None else ""
        attempted_updates.append(f"{field_name}: {new_value}{condition_text}")
    
    result_lines = [
        f"operation: search_and_bulk_update_execute",
        f"status: {'partial_success' if failed_updates else 'success'}",
        f"search_query: {query}",
        f"total_notes: {len(notes)}",
        f"updated_successfully: {success_count}",
        f"skipped_notes: {skipped_count}",
        f"attempted_updates: {', '.join(attempted_updates) if attempted_updates else 'none'}"
    ]
    
    if failed_updates:
        result_lines.append(f"failed_updates: {len(failed_updates)}")
        result_lines.extend([f"  - {error}" for error in failed_updates])
    
    return "\n".join(result_lines)

@create_tool("delete_note", "Delete note")
async def delete_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to delete")]
) -> str:
    """Delete a note from Joplin (moves to trash).

    Moves a note to Joplin's trash. The note can be restored from trash in Joplin Desktop.

    Returns:
        str: Success message confirming the note was moved to trash.
    """
    # Runtime validation for Jan AI compatibility while preserving functionality
    note_id = validate_joplin_id(note_id)

    client = get_joplin_client()
    # NOTE: joppy's delete_note() accepts permanent=1 via **query kwargs to bypass trash.
    # We intentionally do NOT expose that capability — all deletes go to trash for safety.
    client.delete_note(note_id)
    return format_delete_success(ItemType.note, note_id)

@create_tool("list_trash", "List trashed items")
async def list_trash(
    item_type: Annotated[Optional[str], Field(description="Filter by type: 'note', 'notebook', or None for both (default: None)")] = None,
    limit: Annotated[LimitType, Field(description="Max results (1-100, default: 20)")] = 20,
    offset: Annotated[OffsetType, Field(description="Skip count for pagination (default: 0)")] = 0
) -> str:
    """List items in Joplin's trash.

    Shows notes and/or notebooks that have been soft-deleted (moved to trash).
    These items can be restored with restore_from_trash.

    Returns:
        str: List of trashed items with title, ID, deletion date, and original notebook.
    """
    import datetime as dt_module

    client = get_joplin_client()
    epoch_zero = dt_module.datetime(1970, 1, 1, 0, 0)
    results = []

    if item_type is None or item_type == "note":
        notes = client.get_all_notes(
            fields="id,title,deleted_time,parent_id,is_todo",
            include_deleted=1
        )
        trashed_notes = [
            n for n in notes
            if getattr(n, 'deleted_time', None) and n.deleted_time != epoch_zero
        ]
        for n in trashed_notes:
            results.append({
                "type": "note",
                "id": n.id,
                "title": getattr(n, 'title', 'Untitled'),
                "deleted_time": n.deleted_time,
                "parent_id": getattr(n, 'parent_id', ''),
                "is_todo": getattr(n, 'is_todo', False),
            })

    if item_type is None or item_type == "notebook":
        notebooks = client.get_all_notebooks(
            fields="id,title,deleted_time,parent_id",
            include_deleted=1
        )
        trashed_notebooks = [
            n for n in notebooks
            if getattr(n, 'deleted_time', None) and n.deleted_time != epoch_zero
        ]
        for n in trashed_notebooks:
            results.append({
                "type": "notebook",
                "id": n.id,
                "title": getattr(n, 'title', 'Untitled'),
                "deleted_time": n.deleted_time,
                "parent_id": getattr(n, 'parent_id', ''),
            })

    # Sort by deletion time, most recent first
    results.sort(key=lambda x: x["deleted_time"], reverse=True)

    total_count = len(results)

    # Apply pagination
    paginated = results[offset:offset + limit]

    if not paginated:
        return f"TRASH_ITEMS: 0\nSTATUS: Trash is empty"

    # Build notebook name lookup for parent_id display
    try:
        all_notebooks = client.get_all_notebooks(fields="id,title", include_deleted=1)
        nb_map = {getattr(nb, 'id', ''): getattr(nb, 'title', 'Unknown') for nb in all_notebooks}
    except Exception:
        nb_map = {}

    lines = [
        f"TRASH_ITEMS: {total_count}",
        f"SHOWING: {offset + 1}-{offset + len(paginated)} of {total_count}",
        ""
    ]

    for i, item in enumerate(paginated, offset + 1):
        deleted_str = format_timestamp(item["deleted_time"])
        parent_name = nb_map.get(item["parent_id"], item["parent_id"][:12] + "...")
        lines.append(f"ITEM_{i}:")
        lines.append(f"  type: {item['type']}")
        lines.append(f"  id: {item['id']}")
        lines.append(f"  title: {item['title']}")
        lines.append(f"  deleted: {deleted_str}")
        lines.append(f"  original_notebook: {parent_name}")
        if item["type"] == "note" and item.get("is_todo"):
            lines.append(f"  is_todo: true")

    return "\n".join(lines)

@create_tool("restore_from_trash", "Restore item from trash")
async def restore_from_trash(
    item_id: Annotated[JoplinIdType, Field(description="Note or notebook ID to restore")],
    item_type: Annotated[str, Field(description="Item type: 'note' or 'notebook'")] = "note"
) -> str:
    """Restore a note or notebook from Joplin's trash.

    Restores a previously deleted item by setting its deleted_time back to 0.
    The item reappears in its original notebook. If the original notebook was also
    trashed, restore it first or the note may not be visible.

    Returns:
        str: Success message confirming the item was restored.
    """
    item_id = validate_joplin_id(item_id)
    client = get_joplin_client()

    if item_type == "note":
        client.modify_note(item_id, deleted_time=0)
        return f"""OPERATION: RESTORE_FROM_TRASH
STATUS: SUCCESS
ITEM_TYPE: note
ITEM_ID: {item_id}
MESSAGE: Note restored from trash to its original notebook"""
    elif item_type == "notebook":
        client.modify_notebook(item_id, deleted_time=0)
        return f"""OPERATION: RESTORE_FROM_TRASH
STATUS: SUCCESS
ITEM_TYPE: notebook
ITEM_ID: {item_id}
MESSAGE: Notebook restored from trash"""
    else:
        raise ValueError(f"item_type must be 'note' or 'notebook', got '{item_type}'")

@create_tool("get_note_history", "Get note revision history")
async def get_note_history(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to get revision history for")]
) -> str:
    """List all saved revisions for a specific note.

    Shows the revision history with timestamps, enabling recovery of previous
    versions via Joplin Desktop's "Note History" UI or restore_note_revision.
    Revisions are created automatically by Joplin Desktop (every 10 minutes)
    and by MCP's auto-backup before title/body overwrites.

    Returns:
        str: List of revisions with timestamps, titles, and chain information.
    """
    note_id = validate_joplin_id(note_id)
    client = get_joplin_client()

    # Get all revisions and filter to this note
    all_revs = client.get_all_revisions(
        fields="id,item_id,item_type,item_updated_time,parent_id,created_time,title_diff,metadata_diff"
    )
    note_revs = [r for r in all_revs if getattr(r, 'item_id', '') == note_id]

    if not note_revs:
        return f"NOTE_ID: {note_id}\nREVISIONS: 0\nSTATUS: No revision history found for this note"

    # Sort by created_time, most recent first
    note_revs.sort(key=lambda r: getattr(r, 'created_time', 0), reverse=True)

    # Try to get current note title for context
    try:
        note = client.get_note(note_id, fields="id,title")
        current_title = getattr(note, 'title', 'Unknown')
    except Exception:
        current_title = "Unknown (note may be deleted)"

    lines = [
        f"NOTE_ID: {note_id}",
        f"CURRENT_TITLE: {current_title}",
        f"REVISIONS: {len(note_revs)}",
        ""
    ]

    for i, rev in enumerate(note_revs, 1):
        rev_time = format_timestamp(getattr(rev, 'created_time', None))
        parent_id = getattr(rev, 'parent_id', '') or ''

        # Extract title from title_diff by applying patch to empty string
        rev_title = None
        title_diff = getattr(rev, 'title_diff', '') or ''
        if title_diff and title_diff != '[]':
            try:
                patched = _apply_diff(title_diff, '')
                if patched:
                    rev_title = patched
            except Exception:
                pass

        # Fall back to metadata_diff for title
        if not rev_title:
            metadata_diff = getattr(rev, 'metadata_diff', '') or ''
            if metadata_diff:
                try:
                    md = json.loads(metadata_diff)
                    rev_title = md.get('new', {}).get('title', None)
                except Exception:
                    pass

        lines.append(f"REVISION_{i}:")
        lines.append(f"  revision_id: {rev.id}")
        lines.append(f"  created: {rev_time}")
        if rev_title:
            lines.append(f"  title: {rev_title}")
        lines.append(f"  has_parent: {'yes' if parent_id else 'no (first revision)'}")
        if parent_id:
            lines.append(f"  parent_id: {parent_id}")

    return "\n".join(lines)


def _apply_diff(diff_text: str, base: str) -> str:
    """Apply a diff-match-patch diff to a base string.

    Handles both Joplin's JSON format (starts with '[') and legacy format (starts with '@@').

    Args:
        diff_text: The diff string in either JSON or legacy format
        base: The base string to apply the diff to

    Returns:
        The patched string result

    Raises:
        ValueError: If diff cannot be parsed or applied
    """
    if not diff_text or diff_text == '[]':
        return base

    if diff_text.startswith('['):
        # JSON format
        patch_dicts = json.loads(diff_text)
        patches = []
        for pd in patch_dicts:
            p = _PatchObj()
            p.diffs = [tuple(d) for d in pd['diffs']]
            p.start1 = pd['start1']
            p.start2 = pd['start2']
            p.length1 = pd['length1']
            p.length2 = pd['length2']
            patches.append(p)
    else:
        # Legacy format (starts with @@)
        patches = _dmp.patch_fromText(diff_text)

    patched, results = _dmp.patch_apply(patches, base)
    if not all(results):
        failed = sum(1 for r in results if not r)
        logger.warning(f"Patch application had {failed} failed hunks out of {len(results)}")
    return patched


def _reconstruct_revision_content(client: ClientApi, revision_id: str) -> dict:
    """Reconstruct full note content from a revision by walking the parent chain.

    Follows parent_id links back to the first revision, then applies diffs
    sequentially to reconstruct title, body, and metadata.

    Args:
        client: Configured joppy ClientApi instance
        revision_id: ID of the revision to reconstruct

    Returns:
        dict with keys: 'title', 'body', 'metadata' (parsed metadata_diff)
    """
    # Collect the chain from target revision back to root
    chain = []
    current_id = revision_id

    while current_id:
        rev = client.get_revision(current_id, fields="id,parent_id,title_diff,body_diff,metadata_diff")
        chain.append(rev)
        current_id = getattr(rev, 'parent_id', '') or ''

    # Apply diffs from root (last in chain) forward to target (first in chain)
    chain.reverse()

    title = ''
    body = ''
    metadata = {}

    for rev in chain:
        title_diff = getattr(rev, 'title_diff', '') or ''
        body_diff = getattr(rev, 'body_diff', '') or ''
        metadata_diff_str = getattr(rev, 'metadata_diff', '') or ''

        if title_diff and title_diff != '[]':
            title = _apply_diff(title_diff, title)
        if body_diff and body_diff != '[]':
            body = _apply_diff(body_diff, body)
        if metadata_diff_str:
            try:
                md = json.loads(metadata_diff_str)
                # Apply "new" fields, remove "deleted" fields
                metadata.update(md.get('new', {}))
                for key in md.get('deleted', []):
                    metadata.pop(key, None)
            except Exception:
                pass

    return {'title': title, 'body': body, 'metadata': metadata}


@create_tool("restore_note_revision", "Restore a note from revision history")
async def restore_note_revision(
    revision_id: Annotated[str, Field(description="Revision ID to restore (from get_note_history)")],
    target_notebook: Annotated[Optional[str], Field(description="Notebook name for restored note (default: original notebook, or 'Restored Notes' if unavailable)")] = None
) -> str:
    """Restore a previous version of a note from its revision history.

    Reconstructs the note content from revision diffs and creates a NEW note
    with the restored content (same behavior as Joplin Desktop's restore).
    Does not overwrite the current version of the note.

    Use get_note_history first to find the revision_id to restore.

    Returns:
        str: Success message with the restored note's ID and location.
    """
    client = get_joplin_client()

    # Reconstruct content from revision chain
    try:
        content = _reconstruct_revision_content(client, revision_id)
    except Exception as e:
        raise ValueError(f"Failed to reconstruct revision: {e}")

    title = content['title'] or 'Untitled (restored)'
    body = content['body'] or ''
    metadata = content['metadata']

    # Determine target notebook
    target_notebook_id = None
    if target_notebook:
        target_notebook_id = get_notebook_id_by_name(target_notebook)
    elif metadata.get('parent_id'):
        # Try original notebook
        try:
            nb = client.get_notebook(metadata['parent_id'], fields="id,title,deleted_time")
            # Check notebook isn't trashed
            deleted = getattr(nb, 'deleted_time', None)
            import datetime as dt_module
            if deleted and deleted != dt_module.datetime(1970, 1, 1, 0, 0):
                target_notebook_id = None  # Original notebook is trashed
            else:
                target_notebook_id = metadata['parent_id']
        except Exception:
            target_notebook_id = None

    # Fall back to "Restored Notes" notebook (create if needed)
    if not target_notebook_id:
        try:
            target_notebook_id = get_notebook_id_by_name("Restored Notes")
        except ValueError:
            nb = client.add_notebook(title="Restored Notes")
            target_notebook_id = str(nb)

    # Create the restored note
    note_id = str(client.add_note(title=title, body=body, parent_id=target_notebook_id))

    # Get target notebook name for display
    try:
        nb = client.get_notebook(target_notebook_id, fields="id,title")
        nb_name = getattr(nb, 'title', target_notebook_id)
    except Exception:
        nb_name = target_notebook_id

    return f"""OPERATION: RESTORE_NOTE_REVISION
STATUS: SUCCESS
RESTORED_NOTE_ID: {note_id}
TITLE: {title}
NOTEBOOK: {nb_name}
SOURCE_REVISION: {revision_id}
MESSAGE: Note restored from revision history as a new note in "{nb_name}" """

@create_tool("manually_backup_note", "Create manual revision backup")
async def manually_backup_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to backup")]
) -> str:
    """Create a manual revision snapshot of a note's current content.

    Saves the note's current title and body as a Joplin revision, enabling
    recovery via get_note_history + restore_note_revision or Joplin Desktop's
    "Note History" UI. Use before risky manual edits or bulk operations.

    Note: Revisions are also created automatically before title/body overwrites
    by update_note and search_and_bulk_update_execute.

    Returns:
        str: Success message with the revision ID.
    """
    note_id = validate_joplin_id(note_id)
    client = get_joplin_client()

    rev_id = _save_note_revision(client, note_id)
    if rev_id:
        return f"""OPERATION: MANUALLY_BACKUP_NOTE
STATUS: SUCCESS
NOTE_ID: {note_id}
REVISION_ID: {rev_id}
MESSAGE: Revision snapshot created. Recoverable via get_note_history + restore_note_revision or Joplin Desktop's Note History."""
    else:
        return f"""OPERATION: MANUALLY_BACKUP_NOTE
STATUS: FAILED
NOTE_ID: {note_id}
MESSAGE: Failed to create revision snapshot. Check server logs for details."""

@create_tool("backup_database", "Backup Joplin database")
async def backup_database() -> str:
    """Create a full SQLite backup of the Joplin database.

    Creates a complete snapshot of the Joplin database using SQLite's backup
    command, safe even while Joplin Desktop is running. Use before large
    reorganization operations or as a manual safety checkpoint.

    Backups are stored in ~/JoplinBackup/default/mcp-backups/ with timestamps.
    Last 3 backups are retained automatically.

    Note: Bulk operations (search_and_bulk_update_execute, bulk_move_notes)
    trigger this automatically once per day. This tool bypasses the daily
    guard and always creates a fresh backup.

    Returns:
        str: Success message with backup path, or failure details.
    """
    backup_path = _backup_joplin_database(force=True)
    if backup_path:
        size_mb = Path(backup_path).stat().st_size / (1024 * 1024)
        return f"""OPERATION: BACKUP_DATABASE
STATUS: SUCCESS
BACKUP_PATH: {backup_path}
SIZE: {size_mb:.1f} MB
MESSAGE: Full Joplin database backup created. Restore by replacing {_JOPLIN_DB_PATH} with this file (while Joplin Desktop is closed)."""
    else:
        return f"""OPERATION: BACKUP_DATABASE
STATUS: FAILED
MESSAGE: Could not create database backup. Joplin database may not exist at {_JOPLIN_DB_PATH}. Check server logs."""

@create_tool("find_notes", "Find notes")
async def find_notes(
    query: Annotated[str, Field(description="Search text or '*' for all notes")],
    limit: Annotated[LimitType, Field(description="Max results (1-100, default: 20)")] = 20,
    offset: Annotated[OffsetType, Field(description="Skip count for pagination (default: 0)")] = 0,
    task: Annotated[OptionalBoolType, Field(description="Filter by task type (default: None)")] = None,
    completed: Annotated[OptionalBoolType, Field(description="Filter by completion status (default: None)")] = None
) -> str:
    """Find notes by searching their titles and content, with support for listing all notes and pagination.
    
    ⭐ MAIN FUNCTION FOR TEXT SEARCHES AND LISTING ALL NOTES!
    
    Versatile search function that can find specific text in notes OR list all notes with filtering and pagination.
    Use query="*" to list all notes without text filtering. Use specific text to find notes containing those words.
    
    Returns:
        str: List of notes matching criteria, with title, ID, content preview, and dates. 
             Includes pagination info (total results, current page range).
    
    Examples:
        - find_notes("*") - List first 20 notes (all notes)
        - find_notes("meeting") - Find all notes containing "meeting"
        - find_notes("*", task=True) - List all tasks
        - find_notes("*", limit=20, offset=20) - List notes 21-40 (page 2)
        
        💡 TIP: For tag-specific searches, use find_notes_with_tag("tag_name") instead.
        💡 TIP: For notebook-specific searches, use find_notes_in_notebook("notebook_name") instead.
    """
    
    # Runtime validation for Jan AI compatibility while preserving functionality
    task = flexible_bool_converter(task)
    completed = flexible_bool_converter(completed)
    
    client = get_joplin_client()
    
    # Handle special case for listing all notes
    if query.strip() == "*":
        # List all notes with filters
        search_filters = build_search_filters(task, completed)
        
        if search_filters:
            # Use search with filters
            search_query = " ".join(search_filters)
            results = client.search_all(query=search_query, fields=COMMON_NOTE_FIELDS)
            notes = process_search_results(results)
        else:
            # No filters, get all notes
            results = client.get_all_notes(fields=COMMON_NOTE_FIELDS)
            notes = process_search_results(results)
            # Sort by updated time, newest first (consistent with get_all_notes)
            notes = sorted(notes, key=lambda x: getattr(x, 'updated_time', 0), reverse=True)
    else:
        # Build search query with text and filters
        search_parts = [query]
        search_parts.extend(build_search_filters(task, completed))
        
        search_query = " ".join(search_parts)
        
        # Use search_all for full pagination support
        results = client.search_all(query=search_query, fields=COMMON_NOTE_FIELDS)
        notes = process_search_results(results)
    
    # Apply pagination
    paginated_notes, total_count = apply_pagination(notes, limit, offset)
    
    if not paginated_notes:
        # Create descriptive message based on search criteria
        if query.strip() == "*":
            base_criteria = "(all notes)"
        else:
            base_criteria = f'containing "{query}"'
        
        criteria_str = format_search_criteria(base_criteria, task, completed)
        return format_no_results_with_pagination("note", criteria_str, offset, limit)
    
    # Format results with pagination info
    if query.strip() == "*":
        search_description = "all notes"
    else:
        search_description = f'text search: {query}'
    
    return format_search_results_with_pagination(
        search_description, paginated_notes, total_count, limit, offset, "search_results", original_query=query
    )

@create_tool("get_all_notes", "Get all notes")
async def get_all_notes(
    limit: Annotated[LimitType, Field(description="Max results (1-100, default: 20)")] = 20
) -> str:
    """Get all notes in your Joplin instance.
    
    Simple function to retrieve all notes without any filtering or searching.
    Most recent notes are shown first.
    
    Returns:
        str: Formatted list of all notes with title, ID, content preview, and dates.
    
    Examples:
        - get_all_notes() - Get the 20 most recent notes
        - get_all_notes(50) - Get the 50 most recent notes
    """
    
    client = get_joplin_client()
    results = client.get_all_notes(fields=COMMON_NOTE_FIELDS)
    notes = process_search_results(results)
    
    # Sort by updated time, newest first
    notes = sorted(notes, key=lambda x: getattr(x, 'updated_time', 0), reverse=True)
    
    # Apply limit (using consistent pattern but keeping simple offset=0)
    notes = notes[:limit]
    
    if not notes:
        return format_no_results_message("note")
    
    return format_search_results_with_pagination("all notes", notes, len(notes), limit, 0, "search_results")

@create_tool("find_notes_with_tag", "Find notes with tag")
async def find_notes_with_tag(
    tag_name: Annotated[RequiredStringType, Field(description="Tag name to search for")],
    limit: Annotated[LimitType, Field(description="Max results (1-100, default: 20)")] = 20,
    offset: Annotated[OffsetType, Field(description="Skip count for pagination (default: 0)")] = 0,
    task: Annotated[OptionalBoolType, Field(description="Filter by task type (default: None)")] = None,
    completed: Annotated[OptionalBoolType, Field(description="Filter by completion status (default: None)")] = None
) -> str:
    """Find all notes that have a specific tag, with pagination support.
    
    ⭐ MAIN FUNCTION FOR TAG SEARCHES!
    
    Use this when you want to find all notes tagged with a specific tag name.
    
    Returns:
        str: List of all notes with the specified tag, with pagination information.
    
    Examples:
        - find_notes_with_tag("time-slip") - Find all notes tagged with "time-slip"
        - find_notes_with_tag("work", limit=10, offset=10) - Find notes tagged with "work" (page 2)
        - find_notes_with_tag("work", task=True) - Find only tasks tagged with "work"
        - find_notes_with_tag("important", task=True, completed=False) - Find only uncompleted tasks tagged with "important"
    """
    
    # Build search query with tag and filters
    search_parts = [f'tag:"{tag_name}"']
    search_parts.extend(build_search_filters(task, completed))
    search_query = " ".join(search_parts)
    
    # Use search_all API with tag constraint for full pagination support
    client = get_joplin_client()
    results = client.search_all(query=search_query, fields=COMMON_NOTE_FIELDS)
    notes = process_search_results(results)
    
    # Apply pagination
    paginated_notes, total_count = apply_pagination(notes, limit, offset)
    
    if not paginated_notes:
        base_criteria = f'with tag "{tag_name}"'
        criteria_str = format_search_criteria(base_criteria, task, completed)
        return format_no_results_with_pagination("note", criteria_str, offset, limit)
    
    return format_search_results_with_pagination(
        f'tag search: {search_query}', paginated_notes, total_count, limit, offset, "search_results", original_query=tag_name
    )

@create_tool("find_notes_in_notebook", "Find notes in notebook")  
async def find_notes_in_notebook(
    notebook_name: Annotated[RequiredStringType, Field(description="Notebook name to search in")],
    limit: Annotated[LimitType, Field(description="Max results (1-100, default: 20)")] = 20,
    offset: Annotated[OffsetType, Field(description="Skip count for pagination (default: 0)")] = 0,
    task: Annotated[OptionalBoolType, Field(description="Filter by task type (default: None)")] = None,
    completed: Annotated[OptionalBoolType, Field(description="Filter by completion status (default: None)")] = None
) -> str:
    """Find all notes in a specific notebook, with pagination support.
    
    ⭐ MAIN FUNCTION FOR NOTEBOOK SEARCHES!
    
    Use this when you want to find all notes in a specific notebook.
    
    Returns:
        str: List of all notes in the specified notebook, with pagination information.
    
    Examples:
        - find_notes_in_notebook("Work Projects") - Find all notes in "Work Projects"
        - find_notes_in_notebook("Personal Notes", limit=10, offset=10) - Find notes in "Personal Notes" (page 2)
        - find_notes_in_notebook("Personal Notes", task=True) - Find only tasks in "Personal Notes"
        - find_notes_in_notebook("Projects", task=True, completed=False) - Find only uncompleted tasks in "Projects"
    """
    
    # Build search query with notebook and filters
    search_parts = [f'notebook:"{notebook_name}"']
    search_parts.extend(build_search_filters(task, completed))
    search_query = " ".join(search_parts)
    
    # Use search_all API with notebook constraint for full pagination support
    client = get_joplin_client()
    results = client.search_all(query=search_query, fields=COMMON_NOTE_FIELDS)
    notes = process_search_results(results)
    
    # Apply pagination
    paginated_notes, total_count = apply_pagination(notes, limit, offset)
    
    if not paginated_notes:
        base_criteria = f'in notebook "{notebook_name}"'
        criteria_str = format_search_criteria(base_criteria, task, completed)
        return format_no_results_with_pagination("note", criteria_str, offset, limit)
    
    return format_search_results_with_pagination(
        f'notebook search: {search_query}', paginated_notes, total_count, limit, offset, "search_results", original_query=notebook_name
    )



# === NOTEBOOK OPERATIONS ===

@create_tool("list_notebooks", "List notebooks")
async def list_notebooks() -> str:
    """List all notebooks/folders in your Joplin instance.
    
    Retrieves and displays all notebooks (folders) in your Joplin application.
    
    Returns:
        str: Formatted list of all notebooks including title, unique ID, parent notebook (if sub-notebook), and creation date.
    """
    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time,parent_id"
    notebooks = client.get_all_notebooks(fields=fields_list)
    return format_item_list(notebooks, ItemType.notebook)



@create_tool("create_notebook", "Create notebook")
async def create_notebook(
    title: Annotated[RequiredStringType, Field(description="Notebook title")], 
    parent_id: Annotated[Optional[str], Field(description="Parent notebook ID (optional)")] = None
) -> str:
    """Create a new notebook (folder) in Joplin to organize your notes.
    
    Creates a new notebook that can be used to organize and contain notes. You can create 
    top-level notebooks or sub-notebooks within existing notebooks.
    
    Returns:
        str: Success message containing the created notebook's title and unique ID.
    
    Examples:
        - create_notebook("Work Projects") - Create a top-level notebook
        - create_notebook("2024 Projects", "work_notebook_id") - Create a sub-notebook
    """
    
    client = get_joplin_client()
    notebook_kwargs = {"title": title}
    if parent_id:
        notebook_kwargs["parent_id"] = parent_id.strip()
    
    notebook = client.add_notebook(**notebook_kwargs)
    return format_creation_success(ItemType.notebook, title, str(notebook))

@create_tool("update_notebook", "Update notebook")
async def update_notebook(
    notebook_id: Annotated[JoplinIdType, Field(description="Notebook ID to update")],
    title: Annotated[RequiredStringType, Field(description="New notebook title")]
) -> str:
    """Update an existing notebook.
    
    Updates the title of an existing notebook. Currently only the title can be updated.
    
    Returns:
        str: Success message confirming the notebook was updated.
    """
    client = get_joplin_client()
    client.modify_notebook(notebook_id, title=title)
    return format_update_success(ItemType.notebook, notebook_id)

@create_tool("delete_notebook", "Delete notebook")
async def delete_notebook(
    notebook_id: Annotated[JoplinIdType, Field(description="Notebook ID to delete")]
) -> str:
    """Delete a notebook from Joplin (moves to trash).

    Moves a notebook and its contained notes to Joplin's trash.
    Can be restored from trash in Joplin Desktop.

    Returns:
        str: Success message confirming the notebook was moved to trash.
    """
    client = get_joplin_client()
    # NOTE: joppy's delete_notebook() accepts permanent=1 via **query kwargs to bypass trash.
    # We intentionally do NOT expose that capability — all deletes go to trash for safety.
    client.delete_notebook(notebook_id)
    return format_delete_success(ItemType.notebook, notebook_id)





# === TAG OPERATIONS ===

@create_tool("list_tags", "List tags")
async def list_tags() -> str:
    """List all tags in your Joplin instance with note counts.
    
    Retrieves and displays all tags that exist in your Joplin application. Tags are labels
    that can be applied to notes for categorization and organization.
    
    Returns:
        str: Formatted list of all tags including title, unique ID, number of notes tagged with it, and creation date.
    """
    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time"
    tags = client.get_all_tags(fields=fields_list)
    return format_tag_list_with_counts(tags, client)


@create_tool("create_tag", "Create tag")
async def create_tag(
    title: Annotated[RequiredStringType, Field(description="Tag title")]
) -> str:
    """Create a new tag.
    
    Creates a new tag that can be applied to notes for categorization and organization.
    
    Returns:
        str: Success message with the created tag's title and unique ID.
    
    Examples:
        - create_tag("work") - Create a new tag named "work"
        - create_tag("important") - Create a new tag named "important"
    """
    client = get_joplin_client()
    tag = client.add_tag(title=title)
    return format_creation_success(ItemType.tag, title, str(tag))


@create_tool("update_tag", "Update tag")
async def update_tag(
    tag_id: Annotated[JoplinIdType, Field(description="Tag ID to update")],
    title: Annotated[RequiredStringType, Field(description="New tag title")]
) -> str:
    """Update an existing tag.
    
    Updates the title of an existing tag. Currently only the title can be updated.
    
    Returns:
        str: Success message confirming the tag was updated.
    """
    client = get_joplin_client()
    client.modify_tag(tag_id, title=title)
    return format_update_success(ItemType.tag, tag_id)


@create_tool("delete_tag", "Delete tag")
async def delete_tag(
    tag_id: Annotated[JoplinIdType, Field(description="Tag ID to delete")]
) -> str:
    """Delete a tag from Joplin (PERMANENT).

    Permanently removes a tag from Joplin. Unlike notes and notebooks, tags do NOT go to trash.
    The tag will be removed from all notes that currently have it.

    Returns:
        str: Success message confirming the tag was permanently deleted.

    Warning: This action is permanent and cannot be undone.
    """
    client = get_joplin_client()
    # Tags do not use Joplin's trash system — deletion is permanent
    client.delete_tag(tag_id)
    return format_delete_success(ItemType.tag, tag_id, soft_delete=False)


@create_tool("get_tags_by_note", "Get tags by note")
async def get_tags_by_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to get tags from")]
) -> str:
    """Get all tags for a specific note.
    
    Retrieves all tags that are currently applied to a specific note.
    
    Returns:
        str: Formatted list of tags applied to the note with title, ID, and creation date.
    """
    
    client = get_joplin_client()
    fields_list = "id,title,created_time,updated_time"
    tags_result = client.get_tags(note_id=note_id, fields=fields_list)
    tags = process_search_results(tags_result)
    
    if not tags:
        return format_no_results_message("tag", f"for note: {note_id}")
    
    return format_item_list(tags, ItemType.tag)

# === TAG-NOTE RELATIONSHIP OPERATIONS ===

async def _tag_note_impl(note_id: str, tag_name: str) -> str:
    """Shared implementation for adding a tag to a note using note ID and tag name."""
    client = get_joplin_client()
    
    # Verify note exists by getting it
    try:
        note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
        note_title = getattr(note, 'title', 'Unknown Note')
    except Exception:
        raise ValueError(f"Note with ID '{note_id}' not found. Use find_notes to find available notes.")
    
    # Use helper function to get tag ID
    tag_id = get_tag_id_by_name(tag_name)
    
    client.add_tag_to_note(tag_id, note_id)
    return format_relation_success("tagged note", ItemType.note, f"{note_title} (ID: {note_id})", ItemType.tag, tag_name)


async def _untag_note_impl(note_id: str, tag_name: str) -> str:
    """Shared implementation for removing a tag from a note using note ID and tag name."""
    
    client = get_joplin_client()
    
    # Verify note exists by getting it
    try:
        note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
        note_title = getattr(note, 'title', 'Unknown Note')
    except Exception:
        raise ValueError(f"Note with ID '{note_id}' not found. Use find_notes to find available notes.")
    
    # Use helper function to get tag ID
    tag_id = get_tag_id_by_name(tag_name)
    
    # Remove tag from note using DELETE /tags/{tag_id}/notes/{note_id}
    client.delete(f"/tags/{tag_id}/notes/{note_id}")
    return format_relation_success("removed tag from note", ItemType.note, f"{note_title} (ID: {note_id})", ItemType.tag, tag_name)


# Primary tag operations
@create_tool("tag_note", "Tag note")
async def tag_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to add tag to")], 
    tag_name: Annotated[RequiredStringType, Field(description="Tag name to add")]
) -> str:
    """Add a tag to a note for categorization and organization.
    
    Applies an existing tag to a specific note using the note's unique ID and the tag's name.
    Uses note ID for precise targeting and tag name for intuitive selection.
    
    Returns:
        str: Success message confirming the tag was added to the note.
    
    Examples:
        - tag_note("a1b2c3d4e5f6...", "Important") - Add 'Important' tag to specific note
        - tag_note("note_id_123", "Work") - Add 'Work' tag to the note
    
    Note: The note must exist (by ID) and the tag must exist (by name). A note can have multiple tags.
    """
    return await _tag_note_impl(note_id, tag_name)


@create_tool("untag_note", "Untag note")
async def untag_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to remove tag from")], 
    tag_name: Annotated[RequiredStringType, Field(description="Tag name to remove")]
) -> str:
    """Remove a tag from a note.
    
    Removes an existing tag from a specific note using the note's unique ID and the tag's name.
    
    Returns:
        str: Success message confirming the tag was removed from the note.
    
    Examples:
        - untag_note("a1b2c3d4e5f6...", "Important") - Remove 'Important' tag from specific note
        - untag_note("note_id_123", "Work") - Remove 'Work' tag from the note
    
    Note: Both the note (by ID) and tag (by name) must exist in Joplin.
    """
    return await _untag_note_impl(note_id, tag_name)


@create_tool("strip_note_tags", "Remove all tags from note")
async def strip_note_tags(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to remove all tags from")]
) -> str:
    """Remove all tags from a specific note.
    
    Removes all existing tags from a note, effectively clearing its tag associations.
    This is useful for resetting a note's categorization or cleaning up over-tagged notes.
    
    Args:
        note_id: The ID of the note to remove all tags from
    
    Returns:
        str: Success message with details of the tag removal operation.
    
    Examples:
        - strip_note_tags("a1b2c3d4e5f6...") - Remove all tags from specific note
        - strip_note_tags("note_id_123") - Clear all tags from the note
    
    Note: The note must exist (by ID). If the note has no tags, the operation succeeds with no changes.
    """
    
    client = get_joplin_client()
    
    # Verify note exists and get info (following alondmnt's pattern)
    try:
        note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
        note_title = getattr(note, 'title', 'Unknown Note')
    except Exception:
        raise ValueError(f"Note with ID '{note_id}' not found. Use find_notes to find available notes.")
    
    # Get all tags currently on this note
    try:
        fields_list = "id,title,created_time,updated_time"
        tags_result = client.get_tags(note_id=note_id, fields=fields_list)
        note_tags = process_search_results(tags_result)
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve tags for note '{note_title}': {e}")
    
    if not note_tags:
        return f"✅ Note '{note_title}' already has no tags"
    
    # Remove each tag from the note
    successful_removals = []
    failed_removals = []
    
    for tag in note_tags:
        tag_id = getattr(tag, 'id', '')
        tag_name = getattr(tag, 'title', 'Unknown Tag')
        try:
            client.delete(f"/tags/{tag_id}/notes/{note_id}")
            successful_removals.append(tag_name)
        except Exception as e:
            failed_removals.append(f"'{tag_name}': {str(e)}")
    
    # Build result message
    success_count = len(successful_removals)
    total_count = len(note_tags)
    
    if failed_removals:
        result_lines = [
            f"✅ Partially stripped tags from note '{note_title}'",
            f"Successfully removed: {success_count}/{total_count} tags",
            f"Tags removed: {', '.join(successful_removals)}",
            f"Failed removals: {', '.join(failed_removals)}"
        ]
        return "\n".join(result_lines)
    else:
        return f"✅ Successfully stripped all {success_count} tags from note '{note_title}': {', '.join(successful_removals)}"


@create_tool("bulk_tag_notes", "Bulk tag notes")
async def bulk_tag_notes(
    note_ids: Annotated[List[str], Field(description="List of note IDs to add tags to")],
    tag_names: Annotated[List[str], Field(description="List of tag names to add to each note")]
) -> str:
    """Apply multiple tags to multiple notes in a single bulk operation.
    
    Efficiently adds all specified tags to all specified notes using a cartesian product approach.
    Each tag will be applied to each note, creating comprehensive tagging across multiple items.
    
    Args:
        note_ids: List of note IDs to add tags to
        tag_names: List of tag names to add to each note
    
    Returns:
        str: Detailed success message with operation statistics.
    
    Examples:
        - bulk_tag_notes(["note1", "note2"], ["Important", "Work"]) - Apply 'Important' and 'Work' tags to both notes
        - bulk_tag_notes(["abc123", "def456", "ghi789"], ["Project-Alpha"]) - Apply 'Project-Alpha' tag to 3 notes
    
    Note: All notes must exist (by ID) and all tags must exist (by name). Creates note-tag relationships for all combinations.
    """
    
    # Validate inputs
    if not note_ids:
        raise ValueError("At least one note ID must be provided")
    if not tag_names:
        raise ValueError("At least one tag name must be provided")
    
    # Validate all note IDs
    validated_note_ids = []
    for note_id in note_ids:
        validated_note_ids.append(validate_joplin_id(note_id))
    
    client = get_joplin_client()
    
    # Verify all notes exist and collect titles for reporting (matching alondmnt's pattern)
    note_titles = {}
    for note_id in validated_note_ids:
        try:
            note = client.get_note(note_id, fields=COMMON_NOTE_FIELDS)
            note_titles[note_id] = getattr(note, 'title', 'Unknown Note')
        except Exception:
            raise ValueError(f"Note with ID '{note_id}' not found. Use find_notes to find available notes.")
    
    # Apply all tags to all notes (cartesian product) - following alondmnt's pattern
    successful_operations = []
    failed_operations = []
    total_operations = len(validated_note_ids) * len(tag_names)
    
    for note_id in validated_note_ids:
        note_title = note_titles[note_id]
        for tag_name in tag_names:
            try:
                # Use helper function to get tag ID (handles tag validation like alondmnt's pattern)
                tag_id = get_tag_id_by_name(tag_name)
                # Apply tag (let API handle the actual operation like alondmnt's pattern)
                client.add_tag_to_note(tag_id, note_id)
                successful_operations.append(f"'{tag_name}' → '{note_title}' ({note_id[:8]}...)")
            except Exception as e:
                failed_operations.append(f"'{tag_name}' → '{note_title}' ({note_id[:8]}...): {str(e)}")
    
    # Build result message
    success_count = len(successful_operations)
    failure_count = len(failed_operations)
    
    result_parts = [
        f"OPERATION: BULK_TAG_NOTES",
        f"STATUS: {'SUCCESS' if failure_count == 0 else 'PARTIAL_SUCCESS' if success_count > 0 else 'FAILED'}",
        f"NOTES_PROCESSED: {len(validated_note_ids)}",
        f"TAGS_APPLIED: {len(tag_names)}",
        f"TOTAL_OPERATIONS: {total_operations}",
        f"SUCCESSFUL_OPERATIONS: {success_count}",
        f"FAILED_OPERATIONS: {failure_count}",
        ""
    ]
    
    if success_count > 0:
        result_parts.append("SUCCESSFUL_TAGS:")
        for operation in successful_operations:
            result_parts.append(f"  ✓ {operation}")
        result_parts.append("")
    
    if failure_count > 0:
        result_parts.append("FAILED_TAGS:")
        for operation in failed_operations:
            result_parts.append(f"  ✗ {operation}")
        result_parts.append("")
    
    # Summary message
    if failure_count == 0:
        result_parts.append(f"MESSAGE: Successfully applied {len(tag_names)} tags to {len(validated_note_ids)} notes ({success_count} total operations)")
    elif success_count > 0:
        result_parts.append(f"MESSAGE: Partially completed bulk tagging: {success_count} successful, {failure_count} failed operations")
    else:
        result_parts.append(f"MESSAGE: Bulk tagging failed: all {total_operations} operations failed")
    
    return "\n".join(result_parts)

# === RESOURCES ===

@mcp.resource("joplin://server_info")
async def get_server_info() -> dict:
    """Get Joplin server information."""
    try:
        client = get_joplin_client()
        is_connected = client.ping()
        return {
            "connected": bool(is_connected),
            "url": getattr(client, 'url', 'unknown'),
            "version": f"FastMCP-based Joplin Server v{MCP_VERSION}"
        }
    except Exception:
        return {"connected": False}

# === MAIN RUNNER ===

def main(config_file: Optional[str] = None, transport: str = "stdio", host: str = "127.0.0.1", port: int = 8000, path: str = "/mcp", log_level: str = "info"):
    """Main entry point for the FastMCP Joplin server."""
    global _config
    
    try:
        logger.info("🚀 Starting FastMCP Joplin server...")
        
        # Set the runtime config (tools are already filtered at import time)
        if config_file:
            _config = JoplinMCPConfig.from_file(config_file)
            logger.info(f"Runtime configuration loaded from {config_file}")
        else:
            # Use the same config that was used for tool filtering
            _config = _module_config
            logger.info(f"Using module-level configuration for runtime")
        
        # Log final tool registration status
        registered_tools = list(mcp._tool_manager._tools.keys())
        logger.info(f"FastMCP server has {len(registered_tools)} tools registered")
        logger.info(f"Registered tools: {sorted(registered_tools)}")
        
        # Verify we can connect to Joplin
        logger.info("Initializing Joplin client...")
        client = get_joplin_client()
        logger.info("Joplin client initialized successfully")
        
        # Run the FastMCP server with specified transport
        if transport.lower() == "http":
            logger.info(f"Starting FastMCP server with HTTP transport on {host}:{port}{path}")
            mcp.run(transport="http", host=host, port=port, path=path, log_level=log_level)
        elif transport.lower() == "streamable-http":
            logger.info(f"Starting FastMCP server with Streamable HTTP transport on {host}:{port}{path}")
            mcp.run(transport="streamable-http", host=host, port=port, path=path, log_level=log_level)
        elif transport.lower() == "sse":
            logger.info(f"Starting FastMCP server with SSE transport on {host}:{port}{path}")
            mcp.run(transport="sse", host=host, port=port, path=path, log_level=log_level)
        else:
            logger.info("Starting FastMCP server with STDIO transport")
            mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"Failed to start FastMCP Joplin server: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main() 
