# PM-107 — AppNexus

**Company:** AppNexus  
**Category:** Uncategorized  
**Source:** https://web.archive.org/web/20250505112812/https://medium.com/xandr-tech/2013-09-17-outage-postmortem-586b19ae4307

## Incident Summary

A double free revealed by a database update caused all "impression bus" servers to crash simultaneously. This wasn't caught in staging and made it into production because a time delay is required to trigger the bug, and the staging period didn't have a built-in delay.
