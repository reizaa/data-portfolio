# LLM fallback prompt

Used only for reviews the keyword rules cannot decide (no keyword, or a tie).

```
You classify hotel guest reviews into exactly one topic.

Topics:
- cleanliness: room, bathroom, linen, smell, housekeeping
- staff: behaviour or helpfulness of any employee
- food: breakfast, restaurant, room service, drinks
- location: distance, access, transport, surroundings
- price: value, cost, fees, billing

Rules:
- Pick the topic the guest complains or praises MOST, not the first one mentioned.
- If two topics are equal, pick the one tied to the star rating's sentiment.
- Answer with JSON only: {"topic": "<topic>", "confidence": 0-1, "reason": "<max 12 words>"}

Review ({stars} stars): "{text}"
```

Answers with confidence below 0.6 go to a human review queue.
