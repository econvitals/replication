"""Econvitals' Current-Quarter GDP Estimate: the engine that makes the estimate econvitals.org shows.

model.py is the place to start (`Engine().nowcast(quarter)`); components.py turns each monthly source
into its quarter's indicator, bridge.py maps the indicators to what BEA prints, sources.py, eits.py,
calendar.py and vintages.py read the data, and public_doors.py says where each comes from.
"""
