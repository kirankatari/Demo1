# VPN troubleshooting

Document-ID: DOC-VPN-002

## Switch gateway

Employees report: my VPN keeps disconnecting while I am working remotely. When GlobalProtect disconnects repeatedly, the usual cause is the US-East gateway. Sign out of GlobalProtect, open the portal menu, and set the gateway to US-Central instead of US-East. Reconnect and leave the client open for two minutes before you join a meeting. Do this before you reinstall the client.

## Reconnect

If the VPN already shows connected but internal sites fail, disconnect once, wait ten seconds, and connect again to US-Central. Then open https://intranet.northstar.example and confirm the page loads. A laptop reboot is the later step, not the first step, when the only symptom is a repeating disconnect.

## Urgent meeting

If you have a client presentation or another meeting in the next hour, join that meeting from a phone hotspot while the VPN is unstable. Do not wait on a full reinstall before the presentation. After you are in the meeting, ask the help desk to draft an urgent ticket. A ticket is only opened after you confirm it.

## What IT will not ask

Support will not ask you to read out your password or your multi-factor code. If disconnects continue after the US-Central gateway change, note the time of the last drop and the gateway name for the ticket.
