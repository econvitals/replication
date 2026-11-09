"""model_setup.py: build output/model/model_dc.xml, the Board's FRB/US with data-center investment and imports carried as
separate exogenous pieces, so the model's own equations keep deciding everything else.

FRB/US has one business-investment aggregate (ebfi) and one non-oil import aggregate (emo), each a growth-rate
equation that error-corrects toward a desired level. An add factor on either is read by the model as a gap to
close, and is worked off over time. So this file splits each:

    ebfi = ebfio + edc      ebfio = "other BFI": the Board's ebfi equation, verbatim, renamed
                            edc   = data-center investment, exogenous, 2012$ (zero in the baseline)
    emo  = emoo  + emdc     emoo  = "other non-oil imports": the Board's emo equation, verbatim, renamed
                            emdc  = data-center imports, exogenous, 2012$ (zero in the baseline)

Every other equation that uses ebfi or emo (the capital stock, nominal investment, final sales, GDP, the import
identity, the current account) sees the totals. Because edc = emdc = 0 in the baseline, ebfio = ebfi and emoo = emo
there, so the renamed equations reproduce the Board's baseline exactly.

Two reporting identities are added for targeting with mcontrol:  nxgdp = 100*(exn-emn)/xgdpn,  cagdp = 100*fcbn/xgdpn.
"""
import copy, re
from lxml import etree as ET

from . import paths

SRC = paths.FED_MODEL_XML

def rename_block(var, new, root):
    old = next(v for v in root.findall("variable") if v.findtext("name") == var)
    blk = copy.deepcopy(old)
    blk.find("name").text = new
    blk.find("definition").text = (blk.findtext("definition") or "") + f" -- renamed '{new}': excludes the exogenous data-center piece"
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
        if r.text == var: r.text = new
    # the old block becomes an identity: total = renamed + exogenous piece
    piece = {"ebfi": "edc", "emo": "emdc"}[var]
    for child in list(old):
        if child.tag not in ("name", "definition", "sector"): old.remove(child)
    old.find("definition").text = old.findtext("definition") + f" (= {new} + {piece})"
    et = ET.SubElement(old, "equation_type"); et.text = "Identity"
    old.insert(1, et)
    se = ET.SubElement(old, "standard_equation")
    pe = ET.SubElement(se, "eviews_equation"); pe.text = f"{var} - {var}_aerr = {new} + {piece}"
    pe = ET.SubElement(se, "python_equation"); pe.text = f"{var} - {var}_aerr = {new} + {piece}"
    for r in (new, piece):
        x = ET.SubElement(se, "rhs_eq_var"); x.text = r
    old.addnext(blk)

def add_exog(name, definition, root):
    v = ET.SubElement(root, "variable")
    ET.SubElement(v, "name").text = name
    ET.SubElement(v, "equation_type").text = "Exogenous"
    ET.SubElement(v, "definition").text = definition
    ET.SubElement(v, "exogenous_projection").text = "2"

def add_identity(name, definition, eq, rhs, root):
    v = ET.SubElement(root, "variable")
    ET.SubElement(v, "name").text = name
    ET.SubElement(v, "equation_type").text = "Identity"
    ET.SubElement(v, "definition").text = definition
    se = ET.SubElement(v, "standard_equation")
    ET.SubElement(se, "eviews_equation").text = eq
    ET.SubElement(se, "python_equation").text = eq
    for r in rhs: ET.SubElement(se, "rhs_eq_var").text = r


def patch_eq(root, var, old, new):
    v = next(v for v in root.findall("variable") if v.findtext("name") == var)
    se = v.find("standard_equation")
    pe = se.find("python_equation")
    t = re.sub(r"\s+", " ", pe.text)
    o = re.sub(r"\s+", " ", old)
    assert o in t, (var, o, t)
    pe.text = t.replace(o, new)
    ev = se.find("eviews_equation"); ev.text = "(python form) " + pe.text
    return pe.text

def weights_and_capital(root):
    """Two corrections, each behind an exogenous switch (1 = on):

    dcw   GDP weights. Real final sales (xfs) and the real index behind nominal GDP (xp) add up their components with
          FIXED estimated weights (0.132 for BFI and -0.140 for non-oil imports in xfs, 0.118 for BFI in xp). Against
          2026 nominal shares (0.141, 0.134, 0.133) those are close, but a shock that is 75 percent imported nets
          two large numbers: with the fixed weights a dollar of data-center spending adds 14-16 cents to GDP instead
          of 25. With dcw = 1 each real unit of the data-center pieces enters at its baseline dollar price relative
          to nominal final sales (series sbfixfs, semoxfs, sbfixp) -- the chain-weight contribution at current
          shares -- so a dollar of spending adds exactly (1 - import content) to GDP on impact;
          every other component keeps the Board's weights. With dcw = 0 the Board's own terms are used unchanged.
    kdcsw Capital. kbfi accumulates ebfio + kdcsw*edc. kdcsw = 0 (the default here) keeps data-center equipment out of
          the capital services that set potential output, so the experiment is a pure demand shock; kdcsw = 1 counts it
          like any other business capital (the Board's 9.2 percent depreciation, capital share 0.275).
    """
    patch_eq(root, "xfs", "y_xfs_3*log(ebfi/ebfi(-1))",
             "(1-dcw)*y_xfs_3*log(ebfi/ebfi(-1)) + dcw*(y_xfs_3*(ebfio(-1)/ebfi(-1))*log(ebfio/ebfio(-1)) + sbfixfs*(edc-edc(-1)))")
    patch_eq(root, "xfs", "y_xfs_9*log(emo/emo(-1))",
             "(1-dcw)*y_xfs_9*log(emo/emo(-1)) + dcw*(y_xfs_9*(emoo(-1)/emo(-1))*log(emoo/emoo(-1)) - semoxfs*(emdc-emdc(-1)))")
    patch_eq(root, "xp", "(y_xp_3)*log(ebfi/ebfi(-1))",
             "(1-dcw)*(y_xp_3)*log(ebfi/ebfi(-1)) + dcw*((y_xp_3)*(ebfio(-1)/ebfi(-1))*log(ebfio/ebfio(-1)) + sbfixp*(edc-edc(-1)))")
    patch_eq(root, "kbfi", "(pbfir/pkbfir)*ebfi/4", "(pbfir/pkbfir)*(ebfio + kdcsw*edc)/4")
    for n, d in [("dcw", "Switch: data-center pieces enter GDP with current nominal shares (1) or the Board's fixed weights (0)"),
                 ("kdcsw", "Switch: data-center equipment counts in the business capital stock (1) or not (0)"),
                 ("sbfixfs", "Baseline price of a real unit of BFI over nominal final sales, 0.01*pbfir*pxp/xfsn"),
                 ("semoxfs", "Baseline price of a real unit of non-oil imports over nominal final sales, 0.01*pmo/xfsn"),
                 ("sbfixp", "Baseline price of a real unit of BFI over nominal XP, 0.01*pbfir*pxp/xpn")]:
        add_exog(n, d, root)

def build(out):
    tree = ET.parse(str(SRC)); root = tree.getroot()
    rename_block("ebfi", "ebfio", root)
    rename_block("emo", "emoo", root)
    add_exog("edc", "Data-center business investment, cw 2012$ (exogenous add-on; 0 in baseline)", root)
    add_exog("emdc", "Data-center non-oil imports, cw 2012$ (exogenous add-on; 0 in baseline)", root)
    add_identity("nxgdp", "Net exports of goods and services, percent of nominal GDP",
                 "nxgdp - nxgdp_aerr = 100*(exn - emn)/xgdpn", ["exn", "emn", "xgdpn"], root)
    add_identity("cagdp", "Current account balance, percent of nominal GDP",
                 "cagdp - cagdp_aerr = 100*fcbn/xgdpn", ["fcbn", "xgdpn"], root)
    weights_and_capital(root)
    tree.write(str(out), xml_declaration=True, encoding="UTF-8")

def main():
    paths.ensure()
    build(paths.DC_MODEL_XML)
    print("model: wrote", paths.DC_MODEL_XML.relative_to(paths.ROOT) if paths.DC_MODEL_XML.is_relative_to(paths.ROOT) else paths.DC_MODEL_XML)


if __name__ == "__main__":
    main()
