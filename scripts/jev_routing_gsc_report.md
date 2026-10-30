# Jev routing shadow run: GSC queries -> ShutterMath pages

Wall clock: 2026-09-19. Model jev-1.13.0. Harness: scripts/jev_routing_gsc.py,
scoring: scripts/jev_route_analysis.py, evidence: scripts/jev_route_spotcheck.py.

## Method

- Input: every query+page row Google Search Console returns for sc-domain:shuttermath.com
  over the property's whole life (2026-08-05 to 2026-09-16), 501 rows, 458 distinct queries.
  Branded queries dropped; queries whose only serving page is the homepage dropped (13,
  ambiguous owner). 445 scored.
- Label: the page Google itself attributes the query to. External to both methods.
- Ballot: all 98 real pages, title plus meta description. 0 labels off-ballot.
- Baselines: share of query words found in (path+title) and in (path+title+description).
  The stronger one is quoted.

## Result

| set | n | jev top-1 | baseline path+title | baseline +description | jev top-3 | |
| --- | --- | --- | --- | --- | --- | --- |
| all scored queries | 445 | 373 (83.8%) | 270 (60.7%) | 183 (41.1%) | 417 (93.7%) |  |
| queries with >=2 impressions | 212 | 183 (86.3%) | 130 (61.3%) | 84 (39.6%) | 199 (93.9%) |  |
| queries with >=5 impressions | 54 | 52 (96.3%) | 36 (66.7%) | 22 (40.7%) | 53 (98.1%) |  |

On the 70 queries BOTH baselines miss, Jev still returns the labelled page first in 46 (65.7%).

Cost: 6.86M input tokens, 458 calls, 14,973 tokens per call, $0.042/Mtok = **$0.29**.
Latency 0.87 s per call at that size, 7.5 calls/s with 8 workers.

## Confidence gate

| conf | n | correct |
| --- | --- | --- |
| <0.40 | 6 | 1 (16.7%) |
| 0.40-0.49 | 10 | 5 (50.0%) |
| 0.50-0.69 | 11 | 7 (63.6%) |
| 0.70-0.89 | 24 | 18 (75.0%) |
| 0.90-1.00 | 161 | 152 (94.4%) |

Act at >=0.90. Send 0.50-0.89 to a human. Discard <0.50 (16 of 212 queries, 8%).


## Label noise, checked by hand

5 of the 29 misses sit at conf >= 0.90 and, on reading both pages, Google's page is the
wrong type for the query. Removing those labels: 188/207 = 90.8%. Measured headline stays 86.3%.

| query | Google serves | Jev picks | why Jev is right |
| --- | --- | --- | --- |
| hyperfocal calculator | /pages/hyperfocal-chart.html | /tools/hyperfocal.html | served page is the chart, query asks for the calculator |
| npf rule | /pages/guides.html | /tools/star-trails.html | served page is the guides index, star-trails is the NPF calculator |
| hyperfocal distance calculator | /pages/hyperfocal-chart.html | /tools/hyperfocal.html | same pair |
| hyperfocal length calculator | /pages/hyperfocal-chart.html | /tools/hyperfocal.html | same pair |
| exposure triangle calculator | /pages/free-photography-calculators.html | /tools/exposure.html | served page is the calculator list, exposure.html is the calculator |

## Work queue this produced

### Queries where Google serves a page Jev says is not the owner (>=2 impressions, n=29)

| query | imps | served | jev pick | conf |
| --- | --- | --- | --- | --- |
| nd filter chart | 61 | /tools/nd-filter.html | /pages/nd-filter-long-exposure-chart.html | 0.96 |
| hyperfocal length | 6 | /pages/hyperfocal-chart.html | /tools/hyperfocal.html | 0.99 |
| hyperfocal calculator | 4 | /pages/hyperfocal-chart.html | /tools/hyperfocal.html | 1.0 |
| mathematics in photography | 4 | /pages/guides.html | /index.html | 0.48 |
| nd chart | 4 | /tools/nd-filter.html | /pages/nd-filter-long-exposure-chart.html | 0.91 |
| npf rule | 4 | /pages/guides.html | /tools/star-trails.html | 0.92 |
| photography calculator | 4 | /pages/free-photography-calculators.html | /index.html | 0.71 |
| depth of field chart | 3 | /tools/depth-of-field.html | /pages/guides.html | 0.31 |
| exposure formula | 3 | /tools/exposure.html | /pages/exposure-triangle.html | 0.48 |
| hyperfocal distance calculator | 3 | /pages/hyperfocal-chart.html | /tools/hyperfocal.html | 1.0 |
| hyperfocal length calculator | 3 | /pages/hyperfocal-chart.html | /tools/hyperfocal.html | 1.0 |
| nd conversion chart | 3 | /tools/nd-filter.html | /pages/nd-filter-long-exposure-chart.html | 0.89 |
| neutral density filter chart | 3 | /tools/nd-filter.html | /pages/nd-filter-long-exposure-chart.html | 0.87 |
| shutter 172.8 | 3 | /pages/guides.html | /tools/shutter-angle.html | 0.65 |
| 24/1.2 | 2 | /pages/focal-length-explained.html | /pages/dof-table-24mm.html | 0.4 |
| 24mm focal length | 2 | /pages/focal-length-explained.html | /pages/dof-table-24mm.html | 0.76 |
| aperture distance chart | 2 | /pages/guides.html | /pages/hyperfocal-chart.html | 0.22 |
| canon aps-c crop factor | 2 | /pages/crop-factor-explained.html | /pages/camera-sensor-sizes.html | 0.66 |
| depth of field table | 2 | /pages/dof-table-85mm.html | /pages/cameras/index.html | 0.75 |
| equivalent exposure chart | 2 | /tools/exposure.html | /pages/exposure-value-chart.html | 0.44 |
| exposure equation | 2 | /tools/exposure.html | /pages/exposure-triangle.html | 0.57 |
| exposure triangle calculator | 2 | /pages/free-photography-calculators.html | /tools/exposure.html | 0.95 |
| exposure value table | 2 | /tools/exposure.html | /pages/exposure-value-chart.html | 1.0 |
| how to calculate exposure factor | 2 | /pages/exposure-triangle.html | /tools/nd-filter.html | 0.34 |
| nd filter stops chart | 2 | /tools/nd-filter.html | /pages/nd-filter-long-exposure-chart.html | 0.53 |
| nd stops chart | 2 | /tools/nd-filter.html | /pages/nd-filter-long-exposure-chart.html | 0.39 |
| photography formula | 2 | /pages/guides.html | /index.html | 0.41 |
| photography math | 2 | /pages/guides.html | /index.html | 0.7 |
| sony a6000 crop factor | 2 | /pages/crop-factor-explained.html | /pages/cameras/sony-a6000.html | 0.36 |

### Queries Google splits across more than one page (>=2 impressions, n=19)

| query | imps | pages |
| --- | --- | --- |
| nd filter chart | 61 | /tools/nd-filter.html + /tools/nd-filter-buyer.html |
| exposure value calculator | 31 | /tools/exposure.html + /pages/exposure-value-chart.html |
| nd filter calculator | 13 | /tools/nd-filter.html + /index.html |
| shutter angle calculator | 11 | /tools/shutter-angle.html + /pages/free-photography-calculators.html, /index.html, /tools/index.html |
| equivalent exposure | 7 | /tools/exposure.html + /pages/exposure-triangle.html |
| dofmaster | 6 | /tools/depth-of-field.html + /pages/dof-table-50mm.html, /index.html, /pages/dof-table-85mm.html |
| shutter angle to shutter speed conversion | 5 | /tools/shutter-angle.html + /pages/shutter-speed-chart.html |
| calculate exposure factor | 4 | /tools/exposure.html + /pages/exposure-triangle.html |
| equivalent exposures | 4 | /tools/exposure.html + /pages/exposure-triangle.html |
| npf rule | 4 | /pages/guides.html + /index.html, /pages/depth-of-field-astro.html |
| photography calculator | 4 | /pages/free-photography-calculators.html + /index.html |
| hyperfocal distance calculator | 3 | /pages/hyperfocal-chart.html + /tools/depth-of-field.html |
| depth of field table | 2 | /pages/dof-table-85mm.html + /pages/dof-table-135mm.html |
| exposure triangle calculator | 2 | /pages/free-photography-calculators.html + /tools/exposure.html, /pages/exposure-triangle.html |
| how to calculate exposure factor | 2 | /pages/exposure-triangle.html + /tools/exposure.html |
| nd calculator | 2 | /tools/nd-filter.html + /tools/video-nd.html |
| photography math | 2 | /pages/guides.html + /index.html |
| shutter angle chart | 2 | /tools/shutter-angle.html + /pages/guides.html, /pages/shutter-speed-chart.html |
| shutter angle formula | 2 | /tools/shutter-angle.html + /index.html |
