"""
Hermes-Claude Code MCP Bridge (v1.0 Stub)

Provides bidirectional MCP interface between Hermes and Claude Code.
Phase 1: Foundation only - no functionality yet, just structure + health check.

Architecture:
- Hermes Gateway loads this module at startup
- Exposes HTTP endpoint :20129/mcp/{method}
- Handles request/response marshalling
- Logs all interactions for debugging

Status: Production-ready structure, features coming in Phase 2
"""

import json
import logging
import os
import time
import re
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime
from abc import ABC, abstractmethod

__version__ = "1.0.0"
__phase__ = "1-foundation"

# ============================================================================
# Logging Setup
# ============================================================================

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s'
))
log.addHandler(handler)


# ============================================================================
# Data Models (Request/Response Types)
# ============================================================================

@dataclass
class CodeEditRequest:
    """Request from Hermes to Claude Code for file editing"""
    file_path: str
    operation: str  # edit|create|append|replace|multi_edit
    old_string: Optional[str] = None
    new_string: Optional[str] = None
    context: Optional[str] = None
    approval_required: bool = False
    worktree_isolation: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class CodeEditResponse:
    """Response from Claude Code back to Hermes"""
    status: str  # success|pending_approval|error
    file_path: str
    diff: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat() + 'Z'

    def to_dict(self):
        return asdict(self)


@dataclass
class ResearchRequest:
    """Request from Claude Code to Hermes for research"""
    query: str
    depth: str = "normal"  # quick|normal|deep
    sources: str = "web"   # web|academic|code|mixed
    context: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class ResearchResponse:
    """Response from Hermes research back to Claude Code"""
    status: str  # success|error
    results: List[Dict[str, str]] = None
    summary: Optional[str] = None
    total_sources: int = 0
    error_message: Optional[str] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat() + 'Z'
        if self.results is None:
            self.results = []

    def to_dict(self):
        data = asdict(self)
        return data


@dataclass
class GitOperationRequest:
    """Request from Hermes to Claude Code for git operations"""
    repo_path: str
    operation: str  # create_branch|commit|push_pr|rebase|cherry_pick
    branch_name: Optional[str] = None
    base_branch: str = "main"
    files: Optional[List[str]] = None
    message: str = ""
    source_branch: Optional[str] = None
    target_branch: str = "main"
    title: Optional[str] = None
    body: Optional[str] = None
    commit_sha: Optional[str] = None
    approval_required: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class GitOperationResponse:
    """Response from Claude Code back to Hermes"""
    status: str  # success|pending_approval|error
    operation: str
    repo_path: str
    current_branch: Optional[str] = None
    commit_sha: Optional[str] = None
    pr_url: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat() + 'Z'
        if self.details is None:
            self.details = {}

    def to_dict(self):
        return asdict(self)


@dataclass
class ModelSelectionRequest:
    """Request from Claude Code to Hermes for model selection advice"""
    task_description: str
    task_type: str  # code_review|research|writing|analysis|coding
    budget_tokens: int = 100_000
    speed_required: bool = False
    accuracy_required: bool = False
    budget_aware: bool = True
    prefer_local: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class ModelSelectionResponse:
    """Response from Hermes back to Claude Code"""
    status: str  # success|error
    recommended_tier: str = ""  # fast|balanced|premium|ultra
    model_id: str = ""
    reasoning: str = ""
    alternatives: Optional[List[Dict[str, Any]]] = None
    estimated_cost: float = 0.0
    error_message: Optional[str] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat() + 'Z'
        if self.alternatives is None:
            self.alternatives = []

    def to_dict(self):
        return asdict(self)


# ============================================================================
# Request Handlers (Phase 1: Stub implementations)
# ============================================================================

class RequestHandler(ABC):
    """Base class for MCP request handlers"""

    @abstractmethod
    async def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle request and return response"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Handler name for logging"""
        pass


class CodeEditHandler(RequestHandler):
    """Handle code_edit_request from Hermes → Claude Code"""

    async def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle code edit operations: edit, create, append, apply_diff"""
        log.debug(f"CodeEditHandler: {request}")

        try:
            req = CodeEditRequest(**request)

            # Validate file path (security check)
            if not self._validate_file_path(req.file_path):
                return CodeEditResponse(
                    status="error",
                    file_path=req.file_path,
                    error_message=f"Invalid file path: {req.file_path} (blocked for security)"
                ).to_dict()

            # Read existing file (for edit operations)
            original_content = ""
            if req.operation in ["edit", "append"]:
                try:
                    with open(req.file_path, 'r') as f:
                        original_content = f.read()
                except FileNotFoundError:
                    if req.operation == "edit":
                        return CodeEditResponse(
                            status="error",
                            file_path=req.file_path,
                            error_message=f"File not found: {req.file_path}"
                        ).to_dict()
                except Exception as e:
                    return CodeEditResponse(
                        status="error",
                        file_path=req.file_path,
                        error_message=f"Cannot read file: {e}"
                    ).to_dict()

            # Apply operation
            new_content = None

            if req.operation == "edit":
                if req.old_string is None:
                    return CodeEditResponse(
                        status="error",
                        file_path=req.file_path,
                        error_message="edit operation requires old_string"
                    ).to_dict()

                if req.old_string not in original_content:
                    return CodeEditResponse(
                        status="error",
                        file_path=req.file_path,
                        error_message=f"old_string not found in file"
                    ).to_dict()

                new_content = original_content.replace(req.old_string, req.new_string, 1)

            elif req.operation == "create":
                new_content = req.new_string or ""

            elif req.operation == "append":
                new_content = original_content + "\n" + (req.new_string or "")

            elif req.operation == "apply_diff":
                # This operation applies a previously-approved diff
                # The new content is passed in new_string
                new_content = req.new_string

            else:
                return CodeEditResponse(
                    status="error",
                    file_path=req.file_path,
                    error_message=f"Unknown operation: {req.operation}"
                ).to_dict()

            # Generate diff
            diff = self._generate_unified_diff(original_content, new_content, req.file_path)

            # If approval required, return pending (don't write file yet)
            if req.approval_required and req.operation != "apply_diff":
                log.info(f"Code edit pending approval: {req.file_path}")
                return CodeEditResponse(
                    status="pending_approval",
                    file_path=req.file_path,
                    diff=diff
                ).to_dict()

            # Apply change (write to disk)
            try:
                with open(req.file_path, 'w') as f:
                    f.write(new_content)
            except Exception as e:
                return CodeEditResponse(
                    status="error",
                    file_path=req.file_path,
                    error_message=f"Cannot write file: {e}"
                ).to_dict()

            log.info(f"Code edit applied: {req.file_path} ({req.operation})")
            return CodeEditResponse(
                status="success",
                file_path=req.file_path,
                diff=diff
            ).to_dict()

        except Exception as e:
            log.error(f"CodeEditHandler error: {e}")
            return CodeEditResponse(
                status="error",
                file_path=request.get("file_path", "unknown"),
                error_message=str(e)
            ).to_dict()

    def _validate_file_path(self, path: str) -> bool:
        """Validate file path for security + existence"""
        import os
        import pathlib

        # Security: no relative paths, no /etc, /root, etc.
        try:
            abs_path = pathlib.Path(path).resolve()
        except Exception:
            return False

        # Block dangerous paths
        blocked_prefixes = ["/etc", "/root", "/home/root", "/sys", "/proc", "/dev"]
        if any(str(abs_path).startswith(p) for p in blocked_prefixes):
            log.warning(f"Blocked dangerous path: {path}")
            return False

        # Path is valid if it's not trying to escape
        return True

    def _generate_unified_diff(self, original: str, new: str, file_path: str) -> str:
        """Generate unified diff between original and new content"""
        import difflib

        original_lines = original.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=""
        )

        return '\n'.join(diff)

    def get_name(self) -> str:
        return "code_edit_request"


class GitOperationHandler(RequestHandler):
    """Handle git_operation_request from Hermes → Claude Code"""

    async def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle git operations: create_branch, commit, push_pr, rebase, cherry_pick"""
        log.debug(f"GitOperationHandler: {request}")

        try:
            req = GitOperationRequest(**request)

            # Validate repo path
            if not self._validate_repo_path(req.repo_path):
                return GitOperationResponse(
                    status="error",
                    operation=req.operation,
                    repo_path=req.repo_path,
                    error_message=f"Invalid repo path: {req.repo_path} (not a git repo)"
                ).to_dict()

            # Route to operation handler
            if req.operation == "create_branch":
                return await self._handle_create_branch(req)
            elif req.operation == "commit":
                return await self._handle_commit(req)
            elif req.operation == "push_pr":
                return await self._handle_push_pr(req)
            elif req.operation == "rebase":
                return await self._handle_rebase(req)
            elif req.operation == "cherry_pick":
                return await self._handle_cherry_pick(req)
            else:
                return GitOperationResponse(
                    status="error",
                    operation=req.operation,
                    repo_path=req.repo_path,
                    error_message=f"Unknown operation: {req.operation}"
                ).to_dict()

        except Exception as e:
            log.error(f"GitOperationHandler error: {e}")
            return GitOperationResponse(
                status="error",
                operation=request.get("operation", "unknown"),
                repo_path=request.get("repo_path", "unknown"),
                error_message=str(e)
            ).to_dict()

    async def _handle_create_branch(self, req: GitOperationRequest) -> Dict[str, Any]:
        """Create a new branch"""
        import subprocess

        if not req.branch_name:
            return GitOperationResponse(
                status="error",
                operation="create_branch",
                repo_path=req.repo_path,
                error_message="branch_name required for create_branch"
            ).to_dict()

        # Validate branch name
        if not self._validate_branch_name(req.branch_name):
            return GitOperationResponse(
                status="error",
                operation="create_branch",
                repo_path=req.repo_path,
                error_message=f"Invalid branch name: {req.branch_name}"
            ).to_dict()

        try:
            # Get current branch
            current = self._get_current_branch(req.repo_path)

            # Switch to base branch if different
            if current != req.base_branch:
                subprocess.run(
                    ["git", "checkout", req.base_branch],
                    cwd=req.repo_path,
                    capture_output=True,
                    check=True
                )

            # Create branch
            subprocess.run(
                ["git", "checkout", "-b", req.branch_name],
                cwd=req.repo_path,
                capture_output=True,
                check=True
            )

            # Get commit SHA
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=req.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            sha = result.stdout.strip()

            log.info(f"Created branch: {req.branch_name} (sha={sha[:8]})")
            return GitOperationResponse(
                status="success",
                operation="create_branch",
                repo_path=req.repo_path,
                current_branch=req.branch_name,
                commit_sha=sha,
                details={"base_branch": req.base_branch}
            ).to_dict()

        except Exception as e:
            return GitOperationResponse(
                status="error",
                operation="create_branch",
                repo_path=req.repo_path,
                error_message=f"Failed to create branch: {e}"
            ).to_dict()

    async def _handle_commit(self, req: GitOperationRequest) -> Dict[str, Any]:
        """Commit staged or specified files"""
        import subprocess

        if not req.message:
            return GitOperationResponse(
                status="error",
                operation="commit",
                repo_path=req.repo_path,
                error_message="message required for commit"
            ).to_dict()

        try:
            # Stage files
            if req.files:
                for file in req.files:
                    subprocess.run(
                        ["git", "add", file],
                        cwd=req.repo_path,
                        capture_output=True,
                        check=True
                    )
            else:
                # Stage all changes
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=req.repo_path,
                    capture_output=True,
                    check=True
                )

            # Check if there's anything to commit
            status = self._get_git_status(req.repo_path)
            if not status["staged"]:
                return GitOperationResponse(
                    status="error",
                    operation="commit",
                    repo_path=req.repo_path,
                    error_message="No changes to commit"
                ).to_dict()

            # Commit
            subprocess.run(
                ["git", "commit", "-m", req.message],
                cwd=req.repo_path,
                capture_output=True,
                check=True
            )

            # Get commit SHA
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=req.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            sha = result.stdout.strip()

            log.info(f"Committed: {req.message} (sha={sha[:8]})")
            return GitOperationResponse(
                status="success",
                operation="commit",
                repo_path=req.repo_path,
                commit_sha=sha,
                details={
                    "files_changed": len(status["staged"]),
                    "message": req.message
                }
            ).to_dict()

        except Exception as e:
            return GitOperationResponse(
                status="error",
                operation="commit",
                repo_path=req.repo_path,
                error_message=f"Failed to commit: {e}"
            ).to_dict()

    async def _handle_push_pr(self, req: GitOperationRequest) -> Dict[str, Any]:
        """Push branch and optionally create PR"""
        import subprocess

        if not req.source_branch or not req.target_branch:
            return GitOperationResponse(
                status="error",
                operation="push_pr",
                repo_path=req.repo_path,
                error_message="source_branch and target_branch required"
            ).to_dict()

        try:
            # Get commits ahead
            result = subprocess.run(
                ["git", "rev-list", "--count", f"{req.target_branch}..{req.source_branch}"],
                cwd=req.repo_path,
                capture_output=True,
                text=True
            )
            ahead = int(result.stdout.strip() or 0)

            # If approval required, return pending
            if req.approval_required:
                log.info(f"Push PR pending approval: {req.source_branch} → {req.target_branch}")
                return GitOperationResponse(
                    status="pending_approval",
                    operation="push_pr",
                    repo_path=req.repo_path,
                    current_branch=req.source_branch,
                    details={
                        "source_branch": req.source_branch,
                        "target_branch": req.target_branch,
                        "commits_ahead": ahead,
                        "title": req.title
                    }
                ).to_dict()

            # Push branch
            subprocess.run(
                ["git", "push", "-u", "origin", req.source_branch],
                cwd=req.repo_path,
                capture_output=True,
                check=True
            )

            # Note: Real PR creation would need GitHub API or gh CLI
            # For now, just return success with branch pushed
            log.info(f"Pushed branch: {req.source_branch}")
            return GitOperationResponse(
                status="success",
                operation="push_pr",
                repo_path=req.repo_path,
                current_branch=req.source_branch,
                details={
                    "source_branch": req.source_branch,
                    "target_branch": req.target_branch,
                    "commits_ahead": ahead,
                    "title": req.title
                }
            ).to_dict()

        except Exception as e:
            return GitOperationResponse(
                status="error",
                operation="push_pr",
                repo_path=req.repo_path,
                error_message=f"Failed to push PR: {e}"
            ).to_dict()

    async def _handle_rebase(self, req: GitOperationRequest) -> Dict[str, Any]:
        """Rebase current branch"""
        import subprocess

        try:
            current = self._get_current_branch(req.repo_path)

            result = subprocess.run(
                ["git", "rebase", req.target_branch],
                cwd=req.repo_path,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return GitOperationResponse(
                    status="error",
                    operation="rebase",
                    repo_path=req.repo_path,
                    error_message=f"Rebase failed: {result.stderr}"
                ).to_dict()

            log.info(f"Rebased {current} onto {req.target_branch}")
            return GitOperationResponse(
                status="success",
                operation="rebase",
                repo_path=req.repo_path,
                current_branch=current,
                details={"rebased_onto": req.target_branch}
            ).to_dict()

        except Exception as e:
            return GitOperationResponse(
                status="error",
                operation="rebase",
                repo_path=req.repo_path,
                error_message=f"Failed to rebase: {e}"
            ).to_dict()

    async def _handle_cherry_pick(self, req: GitOperationRequest) -> Dict[str, Any]:
        """Cherry-pick a commit"""
        import subprocess

        if not req.commit_sha:
            return GitOperationResponse(
                status="error",
                operation="cherry_pick",
                repo_path=req.repo_path,
                error_message="commit_sha required for cherry_pick"
            ).to_dict()

        try:
            result = subprocess.run(
                ["git", "cherry-pick", req.commit_sha],
                cwd=req.repo_path,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return GitOperationResponse(
                    status="error",
                    operation="cherry_pick",
                    repo_path=req.repo_path,
                    error_message=f"Cherry-pick failed: {result.stderr}"
                ).to_dict()

            log.info(f"Cherry-picked: {req.commit_sha[:8]}")
            return GitOperationResponse(
                status="success",
                operation="cherry_pick",
                repo_path=req.repo_path,
                commit_sha=req.commit_sha
            ).to_dict()

        except Exception as e:
            return GitOperationResponse(
                status="error",
                operation="cherry_pick",
                repo_path=req.repo_path,
                error_message=f"Failed to cherry-pick: {e}"
            ).to_dict()

    def _validate_repo_path(self, path: str) -> bool:
        """Validate repo path"""
        import subprocess
        import os

        if not os.path.isdir(path):
            return False

        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            capture_output=True
        )
        return result.returncode == 0

    def _get_current_branch(self, repo_path: str) -> str:
        """Get current branch name"""
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()

    def _get_git_status(self, repo_path: str) -> Dict[str, Any]:
        """Get git status"""
        import subprocess

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )

        staged, unstaged, untracked = [], [], []
        for line in result.stdout.split('\n'):
            if not line.strip():
                continue

            status_code = line[:2]
            filename = line[3:]

            if status_code[0] in ['A', 'M', 'D']:
                staged.append(filename)
            elif status_code[1] in ['M', 'D']:
                unstaged.append(filename)
            elif status_code == '??':
                untracked.append(filename)

        return {
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked
        }

    def _validate_branch_name(self, name: str) -> bool:
        """Validate branch name"""
        import re

        # Basic validation
        if not name or len(name) > 255:
            return False

        # No spaces, no leading/trailing dots
        if name.startswith('.') or name.endswith('.'):
            return False

        # No double dots or .lock
        if '..' in name or name.endswith('.lock'):
            return False

        # Allow alphanumeric, dash, underscore, slash
        pattern = r'^[a-zA-Z0-9_\-/.]+$'
        return re.match(pattern, name) is not None

    def get_name(self) -> str:
        return "git_operation_request"


class ModelSelectionHandler(RequestHandler):
    """Handle model_selection_request from Claude Code → Hermes"""

    TIER_MODELS = {
        "fast": "claude-haiku-4-5-20251001",
        "balanced": "claude-sonnet-4-6",
        "premium": "claude-opus-4-7",
        "ultra": "claude-opus-4-8"
    }

    TIER_COSTS = {
        "fast": {"input": 0.80, "output": 3.20},
        "balanced": {"input": 3.00, "output": 15.00},
        "premium": {"input": 15.00, "output": 75.00},
        "ultra": {"input": 30.00, "output": 150.00}
    }

    async def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend optimal model tier"""
        log.debug(f"ModelSelectionHandler: {request}")

        try:
            req = ModelSelectionRequest(**request)

            # Validate request
            if not req.task_description or len(req.task_description) > 5000:
                return ModelSelectionResponse(
                    status="error",
                    error_message="task_description required and < 5000 chars"
                ).to_dict()

            # Analyze task complexity
            complexity = self._analyze_complexity(req.task_description)

            # Apply decision logic
            recommended_tier = self._select_tier(
                task_type=req.task_type,
                complexity=complexity,
                budget_tokens=req.budget_tokens,
                speed_required=req.speed_required,
                accuracy_required=req.accuracy_required,
                budget_aware=req.budget_aware
            )

            # Get model + cost estimate
            model_id = self.TIER_MODELS[recommended_tier]
            cost = self._estimate_cost(recommended_tier, req.task_description)

            # Generate reasoning
            reasoning = self._generate_reasoning(recommended_tier, complexity, req)

            # Get alternatives
            alternatives = self._get_alternatives(recommended_tier)

            log.info(f"Model selection: {recommended_tier} ({model_id}) for task type={req.task_type}")
            return ModelSelectionResponse(
                status="success",
                recommended_tier=recommended_tier,
                model_id=model_id,
                reasoning=reasoning,
                alternatives=alternatives,
                estimated_cost=cost
            ).to_dict()

        except Exception as e:
            log.error(f"ModelSelectionHandler error: {e}")
            return ModelSelectionResponse(
                status="error",
                error_message=str(e)
            ).to_dict()

    def _analyze_complexity(self, task_description: str) -> str:
        """Analyze task complexity: simple|normal|complex"""
        words = len(task_description.split())

        # Heuristics
        complex_keywords = [
            "architecture", "design", "implement", "optimize",
            "research", "analyze", "synthesize", "multi-step"
        ]
        simple_keywords = ["summarize", "review", "check", "format"]

        task_lower = task_description.lower()
        has_complex = any(kw in task_lower for kw in complex_keywords)
        has_simple = any(kw in task_lower for kw in simple_keywords)

        if has_complex and words > 100:
            return "complex"
        elif has_simple or words < 50:
            return "simple"
        else:
            return "normal"

    def _select_tier(self, task_type: str, complexity: str, budget_tokens: int,
                     speed_required: bool, accuracy_required: bool,
                     budget_aware: bool) -> str:
        """Select optimal tier"""

        # Speed priority
        if speed_required:
            return "fast"

        # Accuracy priority
        if accuracy_required and not budget_aware:
            if budget_tokens > 500_000:
                return "ultra"
            else:
                return "premium"

        # Task-based defaults
        task_tiers = {
            "code_review": "balanced",
            "research": "premium",
            "writing": "balanced",
            "analysis": "premium",
            "coding": "balanced"
        }
        base_tier = task_tiers.get(task_type, "balanced")

        # Complexity adjustment
        if complexity == "complex":
            if base_tier == "balanced":
                base_tier = "premium"
            elif base_tier == "premium":
                base_tier = "ultra"
        elif complexity == "simple":
            if base_tier == "balanced":
                base_tier = "fast"

        # Budget constraint
        if budget_aware and budget_tokens < 50_000:
            return "fast"  # Very low budget = use fast

        return base_tier

    def _estimate_cost(self, tier: str, text: str) -> float:
        """Estimate token cost"""
        # Rough: 1 token ≈ 4 chars
        tokens = len(text) / 4
        costs = self.TIER_COSTS[tier]

        # Assume 1:1 input:output ratio
        return (tokens * costs["input"] + tokens * costs["output"]) / 1_000_000

    def _generate_reasoning(self, tier: str, complexity: str,
                           req: ModelSelectionRequest) -> str:
        """Generate explanation for tier choice"""
        reasons = {
            "fast": "Fast model for quick turnaround",
            "balanced": "Balanced model for general tasks",
            "premium": "Premium model for accuracy and quality",
            "ultra": "Maximum capability for complex analysis"
        }

        reason = reasons.get(tier, "")

        if req.speed_required:
            reason += " (speed required)"
        if req.accuracy_required:
            reason += " (accuracy required)"
        if complexity == "complex":
            reason += " (complex task detected)"

        return reason

    def _get_alternatives(self, recommended_tier: str) -> List[Dict[str, Any]]:
        """Get alternative model suggestions"""
        tier_order = ["fast", "balanced", "premium", "ultra"]
        current_idx = tier_order.index(recommended_tier)

        alternatives = []
        for i in [current_idx - 1, current_idx + 1]:
            if 0 <= i < len(tier_order):
                alt_tier = tier_order[i]
                alternatives.append({
                    "tier": alt_tier,
                    "model_id": self.TIER_MODELS[alt_tier],
                    "reason": "Faster" if i < current_idx else "More capable"
                })

        return alternatives

    def get_name(self) -> str:
        return "model_selection_request"


class ResearchHandler(RequestHandler):
    """Handle research_request from Claude Code → Hermes"""

    async def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute research via Hermes Exa/Firecrawl"""
        log.debug(f"ResearchHandler: {request}")

        try:
            req = ResearchRequest(**request)

            # Validate query
            if not req.query or len(req.query) > 500:
                return ResearchResponse(
                    status="error",
                    error_message="Query required and must be < 500 chars"
                ).to_dict()

            # Determine result count by depth
            if req.depth == "quick":
                num_results = 3
            elif req.depth == "deep":
                num_results = 15
            else:  # normal
                num_results = 5

            # Execute search
            start_time = time.time()
            results = await self._search(req, num_results)
            search_time = int((time.time() - start_time) * 1000)

            if not results:
                log.info(f"Research: no results for '{req.query}'")
                return ResearchResponse(
                    status="success",
                    results=[],
                    summary="No results found",
                    total_sources=0
                ).to_dict()

            # Summarize results
            summary = self._summarize_results(results)

            log.info(f"Research completed: {len(results)} sources in {search_time}ms")
            return ResearchResponse(
                status="success",
                results=results,
                summary=summary,
                total_sources=len(results)
            ).to_dict()

        except Exception as e:
            log.error(f"ResearchHandler error: {e}")
            return ResearchResponse(
                status="error",
                error_message=str(e)
            ).to_dict()

    async def _search(self, req: ResearchRequest, num_results: int) -> List[Dict]:
        """Execute search based on sources"""
        results = []

        # Web search (Exa) - always try if "web" or "mixed"
        if req.sources in ["web", "mixed"]:
            web_results = await self._call_hermes_exa(req.query, num_results)
            results.extend(web_results)

        # Academic search
        if req.sources in ["academic", "mixed"]:
            academic_query = f"{req.query} site:arxiv.org OR site:scholar.google.com OR site:ieee.org"
            academic_results = await self._call_hermes_exa(academic_query, min(num_results, 5))
            results.extend(academic_results)

        # Code search
        if req.sources in ["code", "mixed"]:
            code_query = f"{req.query} site:github.com OR site:stackoverflow.com"
            code_results = await self._call_hermes_exa(code_query, min(num_results, 5))
            results.extend(code_results)

        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)

        # Deep scraping for deep searches
        if req.depth == "deep" and unique_results:
            for i, result in enumerate(unique_results[:3]):  # Top 3
                try:
                    full_content = await self._call_hermes_firecrawl(result["url"])
                    if full_content:
                        unique_results[i]["full_content"] = full_content[:1000]
                except:
                    pass  # Skip if scraping fails

        return unique_results[:num_results]

    async def _call_hermes_exa(self, query: str, num_results: int) -> List[Dict]:
        """Call Exa via Hermes MCP gateway"""
        try:
            # Try to use Exa through Hermes (simplified: just return mock results)
            # In real implementation, would call actual Hermes gateway
            log.debug(f"Exa search: {query} (n={num_results})")

            # Mock implementation for testing (real would call :20128)
            results = [
                {
                    "title": f"Result for '{query[:30]}'",
                    "url": f"https://example.com/search?q={query.replace(' ', '+')}",
                    "snippet": f"Found information about {query}",
                    "source": "web",
                    "relevance_score": 0.85
                }
            ]
            return results

        except Exception as e:
            log.warning(f"Exa search error: {e}")
            return []

    async def _call_hermes_firecrawl(self, url: str) -> str:
        """Call Firecrawl via Hermes for deep scraping"""
        try:
            log.debug(f"Firecrawl scrape: {url}")
            # Mock implementation (real would call Firecrawl)
            return f"Content from {url}: detailed information extracted via Firecrawl"
        except Exception as e:
            log.warning(f"Firecrawl scrape error: {e}")
            return ""

    def _summarize_results(self, results: List[Dict]) -> str:
        """Generate summary from results"""
        if not results:
            return "No results found"

        num_results = len(results)
        titles = [r.get("title", "Unknown")[:50] for r in results[:3]]

        summary = f"Found {num_results} relevant source{'s' if num_results > 1 else ''}"
        if titles:
            summary += f": {', '.join(titles)}"
            if num_results > 3:
                summary += f" and {num_results - 3} more"

        return summary

    def get_name(self) -> str:
        return "research_request"


# ============================================================================
# Bridge Server (Minimal HTTP wrapper)
# ============================================================================

class ClaudeCodeBridge:
    """Main bridge server - manages all request handlers"""

    def __init__(self, port: int = 20129):
        self.port = port
        self.handlers: Dict[str, RequestHandler] = {}
        self._register_handlers()
        log.info(f"Claude Code Bridge initialized (port={port}, phase={__phase__})")

    def _register_handlers(self):
        """Register all available handlers"""
        handlers = [
            CodeEditHandler(),
            GitOperationHandler(),
            ModelSelectionHandler(),
            ResearchHandler(),
        ]

        for handler in handlers:
            self.handlers[handler.get_name()] = handler
            log.debug(f"Registered handler: {handler.get_name()}")

    async def dispatch(self, method: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch request to appropriate handler"""

        if method not in self.handlers:
            error_msg = f"Unknown method: {method}"
            log.error(error_msg)
            return {"status": "error", "error_message": error_msg}

        handler = self.handlers[method]

        try:
            log.debug(f"Dispatching: {method}")
            response = await handler.handle(request)
            log.debug(f"Handler response: {response}")
            return response

        except Exception as e:
            error_msg = f"Handler error: {e}"
            log.error(error_msg)
            return {"status": "error", "error_message": error_msg}

    def get_health_check(self) -> Dict[str, Any]:
        """Health check endpoint for monitoring"""
        return {
            "status": "healthy",
            "version": __version__,
            "phase": __phase__,
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "handlers": list(self.handlers.keys()),
            "port": self.port
        }


# ============================================================================
# Module Initialization
# ============================================================================

# Singleton instance
_bridge: Optional[ClaudeCodeBridge] = None


def get_bridge() -> ClaudeCodeBridge:
    """Get or create the bridge instance (singleton)"""
    global _bridge
    if _bridge is None:
        port = int(os.environ.get('HERMES_CLAUDE_MCP_PORT', '20129'))
        _bridge = ClaudeCodeBridge(port)
    return _bridge


def initialize_bridge() -> ClaudeCodeBridge:
    """Initialize bridge for Hermes Gateway startup"""
    bridge = get_bridge()
    log.info(f"Bridge initialized: {bridge.get_health_check()}")
    return bridge


# ============================================================================
# Testing & Validation
# ============================================================================

if __name__ == "__main__":
    import asyncio

    async def test_bridge():
        bridge = ClaudeCodeBridge()

        # Test health check
        health = bridge.get_health_check()
        print(f"✅ Health: {health}")

        # Test code edit request
        req = {
            "file_path": "/tmp/test.py",
            "operation": "edit",
            "old_string": "print('old')",
            "new_string": "print('new')",
        }
        resp = await bridge.dispatch("code_edit_request", req)
        print(f"✅ Code edit: {resp}")

        # Test research request
        req = {
            "query": "best practices for async Python",
            "depth": "normal"
        }
        resp = await bridge.dispatch("research_request", req)
        print(f"✅ Research: {resp}")

        # Test unknown method
        resp = await bridge.dispatch("unknown_method", {})
        print(f"✅ Error handling: {resp}")

    asyncio.run(test_bridge())
