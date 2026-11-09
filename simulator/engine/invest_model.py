"""invest_model.py — the Board's FRB/US with business investment and imports split so an investment shock can be
added without the model working it off. Used only by the Simulator's investment shock (`invest`, `investimp` in
build.py); every other shock runs on the Board's model.xml untouched.

Ported from the data-center study's model file (2026-11-05), which is
also what the data-center Occasional Post's runs use, so the two agree. FRB/US has one business-investment aggregate
(ebfi) and one non-oil import aggregate (emo), each an equation that error-corrects toward a desired level; an add
factor on either is read as a gap to close and is worked off. So each is split:

    ebfi = ebfio + edc      ebfio = the Board's ebfi equation, verbatim, renamed; edc = added investment, exogenous
    emo  = emoo  + emdc     emoo  = the Board's emo equation, verbatim, renamed;  emdc = its imported part, exogenous

Every other equation sees the totals. With edc = emdc = 0 the split model reproduces the Board's baseline exactly.

Two corrections, each behind an exogenous switch (the Simulator sets dcw = 1 and kdcsw = 0, the study's central case):
  dcw    GDP weights. Real final sales (xfs) and the real index behind nominal GDP (xp) add components with FIXED
         estimated weights; a shock that is mostly imported nets two large numbers, and with those weights a dollar of
         75-percent-imported spending adds 14-16 cents to GDP instead of 25. With dcw = 1 each real unit of edc and emdc
         enters at its baseline dollar price relative to nominal final sales, so a dollar adds exactly (1 - import share)
         to final demand on impact.
  kdcsw  Capital. kbfi accumulates ebfio + kdcsw*edc. With 0 the added investment does not raise the capital that sets
         potential output: a demand shock. A payoff in capacity is the Simulator's productivity shock.

    python engine/invest_model.py        # (re)writes the XML; build.py calls ensure() itself
"""
import copy, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
from engine_paths import FED       # the Board's packages (engine_paths.py; FRBUS_FED overrides)
SRC = FED / "pyfrbus" / "models" / "model.xml"
OUT = FED / "model_invest.xml"          # beside the Board's package, outside the repo, like the package itself
SERIES = ("edc", "emdc", "dcw", "kdcsw", "sbfixfs", "semoxfs", "sbfixp")


def _rename_block(var, new, root, ET):
    old = next(v for v in root.findall("variable") if v.findtext("name") == var)
    blk = copy.deepcopy(old)
    blk.find("name").text = new
    blk.find("definition").text = (blk.findtext("definition") or "") + f" -- renamed '{new}': excludes the exogenous added piece"
    eq = blk.find("standard_equation")
    for tag in ("python_equation", "eviews_equation"):
        e = eq.find(tag)
        t = e.text
        t = re.sub(rf"\by_{var}([_(])", rf"y_{new}\1", t)
        t = re.sub(rf"\b{var}_aerr\b", f"{new}_aerr", t)
        t = re.sub(rf"\b{var}\b", new, t)
        e.text = t
    for c in eq.iter("cf_name"):
        c.text = re.sub(rf"^y_{var}\(", f"y_{new}(", c.text)
    for r in eq.findall("rhs_eq_var"):
        if r.text == var:
            r.text = new
    piece = {"ebfi": "edc", "emo": "emdc"}[var]
    for child in list(old):                     # the old block becomes an identity: total = renamed + added piece
        if child.tag not in ("name", "definition", "sector"):
            old.remove(child)
    old.find("definition").text = old.findtext("definition") + f" (= {new} + {piece})"
    et = ET.SubElement(old, "equation_type"); et.text = "Identity"
    old.insert(1, et)
    se = ET.SubElement(old, "standard_equation")
    for tag in ("eviews_equation", "python_equation"):
        ET.SubElement(se, tag).text = f"{var} - {var}_aerr = {new} + {piece}"
    for r in (new, piece):
        ET.SubElement(se, "rhs_eq_var").text = r
    old.addnext(blk)


def _add_exog(name, definition, root, ET):
    v = ET.SubElement(root, "variable")
    ET.SubElement(v, "name").text = name
    ET.SubElement(v, "equation_type").text = "Exogenous"
    ET.SubElement(v, "definition").text = definition
    ET.SubElement(v, "exogenous_projection").text = "2"


def _patch_eq(root, var, old, new):
    v = next(v for v in root.findall("variable") if v.findtext("name") == var)
    se = v.find("standard_equation")
    pe = se.find("python_equation")
    t = re.sub(r"\s+", " ", pe.text)
    o = re.sub(r"\s+", " ", old)
    assert o in t, (var, o, t)
    pe.text = t.replace(o, new)
    se.find("eviews_equation").text = "(python form) " + pe.text


def build(out=OUT):
    from lxml import etree as ET
    tree = ET.parse(str(SRC)); root = tree.getroot()
    _rename_block("ebfi", "ebfio", root, ET)
    _rename_block("emo", "emoo", root, ET)
    _add_exog("edc", "Added business investment, cw 2012$ (exogenous; 0 in the baseline)", root, ET)
    _add_exog("emdc", "Imported part of the added investment, cw 2012$ (exogenous; 0 in the baseline)", root, ET)
    _patch_eq(root, "xfs", "y_xfs_3*log(ebfi/ebfi(-1))",
              "(1-dcw)*y_xfs_3*log(ebfi/ebfi(-1)) + dcw*(y_xfs_3*(ebfio(-1)/ebfi(-1))*log(ebfio/ebfio(-1)) + sbfixfs*(edc-edc(-1)))")
    _patch_eq(root, "xfs", "y_xfs_9*log(emo/emo(-1))",
              "(1-dcw)*y_xfs_9*log(emo/emo(-1)) + dcw*(y_xfs_9*(emoo(-1)/emo(-1))*log(emoo/emoo(-1)) - semoxfs*(emdc-emdc(-1)))")
    _patch_eq(root, "xp", "(y_xp_3)*log(ebfi/ebfi(-1))",
              "(1-dcw)*(y_xp_3)*log(ebfi/ebfi(-1)) + dcw*((y_xp_3)*(ebfio(-1)/ebfi(-1))*log(ebfio/ebfio(-1)) + sbfixp*(edc-edc(-1)))")
    _patch_eq(root, "kbfi", "(pbfir/pkbfir)*ebfi/4", "(pbfir/pkbfir)*(ebfio + kdcsw*edc)/4")
    for n, d in [("dcw", "Switch: the added pieces enter GDP at current nominal shares (1) or the Board's fixed weights (0)"),
                 ("kdcsw", "Switch: the added investment counts in the business capital stock (1) or not (0)"),
                 ("sbfixfs", "Baseline price of a real unit of BFI over nominal final sales, 0.01*pbfir*pxp/xfsn"),
                 ("semoxfs", "Baseline price of a real unit of non-oil imports over nominal final sales, 0.01*pmo/xfsn"),
                 ("sbfixp", "Baseline price of a real unit of BFI over nominal XP, 0.01*pbfir*pxp/xpn")]:
        _add_exog(n, d, root, ET)
    tmp = Path(str(out) + f".tmp{os.getpid()}")
    tree.write(str(tmp), xml_declaration=True, encoding="UTF-8")
    os.replace(tmp, out)                        # atomic: parallel workers never read a half-written file
    return out


def ensure():
    """The split model's path, (re)built when missing or older than the Board's model.xml or this file."""
    if not OUT.exists() or OUT.stat().st_mtime < max(SRC.stat().st_mtime, Path(__file__).stat().st_mtime):
        build()
    return str(OUT)


def add_series(d):
    """The series the split model needs, added to a copy of the Board's data (zero shock, corrected weights, the added
    investment kept out of capital)."""
    d = d.copy()
    d["ebfio"] = d["ebfi"]; d["emoo"] = d["emo"]
    d["edc"] = 0.0; d["emdc"] = 0.0; d["kdcsw"] = 0.0; d["dcw"] = 1.0
    xfsn = d["xgdpn"] - d["ein"]
    d["sbfixfs"] = 0.01 * d["pbfir"] * d["pxp"] / xfsn
    d["semoxfs"] = 0.01 * d["pmo"] / xfsn
    d["sbfixp"] = 0.01 * d["pbfir"] * d["pxp"] / d["xpn"]
    return d


if __name__ == "__main__":
    print("wrote", build())
