# Changelog

## 4.4.0

### Added
- Lossless spill (`bocconcini_rami`): during a loop, oversized message content
  moves to disk and the prompt keeps a one-line index entry with its address.
  Nothing is deleted. The model reopens a branch by id and gets byte-identical
  content. The append-only index keeps the prefix stable for KV-cache reuse.
- `pin: True` keeps a message inline at any size.

### Fixed
- Reduction discarded messages by AGE. In an agent loop the oldest messages are
  the tool results - the evidence just fetched. Measured reproducer: a 3368-token
  loop was cut to 92 tokens, 3 of 5 messages deleted, the answering payload lost,
  ending in "nothing to reduce except the request". With spill: 195 tokens,
  5 of 5 messages kept, answering payload intact, nothing deleted.
- A/B on the real reduction path, same 6-message conversation with an early
  reading and a later bulky payload: spill on keeps 6/6 messages and the early
  reading; spill off drops 3 messages and loses it. Deterministic, no model.
