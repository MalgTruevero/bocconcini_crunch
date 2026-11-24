import os

modules = [
    "bocconcini/__init__.py",
    "bocconcini/client.py",
    "bocconcini/memory.py",
    "bocconcini/docs.py",
    "bocconcini/rami.py"
]

with open("bocconcini_lib_complete.txt", "w", encoding="utf-8") as out:
    out.write("=" * 80 + "\n")
    out.write("BOCCONCINI 5.0.0 - COMPLETE LIBRARY SOURCE CODE\n")
    out.write("=" * 80 + "\n\n")
    
    for mod in modules:
        content = open(mod, encoding="utf-8").read()
        lines = len(content.splitlines())
        
        out.write("=" * 80 + "\n")
        out.write(f"FILE: {mod}  ({lines} righe)\n")
        out.write("=" * 80 + "\n\n")
        out.write(content)
        out.write("\n\n")
    
    out.write("=" * 80 + "\n")
    out.write("END OF LIBRARY\n")
    out.write("=" * 80 + "\n")

print(f"File creato: bocconcini_lib_complete.txt")
print(f"Dimensione: {os.path.getsize('bocconcini_lib_complete.txt')} bytes")
