from bocconcini.memory import prepara_albero_ricco

NEEDLES = [
    ("BFR-7491", "__buffer__", "In Python 3.12 __buffer__ restituisce memoryview o TypeError: codice controllo BFR-7491."),
    ("COR-3182", "StopIteration", "PEP 479 StopIteration in coroutine async -> RuntimeError: codice controllo COR-3182."),
    ("TKN-8824", "COMMENT", "tokenize COMMENT non genera INDENT o DEDENT: codice controllo TKN-8824."),
    ("SLT-5509", "__slots__", "__slots__ senza __dict__ -> AttributeError: codice controllo SLT-5509."),
    ("AST-6237", "type_comments", "ast.parse(..., type_comments=True) PEP 484/526: codice controllo AST-6237."),
    ("TSK-9415", "TaskGroup", "asyncio.TaskGroup cancella fratelli e solleva ExceptionGroup: codice controllo TSK-9415."),
]
doc = "\n".join([f"## Sez {i}\nTesto sezione {i}.\n" + (f"Nota: {NEEDLES[i//10][2]}\n" if i % 10 == 0 and i//10 < len(NEEDLES) else "") for i in range(80)])
tree, sess = prepara_albero_ricco(doc, "inspect_matriosca", max_chars=800)
print("TYPE:", type(tree), "SESSION:", sess)
print("ATTRS/METHODS:", [a for a in dir(tree) if not a.startswith("__")][:40])
print("VARS:", list(vars(tree).keys()) if hasattr(tree, "__dict__") else "no __dict__")
