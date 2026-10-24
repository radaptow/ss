```python
import os
import hashlib

def calculate_file_hash(file_path):
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read(65536)
        while buf:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def find_duplicates(directory):
    file_hashes = {}
    duplicates = {}

    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            file_hash = calculate_file_hash(file_path)

            if file_hash in file_hashes:
                if file_hash not in duplicates:
                    duplicates[file_hash] = [file_hashes[file_hash]]
                duplicates[file_hash].append(file_path)
            else:
                file_hashes[file_hash] = file_path

    return duplicates

def remove_duplicates(duplicates):
    for file_hash, file_paths in duplicates.items():
        if len(file_paths) > 1:
            for file_path in file_paths[1:]:
                os.remove(file_path)
                print(f"Removed duplicate file: {file_path}")

if __name__ == "__main__":
    project_directory = "C:\\SyntaxSanctuary\\PROYECTO"
    duplicates = find_duplicates(project_directory)
    remove_duplicates(duplicates)
```
