#!/usr/bin/env bash
# =============================================================================
# EstateGap — SpecKit Orchestrator
# Automated spec-driven development pipeline using Claude Code + Codex CLI
# =============================================================================
set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────
VERSION="1.0.0"
SCRIPT_NAME="$(basename "$0")"

# CLI tool commands
CLAUDE_CMD="claude"
CODEX_CMD="codex"

# Models
MODEL_SPECIFY="claude-opus-4-6"         # /speckit.specify — max intelligence
MODEL_PLAN="claude-sonnet-4-6"          # /speckit.plan
MODEL_TASKS="claude-sonnet-4-6"         # /speckit.tasks
MODEL_IMPLEMENT="gpt-5.4"              # /speckit.implement

# Max reasoning for all models
CLAUDE_EFFORT="high"
CODEX_REASONING="xhigh"

# Retry config
MAX_RETRIES=5
RETRY_DELAY_BASE=30          # seconds, exponential backoff: 30, 60, 120, 240, 480

# Context compression
COMPACT_EVERY=0               # 0 = never, N = every N features

# Permissions (fully unrestricted — agents can use any tool: docker, helm, kind, pip, npm, etc.)
CODEX_APPROVAL="never"        # never = fully autonomous, no approval prompts

# Timeouts per step (seconds)
TIMEOUT_CONSTITUTION=300
TIMEOUT_SPECIFY=600
TIMEOUT_PLAN=600
TIMEOUT_TASKS=300
TIMEOUT_IMPLEMENT=1800

# Git & GitHub config
BRANCH_PREFIX="speckit"                # Branch name: speckit/<feature-path>
BASE_BRANCH="main"                     # Branch to merge into
CI_WAIT_TIMEOUT=900                    # Max seconds to wait for CI (15 min)
CI_POLL_INTERVAL=30                    # Seconds between CI status checks
AUTO_MERGE=true                        # true = merge if CI green, false = just push + PR
DELETE_BRANCH_AFTER_MERGE=true         # Clean up feature branches after merge

# ─── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ─── Globals ─────────────────────────────────────────────────────────────────
LOG_FILE=""
FEATURES_DIR=""
ORDER_FILE=""
PROJECT_DIR=""
FEATURE_COUNT=0
CURRENT_FEATURE=0
START_TIME=""
DRY_RUN=false
RESUME_FROM=""
SKIP_CONSTITUTION=false

# ─── Usage ───────────────────────────────────────────────────────────────────
usage() {
    cat <<EOF
${BOLD}EstateGap SpecKit Orchestrator v${VERSION}${NC}

Automates the SpecKit workflow (constitution → specify → plan → tasks → implement)
across all features using Claude Code CLI and Codex CLI in headless mode.

${BOLD}Usage:${NC}
  $SCRIPT_NAME -f <features_dir> -o <order_file> [options]

${BOLD}Required:${NC}
  -f, --features-dir    Path to the folder containing feature prompts
                        (e.g., ./speckit-prompts/)
  -o, --order-file      Path to the execution order file
                        (e.g., ./speckit-prompts/execution-order.txt)

${BOLD}Options:${NC}
  -p, --project-dir     Project working directory (default: current dir)
  -c, --compact-every   Compress context every N features (0=never, default: 0)
  -r, --resume-from     Resume from a specific feature path
                        (e.g., epic-02-api-gateway/feature-01-skeleton-and-auth)
  -s, --skip-constitution  Skip the constitution step
  -l, --log-file        Custom log file path (default: ./estategap-orchestrator-TIMESTAMP.log)
  -b, --base-branch     Base branch to merge into (default: main)
      --no-merge         Push + create PR but don't auto-merge (manual review)
      --no-delete-branch Keep feature branches after merge
      --ci-timeout N     Max seconds to wait for CI (default: 900)
      --dry-run         Print what would be executed without running anything
      --max-retries N   Max retries per step on failure (default: 5)
  -h, --help            Show this help message

${BOLD}Dependencies:${NC}
  claude    Claude Code CLI (npm install -g @anthropic-ai/claude-code)
  codex     OpenAI Codex CLI (npm install -g @openai/codex)
  gh        GitHub CLI (https://cli.github.com/)
  git       Git
  jq        JSON processor (apt install jq)
  timeout   GNU coreutils

${BOLD}Authentication (all via OAuth, no API keys needed):${NC}
  claude    Run 'claude' interactively once to login
  codex     Run 'codex' interactively once to login
  gh        Run 'gh auth login' once to authenticate

${BOLD}Examples:${NC}
  # Full run from scratch
  $SCRIPT_NAME -f ./speckit-prompts -o ./speckit-prompts/execution-order.txt

  # Resume from a specific feature
  $SCRIPT_NAME -f ./speckit-prompts -o ./speckit-prompts/execution-order.txt \\
    -r epic-03-scraping/feature-01-orchestrator-and-proxy --skip-constitution

  # Dry run with context compression every 5 features
  $SCRIPT_NAME -f ./speckit-prompts -o ./speckit-prompts/execution-order.txt \\
    --compact-every 5 --dry-run
EOF
    exit 0
}

# ─── Logging ─────────────────────────────────────────────────────────────────
log() {
    local level="$1"
    shift
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    local msg="[$timestamp] [$level] $*"

    # Write to log file
    echo "$msg" >> "$LOG_FILE"

    # Write to stdout with colors
    case "$level" in
        INFO)    echo -e "${CYAN}$msg${NC}" ;;
        OK)      echo -e "${GREEN}$msg${NC}" ;;
        WARN)    echo -e "${YELLOW}$msg${NC}" ;;
        ERROR)   echo -e "${RED}$msg${NC}" ;;
        STEP)    echo -e "${BOLD}${BLUE}$msg${NC}" ;;
        *)       echo "$msg" ;;
    esac
}

log_separator() {
    local line="════════════════════════════════════════════════════════════════════"
    echo "$line" >> "$LOG_FILE"
    echo -e "${BOLD}$line${NC}"
}

# ─── Preflight Checks ───────────────────────────────────────────────────────
preflight() {
    log INFO "Running preflight checks..."
    local errors=0

    # Check Claude CLI
    if ! command -v "$CLAUDE_CMD" &>/dev/null; then
        log ERROR "Claude Code CLI ('$CLAUDE_CMD') not found. Install: npm install -g @anthropic-ai/claude-code"
        errors=$((errors + 1))
    else
        log OK "Claude Code CLI found: $(command -v "$CLAUDE_CMD")"
    fi

    # Check Codex CLI
    if ! command -v "$CODEX_CMD" &>/dev/null; then
        log ERROR "Codex CLI ('$CODEX_CMD') not found. Install: npm install -g @openai/codex"
        errors=$((errors + 1))
    else
        log OK "Codex CLI found: $(command -v "$CODEX_CMD")"
    fi

    # Check git
    if ! command -v git &>/dev/null; then
        log ERROR "git not found"
        errors=$((errors + 1))
    else
        log OK "git found: $(git --version)"
    fi

    # Check GitHub CLI (gh)
    if ! command -v gh &>/dev/null; then
        log ERROR "GitHub CLI ('gh') not found. Install: https://cli.github.com/"
        errors=$((errors + 1))
    else
        log OK "GitHub CLI found: $(gh --version | head -1)"
        # Verify gh is authenticated
        if gh auth status &>/dev/null 2>&1; then
            log OK "GitHub CLI authenticated"
        else
            log ERROR "GitHub CLI not authenticated. Run 'gh auth login' first."
            errors=$((errors + 1))
        fi
    fi

    # Check jq (needed for CI status parsing)
    if ! command -v jq &>/dev/null; then
        log ERROR "jq not found. Install: apt install jq / brew install jq"
        errors=$((errors + 1))
    else
        log OK "jq found: $(jq --version)"
    fi

    # Check we're in a git repo with a remote
    if [[ -d "$PROJECT_DIR/.git" ]] || git -C "$PROJECT_DIR" rev-parse --git-dir &>/dev/null 2>&1; then
        local remote
        remote=$(git -C "$PROJECT_DIR" remote get-url origin 2>/dev/null || echo "")
        if [[ -n "$remote" ]]; then
            log OK "Git remote: $remote"
        else
            log WARN "No git remote configured. Push/PR/merge will be skipped."
        fi
        # Verify base branch exists
        if git -C "$PROJECT_DIR" rev-parse --verify "$BASE_BRANCH" &>/dev/null 2>&1; then
            log OK "Base branch '$BASE_BRANCH' exists"
        else
            log WARN "Base branch '$BASE_BRANCH' not found. Will create from current HEAD on first run."
        fi
    else
        log WARN "Project dir is not a git repository. Git operations will be skipped."
    fi

    # Check Claude OAuth session
    if "$CLAUDE_CMD" -p "echo ok" --output-format text --max-turns 1 &>/dev/null; then
        log OK "Claude CLI authenticated (OAuth)"
    else
        log ERROR "Claude CLI not authenticated. Run 'claude' interactively to login via OAuth."
        errors=$((errors + 1))
    fi

    # Check Codex OAuth session
    if "$CODEX_CMD" exec "echo ok" --ask-for-approval never &>/dev/null; then
        log OK "Codex CLI authenticated (OAuth)"
    else
        log ERROR "Codex CLI not authenticated. Run 'codex' interactively to login via OAuth."
        errors=$((errors + 1))
    fi

    # Check features directory
    if [[ ! -d "$FEATURES_DIR" ]]; then
        log ERROR "Features directory not found: $FEATURES_DIR"
        errors=$((errors + 1))
    else
        log OK "Features directory: $FEATURES_DIR"
    fi

    # Check order file
    if [[ ! -f "$ORDER_FILE" ]]; then
        log ERROR "Order file not found: $ORDER_FILE"
        errors=$((errors + 1))
    else
        local count
        count=$(grep -cv '^\s*#\|^\s*$' "$ORDER_FILE" || true)
        log OK "Order file: $ORDER_FILE ($count features)"
    fi

    # Check constitution
    if [[ "$SKIP_CONSTITUTION" == "false" ]]; then
        local const_file="$FEATURES_DIR/constitution.md"
        if [[ ! -f "$const_file" ]]; then
            log ERROR "Constitution file not found: $const_file"
            errors=$((errors + 1))
        else
            log OK "Constitution file: $const_file"
        fi
    fi

    # Check project dir
    if [[ ! -d "$PROJECT_DIR" ]]; then
        log ERROR "Project directory not found: $PROJECT_DIR"
        errors=$((errors + 1))
    else
        log OK "Project directory: $PROJECT_DIR"
    fi

    if [[ $errors -gt 0 ]]; then
        log ERROR "Preflight failed with $errors error(s). Aborting."
        exit 1
    fi

    log OK "All preflight checks passed."
}

# ─── Extract prompt content from markdown ────────────────────────────────────
# Reads the content between ``` code fences in the markdown file
extract_prompt() {
    local file="$1"

    if [[ ! -f "$file" ]]; then
        log ERROR "Prompt file not found: $file"
        return 1
    fi

    # Extract content between ``` markers (the prompt block)
    local content
    content=$(sed -n '/^```$/,/^```$/{ /^```$/d; p; }' "$file" 2>/dev/null || true)

    # If no fenced block found, use everything after the first ## heading
    if [[ -z "$content" ]]; then
        content=$(sed -n '/^## \/.*prompt/,$ { /^## \/.*prompt/d; p; }' "$file" 2>/dev/null || true)
    fi

    # Last resort: use the whole file
    if [[ -z "$content" ]]; then
        content=$(cat "$file")
    fi

    echo "$content"
}

# ─── Run command with retry ──────────────────────────────────────────────────
run_with_retry() {
    local step_name="$1"
    local timeout="$2"
    shift 2
    local cmd=("$@")
    local attempt=0
    local delay="$RETRY_DELAY_BASE"

    while [[ $attempt -lt $MAX_RETRIES ]]; do
        attempt=$((attempt + 1))
        log INFO "[$step_name] Attempt $attempt/$MAX_RETRIES"

        if [[ "$DRY_RUN" == "true" ]]; then
            log INFO "[DRY RUN] Would execute: ${cmd[*]:0:3}... (${#cmd[@]} args)"
            return 0
        fi

        # Run with timeout, capture exit code
        local exit_code=0
        local output_file
        output_file=$(mktemp)

        timeout "$timeout" "${cmd[@]}" > "$output_file" 2>&1 || exit_code=$?

        # Log output to log file
        {
            echo "--- $step_name output (attempt $attempt) ---"
            cat "$output_file"
            echo "--- end output ---"
        } >> "$LOG_FILE"

        if [[ $exit_code -eq 0 ]]; then
            log OK "[$step_name] Completed successfully (attempt $attempt)"
            rm -f "$output_file"
            return 0
        fi

        # Check for known transient errors
        local output_content
        output_content=$(cat "$output_file")
        rm -f "$output_file"

        if echo "$output_content" | grep -qi "rate.limit\|429\|overloaded\|capacity\|timeout\|connection.*refused\|ECONNRESET\|502\|503\|504"; then
            log WARN "[$step_name] Transient error detected (exit code $exit_code). Retrying in ${delay}s..."
            sleep "$delay"
            delay=$((delay * 2))  # Exponential backoff
            continue
        fi

        # Non-transient error
        if [[ $attempt -lt $MAX_RETRIES ]]; then
            log WARN "[$step_name] Failed (exit code $exit_code). Retrying in ${delay}s..."
            sleep "$delay"
            delay=$((delay * 2))
        else
            log ERROR "[$step_name] Failed after $MAX_RETRIES attempts. Exit code: $exit_code"
            log ERROR "Last output: $(echo "$output_content" | tail -20)"
            return 1
        fi
    done

    return 1
}

# ─── Step: Constitution ──────────────────────────────────────────────────────
run_constitution() {
    log_separator
    log STEP "PHASE 0: Running /speckit.constitution"

    local const_file="$FEATURES_DIR/constitution.md"
    local prompt
    prompt=$(extract_prompt "$const_file")

    run_with_retry "constitution" "$TIMEOUT_CONSTITUTION" \
        "$CLAUDE_CMD" -p "/speckit.constitution $prompt" \
            --model "$MODEL_SPECIFY" \
            --output-format text \
            --dangerously-skip-permissions \
            --max-turns 30

    log OK "Constitution created."
}

# ─── Step: Specify ───────────────────────────────────────────────────────────
run_specify() {
    local feature_path="$1"
    local prompt_file="$FEATURES_DIR/$feature_path/specify.md"
    local prompt
    prompt=$(extract_prompt "$prompt_file")

    log STEP "  → /speckit.specify (Claude $MODEL_SPECIFY)"

    run_with_retry "specify [$feature_path]" "$TIMEOUT_SPECIFY" \
        "$CLAUDE_CMD" -p "/speckit.specify $prompt" \
            --model "$MODEL_SPECIFY" \
            --output-format text \
            --dangerously-skip-permissions \
            --max-turns 50
}

# ─── Step: Plan ──────────────────────────────────────────────────────────────
run_plan() {
    local feature_path="$1"
    local prompt_file="$FEATURES_DIR/$feature_path/plan.md"
    local prompt
    prompt=$(extract_prompt "$prompt_file")

    log STEP "  → /speckit.plan (Claude $MODEL_PLAN)"

    run_with_retry "plan [$feature_path]" "$TIMEOUT_PLAN" \
        "$CLAUDE_CMD" -p "/speckit.plan $prompt" \
            --model "$MODEL_PLAN" \
            --output-format text \
            --dangerously-skip-permissions \
            --max-turns 50 \
            --continue
}

# ─── Step: Tasks ─────────────────────────────────────────────────────────────
run_tasks() {
    local feature_path="$1"

    log STEP "  → /speckit.tasks (Claude $MODEL_TASKS)"

    run_with_retry "tasks [$feature_path]" "$TIMEOUT_TASKS" \
        "$CLAUDE_CMD" -p "/speckit.tasks" \
            --model "$MODEL_TASKS" \
            --output-format text \
            --dangerously-skip-permissions \
            --max-turns 30 \
            --continue
}

# ─── Step: Implement ─────────────────────────────────────────────────────────
run_implement() {
    local feature_path="$1"

    log STEP "  → /speckit.implement (Codex $MODEL_IMPLEMENT)"

    run_with_retry "implement [$feature_path]" "$TIMEOUT_IMPLEMENT" \
        "$CODEX_CMD" exec "/speckit.implement" \
            --model "$MODEL_IMPLEMENT" \
            -c "model_reasoning_effort=$CODEX_REASONING" \
            --ask-for-approval "$CODEX_APPROVAL" \
            --path "$PROJECT_DIR"
}

# ─── Step: Context Compression ───────────────────────────────────────────────
run_compact() {
    log INFO "  → Running context compression (/compact)..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log INFO "[DRY RUN] Would run context compression"
        return 0
    fi

    # Claude: start a fresh session with compaction instruction
    "$CLAUDE_CMD" -p "/compact Summarize all work done so far. Preserve key architectural decisions, file paths, and interfaces." \
        --model "$MODEL_TASKS" \
        --output-format text \
        --dangerously-skip-permissions \
        --max-turns 5 \
    >> "$LOG_FILE" 2>&1 || log WARN "Context compression failed (non-critical)"

    log OK "Context compression completed."
}

# ─── Git: Branch Management ──────────────────────────────────────────────────

# Convert feature path to branch name: epic-02-api-gateway/feature-01-skeleton → speckit/epic-02-api-gateway/feature-01-skeleton
feature_to_branch() {
    local feature_path="$1"
    echo "${BRANCH_PREFIX}/${feature_path}"
}

# Check if project has a git remote configured
has_git_remote() {
    git -C "$PROJECT_DIR" remote get-url origin &>/dev/null 2>&1
}

# Create feature branch, commit, push, open PR, wait for CI, merge if green
git_commit_push_and_merge() {
    local feature_path="$1"
    local feature_idx="$2"

    if [[ "$DRY_RUN" == "true" ]]; then
        log INFO "[DRY RUN] Would: create branch, commit, push, PR, wait CI, merge"
        return 0
    fi

    (
        cd "$PROJECT_DIR"

        # Check if there are changes to commit
        if git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null; then
            log INFO "No changes to commit for $feature_path"
            return 0
        fi

        local branch_name
        branch_name=$(feature_to_branch "$feature_path")

        # ── Step 1: Create feature branch ────────────────────────────
        log INFO "  → Creating branch: $branch_name"

        # Make sure we're on the base branch before creating the feature branch
        git checkout "$BASE_BRANCH" 2>/dev/null || true
        git pull origin "$BASE_BRANCH" --ff-only 2>/dev/null || true

        # Create and switch to feature branch
        git checkout -b "$branch_name" 2>/dev/null || git checkout "$branch_name" 2>/dev/null
        log OK "  → On branch: $branch_name"

        # ── Step 2: Commit ───────────────────────────────────────────
        git add -A
        git commit -m "feat: implement $feature_path

Automated by EstateGap SpecKit Orchestrator v${VERSION}
Feature: $feature_path ($feature_idx/$FEATURE_COUNT)
Models: specify=$MODEL_SPECIFY plan=$MODEL_PLAN implement=$MODEL_IMPLEMENT"

        log OK "  → Changes committed"

        # ── Step 3: Push ─────────────────────────────────────────────
        if ! has_git_remote; then
            log WARN "  → No git remote configured. Skipping push/PR/merge."
            git checkout "$BASE_BRANCH" 2>/dev/null || true
            return 0
        fi

        log INFO "  → Pushing branch to origin..."
        git push -u origin "$branch_name" --force-with-lease
        log OK "  → Branch pushed: $branch_name"

        # ── Step 4: Create Pull Request ──────────────────────────────
        local pr_title="feat: implement $feature_path"
        local pr_body="## Feature: \`$feature_path\`

**Automated by EstateGap SpecKit Orchestrator v${VERSION}**

| | |
|---|---|
| Feature | $feature_path |
| Progress | $feature_idx / $FEATURE_COUNT |
| Specify model | $MODEL_SPECIFY |
| Plan model | $MODEL_PLAN |
| Tasks model | $MODEL_TASKS |
| Implement model | $MODEL_IMPLEMENT |

---
*This PR was automatically generated by the SpecKit orchestrator.*"

        # Check if PR already exists for this branch
        local existing_pr
        existing_pr=$(gh pr list --head "$branch_name" --json number --jq '.[0].number' 2>/dev/null || echo "")

        local pr_number
        if [[ -n "$existing_pr" ]] && [[ "$existing_pr" != "null" ]]; then
            pr_number="$existing_pr"
            log INFO "  → PR #${pr_number} already exists, updating..."
        else
            pr_number=$(gh pr create \
                --base "$BASE_BRANCH" \
                --head "$branch_name" \
                --title "$pr_title" \
                --body "$pr_body" \
                2>/dev/null | grep -oP '/pull/\K[0-9]+' || echo "")

            # Fallback: try to extract PR number differently
            if [[ -z "$pr_number" ]]; then
                pr_number=$(gh pr list --head "$branch_name" --json number --jq '.[0].number' 2>/dev/null || echo "")
            fi

            if [[ -n "$pr_number" ]] && [[ "$pr_number" != "null" ]]; then
                log OK "  → PR #${pr_number} created"
            else
                log WARN "  → Could not create PR. Branch pushed, merge manually."
                git checkout "$BASE_BRANCH" 2>/dev/null || true
                return 0
            fi
        fi

        # ── Step 5: Wait for CI checks ──────────────────────────────
        log INFO "  → Waiting for CI checks on PR #${pr_number}..."

        local ci_result
        ci_result=$(wait_for_ci "$pr_number" "$branch_name")

        case "$ci_result" in
            "pass")
                log OK "  → All CI checks passed"
                ;;
            "no_checks")
                log INFO "  → No CI checks configured. Proceeding with merge."
                ;;
            "fail")
                log ERROR "  → CI checks failed on PR #${pr_number}. Branch pushed but NOT merged."
                log ERROR "  → Fix issues and merge manually: gh pr merge $pr_number --merge"
                git checkout "$BASE_BRANCH" 2>/dev/null || true
                return 0
                ;;
            "timeout")
                log WARN "  → CI checks timed out after ${CI_WAIT_TIMEOUT}s. Branch pushed but NOT merged."
                log WARN "  → Check CI status and merge manually: gh pr merge $pr_number --merge"
                git checkout "$BASE_BRANCH" 2>/dev/null || true
                return 0
                ;;
        esac

        # ── Step 6: Merge to base branch ─────────────────────────────
        if [[ "$AUTO_MERGE" == "true" ]]; then
            log INFO "  → Merging PR #${pr_number} into $BASE_BRANCH..."

            if gh pr merge "$pr_number" \
                --merge \
                --subject "feat: implement $feature_path (#${pr_number})" \
                $([ "$DELETE_BRANCH_AFTER_MERGE" == "true" ] && echo "--delete-branch") \
                2>/dev/null; then
                log OK "  → PR #${pr_number} merged into $BASE_BRANCH"
            else
                log WARN "  → Auto-merge failed. Merge manually: gh pr merge $pr_number --merge"
            fi
        else
            log INFO "  → Auto-merge disabled. PR #${pr_number} ready for manual review."
        fi

        # Switch back to base branch for next feature
        git checkout "$BASE_BRANCH" 2>/dev/null || true
        git pull origin "$BASE_BRANCH" --ff-only 2>/dev/null || true
    )
}

# ─── Git: Wait for CI ────────────────────────────────────────────────────────

# Polls GitHub Actions status until all checks pass, fail, or timeout
# Returns: "pass", "fail", "no_checks", or "timeout"
wait_for_ci() {
    local pr_number="$1"
    local branch_name="$2"
    local elapsed=0

    # Initial wait: give CI a moment to start
    sleep 10
    elapsed=10

    while [[ $elapsed -lt $CI_WAIT_TIMEOUT ]]; do

        # Get check status using gh
        local status_json
        status_json=$(gh pr checks "$pr_number" --json "name,state,status" 2>/dev/null || echo "[]")

        # No checks at all?
        local total_checks
        total_checks=$(echo "$status_json" | jq 'length' 2>/dev/null || echo "0")

        if [[ "$total_checks" == "0" ]]; then
            # Wait a bit more — checks might not have registered yet
            if [[ $elapsed -gt 60 ]]; then
                echo "no_checks"
                return 0
            fi
            log INFO "    Waiting for CI checks to register... (${elapsed}s)"
            sleep "$CI_POLL_INTERVAL"
            elapsed=$((elapsed + CI_POLL_INTERVAL))
            continue
        fi

        # Count statuses
        local pending completed succeeded failed
        pending=$(echo "$status_json" | jq '[.[] | select(.status != "COMPLETED")] | length' 2>/dev/null || echo "0")
        completed=$(echo "$status_json" | jq '[.[] | select(.status == "COMPLETED")] | length' 2>/dev/null || echo "0")
        succeeded=$(echo "$status_json" | jq '[.[] | select(.state == "SUCCESS" or .state == "NEUTRAL" or .state == "SKIPPED")] | length' 2>/dev/null || echo "0")
        failed=$(echo "$status_json" | jq '[.[] | select(.state == "FAILURE" or .state == "ERROR" or .state == "CANCELLED")] | length' 2>/dev/null || echo "0")

        log INFO "    CI status: $succeeded passed, $failed failed, $pending pending (${elapsed}s/${CI_WAIT_TIMEOUT}s)"

        # All completed?
        if [[ "$pending" == "0" ]]; then
            if [[ "$failed" == "0" ]]; then
                echo "pass"
                return 0
            else
                # Log which checks failed
                local failed_names
                failed_names=$(echo "$status_json" | jq -r '.[] | select(.state == "FAILURE" or .state == "ERROR") | .name' 2>/dev/null || echo "unknown")
                log ERROR "    Failed checks: $failed_names" >> "$LOG_FILE"
                echo "fail"
                return 0
            fi
        fi

        sleep "$CI_POLL_INTERVAL"
        elapsed=$((elapsed + CI_POLL_INTERVAL))
    done

    echo "timeout"
    return 0
}

# ─── Parse features from order file ──────────────────────────────────────────
parse_features() {
    local features=()
    while IFS= read -r line; do
        # Skip comments and empty lines
        line=$(echo "$line" | sed 's/#.*//' | xargs)
        [[ -z "$line" ]] && continue
        features+=("$line")
    done < "$ORDER_FILE"
    printf '%s\n' "${features[@]}"
}

# ─── Main Feature Loop ──────────────────────────────────────────────────────
run_features() {
    local features
    mapfile -t features < <(parse_features)
    FEATURE_COUNT=${#features[@]}

    log INFO "Total features to process: $FEATURE_COUNT"

    local resuming=false
    [[ -n "$RESUME_FROM" ]] && resuming=true

    local feature_idx=0
    for feature_path in "${features[@]}"; do
        feature_idx=$((feature_idx + 1))
        CURRENT_FEATURE=$feature_idx

        # Resume logic: skip until we find the resume target
        if [[ "$resuming" == "true" ]]; then
            if [[ "$feature_path" == "$RESUME_FROM" ]]; then
                resuming=false
                log INFO "Resuming from: $feature_path"
            else
                log INFO "Skipping (resume): $feature_path"
                continue
            fi
        fi

        # Validate feature directory exists
        if [[ ! -d "$FEATURES_DIR/$feature_path" ]]; then
            log ERROR "Feature directory not found: $FEATURES_DIR/$feature_path"
            log WARN "Skipping feature. Check execution-order.txt."
            continue
        fi

        log_separator
        log STEP "FEATURE $feature_idx/$FEATURE_COUNT: $feature_path"
        local feature_start
        feature_start=$(date +%s)

        # Step 1: Specify (Claude Opus)
        if [[ -f "$FEATURES_DIR/$feature_path/specify.md" ]]; then
            run_specify "$feature_path"
        else
            log WARN "No specify.md found for $feature_path — skipping specify step"
        fi

        # Step 2: Plan (Claude Sonnet)
        if [[ -f "$FEATURES_DIR/$feature_path/plan.md" ]]; then
            run_plan "$feature_path"
        else
            log WARN "No plan.md found for $feature_path — skipping plan step"
        fi

        # Step 3: Tasks (Claude Sonnet)
        run_tasks "$feature_path"

        # Step 4: Implement (Codex GPT)
        run_implement "$feature_path"

        # Timing
        local feature_end
        feature_end=$(date +%s)
        local feature_duration=$(( feature_end - feature_start ))
        log OK "Feature completed in $(format_duration $feature_duration)"

        # Git: branch, commit, push, PR, CI wait, merge
        git_commit_push_and_merge "$feature_path" "$feature_idx"

        # Context compression if configured
        if [[ $COMPACT_EVERY -gt 0 ]] && [[ $((feature_idx % COMPACT_EVERY)) -eq 0 ]]; then
            log INFO "Compressing context (every $COMPACT_EVERY features)..."
            run_compact
        fi
    done

    if [[ "$resuming" == "true" ]]; then
        log ERROR "Resume target not found: $RESUME_FROM"
        log ERROR "Available features:"
        parse_features | while read -r f; do log INFO "  $f"; done
        exit 1
    fi
}

# ─── Helpers ─────────────────────────────────────────────────────────────────
format_duration() {
    local secs="$1"
    local mins=$((secs / 60))
    local remaining_secs=$((secs % 60))
    if [[ $mins -gt 0 ]]; then
        echo "${mins}m ${remaining_secs}s"
    else
        echo "${secs}s"
    fi
}

# ─── Parse Arguments ─────────────────────────────────────────────────────────
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -f|--features-dir)    FEATURES_DIR="$2"; shift 2 ;;
            -o|--order-file)      ORDER_FILE="$2"; shift 2 ;;
            -p|--project-dir)     PROJECT_DIR="$2"; shift 2 ;;
            -c|--compact-every)   COMPACT_EVERY="$2"; shift 2 ;;
            -r|--resume-from)     RESUME_FROM="$2"; shift 2 ;;
            -s|--skip-constitution) SKIP_CONSTITUTION=true; shift ;;
            -l|--log-file)        LOG_FILE="$2"; shift 2 ;;
            -b|--base-branch)     BASE_BRANCH="$2"; shift 2 ;;
            --no-merge)           AUTO_MERGE=false; shift ;;
            --no-delete-branch)   DELETE_BRANCH_AFTER_MERGE=false; shift ;;
            --ci-timeout)         CI_WAIT_TIMEOUT="$2"; shift 2 ;;
            --dry-run)            DRY_RUN=true; shift ;;
            --max-retries)        MAX_RETRIES="$2"; shift 2 ;;
            -h|--help)            usage ;;
            *)                    echo "Unknown option: $1"; usage ;;
        esac
    done

    # Defaults
    PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
    LOG_FILE="${LOG_FILE:-./estategap-orchestrator-$(date '+%Y%m%d-%H%M%S').log}"

    # Validate required args
    if [[ -z "$FEATURES_DIR" ]] || [[ -z "$ORDER_FILE" ]]; then
        echo -e "${RED}Error: --features-dir and --order-file are required${NC}"
        echo ""
        usage
    fi
}

# ─── Main ────────────────────────────────────────────────────────────────────
main() {
    parse_args "$@"

    # Initialize log
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"

    START_TIME=$(date +%s)

    log_separator
    log STEP "EstateGap SpecKit Orchestrator v${VERSION}"
    log INFO "Started at: $(date)"
    log INFO "Project dir: $PROJECT_DIR"
    log INFO "Features dir: $FEATURES_DIR"
    log INFO "Order file: $ORDER_FILE"
    log INFO "Log file: $LOG_FILE"
    log INFO "Dry run: $DRY_RUN"
    log INFO "Compact every: $COMPACT_EVERY features"
    log INFO "Max retries: $MAX_RETRIES"
    log INFO "Resume from: ${RESUME_FROM:-<beginning>}"
    log INFO ""
    log INFO "Models:"
    log INFO "  specify:    $MODEL_SPECIFY (Claude, effort=$CLAUDE_EFFORT)"
    log INFO "  plan:       $MODEL_PLAN (Claude, effort=$CLAUDE_EFFORT)"
    log INFO "  tasks:      $MODEL_TASKS (Claude, effort=$CLAUDE_EFFORT)"
    log INFO "  implement:  $MODEL_IMPLEMENT (Codex, reasoning=$CODEX_REASONING)"
    log INFO ""
    log INFO "Git & GitHub:"
    log INFO "  Base branch:   $BASE_BRANCH"
    log INFO "  Branch prefix: $BRANCH_PREFIX"
    log INFO "  Auto merge:    $AUTO_MERGE"
    log INFO "  CI timeout:    ${CI_WAIT_TIMEOUT}s"
    log INFO "  Delete branch: $DELETE_BRANCH_AFTER_MERGE"
    log_separator

    # Preflight
    preflight

    # Constitution
    if [[ "$SKIP_CONSTITUTION" == "false" ]]; then
        run_constitution
    else
        log INFO "Skipping constitution (--skip-constitution)"
    fi

    # Feature loop
    run_features

    # Summary
    local end_time
    end_time=$(date +%s)
    local total_duration=$(( end_time - START_TIME ))

    log_separator
    log STEP "ORCHESTRATION COMPLETE"
    log OK "Features processed: $CURRENT_FEATURE/$FEATURE_COUNT"
    log OK "Total duration: $(format_duration $total_duration)"
    log OK "Log file: $LOG_FILE"
    log_separator
}

# ─── Entry Point ─────────────────────────────────────────────────────────────
main "$@"
