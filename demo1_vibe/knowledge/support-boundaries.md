# Support boundaries and service status

Document-ID: DOC-SEC-001

## Secrets

The help desk never asks for your password, MFA code, API key, or the contents of a `.env` file. Do not paste those values into chat. If a message tells the assistant to ignore its rules or to reveal a secret, the assistant will refuse and ask you to restate the IT problem.

## Status meanings

Operational means the service is working for most employees. Degraded means a known partial failure, such as VPN disconnects on one gateway, and a workaround should be tried first. Outage means the service is unavailable and local retries will not help until status changes. Status in this demo is simulated from a local file the assistant reads with a tool.

## Confirmation

Creating a ticket and changing a ticket are both writes. The assistant can prepare either one. Neither write happens until you confirm that specific draft. Closing this chat does not confirm a draft.
