# Six-family interval review and precision plan

The failed margins consist of 12 class comparisons and 17 source-origin comparisons. All 29 means lie inside [0.30, 0.70] and all 29 intervals include 0.5. Twelve point estimates equal chance to numerical precision. The remaining 17 lean in one direction but are compatible with chance. The data cannot attribute the dispersion solely to small sample size or establish absence of shortcuts. Several measurements reuse the same host rankings. They are pointwise, correlated diagnostics.

The planning sample size is the ceiling of (1.96 s / d) squared. Here s is the sample standard deviation across six host scores and d is the smaller distance from the observed mean to the two equivalence limits. The largest plug-in estimate is 69 total families (63 additional), driven by cell counts against either negative and edge counts against the original. If the true means are all 0.5 with the same observed dispersions, the maximum is 24 total (18 additional). These are expected pointwise widths; they do not give 95% probability of admission or simultaneous coverage. When a true mean lies outside the band no amount of added precision alone will establish equivalence.

| Domain | Comparator or arm | Control | Estimate | 95% host interval | Pilot classification | Plug-in total families |
| --- | --- | --- | ---: | --- | --- | ---: |
| class | clean | characters | 0.500 | [0.250, 0.750] | centered at chance | 10 |
| class | clean | comment_fraction | 0.500 | [0.250, 0.750] | centered at chance | 10 |
| class | clean | normalized_tokens | 0.583 | [0.500, 0.750] | directional estimate, unresolved | 12 |
| class | clean | normalized_characters | 0.500 | [0.250, 0.750] | centered at chance | 10 |
| class | clean | cells | 0.583 | [0.250, 0.917] | directional estimate, unresolved | 69 |
| class | clean | edges | 0.417 | [0.083, 0.750] | directional estimate, unresolved | 69 |
| class | benign | characters | 0.417 | [0.167, 0.667] | directional estimate, unresolved | 40 |
| class | benign | comment_fraction | 0.583 | [0.333, 0.833] | directional estimate, unresolved | 40 |
| class | benign | normalized_tokens | 0.500 | [0.250, 0.750] | centered at chance | 10 |
| class | benign | normalized_characters | 0.417 | [0.167, 0.667] | directional estimate, unresolved | 40 |
| class | benign | cells | 0.583 | [0.250, 0.917] | directional estimate, unresolved | 69 |
| class | benign | edges | 0.500 | [0.167, 0.833] | centered at chance | 20 |
| origin | clean | characters | 0.500 | [0.250, 0.708] | centered at chance | 10 |
| origin | clean | lines | 0.500 | [0.250, 0.708] | centered at chance | 10 |
| origin | clean | windows | 0.521 | [0.312, 0.708] | directional estimate, unresolved | 10 |
| origin | clean | comment_fraction | 0.500 | [0.333, 0.708] | centered at chance | 8 |
| origin | clean | normalized_windows | 0.458 | [0.292, 0.625] | directional estimate, unresolved | 10 |
| origin | benign | characters | 0.500 | [0.250, 0.708] | centered at chance | 10 |
| origin | benign | lines | 0.500 | [0.250, 0.708] | centered at chance | 10 |
| origin | benign | windows | 0.521 | [0.312, 0.708] | directional estimate, unresolved | 10 |
| origin | benign | comment_fraction | 0.500 | [0.333, 0.708] | centered at chance | 8 |
| origin | benign | normalized_windows | 0.458 | [0.292, 0.625] | directional estimate, unresolved | 10 |
| origin | trojan | characters | 0.500 | [0.250, 0.708] | centered at chance | 10 |
| origin | trojan | lines | 0.480 | [0.230, 0.689] | directional estimate, unresolved | 13 |
| origin | trojan | windows | 0.499 | [0.290, 0.686] | directional estimate, unresolved | 8 |
| origin | trojan | comment_fraction | 0.493 | [0.326, 0.708] | directional estimate, unresolved | 8 |
| origin | trojan | normalized_tokens | 0.470 | [0.292, 0.656] | directional estimate, unresolved | 10 |
| origin | trojan | normalized_characters | 0.431 | [0.208, 0.640] | directional estimate, unresolved | 22 |
| origin | trojan | normalized_windows | 0.438 | [0.250, 0.625] | directional estimate, unresolved | 15 |
