# Release notes — v0.5.0

## Hayes PROCESS model 4 support

This release keeps all existing SPSS Studio MCP tools and adds one public MCP
tool: `spss_process`.

### Added

- Local Hayes PROCESS macro discovery through the trusted
  `SPSS_PROCESS_MACRO_PATH` setting or common SPSS installation locations.
- PROCESS model 4 mediation with one mediator or multiple parallel mediators.
- Bootstrap confidence intervals, covariates, total/direct/indirect effects,
  pairwise indirect-effect contrasts, effect sizes, standardized coefficients,
  and reproducible seeds.
- PROCESS availability and version reporting in `spss_check_status`.
- Parameter validation and tests for PROCESS syntax generation and secure macro
  loading.

### Runtime integration

The persistent SPSS engine can now load a trusted macro prelude separately and
preserve physical syntax line boundaries. General-purpose `INSERT FILE` remains
blocked; tool callers cannot supply an arbitrary macro path.

### Third-party dependency

PROCESS is not distributed with this project. Users must obtain `process.sps`
from the [official Andrew F. Hayes website](https://www.afhayes.com/download.html)
and comply with its copyright and usage terms. The optional SPSS graphical
dialog is not required.

### Compatibility

- Package version: `0.5.0`
- Python: 3.10+
- Platform: macOS
- Locally integration-tested with IBM SPSS Statistics 27 and PROCESS 3.3
- Existing non-PROCESS tools remain backward compatible
