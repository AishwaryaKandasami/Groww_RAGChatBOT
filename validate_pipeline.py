"""Quick validation of RAG pipeline files."""
import ast
import os

files = ['ingest.py', 'retriever.py', 'generator.py', 'requirements.txt', '.env.example']

print("=== RAG Pipeline Files ===")
for f in files:
    size = os.path.getsize(f)
    lines = sum(1 for _ in open(f, encoding='utf-8'))
    # Syntax check for .py files
    status = ""
    if f.endswith('.py'):
        try:
            ast.parse(open(f, 'r', encoding='utf-8').read())
            status = "  [syntax OK]"
        except SyntaxError as e:
            status = f"  [SYNTAX ERROR: {e}]"
    print(f"  {f:25s} {size:>6d} bytes  {lines:>4d} lines{status}")

print("\n=== Folder Structure ===")
print("RAG_GRoww/")
for f in sorted(files):
    print(f"  ├── {f}")
print("  ├── extracted_facts.json")
print("  ├── knowledge_base.md")
print("  ├── url_registry.md")
print("  ├── architecture.md")
print("  ├── pdf_extracts/")
print("  └── vector_store/          (created by ingest.py)")
