# ---- static visualizer tracer body (USER_SRC and STDIN_DATA are prepended by the server) ----
import sys, json, io

MAX_STEPS = 800
MAX_STR = 160
MAX_ITEMS = 50
MAX_DEPTH = 4
MAX_FRAMES = 24

steps = []
out_buf = io.StringIO()


class _Stop(Exception):
    pass


def ser(v, depth=0):
    if depth > MAX_DEPTH:
        return {"t": "obj", "v": "…"}
    if v is None or isinstance(v, bool):
        return {"t": "prim", "v": repr(v)}
    if isinstance(v, (int, float)):
        return {"t": "prim", "v": repr(v)}
    if isinstance(v, str):
        s = v if len(v) <= MAX_STR else v[:MAX_STR] + "…"
        return {"t": "str", "v": s}
    if isinstance(v, (list, tuple)):
        out = [ser(x, depth + 1) for x in list(v)[:MAX_ITEMS]]
        return {"t": "tuple" if isinstance(v, tuple) else "list", "v": out,
                "more": max(0, len(v) - MAX_ITEMS)}
    if isinstance(v, (set, frozenset)):
        lv = list(v)
        out = [ser(x, depth + 1) for x in lv[:MAX_ITEMS]]
        return {"t": "set", "v": out, "more": max(0, len(lv) - MAX_ITEMS)}
    if isinstance(v, dict):
        items = list(v.items())[:MAX_ITEMS]
        out = [[ser(k, depth + 1), ser(val, depth + 1)] for k, val in items]
        return {"t": "dict", "v": out, "more": max(0, len(v) - MAX_ITEMS)}
    r = repr(v)
    if len(r) > MAX_STR:
        r = r[:MAX_STR] + "…"
    return {"t": "obj", "v": r}


_SKIP = ("__builtins__",)


def _locals(frame):
    out = {}
    for k, val in list(frame.f_locals.items()):
        if k in _SKIP or (k.startswith("__") and k.endswith("__")):
            continue
        # skip modules / functions / classes to keep the panel about DATA
        t = type(val).__name__
        if t in ("module", "function", "builtin_function_or_method", "type"):
            continue
        out[k] = ser(val)
    return out


def tracer(frame, event, arg):
    if frame.f_code.co_filename != "<user>":
        return None
    if event in ("line", "call", "return", "exception"):
        chain = []
        f = frame
        while f is not None:
            if f.f_code.co_filename == "<user>":
                chain.append(f)
            f = f.f_back
        chain.reverse()
        chain = chain[-MAX_FRAMES:]
        stack = [{"func": fr.f_code.co_name, "line": fr.f_lineno, "locals": _locals(fr)}
                 for fr in chain]
        steps.append({"event": event, "line": frame.f_lineno,
                      "func": frame.f_code.co_name, "stack": stack,
                      "o": out_buf.tell()})
        if len(steps) >= MAX_STEPS:
            raise _Stop()
    return tracer


def _main():
    sys.stdin = io.StringIO(STDIN_DATA)  # noqa: F821
    real = sys.stdout
    sys.stdout = out_buf
    err = None
    truncated = False
    try:
        code = compile(USER_SRC, "<user>", "exec")  # noqa: F821
    except SyntaxError as e:
        sys.stdout = real
        print(json.dumps({"ok": False, "error": "SyntaxError: %s (line %s)" % (e.msg, e.lineno)}))
        return
    sys.settrace(tracer)
    try:
        exec(code, {"__name__": "__main__"})
    except _Stop:
        truncated = True
    except SystemExit:
        pass
    except BaseException:  # noqa: BLE001
        import traceback
        err = traceback.format_exc(limit=2)
    finally:
        sys.settrace(None)
        sys.stdout = real
    print(json.dumps({"ok": True, "steps": steps, "stdout": out_buf.getvalue(),
                      "error": err, "truncated": truncated}))


_main()
