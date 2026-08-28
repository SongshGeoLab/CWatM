#!/usr/bin/env python3
"""Verify every lab patch survived the last upstream merge.

Run after `git merge upstream/develop`, before `--ff-only` into lab/main.
A merge can resolve cleanly and still drop a patch, so this is not optional.
The 2026-08 re-baseline proved the point: soil.py and water_demand.py merged
"cleanly" while irrigation.py and inflow.py conflicted -- a clean merge tells
you nothing about whether the patch survived.

    python3 tools/check_lab_patches.py

Exit 0 = all patches intact. Exit 1 = at least one is missing or altered.

The strongest check is the DEVIATION SURFACE: `git diff upstream/develop --
cwatm/` must touch exactly the four patched files and nothing else. That
catches what the per-patch patterns below cannot -- an accidental edit, a
half-resolved merge hunk, a stray upstream file left behind. It needs the
`upstream` remote fetched, and is skipped with a warning if it is not.

The per-patch patterns are deliberately not a grep: soil.py contains the same crop-group expression twice
(the irrigated branch, which is ours, and upstream's own non-irrigated branch),
and irrigation.py writes `( 5 -` with a space that a naive pattern misses.
Checks are whitespace-insensitive and scoped to the right branch.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def active_lines(text: str) -> list[str]:
    """Source lines with comments and blanks stripped out."""
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            out.append(line)
    return out


def squash(s: str) -> str:
    """Collapse all whitespace so spacing changes never cause a false alarm."""
    return re.sub(r"\s+", "", s)


IRRIGATION = "cwatm/hydrological_modules/water_demand/irrigation.py"
SOIL = "cwatm/hydrological_modules/soil.py"
WATER_DEMAND = "cwatm/hydrological_modules/water_demand/water_demand.py"
DATA_HANDLING = "cwatm/management_modules/data_handling.py"
INFLOW = "cwatm/hydrological_modules/inflow.py"

# The exact set of files this fork may differ from upstream/develop in.
UPSTREAM_REF = "upstream/develop"
EXPECTED_DEVIATION = {IRRIGATION, SOIL, WATER_DEMAND, INFLOW}

CROP_GROUP_TERM = squash("- 0.10 * (5 - self.var.cropGroupNumber)")
FIXED_TERM = squash("- 0.4")

results: list[tuple[bool, str, str]] = []


def check(ok: bool, patch: str, msg: str) -> None:
    results.append((ok, patch, msg))


# --- fail fast on an unresolved merge ------------------------------------
# Every check below assumes one active version of each line. A file still
# carrying conflict markers has two, which would produce a confusing failure.
_conflicted = [
    rel
    for rel in (
        "cwatm/hydrological_modules/water_demand/irrigation.py",
        "cwatm/hydrological_modules/soil.py",
        "cwatm/hydrological_modules/water_demand/water_demand.py",
        "cwatm/management_modules/data_handling.py",
        "cwatm/hydrological_modules/inflow.py",
    )
    if re.search(r"^<{7} ", (ROOT / rel).read_text(encoding="utf-8"), re.MULTILINE)
]
if _conflicted:
    print("Unresolved merge conflicts -- resolve these first, then re-run:")
    for rel in _conflicted:
        print(f"  {rel}")
    sys.exit(1)


# --- deviation surface ----------------------------------------------------
# The strongest check there is: our tree may differ from upstream/develop in
# exactly four files under cwatm/, and no others. Anything else -- an editor
# stray, a half-resolved merge hunk, an upstream file we forgot to take -- is
# caught here even when every pattern below still matches.

_diff = subprocess.run(
    ["git", "diff", "--name-only", UPSTREAM_REF, "--", "cwatm/"],
    cwd=ROOT, capture_output=True, text=True,
)
if _diff.returncode != 0:
    print(
        f"WARN  surface  cannot compare against {UPSTREAM_REF}"
        f" ({_diff.stderr.strip().splitlines()[-1] if _diff.stderr.strip() else 'unknown error'})."
        "\n                Run `git fetch upstream` to enable the strongest check."
    )
else:
    actual = {ln for ln in _diff.stdout.split() if ln}
    extra = sorted(actual - EXPECTED_DEVIATION)
    missing = sorted(EXPECTED_DEVIATION - actual)
    detail = ""
    if extra:
        detail += f" unexpected: {extra}"
    if missing:
        detail += f" no longer deviating (patch dropped?): {missing}"
    check(
        not extra and not missing,
        "surface",
        f"cwatm/ must differ from {UPSTREAM_REF} in exactly the four patched"
        f" files.{detail}",
    )


# --- P1: cropGroupNumber-based depletion fraction -------------------------

irr = read(IRRIGATION)

check(
    bool(re.search(r"self\.var\.cropGroupNumber\s*=\s*loadmap\(\s*['\"]cropgroupnumber['\"]\s*\)", irr)),
    "P1",
    f"{IRRIGATION}: initial() must load 'cropgroupnumber'",
)

irr_p = [ln for ln in active_lines(irr) if re.match(r"\s*p\s*=\s*1\s*/\s*\(\s*0\.76", ln)]
check(
    len(irr_p) == 1 and CROP_GROUP_TERM in squash(irr_p[0]),
    "P1",
    f"{IRRIGATION}: the active p formula must use cropGroupNumber, not the fixed -0.4"
    + (f" (found: {irr_p[0].strip()!r})" if irr_p else " (no p formula found)"),
)

# soil.py: only the IRRIGATED branch is ours. Upstream's non-irrigated branch
# uses the same expression, so scope the check to the if-block.
soil = read(SOIL)
# Anchor on the combined irrPaddy-or-irrNonPaddy test: soil.py has an earlier
# `if coverType == 'irrPaddy':` block (paddy flooding) with no p formula in it.
m = re.search(
    r"if\s+coverType\s*==\s*['\"]irrPaddy['\"]\s+or\s+coverType\s*==\s*['\"]irrNonPaddy['\"]\s*:\n"
    r"(?P<body>.*?)\n\s*else:",
    soil,
    re.DOTALL,
)
if m is None:
    check(False, "P1", f"{SOIL}: could not locate the irrPaddy/irrNonPaddy branch")
else:
    soil_p = [ln for ln in active_lines(m.group("body")) if re.match(r"\s*p\s*=\s*1\s*/\s*\(\s*0\.76", ln)]
    check(
        len(soil_p) == 1 and CROP_GROUP_TERM in squash(soil_p[0]),
        "P1",
        f"{SOIL}: the irrigated branch's p formula must use cropGroupNumber"
        + (f" (found: {soil_p[0].strip()!r})" if soil_p else " (no p formula in that branch)"),
    )

# P1 second term: must be the general Van Diepen form, not the n_cg = 1
# special case `/ 4`. The two terms have to move together -- a crop-group first
# term with a hardcoded second term is the inconsistency P1 originally shipped.
GENERAL_TERM = squash("(self.var.cropGroupNumber * (self.var.cropGroupNumber + 3))")

for label, text, scope in (
    (IRRIGATION, irr, irr),
    (SOIL, soil, m.group("body") if m else ""),
):
    second = [ln for ln in active_lines(scope) if "etpotMax - 0.6" in ln or "(etpotMax-0.6)" in squash(ln)]
    joined = squash(" ".join(second))
    check(
        bool(second) and GENERAL_TERM in joined and "0.6)/4" not in joined,
        "P1",
        f"{label}: the p correction term must use the general Van Diepen denominator"
        " n_cg*(n_cg+3), not the hardcoded / 4"
        + (f" (found: {[x.strip() for x in second]})" if second else " (term not found)"),
    )


# --- P2: swAbstractionFrac array guard -----------------------------------

wd = read(WATER_DEMAND)
wd_cmp = [ln for ln in active_lines(wd) if re.search(r"swAbstractionFraction\b.*<\s*0", ln)]
check(
    len(wd_cmp) == 1 and "np.min(np.asarray(" in wd_cmp[0],
    "P2",
    f"{WATER_DEMAND}: swAbstractionFrac must be reduced with np.min(np.asarray(...))"
    " before the '< 0' comparison. A bare comparison raises ValueError when the"
    " setting points at a map; isinstance(x, float) misses np.float32"
    + (f" (found: {[x.strip() for x in wd_cmp]})" if wd_cmp else " (comparison not found)"),
)

# --- P3: dropped at the 2026-08 re-baseline -------------------------------
# Upstream now filters _FillValue at the source, where metadataNCDF is built
# (data_handling.py:869, a dict comprehension), so our writenetcdf-side guard
# is redundant and no longer applied. What is worth checking is that upstream
# does not REGRESS that fix -- without it, writing netCDF crashes on any input
# that carries the attribute.

dh = read(DATA_HANDLING)
check(
    bool(re.search(r"metadataNCDF\[var\]\s*=\s*\{.*_FillValue", dh)),
    "P3",
    f"{DATA_HANDLING}: upstream must still filter _FillValue when building"
    " metadataNCDF. If that fix is gone, re-apply the old lab-side guard"
    " (see LAB_CHANGES.md P3)",
)


# --- P4: inflow utf-8 BOM hint --------------------------------------------

inf = read(INFLOW)
check(
    "utf-8 BOM" in inf,
    "P4",
    f"{INFLOW}: the Error 218 message must keep the utf-8 BOM hint",
)


# --- CP1: satAreaFrac / arnoBeta -----------------------------------------

# Only the assignment itself. `potInf = store - store * (1 - (1 - satAreaFrac)
# ** potBeta)` also mentions satAreaFrac and ** and must not be picked up.
sat = [ln for ln in active_lines(irr) if re.match(r"\s*satAreaFrac\s*=", ln) and "arnoBeta" in ln]
check(
    len(sat) == 1 and squash(sat[0]).startswith(squash("satAreaFrac = 1 - np.maximum(")),
    "CP1",
    f"{IRRIGATION}: satAreaFrac must be '1 - np.maximum((1 - relSat), 0) ** arnoBeta'."
    " The form 'np.maximum(1 - (1 - relSat), 0) ** arnoBeta' collapses potInf and"
    " silently clamps non-paddy irrigation to zero"
    + (f" (found: {sat[0].strip()!r})" if sat else " (not found)"),
)


# --- report ---------------------------------------------------------------

failed = [r for r in results if not r[0]]
for ok, patch, msg in results:
    print(f"{'PASS' if ok else 'FAIL'}  {patch:4}  {msg if not ok else msg.split(':')[0]}")

if failed:
    print(f"\n{len(failed)} of {len(results)} checks FAILED -- do not fast-forward lab/main.")
    sys.exit(1)

print(f"\nAll {len(results)} checks passed.")
