# Creation and targeted-edit examples

Names, rules, and values below are fictional teaching examples. Do not apply them to a real system without a source.

## Create a Use Case diagram

Given: a buyer places an order; checking restrictions is mandatory; applying a promo code is optional. The question concerns goals and the system boundary, not call order.

```plantuml
@startuml
left to right direction
actor "Buyer" as Buyer
rectangle "Order system" {
  usecase "Place an order" as Checkout
  usecase "Check restrictions" as CheckRules
  usecase "Apply a promo code" as ApplyPromo
}
Buyer -- Checkout
Checkout ..> CheckRules : <<include>>
ApplyPromo ..> Checkout : <<extend>>\n[promo code provided]
@enduml
```

Check: `include` points to the mandatory behavior, `extend` points to the base use case, and the actor is outside the boundary. Do not add authentication without a requirement.

## Create an Activity diagram

Given: invalid input is rejected; for a valid request, checking restrictions and calculating the amount run in parallel; both finish before a decision. The source does not specify early cancellation.

```plantuml
@startuml
title Request processing
start
:Receive request;
if (Is the input valid?) then (yes)
  fork
    :Check restrictions;
  fork again
    :Calculate amount;
  end fork
  if (Do the results allow acceptance?) then (yes)
    :Accept request;
  else (no)
    :Report rejection;
  endif
else (no)
  :Report input errors;
endif
stop
@enduml
```

Check: the join follows parallel branches that were started, alternatives converge through merge, and all outcomes finish. Do not add a database or HTTP codes without a source.

## Edit a Sequence diagram while preserving IDs

Original source:

```mermaid
sequenceDiagram
    participant UI as User interface
    participant API as Orders API
    participant Stock as Inventory
    %% correlationId is passed in every request
    UI->>API: Place an order
    API->>Stock: Reserve item
    Stock-->>API: Reservation created
    API-->>UI: Order accepted
```

Request: inventory may also return "Out of stock"; reject the order after that response. No other guarantees or response codes are specified.

Edited source:

```mermaid
sequenceDiagram
    participant UI as User interface
    participant API as Orders API
    participant Stock as Inventory
    %% correlationId is passed in every request
    UI->>API: Place an order
    API->>Stock: Reserve item
    alt Reservation created
        Stock-->>API: Reservation created
        API-->>UI: Order accepted
    else Out of stock
        Stock-->>API: Out of stock
        API-->>UI: Order rejected
    end
```

Delta: replace the single success response with mutually exclusive outcomes. Preserve aliases, participants, the comment, and requests. Keep success inside the successful branch; no shared "Order accepted" follows a failure. Do not invent HTTP codes, retries, or compensations.

## Layout-only edit

"Make it more readable without changing behavior" permits changes to layout, label wrapping, and visual groups. Compare before and after: participants/relationships, directions/types, conditions, order, and outcomes must match. If simplification requires changing the model or splitting the file, present it as a separate proposal.

## Inconsistent diagrams

If Use Case says "Place an order", Activity finishes after payment, and Sequence accepts the order before payment, check the sources. Do not choose an arbitrary interpretation. Establish what "accepted" means, when the status is reached, and which source describes current or target behavior. Apply only a confirmed, authorized delta.
