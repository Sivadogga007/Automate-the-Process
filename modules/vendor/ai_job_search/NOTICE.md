# Source and modifications

Source: https://github.com/ai-job-search-dev/ai-job-search
Pinned commit: d554e797f9aecfa46185cc54fdbb6457f5d7e681
Copyright (c) 2026 Mads Lorentzen. MIT license included in LICENSE.

Imported: tools/job_key.py, tools/posting_guard.py, tools/page_decode.py.
Modification: posting_guard uses a package-relative page_decode import instead
of modifying sys.path. Other imported helper code is unchanged.

Our career_workspace module adapts the four weighted fit dimensions from
rank_state.py and the evidence, reviewer, and STAR preparation workflow concepts.
It uses our SQLite store and local text/OpenJev routing. We do not import the
upstream personal profile, deployment scripts, or agent instructions. Eligibility
unknowns stay unknown rather than assuming missing facts establish incompatibility.
