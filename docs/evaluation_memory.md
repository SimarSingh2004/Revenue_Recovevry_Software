## Objective

Verify that historical recovery outcomes can influence a subsequent
recovery decision.

## Experiment

The same RecoveryContext was evaluated twice:

1. Memory OFF — no historical insights supplied to Gemini.
2. Memory ON — three relevant historical recovery outcomes supplied.

## Result

|                     | Memory OFF    | Memory ON         |
| ------------------- | ------------- | ----------------- |
| Action              | RETRY_PAYMENT | SEND_PAYMENT_LINK |
| Predicted recovery  | 0.80          | 0.85              |
| Historical insights | None          | 3                 |

### Observation

Without historical memory, Gemini selected `RETRY_PAYMENT` as the
standard first-line response to a temporary UPI failure.

With historical memory, Gemini selected `SEND_PAYMENT_LINK`, explicitly
using the previous outcomes:

- SEND_PAYMENT_LINK → SUCCESS / POSITIVE_RECOVERY
- ALTERNATE_PAYMENT_METHOD → FAILED / FEE_LOSS
- RETRY_PAYMENT → FAILED / FEE_LOSS

## Conclusion

Historical recovery outcomes successfully influenced the subsequent
recovery decision.

## Limitation

The recovery simulator is stochastic and synthetic. A single SUCCESS or
FAILED outcome is therefore not evidence of real-world recovery
performance. This experiment demonstrates the memory → decision feedback
loop, not real-world lift.
