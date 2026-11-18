# Application protocol (UDP, JSON payloads)

All messages are single UDP datagrams carrying a JSON object. The server listens on **UDP 5000**.

| Direction | `type` | Fields | Purpose |
|---|---|---|---|
| player → server | `JOIN` | `name` | Register. Re-sent until `WELCOME` arrives (UDP may lose it). |
| server → player | `WELCOME` | `player_id`, `name`, `message` | Registration confirmed (`"Successfully joined"`). |
| player → server | `STATE` | `name`, `seq`, `ts`, `pos` | Player position. `seq` increases by 1 per packet; `ts` is the send time. |
| server → player | `WORLD` | `players`, `world`, `echo_seq`, `echo_ts`, `server_ts` | Snapshot of all players, broadcast at 20 Hz. `echo_ts` is the last `ts` received from this player. |
| player → server | `LEAVE` | `name` | Leave; the server writes the player's final statistics. |

## Server-side accounting (per player)
| Condition | Action |
|---|---|
| `seq == last_seq` | `dup += 1`, packet ignored |
| `seq < last_seq` | `ooo += 1`, packet discarded as stale |
| `seq > last_seq + 1` | `lost += seq - last_seq - 1` |
| accepted packet | one-way delay `now - ts`; jitter `J += (|D| - J) / 16` (RFC 3550) |

## Client-side measurement
`rtt = receive_time - echo_ts`, taken from each `WORLD` packet. Because the echo travels in the next 20 Hz broadcast it includes up to one 50 ms server tick.

## Files linking the components
| File | Written by | Read by | Content |
|---|---|---|---|
| `logs/game_events.jsonl` | game server | Ryu controller | `JOIN` / `LEAVE` events (player name and IP) |
| `logs/qos_mode` | operator / experiment | Ryu controller | `off`, `static` or `dynamic` |
| `logs/ctrl_events.jsonl` | Ryu controller | experiment, plots | `MODE_CHANGE`, `PLAYER_JOIN/LEAVE`, `CONGESTION_ON/OFF`, `QOS_INSTALLED/REMOVED` |
| `logs/port_rate.csv` | Ryu controller | plots | server-port rate in Mbps over time |
| `logs/rtt_<name>.csv`, `logs/client_stats.jsonl` | player client | experiment | per-sample RTT and final statistics |
| `logs/server_stats.jsonl` | game server | experiment | final per-player loss / duplicate / reorder / delay / jitter |
