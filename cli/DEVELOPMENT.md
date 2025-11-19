# Development Guide

## Quick Iteration Setup

### Option 1: Editable Install (Recommended)

Install once in editable mode - changes are immediately available:

```bash
cd cli
pip install -e .
```

Now you can:
- Edit code in `badger/` directory
- Run `badger` command immediately - no reinstall needed!
- Changes are live instantly

### Option 2: Run Directly (No Install)

Run the module directly without installing:

```bash
cd cli
python -m badger.main
```

Or:

```bash
cd cli
python badger/main.py
```

### Option 3: Development Script

Create a simple dev script for even faster iteration:

```bash
# In cli/ directory, create a script:
#!/bin/bash
cd "$(dirname "$0")"
python -m badger.main "$@"
```

Then make it executable:
```bash
chmod +x dev.sh
./dev.sh
```

## Testing Workflow

1. **Make changes** to code in `badger/` directory
2. **Run immediately**:
   - If installed: `badger`
   - If not installed: `python -m badger.main`
3. **No reinstall needed!**

## Installing Dependencies

If you add new dependencies:

1. Add to `requirements.txt`
2. Install: `pip install -r requirements.txt`
3. If using editable install, update `pyproject.toml` and reinstall:
   ```bash
   pip install -e .
   ```

## Virtual Environment (Recommended)

Use a virtual environment to keep dependencies isolated:

```bash
# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install in editable mode
pip install -e .

# Now you can iterate quickly!
badger
```

## Quick Test Commands

```bash
# Test basic functionality
badger --help

# Test in a sample directory
cd test_code
badger

# Test with verbose output
badger --verbose

# Test with custom endpoint
badger --graphdb-endpoint http://localhost:8080
```


