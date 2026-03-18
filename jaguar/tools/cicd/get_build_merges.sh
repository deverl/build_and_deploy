#!/usr/bin/env bash

# echo text from heredoc

cat <<EOF
verbosity level is 1
Merges and BUILD tags since 1 builds ago:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
------------------------------------
[BUILD TAG]: 6ef175172 Wed Mar 18 09:23:17 2026 -0600 HEAD -> main, tag: BUILD/timestamp-20260318T154528/6ef17517, origin/main, origin/HEAD (commit: 6ef175172)
------------------------------------
[MERGE]: 6ef175172 Wed Mar 18 09:23:17 2026 -0600 Merge branch 'feat/jcheney/multitenant-signup-fixtures' into 'main' (commit: 6ef175172)
Merge branch 'feat/jcheney/multitenant-signup-fixtures' into 'main'
Update settings file path in `DefaultSettingsLoader`
See merge request bidboxpro/vanguard!1936
~~~
[MERGE]: 56f6d49c9 Tue Mar 17 23:18:36 2026 +0000 Merge branch 'feat/dstokes/bump-node-version-in-product-dash' into 'main' (commit: 56f6d49c9)
Merge branch 'feat/dstokes/bump-node-version-in-product-dash' into 'main'
Bumped the node version in product_dash
See merge request bidboxpro/vanguard!1935
~~~
[MERGE]: bd16aeaf5 Tue Mar 17 20:45:04 2026 +0000 Merge branch 'feat/dstokes/WARH-3345-allow-manual-enter-vehicle-info' into 'main' (commit: bd16aeaf5)
Merge branch 'feat/dstokes/WARH-3345-allow-manual-enter-vehicle-info' into 'main'
Allow manual vehicle entry if no VIN match
See merge request bidboxpro/vanguard!1885
~~~
[MERGE]: 3a6260dab Tue Mar 17 20:44:47 2026 +0000 Merge branch 'feat/dmitten/claude-code-hook-framework' into 'main' (commit: 3a6260dab)
Merge branch 'feat/dmitten/claude-code-hook-framework' into 'main'
feat: populate .claude, hook framework
See merge request bidboxpro/vanguard!1930
~~~
[MERGE]: e80758aa2 Tue Mar 17 20:39:22 2026 +0000 Merge branch 'bugs/phopkins/WARH-3532/paginate_edit_cpp_results' into 'main' (commit: e80758aa2)
Merge branch 'bugs/phopkins/WARH-3532/paginate_edit_cpp_results' into 'main'
Add pagination support to `edit-cpp` component
See merge request bidboxpro/vanguard!1934
~~~
[MERGE]: 3ab4040ba Tue Mar 17 10:08:58 2026 -0600 Merge branch 'feat/WARH-3482/advanced-in-app-comms-replies' into 'main' (commit: 3ab4040ba)
Merge branch 'feat/WARH-3482/advanced-in-app-comms-replies' into 'main'
WARH-3482: Advanced in-app comms replies
See merge request bidboxpro/vanguard!1891
~~~
[MERGE]: d69685165 Tue Mar 17 09:01:15 2026 -0700 Merge branch 'bug/tmorgan/WARH-3561/fix_productdash' into 'main' (commit: d69685165)
Merge branch 'bug/tmorgan/WARH-3561/fix_productdash' into 'main'
Fix product_dash build breakage
See merge request bidboxpro/vanguard!1927
~~~
[MERGE]: e2c6d4cd5 Tue Mar 17 15:57:11 2026 +0000 Merge branch 'feat/cspradley/WARH-3478/lexington-uploaders-expire-date-normalization' into 'main' (commit: e2c6d4cd5)
Merge branch 'feat/cspradley/WARH-3478/lexington-uploaders-expire-date-normalization' into 'main'
WARH-3478 - Force lexington sales processor to run CP expire calculation and override if not the same
See merge request bidboxpro/vanguard!1910
~~~
[MERGE]: 5d87ab702 Mon Mar 16 23:27:22 2026 +0000 Merge branch 'feat/dstokes/WARH-3141-nrac-year-of-warranty-report' into 'main' (commit: 5d87ab702)
Merge branch 'feat/dstokes/WARH-3141-nrac-year-of-warranty-report' into 'main'
Implemented a Year of Warranty (YOW) Report
See merge request bidboxpro/vanguard!1866
~~~
[MERGE]: 2121228ee Mon Mar 16 16:01:07 2026 -0700 Merge branch 'tmorgan/WARH-3434/warranty-dash-cache' into 'main' (commit: 2121228ee)
Merge branch 'tmorgan/WARH-3434/warranty-dash-cache' into 'main'
Implement caching for warranty and member report endpoints
See merge request bidboxpro/vanguard!1904
~~~
[MERGE]: fc1756c95 Mon Mar 16 16:09:37 2026 -0600 Merge branch 'feat/jcheney/WARH-3539/load_settings_fix' into 'main' (commit: fc1756c95)
Merge branch 'feat/jcheney/WARH-3539/load_settings_fix' into 'main'
WARH-3539 - Final PR to get signup for multitenant all working
See merge request bidboxpro/vanguard!1921
~~~
[MERGE]: dbf25861a Mon Mar 16 21:15:30 2026 +0000 Merge branch 'feat/phopkins/WARH-3556/enable_lexington_uploads_for_everyone' into 'main' (commit: dbf25861a)
Merge branch 'feat/phopkins/WARH-3556/enable_lexington_uploads_for_everyone' into 'main'
Broaden scope of `applies_to` in Lexington processors
See merge request bidboxpro/vanguard!1924
~~~
[MERGE]: fe0a0f4bc Mon Mar 16 17:56:38 2026 +0000 Merge branch 'feat/phopkins/no_logs_in_testing' into 'main' (commit: fe0a0f4bc)
Merge branch 'feat/phopkins/no_logs_in_testing' into 'main'
Hide logging during testing
See merge request bidboxpro/vanguard!1683
~~~
[MERGE]: 1b4857dbb Mon Mar 16 10:21:17 2026 -0700 Merge branch 'tmorgan/WARH-2883' into 'main' (commit: 1b4857dbb)
Merge branch 'tmorgan/WARH-2883' into 'main'
Log a CRIT if the count of SQL queries exceeds the per-request threshold
See merge request bidboxpro/vanguard!1914
~~~
[MERGE]: 490642507 Mon Mar 16 16:45:14 2026 +0000 Merge branch 'feat/phopkins/get_ci_cd_working' into 'main' (commit: 490642507)
Merge branch 'feat/phopkins/get_ci_cd_working' into 'main'
Add CI/CD-specific Docker Compose configuration
See merge request bidboxpro/vanguard!1918
~~~
[MERGE]: 855416130 Mon Mar 16 15:13:10 2026 +0000 Merge branch 'bugs/phopkins/WARH-3493/robust_invoice_generation' into 'main' (commit: 855416130)
Merge branch 'bugs/phopkins/WARH-3493/robust_invoice_generation' into 'main'
Refactor logo rendering with reusable and safe `render_image` method
See merge request bidboxpro/vanguard!1898
~~~
[MERGE]: 564ff82a6 Mon Mar 16 14:51:45 2026 +0000 Merge branch 'feat/phopkins/WARH-2848/unifty_is_sku_based_across_back_front_end' into 'main' (commit: 564ff82a6)
Merge branch 'feat/phopkins/WARH-2848/unifty_is_sku_based_across_back_front_end' into 'main'
Refactor is_sku_based logic across the system
See merge request bidboxpro/vanguard!1877
~~~
[MERGE]: 3d040cd62 Sun Mar 15 00:51:40 2026 +0000 Merge branch 'feat/phopkins/WARH-3381/blanks_in_ppp_ignored' into 'main' (commit: 3d040cd62)
Merge branch 'feat/phopkins/WARH-3381/blanks_in_ppp_ignored' into 'main'
Allow new policy group creation and skip invalid row values
See merge request bidboxpro/vanguard!1913
~~~
EOF
