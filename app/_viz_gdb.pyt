# gdb-driven C++ step tracer. gdb runs this as: gdb -q -batch -nx -x viz_gdb.py --args ./sol
# Only sol.cpp is built with -g, and we `skip` /usr/* so `step` descends into the user's own
# functions but steps OVER STL / library internals — the Python-Tutor feel, in C++.
# Emits the SAME JSON shape as the Python tracer to <cwd>/trace.json.
import gdb
import json

SRC = "sol.cpp"
MAX_STEPS = 600      # recorded user-line steps
MAX_RAW = 12000      # hard cap on underlying gdb steps (protects against STL-heavy lines)
MAX_STR = 200
MAX_FRAMES = 24

steps = []


def _sal_line(f):
    try:
        sal = f.find_sal()
        return sal.line if (sal and sal.symtab) else 0
    except Exception:
        return 0


def _in_user(f):
    try:
        sal = f.find_sal()
        return bool(sal and sal.symtab and sal.symtab.filename.endswith(SRC))
    except Exception:
        return False


def _user_frames():
    frames = []
    try:
        f = gdb.newest_frame()
    except gdb.error:
        return frames
    while f is not None:
        if _in_user(f):
            frames.append(f)
        try:
            f = f.older()
        except gdb.error:
            break
    frames.reverse()
    return frames[-MAX_FRAMES:]


def _locals(frame):
    out = {}
    try:
        block = frame.block()
    except Exception:
        return out
    seen = set()
    while block is not None:
        try:
            if block.is_global or block.is_static:
                break
        except Exception:
            break
        for sym in block:
            try:
                if not (sym.is_variable or sym.is_argument):
                    continue
                if sym.name in seen:
                    continue
                seen.add(sym.name)
                v = str(sym.value(frame))
            except Exception:
                continue
            if len(v) > MAX_STR:
                v = v[:MAX_STR] + "…"
            out[sym.name] = {"t": "raw", "v": v}
        try:
            block = block.superblock
        except Exception:
            break
    return out


def _snap():
    fr = _user_frames()
    if not fr:
        return None
    cur = fr[-1]
    stack = [{"func": (f.name() or "?"), "line": _sal_line(f), "locals": _locals(f)} for f in fr]
    return {"event": "line", "line": _sal_line(cur), "func": (cur.name() or "?"),
            "stack": stack, "o": 0}


def _alive():
    try:
        return gdb.selected_thread() is not None
    except Exception:
        return False


def main():
    err = None
    truncated = False
    for cmd in ("set pagination off", "set confirm off", "set height 0", "set width 0",
                "set auto-load safe-path /", "set print pretty off"):
        try:
            gdb.execute(cmd)
        except gdb.error:
            pass
    # Skip standard library sources so `step` never stops inside them.
    for g in ("/usr/*", "*/include/c++/*", "*/bits/*"):
        try:
            gdb.execute("skip -gfi " + g)
        except gdb.error:
            pass
    try:
        gdb.execute("break main")
        gdb.execute("run > prog_out.txt < prog_in.txt")
    except gdb.error as e:
        err = "gdb: " + str(e)

    raw = 0
    while len(steps) < MAX_STEPS and raw < MAX_RAW:
        if not _alive():
            break
        snap = _snap()
        if snap is not None:      # record every stop in user code (loop iterations included)
            steps.append(snap)
        try:
            gdb.execute("step", to_string=True)
        except gdb.error:
            break
        raw += 1
    else:
        truncated = len(steps) >= MAX_STEPS

    prog_out = ""
    try:
        with open("prog_out.txt") as f:
            prog_out = f.read()
    except Exception:
        pass
    with open("trace.json", "w") as f:
        f.write(json.dumps({"ok": True, "lang": "cpp", "steps": steps, "stdout": prog_out,
                            "error": err, "truncated": truncated}))


try:
    main()
except Exception as e:  # never let the tracer take gdb down without a note
    try:
        with open("trace.json", "w") as f:
            f.write(json.dumps({"ok": False, "error": "tracer: " + str(e)}))
    except Exception:
        pass
try:
    gdb.execute("quit")
except Exception:
    pass
