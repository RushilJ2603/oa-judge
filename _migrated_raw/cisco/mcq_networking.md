# CISCO OA — MCQs: Networking & Security

Cisco-flavoured (CCNA-adjacent). Single-select. Transcribed by hand; answers with reasoning.

---

## NET-1 — DDoS mitigation with firewall capability
An organisation's network is under a **DDoS** attack; the firewall is struggling with the high volume of
incoming traffic, blocking legitimate access. What is the **most effective** approach to mitigate the
attack **using firewall capability**?
- Implement **rate limiting** on the firewall to restrict connections/second from individual source IPs.
- Increase the maximum connection limit to accommodate the surge.
- Configure the firewall to auto-block all incoming traffic, allowing only whitelisted IPs during the attack.
- Deploy additional firewalls in parallel to distribute the load.

**Answer:** **Rate limiting per source IP.** It directly throttles abusive sources while letting normal
traffic through. Raising the connection limit *helps* the attacker; whitelist-only blocks legitimate users
and isn't scalable; adding firewalls is capacity, not a firewall *capability* fix.

---

## NET-2 — Serial interface with no IP address
A router's serial interface `Gi0/0/0` was configured **without** the `ip address` command. The router
cannot ping the directly-connected neighbour on that interface. What should the technician do?
- Configure the description on the interface.
- **Configure an IP address on interface serial `Gi0/0/0`.**
- Remove the `no shutdown` command on the interface.
- Reboot the router.

**Answer:** **Configure an IP address.** A layer-3 interface needs an IP in the same subnet as the neighbour
to route/ping; without it there is no L3 reachability. A description is cosmetic; removing `no shutdown`
would *disable* the interface; a reboot changes nothing.

---

## NET-3 — ACL applied in the wrong direction
An ACL meant to **block all inbound traffic from external sources to the internal network** is configured,
but a penetration test shows internal users are still reachable from the internet. Most accurate fix?
- Add an outbound deny rule.
- Configure reverse ACLs.
- **The ACL has been applied to the wrong interface direction.**
- Enable stateful inspection.

**Answer:** **Wrong interface/direction.** Traffic *from the internet to internal hosts* is **inbound** on
the external (WAN) interface. If the ACL is applied outbound (or on the wrong interface), it never inspects
that traffic. ACL effectiveness depends entirely on `(interface, in|out)` placement.

---

## NET-4 — TCP congestion-control phase
A TCP connection uses congestion control. Which phase is responsible for **increasing the congestion
window until a packet loss occurs**?
- **Slow Start** · Congestion Avoidance · Fast Recovery · Fast Retransmit

**Answer:** **Slow Start.** At connection start `cwnd` begins at 1 MSS and **doubles every RTT**
(exponential growth), probing upward until it hits `ssthresh` or a loss is detected. *(Nuance: after
`ssthresh`, **Congestion Avoidance** takes over with slow linear/additive growth — if the option wording
stresses "gradual/linear increase," that is Congestion Avoidance. For "keeps growing the window until loss,"
Slow Start is the intended answer.)*

---

## NET-5 — Purpose of DNS
What is the purpose of **DNS**?
- Transferring files
- Assigning IP addresses
- **Translating domain names to IP addresses**
- Encrypting network data

**Answer:** **Translating domain names to IP addresses.** File transfer is FTP/HTTP; dynamic IP assignment
is DHCP; encryption is TLS/IPsec.
