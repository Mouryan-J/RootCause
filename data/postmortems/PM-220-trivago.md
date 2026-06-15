# PM-220 — trivago

**Company:** trivago  
**Category:** Uncategorized  
**Source:** https://tech.trivago.com/2021/10/05/postmortem-removing-all-users-from-github.com/trivago/

## Incident Summary

Due to a human error, all engineers lost access to the central source code management platform (GitHub organization). An Azure Active Directory Security group controls the access to the GitHub organization. This group was removed during the execution of a manual and repetitive task.
