# Platform Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        UI[Web UI]
        SDK[SDKs]
        API[API Clients]
        EMB[Embedded Widgets]
    end

    subgraph "Platform Core"
        NLP[Natural Language Processing]
        QG[Query Generation]
        RV[Result Validation]
        FL[Feedback Loop]
    end

    subgraph "Schema Intelligence"
        SC[Schema Context Manager]
        CE[Context Enrichment]
        VC[Version Control]
        KG[Knowledge Graph]
    end

    subgraph "Data Layer"
        DC[Data Connectors]
        CM[Connection Manager]
        SEC[Security/Auth]
        subgraph "Data Sources"
            SF[Snowflake]
            PG[PostgreSQL]
            BQ[BigQuery]
            RS[Redshift]
        end
    end

    %% Client Layer Connections
    UI --> API
    SDK --> API
    EMB --> API

    %% Core Processing Flow
    API --> NLP
    NLP --> QG
    QG --> RV
    RV --> FL
    FL --> NLP

    %% Schema Intelligence Integration
    QG <--> SC
    SC <--> CE
    SC <--> VC
    CE <--> KG

    %% Data Layer Integration
    QG --> DC
    DC --> CM
    CM --> SEC
    SEC --> SF & PG & BQ & RS

    %% Feedback Systems
    RV --> KG
    FL --> CE

    classDef primary fill:#2374ab,stroke:#2374ab,stroke-width:2px,color:#fff
    classDef secondary fill:#ff8c42,stroke:#ff8c42,stroke-width:2px,color:#fff
    classDef tertiary fill:#4cb944,stroke:#4cb944,stroke-width:2px,color:#fff
    classDef quaternary fill:#8c4843,stroke:#8c4843,stroke-width:2px,color:#fff

    class UI,SDK,API,EMB primary
    class NLP,QG,RV,FL secondary
    class SC,CE,VC,KG tertiary
    class DC,CM,SEC,SF,PG,BQ,RS quaternary

```

## Component Descriptions

### Client Layer
- **Web UI**: Primary web interface for direct user interaction
- **SDKs**: Development kits for various programming languages
- **API Clients**: Direct API integration points
- **Embedded Widgets**: Embeddable components for third-party applications

### Platform Core
- **Natural Language Processing**: Converts user questions to structured queries
- **Query Generation**: Creates optimized database queries
- **Result Validation**: Ensures quality and relevance of results
- **Feedback Loop**: Captures and processes user interactions

### Schema Intelligence
- **Schema Context Manager**: Maintains and serves schema configurations
- **Context Enrichment**: Enhances schema with business context
- **Version Control**: Manages schema evolution
- **Knowledge Graph**: Builds relationships between data concepts

### Data Layer
- **Data Connectors**: Database-specific integration modules
- **Connection Manager**: Handles database connections
- **Security/Auth**: Manages authentication and authorization
- **Data Sources**: Supported databases (expandable)

## Key Features

1. **Modular Architecture**
   - Independent components
   - Pluggable data sources
   - Extensible processing pipeline

2. **Intelligent Processing**
   - Multi-stage query generation
   - Context-aware processing
   - Learning feedback system

3. **Enterprise Ready**
   - Scalable architecture
   - Security focused
   - Multi-tenant capable

4. **Integration Friendly**
   - Multiple access patterns
   - Standard protocols
   - Flexible deployment options
