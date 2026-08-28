#!/usr/bin/env python3
"""Verify every lab patch survived the last upstream merge.

Run after `git merge upstream/develop`, before `--ff-only` into lab/main.
A merge can resolve cleanly and still drop a patch, so this is not optional.

    python3 tools/check_lab_patches.py

Exit 0 = all patches intact. Exit 1 = at least one is missing or altered.

Deliberately not a grep: soil.py contains the same crop-group expression twice
(the irrigated branch, which is ours, and upstream's own non-irrigated branch),
and irrigation.py writes `( 5 -` with a space that a naive pattern misses.
Checks are whitespace-insensitive and scoped to the right branch.
"""

from __future__ import annotations

import re
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


# --- P1: WITHDRAWN -------------------------------------------------------
# The cropGroupNumber depletion-fraction change was reverted (option B): the
# first term was crop-group dependent while the second stayed hardcoded to the
# n_cg = 1 special case, and the two could not be reconciled without adopting
# the general Van Diepen form. Both files now match upstream. See LAB_CHANGES.md.
irr = read(IRRIGATION)

# --- P2: swAbstractionFrac array guard -----------------------------------

wd = read(WATER_DEMAND)
check(
    "min_swAbstractionFraction" in wd or bool(re.search(r"np\.min\(.*swAbstractionFraction", wd)),
    "P2",
    f"{WATER_DEMAND}: swAbstractionFrac must be reduced to a scalar before '< 0'",
)

# --- P3: _FillValue guard (drop this check when the patch is dropped) ----

dh = read(DATA_HANDLING)
check(
    dh.count("if i != '_FillValue':") >= 2,
    "P3",
    f"{DATA_HANDLING}: lon/lat attribute loops must skip _FillValue"
    " -- if upstream now filters it in metadataNCDF, drop P3 and this check",
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
