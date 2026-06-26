# 📐 System Diagrams — Quick Reference

[🏠 Docs Home](../README.md)

A one-stop collection of the headline diagrams for presentations and quick onboarding. Each diagram
links to the chapter where it is explained in depth. All diagrams are **Mermaid** and render natively
on GitHub.

| Type | Diagram | Explained in |
|------|---------|--------------|
| 🎭 Use case | Actors & capabilities | [01 · Overview](../01-overview/README.md) |
| 🧱 Component | Layered architecture | [02 · Architecture](../02-architecture/README.md) |
| 🔁 Sequence | Request lifecycle | [02](../02-architecture/README.md) · [04](../04-investigation-pipeline/README.md) |
| 🏃 Activity | Investigation pipeline | [04 · Pipeline](../04-investigation-pipeline/README.md) |
| 🏃 Activity | Evidence decision tree | [07 · Evidence](../07-evidence-matching/README.md) |
| 🏃 Activity | Safety filter | [09 · Safety](../09-safety-system/README.md) |

---

## 🎭 Use case — who uses the system

```mermaid
flowchart LR
    judge(("👨‍⚖️ Judge<br/>Harness"))
    agent(("🧑‍💼 Support<br/>Agent"))
    ops(("🛠️ Ops"))

    subgraph SYS [" QueueStorm Investigator "]
        UC1(["Check health"])
        UC2(["Analyze a ticket"])
        UC6(["Get a safe reply"])
        UC7(["Controlled errors"])
        UC8(["Deploy / run"])
        UC2 -. includes .-> UC6
    end

    judge --> UC1 & UC2 & UC7
    agent --> UC2 & UC6
    ops --> UC1 & UC8

    style SYS fill:#f8fafc,stroke:#64748b
    style UC2 fill:#dbeafe,stroke:#3b82f6
```

---

## 🧱 Component — layered architecture

```mermaid
flowchart TB
    client([🌐 Client]) --> API["🌐 API layer<br/>routes · errors · middleware"]
    API --> DOM["🧠 Domain core (pure)<br/>parsing → normalization → classification<br/>→ matching → routing → templates → safety"]
    API --> SCH["📐 Schemas<br/>StrEnums · response_model"]
    DOM --> SCH
    DOM -. low-confidence only .-> ML["🤖 ML fallback (optional)"]
    DOM -. reads .-> CFG["⚙️ config · logging"]

    style DOM fill:#eef7ff,stroke:#3b82f6
    style ML fill:#fef9c3,stroke:#eab308,stroke-dasharray:4 3
    style SCH fill:#ede9fe,stroke:#8b5cf6
```

---

## 🔁 Sequence — request lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant R as analyze route
    participant I as investigator
    participant D as domain core
    participant S as safety filter
    C->>R: POST /analyze-ticket
    R->>R: parse + 400/422 guards
    R->>I: analyze(ParsedTicket)
    I->>D: normalize → classify → match → route
    D-->>I: six scored fields + draft text
    I->>S: enforce(reply, next_action)
    S-->>I: safe text
    I-->>R: AnalyzeResponse
    R-->>C: 200 validated JSON
```

---

## 🏃 Activity — the investigation pipeline

```mermaid
flowchart TD
    A([ParsedTicket]) --> B["normalize"]
    B --> C["classify case_type<br/>(rules + optional ML)"]
    C --> D["match transaction"]
    D --> E["judge evidence_verdict"]
    E --> F["route department"]
    F --> G["set severity"]
    G --> H["set human_review"]
    H --> I["draft text"]
    I --> J[/"safety.enforce()"/]
    J --> K([200 verdict])

    style C fill:#eef7ff,stroke:#3b82f6
    style D fill:#eef7ff,stroke:#3b82f6
    style E fill:#eef7ff,stroke:#3b82f6
    style J fill:#fee2e2,stroke:#ef4444,stroke-width:2px
    style K fill:#dcfce7,stroke:#22c55e
```

---

## 🏃 Activity — evidence decision (the investigator's brain)

```mermaid
flowchart TD
    S([signals · case_type · txns]) --> E{"history empty?"}
    E -- yes --> N1["null · insufficient_data"]:::null
    E -- no --> M{"strong amount matches?"}
    M -- 0 --> N2["null · insufficient_data"]:::null
    M -- 1 --> V{"data contradicts story?"}
    M -- "≥2" --> A{"a disambiguator<br/>(counterparty)?"}
    A -- yes --> V
    A -- no --> N3["null · insufficient_data<br/>(multiple plausible)"]:::null
    V -- yes --> I["matched id · inconsistent"]:::bad
    V -- no --> C["matched id · consistent"]:::ok

    classDef ok fill:#dcfce7,stroke:#22c55e;
    classDef bad fill:#ffedd5,stroke:#f97316;
    classDef null fill:#e2e8f0,stroke:#64748b;
```

---

## 🏃 Activity — the safety filter

```mermaid
flowchart TD
    T([draft text]) --> AU["audit (EN+BN)"]
    AU --> R1["P2 confirmations → safe phrasing"]
    R1 --> R2["P3 / phones / URLs → official channels"]
    R2 --> R3["strip leaks / injection"]
    R3 --> R4["drop P1 credential-request sentences"]
    R4 --> REM["append credential reminder (right language)"]
    REM --> Q{"still unsafe?"}
    Q -- yes --> FB["canned safe fallback"]:::fb
    Q -- no --> OK["✅ safe text"]:::ok
    FB --> OK

    classDef ok fill:#dcfce7,stroke:#22c55e;
    classDef fb fill:#fef9c3,stroke:#eab308;
    style R1 fill:#fee2e2,stroke:#ef4444
    style R4 fill:#fee2e2,stroke:#ef4444
```

---

[🏠 Docs Home](../README.md)
