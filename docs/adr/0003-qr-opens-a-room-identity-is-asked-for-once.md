# The QR code is the room's credential; identity is asked for once, at the signature

Anyone holding a room's QR code lands in that room with no account, no password and nothing to type.
But the code in that QR **is a credential**, not merely an address: it is presented to the front end
as an authenticated identity, one identity per room. An email address may be given at the door and is
never required. Identity is demanded at exactly one moment: the Stage 5 signature.

The method already says where identity genuinely matters — a signature must identify someone with
authority to give it — so demanding it at the door buys nothing and costs the demo.

**"No login" must not be read as "no auth".** Measured on this box at Chainlit 2.12.0 (see
`docs/research/chainlit-multitenancy.md`): with no auth callback registered, `get_current_user`
returns `None` and every `if current_user:` guard in the server becomes a no-op *at the same time*.
A cookieless stranger read another room's file over an HTTP GET, fired another room's action
callback, and joined another room's websocket — inheriting its chat context and silently evicting the
real occupant. With header auth on and the identifier set to the room, the same three probes returned
401, 401 and refused. Isolation in Chainlit is not a framework property; it is a property of having
distinct user identifiers, and there is no partial credit.

## Consequences

- Where an email was given, the signature binds to it and the certificate reads **identity confirmed
  by email**. Where none was given, it reads **identity asserted in session, not verified**, in those
  words. The certificate must never overclaim.
- A room code is therefore secret-shaped. A QR code on a conference slide is a published credential,
  and demo rooms must hold nothing that matters — which ADR-0002 already requires.
- The auth cookie is set at `Path=/`, so **one browser is in one room at a time**. Two rooms means two
  browsers or a private window. This constrains how the demo is run and must be known before the day.
