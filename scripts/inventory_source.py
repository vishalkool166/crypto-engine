"""Static code inventory; does not import application or connect to brokers."""
import ast
import json
import hashlib
from pathlib import Path

root=Path(__file__).resolve().parents[1]
backend=root
routes=[];jobs=[];imports=[];syntax=[]
for p in sorted(backend.rglob('*.py')):
    if any(i in p.relative_to(root).parts for i in ('__pycache__','.venv','dashboard','frontend','scripts','tests','docs')): continue
    rel=p.relative_to(root).as_posix()
    try:
        source=p.read_text()
        tree=ast.parse(source,filename=rel)
    except (UnicodeError,SyntaxError) as err:
        syntax.append({'file':rel,'error':type(err).__name__});continue
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                if isinstance(deco,ast.Call) and isinstance(deco.func,ast.Attribute) and deco.func.attr in ('get','post','put','patch','delete','websocket','route') and deco.args:
                    try: path=ast.literal_eval(deco.args[0])
                    except (ValueError,TypeError):continue
                    if isinstance(path,str):routes.append({'method':deco.func.attr.upper(),'path':path,'file':rel,'handler':node.name})
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='add_job':
            params={}
            for kw in node.keywords:
                if kw.arg in ('id','trigger','seconds','minutes','hours'):
                    try:params[kw.arg]=ast.literal_eval(kw.value)
                    except (ValueError,TypeError): pass
            jobs.append({'file':rel,'line':node.lineno,'function':ast.unparse(node.args[0]) if node.args else 'dynamic',**params})
        if isinstance(node,ast.Import): imports.extend(a.name.split('.')[0] for a in node.names)
        if isinstance(node,ast.ImportFrom) and node.module:imports.append(node.module.split('.')[0])
result={'source':'static AST only: no live verification',
        'routes':sorted(routes,key=lambda r:(r['file'],r['path'])),
        'scheduled_jobs':jobs,'python_files':len([p for p in backend.rglob('*.py') if not any(x in p.relative_to(root).parts for x in ('__pycache__','.venv','dashboard','frontend','scripts','tests','docs'))]),
        'top_imports':sorted(set(imports)),'unparsed':syntax}
# Print the inventory on demand instead of committing stale generated JSON.
print(json.dumps(result, indent=2))
