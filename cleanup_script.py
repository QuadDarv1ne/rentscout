import os
import re
from pathlib import Path

def find_and_remove_temp_files(root_dir):
    """Find and remove temporary and duplicate-like files"""
    root_path = Path(root_dir)
    
    # Patterns for temporary/duplicate files
    temp_patterns = [
        r'.*temp.*',
        r'.*backup.*',
        r'.*copy.*',
        r'.*duplicate.*',
        r'.*old.*',
        r'.*_backup.*',
        r'.*_old.*',
        r'.*_copy.*',
        r'.*_duplicate.*',
        r'.* \(1\).*',
        r'.* \(2\).*',
        r'.* \(3\).*'
    ]
    
    excluded_dirs = {'.git', 'alembic', 'docker', 'docs', 'logs', 'scripts', '.github'}
    
    removed_count = 0
    
    for root, dirs, files in os.walk(root_path):
        # Remove excluded directories from dirs to prevent walking into them
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        
        for file in files:
            for pattern in temp_patterns:
                if re.match(pattern, file, re.IGNORECASE):
                    file_path = Path(root) / file
                    try:
                        print(f"Removing: {file_path}")
                        file_path.unlink()
                        removed_count += 1
                    except Exception as e:
                        print(f"Error removing {file_path}: {e}")
                    break  # Break to avoid checking other patterns for the same file
    
    print(f"Total files removed: {removed_count}")

if __name__ == "__main__":
    find_and_remove_temp_files(".")