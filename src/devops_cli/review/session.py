"""The review session store: where review sessions live on disk (#771).

Every command that writes or reads a review session finds the sessions directory here, so a
review, the dashboard and the history figures cannot disagree about where it is.
"""

from __future__ import annotations

import os
from pathlib import Path

from devops_cli.config.constants import CONST_REVIEWS_DIR_NAME
from devops_cli.config.env import ENV_DATA_DIR
from devops_cli.config.settings import load_settings
from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal
from devops_cli.core.repo import resolve_review_data_path
from devops_cli.exceptions import SecurityError


class ReviewSessionStore:
    """Where review sessions are kept."""

    @staticmethod
    def root() -> Path:
        """The directory holding review sessions, resolved and not created.

        `DEVOPS_CLI_DATA_DIR`, when set, holds them in its `reviews`; otherwise `data.reviews_dir`
        says where. A relative path is under the review data root, where a review keeps its data
        whichever directory the command runs from (`resolve_review_data_path`, #972). Reading
        never creates the directory: writing a session does.

        Raises:
            SecurityError: The path holds a traversal sequence or is a host system directory.
        """
        data_dir = os.environ.get(ENV_DATA_DIR)
        configured = (
            Path(data_dir) / CONST_REVIEWS_DIR_NAME
            if data_dir
            else load_settings().data.reviews_dir
        )
        validate_no_path_traversal(configured, label="Review sessions directory")
        root = resolve_review_data_path(configured).resolve()
        if is_forbidden_system_path(root):
            raise SecurityError(f"Review sessions directory {root} is a forbidden system path")
        return root
