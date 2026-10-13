"""Real-world (SEC EDGAR XBRL) evaluation: authoritative ground truth for
measuring whether the adapter generalizes beyond the synthetic template.

Ground truth comes from the SEC XBRL `companyconcept` API (public-domain US
government data): exact reported values, units, and periods tied to real
filings (form + accession). No model-generated answers are used as ground
truth, and no figures are typed from memory."""
