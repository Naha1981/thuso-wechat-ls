# Econet Revenue Proof

## What must be proven

The pilot is successful only when THUSO can connect user activity to an observed commercial outcome.

### Primary attribution chain

```
THUSO user
  -> AI interaction
  -> service/action
  -> Econet-controlled product/API
  -> transaction or paid subscription
  -> observable revenue/value event
```

### Dashboard metrics

**Acquisition**
- THUSO users
- AI activations
- paid AI activations

**Engagement**
- AI sessions/user
- completed AI tasks
- repeat usage

**Telecom**
- incremental data usage
- AI package purchases
- package renewal rate

**Fintech**
- EcoCash transaction count
- EcoCash transaction value
- active wallet users
- repeat transaction rate

**Enterprise**
- active enterprise accounts
- seats
- contracted recurring revenue
- completed billable actions

**Outcome**
- task completion rate
- time saved
- service completion rate
- support contacts avoided

### Attribution rules

- **Observed:** directly recorded from a partner/system-of-record event.
- **Attributed:** observed event linked to a THUSO trace/session through an agreed attribution window.
- **Estimated:** modelled value. It must be labelled estimated and never presented as booked revenue.

### Pilot experiment

Before launch, define:
- pilot cohort
- baseline period
- control/matched cohort where available
- attribution window
- excluded traffic
- revenue definitions
- privacy/consent requirements

At the end of the pilot, produce:

```
Incremental revenue/value
= pilot observed outcome
  - baseline/control expected outcome
```

The commercial report must show both absolute totals and incremental change, with methodology and uncertainty.
