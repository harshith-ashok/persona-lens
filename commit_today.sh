#!/usr/bin/env bash
# Commits today's work as a handful of short commits: (<action>):<name>
# Usage: ./commit_today.sh            commit
#        ./commit_today.sh --dry-run  show what each commit would contain
set -euo pipefail
cd "$(dirname "$0")"

DRY=false; [ "${1:-}" = "--dry-run" ] && DRY=true

git reset -q   # start from an empty index so each commit holds only its own files

# never commit secrets or compiled Python (uploaded files in backend/data are git-ignored)
skip() { [[ "$1" =~ \.pyc$ || "$1" =~ (^|/)__pycache__/ || "$1" =~ (^|/)\.env$ || "$1" =~ (^|/)\.env\.local$ ]]; }

commit() {  # commit "<message>" <paths...>
  local msg="$1"; shift
  local files=() f
  while IFS= read -r -d '' f; do
    skip "$f" || files+=("$f")
  done < <(git ls-files -z -m -o -d --exclude-standard -- "$@" | sort -zu)
  [ ${#files[@]} -gt 0 ] || return 0

  git add -A -- "${files[@]}"
  if $DRY; then echo "$msg"; git diff --cached --name-status | sed 's/^/    /'; git reset -q
  else git commit -q -m "$msg" && echo "$msg  (${#files[@]} files)"; fi
}

commit "(add):docker-stack"     docker-compose.yml docker
commit "(add):migrations"       migrations supabase.sql
commit "(update):config"        .gitignore backend/db.py backend/config.py backend/.env.example backend/requirements.txt \
                                frontend/.env.example frontend/index.html frontend/src/lib testing/getToken.js
commit "(add):sessions"         backend/session.py backend/speech.py backend/llm.py backend/auth.py
commit "(add):voice"            backend/voice.py backend/live.py backend/enrollment.py backend/host.py
commit "(add):vision"           backend/face.py backend/vision.py
commit "(add):gallery"          backend/gallery.py
commit "(add):memory-timeline"  backend/memory.py backend/events.py
commit "(update):api"           backend/main.py
commit "(add):web-ui"           frontend/src
commit "(add):docs"             CLAUDE.md MASTER_DOC.md TODO.md docs features.md new_things.md slide_content.md ref.html
commit "(add):testing"          testing/loadtest.py testing/pitch_demo_script.md
commit "(remove):vision-pro"    vision-pro
commit "(add):commit-script"    commit_today.sh
commit "(update):misc"          .

echo; echo "left uncommitted (compiled files, not for git):"; git status --short | head -5
