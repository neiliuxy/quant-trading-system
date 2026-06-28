"""Stock screener — pre-funnel filter + scoring for A-share picking.

Output is a ScreenerResult artifact (date + ranked candidates + reasons).
Does not depend on strategy layer; strategies consume results.
"""