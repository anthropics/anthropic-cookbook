## Diagrammatic Code Analysis with Mermaid

Learn how to analyze and understand the synoptic, architectural, and systematic aspects of codebases by programmatically generating flurries of mermaid diagrams which aim to model a repository for human understandability

## Plan for Contents

- `diagrammatic-code-analysis-guide.ipynb`:
- `data/`: // Add exmaple raw-code base data here to analyze
- `evaluation/`: Make some appropriate evals for the analysis
- `canned-prompts`
- [ ] Write a python notebook guide
  - [ ] Find a Python-notebook (equivalent) for runtime for TypeScript snippets
  - [ ] Get a Python Notebook working & make instructions 
  - [ ] Write a script that automatically calls Claude (via custom MCP server/server-extension?) to procedurally generate the prompts
    - [ ]Per the modality chosen: figure out the best modality for file creation via tool usage.
- [ ] Create a template notebook/.md file to write the outputs to
  - [ ] Write prompts to coerce IDE-markdown reader accessibility
  - [ ] Write instruction for system prompt customization
  - [ ] List out the prompts
- [ ] Make a directory with example outputs
- [ ] Build out the evals in the convention of this codebase
  - [ ] "For evaluation instructions, see `evaluation/README.md`."
- __**stretch**__[ ]Build stand-alone react app that conducts the analysis using proceduraly generation using Claude given a GitHub repo URL

The prompts
```bash
1. System Architecture Diagram Generation
Prompt:
"Index over the entire codebase to identify back-end architectural layers, including data stores, routes, internal modules, and inter-module communication patterns. Generate a high-level system(s) architecture diagram that visualizes how data flows between these parts. Focus on showing how requests move from external entry points (e.g., APIs, routes) through controllers, services, database queries, and responses. Use Mermaid for the diagram. Place the resulting diagram and a brief explanatory description into a new Markdown file (e.g., @refs/system-architecture.md)."

2. File Structure Tree Extraction (Basic)
Prompt:
"Index over the entire codebase and produce a file structure tree diagram using Mermaid. Show directories as nodes and files as leaf nodes. Create a @refs/file-structure.md file and include a Mermaid code block. Label each major directory and file with short notes indicating their purpose."

3. File Structure Tree with Contextual Comments
Prompt:
"Index the entire codebase to produce a detailed file structure tree. For each file, append a one-line comment explaining its role within the application. Write this as a Markdown file (e.g., @refs/file-structure-with-comments.md) and use Mermaid to represent the hierarchy. Below the diagram, list each file with its corresponding comment for clarity."

4. Data Stores and Database Diagram
Prompt:
"Index the entire codebase and identify all stores, models, and database-related elements (e.g., entities, schemas, migrations, queries). Generate a Mermaid diagram that shows how these stores and database entities relate to each other. Place this diagram into @refs/data-store-diagram.md along with a short textual description of each entity’s purpose."

5. Missing Data and Routes (Introspection on Planned Features)
Prompt:
"Index the entire codebase and identify routes, database operations, and data pathways that are defined or implied but not yet fully implemented. Using this information, create a UML-style Mermaid diagram illustrating these not-yet-implemented data flows and their intended connections. Include brief textual notes on what’s missing. Write the output to @refs/missing-data-flows.md."

6. Technologies and Dependencies Overview
Prompt:
"Index the entire codebase to detect all libraries, frameworks, and external dependencies. Group them by their roles (e.g., Frontend Frameworks, Backend Frameworks, Database Clients, Utility Libraries, Build Tools, Testing Libraries). Create a new Markdown file @refs/dependencies-overview.md listing them by category and importance. Include a short explanation of each dependency’s significance and how it relates to the core features of the application."

7. User Data Model Diagram
Prompt:
"Analyze all user-interaction points across modules in the codebase. Model a user data profile that demonstrates how user data flows through these modules. Create a Mermaid diagram that shows the user data lifecycle (e.g., creation, reading, updates) and place it in @refs/user-data-flow.md. Include a brief textual legend explaining the notation and relationships."

8. User Experience (UX) Flow Diagram
Prompt:
"From the codebase, identify each module contributing to the user experience (e.g., authentication flow, main dashboard, settings page). Create an inline Mermaid diagram in a new Markdown file @refs/ux-flow.md that shows the sequential flow and transitions between these modules from a user's perspective. Add annotations for key decision points."

9. MVC Representational Diagram
Prompt:
"Index the codebase and classify all relevant files into Model, View, or Controller layers. Produce a Mermaid diagram (or multiple diagrams) showing how these layers connect. Include it in @refs/mvc-diagram.md as a Markdown file. Provide a short text section clarifying which files belong to which layer and how requests move through MVC."

10. Inverse Product Requirements Document
Prompt:
"Examine the instantiated elements (e.g., data models, routes, functionalities) and infer the implied product requirements from the existing code. Create a structured product requirements document that maps code elements to feature requirements. Write this in @refs/inverse-prd.md as Markdown, including brief sections for each feature, its corresponding code elements, and the inferred user value."

11. Detailed Application Structure Tree
Prompt:
"Produce a highly detailed tree diagram of the application structure (including directories, key files, primary functions, classes, and their relationships) in a new Mermaid diagram. Write it to @refs/application-structure-tree.md. Annotate key nodes with short summaries of their responsibilities."

12. External Services Integration Diagram
Prompt:
"Identify all external services that the application accesses (e.g., RESTful APIs, external databases, third-party integrations). Create a Mermaid diagram in @refs/external-services.md that shows these external connections, including request-response flows. Add notes for each external service detailing what it provides and how the application uses it."

13. Prospective Systems Architecture (with Grouping)
Prompt:
"Using the Mermaid grouping syntax and visual notations, generate a forward-looking (prospective) systems architecture diagram. Group related components logically (e.g., a group for services, a group for databases, a group for UI elements). Output this to @refs/prospective-architecture.md and provide a short rationale for each group and its components."

14. C4 Model Diagram
Prompt:
"Apply the C4 diagramming methodology (Context, Container, Component, Code) to represent the current architecture. Using Mermaid’s new C4 support, create a C4 model diagram of the system and write it to @refs/c4-diagram.md. Include one diagram or multiple diagrams covering different C4 levels, along with a short explanatory section on how to interpret them."

15. Shadcn Component Invocation Map
Prompt:
"Find every location in the codebase where a Shadcn(or another given standard library if applicable) component is invoked. List each component and enumerate each file and line or code snippet (if possible) where it appears. Output this data into @refs/shadcn-usage.md. For each component, briefly describe its purpose and how it fits into the user interface."

---

16. Dependency Graph (Internal Modules & External Packages)
Prompt:
"Index the entire codebase to identify internal and external dependencies between modules. Generate a directed graph (in Mermaid) that visualizes which modules import or require which others. Also highlight external third-party dependencies. Write this as a new Markdown file @refs/module-dependency-graph.md with a brief explanation of the major dependency chains and any observed dependency clusters."

17. State Machine Diagram for Complex Components
Prompt:
"Identify a particularly complex component or subsystem (e.g., a stateful component managing a complex UI interaction or a service orchestrating multiple steps). Create a UML state machine diagram (using Mermaid UML syntax) showing the states and transitions this component undergoes. Include it in @refs/state-machine.md and provide a short commentary on each state and event."

18. Data Flow Diagram (DFD) for Key Processes
Prompt:
"Analyze the codebase to isolate a core business process (e.g., user onboarding, order processing, data synchronization). Generate a Data Flow Diagram (DFD) at level 1 or 2 using Mermaid to illustrate data inputs, transformations, outputs, and data stores involved. Place the diagram in @refs/data-flow-diagram.md along with a description of each process node and data store."

19. Request Lifecycle Diagram
Prompt:
"Trace the lifecycle of a typical HTTP request through the application (from entry point, routing, controller logic, business logic layer, database calls, and finally response generation). Create a sequence diagram (using Mermaid sequence syntax) and save it to @refs/request-lifecycle.md. Add annotations explaining each step to help newcomers understand the request flow."

20. API Endpoint Summary and Diagram
Prompt:
"Index all the API endpoints (REST or GraphQL) exposed by the application. Create a table or list in Markdown summarizing each endpoint (method, path, purpose, authentication requirements), then produce a Mermaid diagram (e.g., a graph or flowchart) illustrating their relationships and data dependencies. Save to @refs/api-endpoints-overview.md."

21. CI/CD Pipeline Visualization
Prompt:
"Analyze the project’s CI/CD configuration (GitHub Actions, CircleCI, Jenkins, etc.). Generate a pipeline diagram (in Mermaid) that shows stages (build, test, deploy), triggers, conditional steps, and artifacts produced. Place it in @refs/cicd-pipeline.md along with a short explanation of each stage and its purpose. If the project does not have a CI/CD pipeline, recomend one based on the instantiated elements of the codebase"

22. Deployment & Infrastructure Diagram
Prompt:
"Identify how the application is(or how it may be) deployed and hosted (containers, serverless functions, VM instances, load balancers, CDN). Produce a high-level infrastructure diagram using Mermaid or C4 notations that visualizes the runtime environment. Include nodes for servers, containers, services, and external integrations. Save to @refs/infrastructure-diagram.md with brief deployment notes."

23. Logging & Monitoring Overview
Prompt:
"Peruse the codebase for logging, metrics, and monitoring calls. Identify where logs are written, how metrics are exposed, and what external monitoring services are integrated. Generate a Mermaid diagram mapping logging and monitoring flows (from application modules to logging sinks, metric aggregators, and dashboards). Write the results into @refs/logging-monitoring.md with textual summaries of key log/metric categories."

24. Security & Authentication Flow
Prompt:
"Examine how the application handles authentication (e.g., OAuth flows, JWT verification, session handling). Create a sequence or flow diagram in Mermaid showing the user authentication process end-to-end. Note where secrets or keys are used, and how tokens are validated. Place this in @refs/security-auth-flow.md and add notes on best practices and any potential gaps."

25. Error Handling & Exception Pathways Diagram
Prompt:
"Review the codebase for error handling logic (e.g., try/catch blocks, error-boundary components, middleware that handles HTTP errors). Build a flowchart in Mermaid showing the main error pathways: where errors originate, how they propagate through the system, and where/how they are ultimately logged or presented to users. Include in @refs/error-handling-flow.md along with textual commentary."

26. Internationalization & Localization Mapping
Prompt:
"If applicable, examine how the application supports multiple languages or regions (i18n/l10n). Generate a map or flowchart illustrating how text content is loaded, translated strings are fetched, and locale data is applied within the UI. Add this diagram to @refs/i18n-localization.md along with a summary of the libraries or frameworks used."

27. Configuration & Environment Variables Diagram
Prompt:
"Index all configuration files and environment variables used throughout the codebase. Draw a dependency graph or table in @refs/config-variables.md showing which modules rely on which configurations. Accompany this with a Mermaid diagram that shows the flow of configuration data from environment variables or config files into different parts of the system."

28. Caching and Performance Flow Diagram
Prompt:
"Identify where caching mechanisms are employed (e.g., Redis, in-memory caches, memoization strategies). Create a Mermaid diagram in @refs/caching-flow.md showing how data is retrieved, cached, invalidated, and refreshed, as well as how caching interacts with primary data stores."

29. Testing Coverage & Workflow Overview
Prompt:
"Analyze the project’s tests (unit, integration, end-to-end). Generate a documentation file @refs/testing-overview.md that summarizes the types of tests, their structure, and coverage. Include a Mermaid diagram or simple flowchart that shows how tests are triggered, where results are stored, and which components have more or less coverage."

30. Domain-Driven Design (DDD) Context Map
Prompt:
"If the application uses domain-driven design concepts (or can be interpreted that way), identify bounded contexts, aggregates, and domain services. Create a context map diagram in Mermaid, placing the result in @refs/ddd-context-map.md. Include notes on each bounded context and their relationships to one another."
```

