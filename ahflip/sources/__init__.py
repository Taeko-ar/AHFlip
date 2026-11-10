"""Where price snapshots come from. Each source turns its data into {item: (min, qty)} and calls
prices.store(..., src=<name>). Add a new source as a new module here."""
