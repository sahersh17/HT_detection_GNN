# Reassessment of the 29 original intervals

Rows are matched to the six-family results before interpreting the expanded cohort. An interval wholly beyond the practical band is evidence of a substantial directional signature. A point estimate beyond the band with an overlapping interval is a candidate signature. An in-band estimate with an interval that crosses a margin is still precision-limited. Small directional effects can coexist with practical equivalence.

| Domain | Arm | Control | Six-family mean | Expanded mean | Expanded 95% interval | Interpretation | Excludes 0.5 |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| class | clean | characters | 0.500 | 0.623 | [0.5342, 0.7123] | Precision-limited | Yes |
| class | clean | comment_fraction | 0.500 | 0.384 | [0.2945, 0.4726] | Precision-limited | Yes |
| class | clean | normalized_tokens | 0.583 | 0.623 | [0.5753, 0.6712] | Passes practical equivalence | Yes |
| class | clean | normalized_characters | 0.500 | 0.623 | [0.5342, 0.7123] | Precision-limited | Yes |
| class | clean | cells | 0.583 | 0.630 | [0.5274, 0.7260] | Precision-limited | Yes |
| class | clean | edges | 0.417 | 0.596 | [0.4932, 0.6918] | Passes practical equivalence | No |
| class | benign | characters | 0.417 | 0.541 | [0.5000, 0.5822] | Passes practical equivalence | No |
| class | benign | comment_fraction | 0.583 | 0.459 | [0.4178, 0.5000] | Passes practical equivalence | No |
| class | benign | normalized_tokens | 0.500 | 0.500 | [0.4795, 0.5205] | Passes practical equivalence | No |
| class | benign | normalized_characters | 0.417 | 0.541 | [0.5000, 0.5822] | Passes practical equivalence | No |
| class | benign | cells | 0.583 | 0.637 | [0.5479, 0.7260] | Precision-limited | Yes |
| class | benign | edges | 0.500 | 0.637 | [0.5479, 0.7260] | Precision-limited | Yes |
| origin | clean | characters | 0.500 | 0.384 | [0.3322, 0.4349] | Passes practical equivalence | Yes |
| origin | clean | lines | 0.500 | 0.288 | [0.2226, 0.3562] | Candidate signature; margin overlaps | Yes |
| origin | clean | windows | 0.521 | 0.367 | [0.3151, 0.4199] | Passes practical equivalence | Yes |
| origin | clean | comment_fraction | 0.500 | 0.423 | [0.3904, 0.4555] | Passes practical equivalence | Yes |
| origin | clean | normalized_windows | 0.458 | 0.378 | [0.3373, 0.4212] | Passes practical equivalence | Yes |
| origin | benign | characters | 0.500 | 0.387 | [0.3356, 0.4384] | Passes practical equivalence | Yes |
| origin | benign | lines | 0.500 | 0.288 | [0.2226, 0.3562] | Candidate signature; margin overlaps | Yes |
| origin | benign | windows | 0.521 | 0.367 | [0.3151, 0.4199] | Passes practical equivalence | Yes |
| origin | benign | comment_fraction | 0.500 | 0.423 | [0.3904, 0.4555] | Passes practical equivalence | Yes |
| origin | benign | normalized_windows | 0.458 | 0.382 | [0.3408, 0.4247] | Passes practical equivalence | Yes |
| origin | trojan | characters | 0.500 | 0.366 | [0.3165, 0.4160] | Passes practical equivalence | Yes |
| origin | trojan | lines | 0.480 | 0.264 | [0.2010, 0.3301] | Candidate signature; margin overlaps | Yes |
| origin | trojan | windows | 0.499 | 0.350 | [0.2999, 0.4025] | Precision-limited | Yes |
| origin | trojan | comment_fraction | 0.493 | 0.389 | [0.3570, 0.4230] | Passes practical equivalence | Yes |
| origin | trojan | normalized_tokens | 0.470 | 0.393 | [0.3427, 0.4448] | Passes practical equivalence | Yes |
| origin | trojan | normalized_characters | 0.431 | 0.370 | [0.3202, 0.4217] | Passes practical equivalence | Yes |
| origin | trojan | normalized_windows | 0.438 | 0.347 | [0.3014, 0.3950] | Passes practical equivalence | Yes |
