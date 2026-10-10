import os
TRELLIS_DIR = os.path.expanduser("~/miniconda3/TRELLIS.2")
"""Add an 'sdpa' backend to TRELLIS.2's sparse attention (no flash_attn/xformers needed).
Uses flexible matching - works regardless of exact indentation/formatting."""

# --- 1. Patch trellis2/modules/sparse/attention/full_attn.py ---
p1 = TRELLIS_DIR + "/trellis2/modules/sparse/attention/full_attn.py"
lines = open(p1).read().split("\n")

if any("config.ATTN == 'sdpa'" in l for l in lines):
    print("full_attn.py already patched, skipping")
else:
    # Find the "else: raise ValueError(Unknown attention module...)" line
    idx = None
    for i, l in enumerate(lines):
        if "Unknown attention module" in l and "raise ValueError" in l:
            idx = i
            break
    assert idx is not None, "could not find the backend-dispatch else clause"
    indent = lines[idx][: len(lines[idx]) - len(lines[idx].lstrip())]
    print(f"found dispatch else at line {idx+1}: {lines[idx].strip()!r}")

    branch = [
        f"{indent}elif config.ATTN == 'sdpa':",
        f"{indent}    from torch.nn.functional import scaled_dot_product_attention as _sdpa",
        f"{indent}    if num_all_args == 1: q, k, v = qkv.unbind(dim=1)",
        f"{indent}    elif num_all_args == 2: k, v = kv.unbind(dim=1)",
        f"{indent}    # SDPA fallback: standard attention per batch element (no flash_attn/xformers).",
        f"{indent}    # q: [T_q, H, C], k/v: [T_kv, H, C]; q_seqlen/kv_seqlen = per-element lengths.",
        f"{indent}    _q_splits = torch.split(q, q_seqlen, dim=0)",
        f"{indent}    _k_splits = torch.split(k, kv_seqlen, dim=0)",
        f"{indent}    _v_splits = torch.split(v, kv_seqlen, dim=0)",
        f"{indent}    _outs = []",
        f"{indent}    for _qi, _ki, _vi in zip(_q_splits, _k_splits, _v_splits):",
        f"{indent}        _o = _sdpa(_qi.transpose(0, 1).unsqueeze(0),",
        f"{indent}                   _ki.transpose(0, 1).unsqueeze(0),",
        f"{indent}                   _vi.transpose(0, 1).unsqueeze(0))",
        f"{indent}        _outs.append(_o.squeeze(0).transpose(0, 1))",
        f"{indent}    out = torch.cat(_outs, dim=0)  # [T_q, H, C]",
    ]
    lines[idx:idx] = branch
    open(p1, "w").write("\n".join(lines))
    print("patched full_attn.py")

# --- 2. Patch trellis2/modules/sparse/config.py to accept 'sdpa' ---
p2 = TRELLIS_DIR + "/trellis2/modules/sparse/config.py"
src = open(p2).read()
if "'sdpa'" in src:
    print("config.py already patched, skipping")
else:
    # Find the allowed-backends list and add 'sdpa'
    import re
    m = re.search(r"env_sparse_attn_backend in \[([^\]]*)\]", src)
    assert m, "could not find backend allow-list in config.py"
    print(f"found allow-list: [{m.group(1)}]")
    assert "flash_attn_3" in m.group(1), "unexpected allow-list contents"
    src = src[: m.start(1)] + m.group(1).rstrip() + ", 'sdpa'" + src[m.end(1):]
    open(p2, "w").write(src)
    print("patched config.py")

print("OK - ATTN_BACKEND=sdpa now covers dense AND sparse attention")
