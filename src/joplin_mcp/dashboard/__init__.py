"""Joplin dashboard library.

Config-driven query and render of Joplin notes into Markdown dashboards.
First consumer: the job_search project. Designed for reuse across other
GTD-style aggregations where the table IS the answer (no priority triage).

See markdowns/plans_draft/dashboard_script_mini_plan.md for design.
"""

from joplin_mcp.dashboard.config import DashboardConfig, SectionConfig, load_config
from joplin_mcp.dashboard.loader import JoplinRestLoader, Loader
from joplin_mcp.dashboard.render import assemble_dashboard, render_section
from joplin_mcp.dashboard.types import NoteRecord

__all__ = [
    "DashboardConfig",
    "JoplinRestLoader",
    "Loader",
    "NoteRecord",
    "SectionConfig",
    "assemble_dashboard",
    "load_config",
    "render_section",
]
