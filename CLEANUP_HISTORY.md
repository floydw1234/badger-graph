# Cleaning Git History of Large Files

## Current Status

✅ **Files removed from tracking:**
- `vscode_ext/badger-0.0.4.vsix` (1.4GB)
- All `.badger-index/` directories
- `cli/mcp_server.log` (2.5MB)
- `cli/graph.json` (888KB)

✅ **.gitignore updated** to exclude:
- `venv/`, `node_modules/`, `__pycache__/`
- `.badger-index/`, `*.vsix`, `*.log`
- `vllm/` (174GB directory)
- Test cache directories

⚠️ **Issue:** `.git` directory is still 154GB because large files are in git history.

## Options to Clean History

### Option 1: Start Fresh (Recommended for new repo)

If this is a new remote repo and you haven't pushed yet:

```bash
# Remove the old .git directory
rm -rf .git

# Initialize fresh repo
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main --force
```

### Option 2: Clean History with git filter-repo (Preserves history)

**Install git-filter-repo:**
```bash
pip install git-filter-repo
```

**Remove large files from history:**
```bash
# Remove .vsix files
git filter-repo --path vscode_ext/badger-0.0.4.vsix --invert-paths

# Remove .badger-index directories
git filter-repo --path-glob '**/.badger-index/**' --invert-paths

# Remove log files
git filter-repo --path-glob '**/*.log' --invert-paths

# Remove vllm/ directory (except small config files)
git filter-repo --path vllm/ --invert-paths
# Then re-add just the config files:
git add vllm/README-vllm.md vllm/docker-compose.*.yml vllm/test-models.sh
git commit -m "Re-add vllm config files"
```

**Force push to new remote:**
```bash
git remote add origin <your-repo-url>
git push -u origin main --force
```

### Option 3: Use BFG Repo-Cleaner (Alternative)

```bash
# Download BFG: https://rtyley.github.io/bfg-repo-cleaner/
java -jar bfg.jar --delete-files '*.vsix' --delete-folders '.badger-index' .
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

## Current Changes Ready to Commit

After running the cleanup commands, you have:
- Updated `.gitignore`
- Removed large files from tracking
- 42 files staged for deletion

**Next steps:**
1. Commit the changes: `git commit -m "Remove large files and update .gitignore"`
2. Choose one of the history cleanup options above
3. Push to your new remote

## Verification

After cleanup, verify:
```bash
du -sh .git  # Should be much smaller
git ls-files | wc -l  # Should show reasonable file count
```

