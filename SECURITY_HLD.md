# SAP RCA MCP Server — Security High-Level Design (HLD)

| **Document**      | Security High-Level Design                        |
|-------------------|---------------------------------------------------|
| **Version**       | 1.0                                               |
| **Date**          | July 2026                                         |
| **Status**        | DRAFT — For Team Review                           |
| **Component**     | AMS SAP MCP Server (Managed MCP Server)           |
| **Classification**| Internal — Microsoft Confidential                 |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Threat Model](#3-threat-model)
4. [Network Security](#4-network-security)
5. [Identity & Authentication](#5-identity--authentication)
6. [Authorization & Access Control](#6-authorization--access-control)
7. [Secrets Management](#7-secrets-management)
8. [Data Protection](#8-data-protection)
9. [Query Safety & Input Validation](#9-query-safety--input-validation)
10. [Audit, Logging & Monitoring](#10-audit-logging--monitoring)
11. [Container & Supply Chain Security](#11-container--supply-chain-security)
12. [Cross-Tenant Access Model](#12-cross-tenant-access-model)
13. [Deployment Security Controls](#13-deployment-security-controls)
14. [Compliance Alignment](#14-compliance-alignment)
15. [Security Checklist](#15-security-checklist)
16. [Appendix A — Reference Implementation Snippets](#appendix-a--reference-implementation-snippets)

---

## 1. Executive Summary

The SAP RCA MCP Server is an enterprise-grade Model Context Protocol (MCP) server that provides SAP observability and root-cause-analysis capabilities to AI agents. It is deployed **within the customer's Azure tenant and VNet boundaries**, connecting to customer-owned data sources (Azure Log Analytics Workspaces) and invoked by agent orchestrators running inside the same network perimeter.

This document defines the security controls required for enterprise deployment, ensuring:

- **Zero public internet exposure** — all traffic stays within the customer's VNet
- **Entra ID–based authentication** — every request is validated against the customer's identity provider
- **Managed Identity for backend access** — no stored credentials for data-source connectivity
- **Read-only data access** — the server can never modify, delete, or exfiltrate customer data
- **Full audit trail** — every tool invocation is logged for compliance and forensics

### Scope

| In Scope | Out of Scope |
|----------|--------------|
| MCP Server (Container App) | Agent Orchestrator internals |
| Network perimeter (VNet, Private Endpoints) | LLM model security |
| Authentication & authorization middleware | Agent Platform Control Plane (Microsoft Tenant) |
| Data-source connectivity (LAWS) | Customer application layer |
| Audit logging pipeline | SOC/SIEM operations |

---

## 2. Architecture Overview

### 2.1 Deployment Context

```
┌───────────────────────────────── Customer Tenant ──────────────────────────────────┐
│                                                                                    │
│  ┌─────────────────────────────── Customer VNet ─────────────────────────────────┐ │
│  │                                                                               │ │
│  │  ┌────────────────┐                    ┌──────────────────────────────────┐   │ │
│  │  │ Agent Client   │──── 1.a ──────────►│ Agent Orchestrator               │   │ │
│  │  │ Layer / User   │                    │ (routes to SAP Agent)            │   │ │
│  │  └────────────────┘                    └──────────┬───────────────────────┘   │ │
│  │                                                   │ 4.a                       │ │
│  │                                                   ▼                           │ │
│  │  ┌──────────────────────────── MCP Servers ────────────────────────────────┐  │ │
│  │  │                                                                        │  │ │
│  │  │  ┌───────────────────┐  ┌────────────────┐  ┌─────────────────────┐   │  │ │
│  │  │  │ AMS SAP MCP       │  │ Oracle MCP     │  │ 3P MCP Servers      │   │  │ │
│  │  │  │ (This Server)     │  │                │  │ (Splunk, NewRelic)  │   │  │ │
│  │  │  │                   │  │                │  │                     │   │  │ │
│  │  │  │ ┌──────────────┐  │  │                │  │                     │   │  │ │
│  │  │  │ │ Auth         │  │  │                │  │                     │   │  │ │
│  │  │  │ │ Middleware   │  │  │                │  │                     │   │  │ │
│  │  │  │ ├──────────────┤  │  │                │  │                     │   │  │ │
│  │  │  │ │ MCP Tools    │  │  │                │  │                     │   │  │ │
│  │  │  │ │ ┌──────────┐ │  │  │                │  │                     │   │  │ │
│  │  │  │ │ │get_schema│ │  │  │                │  │                     │   │  │ │
│  │  │  │ │ │exe_query │ │  │  │                │  │                     │   │  │ │
│  │  │  │ │ │rca_anlys │ │  │  │                │  │                     │   │  │ │
│  │  │  │ │ └──────────┘ │  │  │                │  │                     │   │  │ │
│  │  │  │ ├──────────────┤  │  │                │  │                     │   │  │ │
│  │  │  │ │ Query Guard  │  │  │                │  │                     │   │  │ │
│  │  │  │ │ Audit Logger │  │  │                │  │                     │   │  │ │
│  │  │  │ └──────────────┘  │  │                │  │                     │   │  │ │
│  │  │  └────────┬──────────┘  └────────────────┘  └─────────────────────┘   │  │ │
│  │  │           │ Private Endpoint                                          │  │ │
│  │  └───────────┼───────────────────────────────────────────────────────────┘  │ │
│  │              ▼                                                              │ │
│  │  ┌───────────────────────────── Data Sources ──────────────────────────┐    │ │
│  │  │  ┌────────────────────┐   ┌──────────────┐   ┌────────────────┐   │    │ │
│  │  │  │ AMS LAWS           │   │ Key Vault    │   │ Container      │   │    │ │
│  │  │  │ (Log Analytics)    │   │ (Secrets)    │   │ Registry (ACR) │   │    │ │
│  │  │  └────────────────────┘   └──────────────┘   └────────────────┘   │    │ │
│  │  └────────────────────────────────────────────────────────────────────┘    │ │
│  │                                                                            │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  ┌────── Telemetry ──────┐   ┌────── Knowledge Base ──────┐                     │
│  │ RCA Reports           │   │ Domain Knowledge Vector DB │                     │
│  │ Metrics & Traces      │   │ TSG Vector DB              │                     │
│  │ Audit Storage         │   └────────────────────────────┘                     │
│  │ Evals                 │                                                       │
│  └───────────────────────┘                                                       │
└──────────────────────────────────────────────────────────────────────────────────┘

    ▲ Cross-Tenant (Entra ID multi-tenant app registration)
    │
┌───┴──────────────────────────── Microsoft Tenant ────────────────────────────────┐
│  ┌──────────────────────────────────────────────────┐                            │
│  │ Agent Platform Control Plane                      │                            │
│  │ ┌──────────────┐ ┌────────────┐ ┌──────────────┐ │   ┌──────────────────┐    │
│  │ │ Agent/MCP    │ │ Versioning │ │ Skills &     │ │   │ Managed LLM      │    │
│  │ │ Deployment   │ │ Lifecycle  │ │ Knowledge DB │ │   │ (Azure OpenAI)   │    │
│  │ └──────────────┘ └────────────┘ └──────────────┘ │   └──────────────────┘    │
│  └──────────────────────────────────────────────────┘                            │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow Summary

| Step | From | To | Protocol | Auth Mechanism |
|------|------|----|----------|----------------|
| 1.a | User | Agent Client Layer | HTTPS | User identity (Entra ID SSO) |
| 2.a/2.b | Agent Client | Agent Orchestrator | HTTPS | Entra ID token (delegated) |
| 3.a/3.b | Orchestrator | SAP Agent | Internal | Agent runtime session |
| 4.a | SAP Agent | AMS SAP MCP Server | HTTPS (internal) | Entra ID app token (client_credentials) |
| 5 | MCP Server | AMS LAWS | HTTPS (Private Endpoint) | Managed Identity |
| 5 | MCP Server | Key Vault | HTTPS (Private Endpoint) | Managed Identity |

---

## 3. Threat Model

### 3.1 STRIDE Analysis

| Threat | Category | Risk | Mitigation |
|--------|----------|------|------------|
| Unauthorized agent invokes MCP tools | **Spoofing** | High | Entra ID token validation; allow-listed client app IDs only |
| Attacker crafts malicious KQL to delete data | **Tampering** | Critical | Query guard blocks all write/delete/purge operations |
| Agent sends KQL to exfiltrate data via `externaldata()` | **Information Disclosure** | High | Block `externaldata` operator; VNet-only egress |
| MCP server overwhelmed by excessive queries | **Denial of Service** | Medium | Rate limiting per caller identity; row caps; timeout enforcement |
| Tool invocations not logged | **Repudiation** | Medium | Structured audit logging to immutable storage |
| Man-in-the-middle intercepts agent-to-MCP traffic | **Information Disclosure** | Medium | TLS 1.2+ enforced; VNet-internal traffic; optional mTLS |
| Container image contains vulnerable packages | **Elevation of Privilege** | Medium | Defender for Containers; base image scanning; non-root runtime |

### 3.2 Trust Boundaries

```
┌─────────────────────────────────────────────────────┐
│ Trust Boundary 1: Customer VNet                      │
│  ┌───────────────────────────────────────────────┐  │
│  │ Trust Boundary 2: Container Apps Environment   │  │
│  │  ┌─────────────────────────────────────────┐  │  │
│  │  │ Trust Boundary 3: MCP Server Container   │  │  │
│  │  │  ┌───────────────────────────────────┐  │  │  │
│  │  │  │ Auth Middleware (validates tokens) │  │  │  │
│  │  │  ├───────────────────────────────────┤  │  │  │
│  │  │  │ Query Guard (validates KQL)       │  │  │  │
│  │  │  ├───────────────────────────────────┤  │  │  │
│  │  │  │ MCP Tools (business logic)        │  │  │  │
│  │  │  └───────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

Validation occurs at **every boundary crossing**:
- **Boundary 1 → 2**: NSG rules, Private Endpoint
- **Boundary 2 → 3**: Entra ID token validation (auth middleware)
- **Inside Boundary 3**: KQL query safety validation, rate limiting, audit logging

---

## 4. Network Security

### 4.1 VNet Integration (Mandatory)

The Container Apps Environment **must** be deployed with VNet injection and internal-only ingress. No public IP address is assigned.

```
Customer VNet (e.g. 10.0.0.0/16)
├── subnet-aca-infra    (10.0.1.0/23)  — Container Apps Environment (delegated)
├── subnet-private-eps  (10.0.3.0/24)  — Private Endpoints (LAWS, Key Vault, ACR)
└── subnet-agents       (10.0.4.0/24)  — Agent Orchestrator / compute
```

**Key Configuration:**

| Setting | Value | Rationale |
|---------|-------|-----------|
| Container Apps ingress | `internal` | No public internet access |
| VNet injection | Required | All traffic stays within VNet |
| ACA infrastructure subnet | `/23` minimum | Azure requirement for ACA |
| Private Endpoints | LAWS, Key Vault, ACR | All backend access over private network |

### 4.2 Network Security Groups (NSGs)

| Rule | Direction | Source | Destination | Port | Action |
|------|-----------|--------|-------------|------|--------|
| Allow Agent → MCP | Inbound | `subnet-agents` | `subnet-aca-infra` | 443 | Allow |
| Allow MCP → LAWS PE | Outbound | `subnet-aca-infra` | `subnet-private-eps` | 443 | Allow |
| Allow MCP → KV PE | Outbound | `subnet-aca-infra` | `subnet-private-eps` | 443 | Allow |
| Allow MCP → Entra ID | Outbound | `subnet-aca-infra` | `AzureActiveDirectory` | 443 | Allow |
| Deny all other inbound | Inbound | `*` | `subnet-aca-infra` | `*` | **Deny** |
| Deny all other outbound | Outbound | `subnet-aca-infra` | `Internet` | `*` | **Deny** |

### 4.3 DNS Configuration

| Zone | Purpose |
|------|---------|
| `privatelink.oms.opinsights.azure.com` | Log Analytics Private Link |
| `privatelink.vaultcore.azure.net` | Key Vault Private Link |
| `privatelink.azurecr.io` | Container Registry Private Link |
| Customer's Private DNS Zone | Internal resolution of `*.internal.<region>.azurecontainerapps.io` |

### 4.4 Egress Lockdown

All outbound traffic from the MCP server is restricted to:

1. Private Endpoints (LAWS, Key Vault, ACR) — via VNet routing
2. Entra ID endpoints (`login.microsoftonline.com`) — via Service Tag
3. **No general internet egress** — prevents data exfiltration

---

## 5. Identity & Authentication

### 5.1 Authentication Layers

```
                    ┌────────────────────────────────┐
                    │ Entra ID (Customer Tenant)      │
                    │                                  │
                    │  App Registration:               │
                    │  "AMS-SAP-MCP-Server"           │
                    │  ┌──────────────────────────┐   │
                    │  │ App Roles:               │   │
                    │  │  MCP.Tools.Invoke        │   │
                    │  │  MCP.Schema.Read         │   │
                    │  └──────────────────────────┘   │
                    └────────┬───────────┬─────────────┘
                             │           │
              ┌──────────────┘           └──────────────┐
              ▼                                          ▼
   ┌──────────────────────┐                 ┌────────────────────────┐
   │ Agent Orchestrator    │                 │ SRE Automation Scripts │
   │ (Service Principal)   │                 │ (Service Principal)    │
   │                        │                 │                        │
   │ client_credentials     │                 │ client_credentials     │
   │ grant → Bearer token   │                 │ grant → Bearer token   │
   └──────────────────────┘                 └────────────────────────┘
```

### 5.2 Token Validation (Server-Side Middleware)

Every request to the MCP server must include a valid Entra ID bearer token. The middleware validates:

| Check | Description | Failure Action |
|-------|-------------|----------------|
| Token presence | `Authorization: Bearer <token>` header required | 401 Unauthorized |
| Signature | Validated against Entra ID JWKS endpoint | 403 Forbidden |
| Issuer (`iss`) | Must match customer's tenant: `https://login.microsoftonline.com/{tenant-id}/v2.0` | 403 Forbidden |
| Audience (`aud`) | Must match MCP server's app registration client ID | 403 Forbidden |
| Expiry (`exp`) | Token must not be expired | 401 Unauthorized |
| App ID (`azp`/`appid`) | Must be in the server's allow list of approved client app IDs | 403 Forbidden |
| App Role | Caller must have `MCP.Tools.Invoke` role assigned | 403 Forbidden |

### 5.3 Managed Identity (Outbound)

The MCP server uses a **system-assigned Managed Identity** to authenticate to all backend services. No credentials are stored.

| Target Service | Role Assignment | Scope |
|----------------|-----------------|-------|
| Log Analytics Workspace | `Log Analytics Reader` | LAWS resource |
| Azure Key Vault | `Key Vault Secrets User` | Key Vault resource |
| Azure Container Registry | `AcrPull` | ACR resource |

### 5.4 Health Endpoint Exception

The `/health` and `/ready` endpoints are excluded from authentication to support:
- Azure Container Apps liveness/readiness probes
- Load balancer health checks

These endpoints return only a status code and a static JSON body — no data is exposed.

---

## 6. Authorization & Access Control

### 6.1 RBAC Model

```
┌─────────────────────────────────────────────────────────────┐
│ Entra ID App Registration: "AMS-SAP-MCP-Server"            │
│                                                              │
│  App Roles:                                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ MCP.Tools.Invoke                                     │   │
│  │   → Can invoke execute_query, deeper_rca_analysis,   │   │
│  │     run_full_rca                                     │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ MCP.Schema.Read                                      │   │
│  │   → Can invoke get_schema only                       │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ MCP.Admin                                            │   │
│  │   → Full access + configuration endpoints            │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Role Assignments

| Principal | Type | Assigned Role | Justification |
|-----------|------|---------------|---------------|
| Agent Orchestrator SP | Application | `MCP.Tools.Invoke` | Needs to run queries and RCA |
| SRE Automation SP | Application | `MCP.Tools.Invoke` | Automated incident response |
| Monitoring Dashboard SP | Application | `MCP.Schema.Read` | Only needs schema metadata |
| Platform Admin Group | User/Group | `MCP.Admin` | Configuration and management |

### 6.3 Principle of Least Privilege

- The MCP server's Managed Identity has **read-only** access to Log Analytics — it cannot write, delete, or purge data
- Each caller is restricted to the minimum role needed
- No wildcard permissions — all roles are explicitly scoped

---

## 7. Secrets Management

### 7.1 Secret Storage Strategy

| Secret | Storage Location | Access Method |
|--------|-----------------|---------------|
| LAWS Workspace ID | Azure Key Vault | Managed Identity → Key Vault Secrets User |
| Tenant ID | Azure Key Vault | Managed Identity → Key Vault Secrets User |
| MCP App Registration Client ID | Container App env var (non-secret) | Direct |
| Allowed Client IDs list | Container App env var (non-secret) | Direct |
| Service Principal credentials | **NOT USED** | Managed Identity replaces SP auth |

### 7.2 Key Vault Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| RBAC authorization | Enabled | No access policies — Entra ID RBAC only |
| Public network access | Disabled | Private Endpoint only |
| Soft delete | Enabled (90 days) | Accidental deletion recovery |
| Purge protection | Enabled | Prevent permanent secret loss |
| Diagnostic logging | Enabled → LAWS | Audit all secret access |

### 7.3 Secret Rotation

| Secret | Rotation Frequency | Mechanism |
|--------|-------------------|-----------|
| Managed Identity | Automatic | Azure-managed, no human intervention |
| Key Vault secrets | 90 days | Azure Key Vault auto-rotation policy |
| App Registration certificates | 12 months | Entra ID certificate rotation |

---

## 8. Data Protection

### 8.1 Encryption

| Layer | Mechanism | Standard |
|-------|-----------|----------|
| In transit (Agent → MCP) | TLS 1.2+ | Enforced by Container Apps |
| In transit (MCP → LAWS) | TLS 1.2+ | Enforced by Private Endpoint |
| At rest (LAWS data) | Azure-managed keys (default) or Customer-managed keys (CMK) | AES-256 |
| At rest (Key Vault) | HSM-backed encryption | FIPS 140-2 Level 2 |
| At rest (Audit logs) | Azure-managed keys or CMK | AES-256 |

### 8.2 Data Residency

- All data stays within the customer's Azure tenant
- The MCP server **does not store any query results** — data flows through and is returned to the caller
- Audit logs are written to the customer's own Log Analytics workspace or storage account
- No data is transmitted to Microsoft's tenant (the LLM receives only the structured findings, not raw LAWS data)

### 8.3 Data Classification

| Data Type | Classification | Handling |
|-----------|---------------|----------|
| KQL queries | Internal | Logged (hash only in audit) |
| Query results (SAP metrics) | Confidential | Not persisted; returned to caller |
| Schema metadata | Internal | Cached in memory; no PII |
| Audit logs | Internal | Immutable storage, 90-day retention |
| Authentication tokens | Restricted | Validated in memory; never logged |

---

## 9. Query Safety & Input Validation

### 9.1 KQL Query Guard

Every KQL query submitted to the MCP server is validated before execution:

| Rule | Pattern Blocked | Risk Mitigated |
|------|----------------|----------------|
| No destructive operations | `.drop`, `.delete`, `.purge` | Data loss |
| No write operations | `.set`, `.append`, `.set-or-append` | Data tampering |
| No external data access | `externaldata()` | Data exfiltration |
| No resource exhaustion | Unbounded `materialize()` | DoS |
| Row cap enforcement | Auto-inject `take` if missing | Resource abuse |
| Time window limit | Max 168 hours (7 days) | Excessive data scan |

### 9.2 Rate Limiting

| Limit | Value | Scope |
|-------|-------|-------|
| Requests per minute | 30 | Per caller identity (appid) |
| Concurrent queries | 5 | Per caller identity |
| Max rows per query | 5,000 | Global |
| Query timeout | 90 seconds | Per query |

### 9.3 Input Sanitization

- KQL strings are passed directly to the Azure Monitor Query SDK — **no string interpolation or concatenation** with user inputs
- SID parameter is validated against alphanumeric pattern: `^[A-Z0-9]{2,5}$`
- Workspace ID is validated as GUID format or ARM resource ID pattern
- `analysis_type` is validated against a fixed enum of allowed values

---

## 10. Audit, Logging & Monitoring

### 10.1 Audit Log Schema

Every MCP tool invocation generates a structured audit record:

```json
{
  "timestamp": "2026-07-26T14:30:00.000Z",
  "event": "tool_invocation",
  "tool": "execute_query",
  "caller_oid": "a1b2c3d4-...",
  "caller_app": "agent-orchestrator-app-id",
  "caller_ip": "10.0.4.15",
  "parameters": {
    "sid": "CHA",
    "timespan_hours": 24,
    "analysis_type": "availability"
  },
  "kql_hash": "sha256:e3b0c44298fc...",
  "result_rows": 42,
  "duration_ms": 1250,
  "status": "success",
  "query_guard_violations": []
}
```

### 10.2 Log Destinations

| Log Type | Destination | Retention |
|----------|-------------|-----------|
| Audit logs (tool invocations) | Customer LAWS / Sentinel | 90 days (configurable) |
| Authentication failures | Customer LAWS / Sentinel | 90 days |
| Query guard violations | Customer LAWS / Sentinel + Alert | 90 days |
| Container stdout/stderr | ACA-managed LAWS | 30 days |
| Key Vault access logs | Customer LAWS | 90 days |
| NSG flow logs | Customer Storage Account | 30 days |

### 10.3 Alerting Rules

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| Auth failure spike | > 10 failed auth attempts in 5 min | High | Notify SOC |
| Query guard violation | Any blocked query detected | Medium | Notify SOC + log caller |
| Rate limit exceeded | Caller hits rate limit | Low | Log + throttle |
| MCP server unhealthy | Health probe fails for > 2 min | Critical | Auto-restart + notify |
| Unusual query volume | > 3x baseline in 15 min | Medium | Notify ops |

### 10.4 Microsoft Sentinel Integration

For customers using Microsoft Sentinel, audit logs can be ingested via:
1. **Diagnostic Settings** on the Container App → LAWS
2. **Custom log table** (`MCPAudit_CL`) for structured tool invocation records
3. **Analytic Rules** for detecting suspicious patterns (e.g., repeated query guard violations from a single caller)

---

## 11. Container & Supply Chain Security

### 11.1 Container Hardening

| Control | Implementation | Rationale |
|---------|---------------|-----------|
| Non-root execution | `USER mcpuser` in Dockerfile | Prevent container escape privilege escalation |
| Read-only filesystem | `--read-only` + tmpfs for `/tmp` | Prevent runtime binary modification |
| No capabilities | Drop all Linux capabilities | Minimize attack surface |
| Minimal base image | `python:3.11-slim` | Reduce CVE surface |
| No shell (optional) | Distroless variant for production | Prevent interactive exploitation |

### 11.2 Image Security

| Control | Tool | Frequency |
|---------|------|-----------|
| Vulnerability scanning | Microsoft Defender for Containers | Every push + daily |
| Base image updates | Dependabot / Renovate | Weekly |
| Dependency pinning | `requirements-lock.txt` with hashes | Every build |
| Image signing | Notation (Notary v2) | Every push |
| Admission control | Azure Policy on ACA | Every deployment |

### 11.3 Secure Dockerfile

```dockerfile
FROM python:3.11-slim AS base

# Non-root user
RUN groupadd -r mcpuser && useradd --no-log-init -r -g mcpuser mcpuser

WORKDIR /app

# Pin dependencies with hashes
COPY requirements-lock.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements-lock.txt

COPY --chown=mcpuser:mcpuser . .

USER mcpuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

CMD ["python", "run_server.py"]
```

---

## 12. Cross-Tenant Access Model

### 12.1 Microsoft Tenant → Customer Tenant

The Agent Platform Control Plane in Microsoft's tenant manages deployments but **does not access customer data**. Access is controlled via:

```
┌─────────── Microsoft Tenant ───────────┐     ┌─────────── Customer Tenant ──────────┐
│                                         │     │                                       │
│  Platform Control Plane                 │     │  Cross-Tenant Access Policy            │
│  (Multi-tenant App Registration)        │────►│  ┌─────────────────────────────────┐  │
│                                         │     │  │ Allowed: Microsoft Platform App  │  │
│  Actions:                               │     │  │ Scope: Deployment only           │  │
│  - Deploy/update MCP container          │     │  │ No data-plane access             │  │
│  - Push agent configurations            │     │  └─────────────────────────────────┘  │
│  - Read health/readiness status         │     │                                       │
│                                         │     │  MCP Server App Registration           │
│  Cannot:                                │     │  (Single-tenant: "AzureADMyOrg")      │
│  - Invoke MCP tools                     │     │  - Only customer tenant identities     │
│  - Read query results                   │     │    can invoke tools                    │
│  - Access LAWS data                     │     │                                       │
└─────────────────────────────────────────┘     └───────────────────────────────────────┘
```

### 12.2 App Registration Settings

| Setting | Value | Rationale |
|---------|-------|-----------|
| Supported account types | "Accounts in this organizational directory only" (`AzureADMyOrg`) | No external tenant can invoke tools |
| App roles | `MCP.Tools.Invoke`, `MCP.Schema.Read`, `MCP.Admin` | Granular authorization |
| API permissions | None (server-side only) | MCP server doesn't call external APIs |
| Token version | v2.0 | Modern Entra ID token format |

---

## 13. Deployment Security Controls

### 13.1 Infrastructure-as-Code Security

| Control | Implementation |
|---------|---------------|
| No secrets in IaC scripts | All secrets in Key Vault; deployment scripts reference Key Vault |
| Parameterized deployments | Subscription, resource group, names are parameters |
| RBAC for deployment | Only platform admins can run deployment scripts |
| State protection | ACA manages state; no Terraform state file exposure |

### 13.2 CI/CD Pipeline Security

| Stage | Security Control |
|-------|-----------------|
| Source | Branch protection; signed commits; PR reviews |
| Build | Pinned dependencies with hash verification |
| Scan | Defender for Containers image scan; SAST (CodeQL/Semgrep) |
| Sign | Image signed with Notation before push to ACR |
| Deploy | ACR → ACA via Managed Identity (AcrPull); no admin credentials |
| Verify | Post-deploy health check; smoke test against `/health` |

### 13.3 Environment Separation

| Environment | Purpose | Network | Auth |
|-------------|---------|---------|------|
| Dev | Development & testing | Separate VNet or peered subnet | Dev Entra ID app |
| Staging | Pre-production validation | Customer VNet (isolated subnet) | Staging Entra ID app |
| Production | Live customer deployment | Customer VNet (production subnet) | Production Entra ID app |

---

## 14. Compliance Alignment

### 14.1 Framework Mapping

| Security Control | SOC 2 | ISO 27001 | NIST 800-53 | CIS |
|-----------------|-------|-----------|-------------|-----|
| Entra ID authentication | CC6.1 | A.9.4.1 | IA-2, IA-8 | 16.2 |
| RBAC authorization | CC6.3 | A.9.4.1 | AC-3, AC-6 | 16.7 |
| VNet isolation | CC6.6 | A.13.1.1 | SC-7 | 12.1 |
| TLS encryption | CC6.7 | A.10.1.1 | SC-8, SC-13 | 14.4 |
| Audit logging | CC7.2 | A.12.4.1 | AU-2, AU-3 | 8.2 |
| Key Vault secrets | CC6.7 | A.10.1.2 | SC-12, SC-28 | 14.8 |
| Query safety validation | CC6.1 | A.14.2.5 | SI-10 | 16.5 |
| Container hardening | CC6.8 | A.12.6.1 | CM-7, SI-3 | 5.1 |

---

## 15. Security Checklist

### Mandatory (Must-Have for Production)

| # | Control | Category | Owner | Status |
|---|---------|----------|-------|--------|
| 1 | VNet-injected Container Apps with `--internal-only` ingress | Network | Platform | ☐ |
| 2 | Private Endpoints for LAWS, Key Vault, ACR | Network | Platform | ☐ |
| 3 | NSG rules restricting inbound to agent subnet only | Network | Platform | ☐ |
| 4 | Internet egress blocked (except Entra ID service tag) | Network | Platform | ☐ |
| 5 | Entra ID app registration (single-tenant, `AzureADMyOrg`) | Identity | Security | ☐ |
| 6 | OAuth2 bearer token validation middleware | Identity | Dev | ☐ |
| 7 | App Role enforcement (`MCP.Tools.Invoke`) | AuthZ | Dev | ☐ |
| 8 | Allowed client app ID allow-list | AuthZ | Security | ☐ |
| 9 | System-assigned Managed Identity for LAWS, KV, ACR | Identity | Platform | ☐ |
| 10 | Key Vault for all secrets (RBAC mode, private endpoint) | Secrets | Platform | ☐ |
| 11 | KQL query guard (block write/delete/externaldata) | Data | Dev | ☐ |
| 12 | Row cap and time window enforcement | Data | Dev | ☐ |
| 13 | Rate limiting per caller identity | Data | Dev | ☐ |
| 14 | Structured audit logging (every tool invocation) | Audit | Dev | ☐ |
| 15 | TLS 1.2+ enforced on all connections | Encryption | Platform | ☐ |
| 16 | Non-root container execution | Container | Dev | ☐ |
| 17 | Pinned dependencies with hash verification | Supply Chain | Dev | ☐ |
| 18 | Defender for Containers enabled | Container | Security | ☐ |

### Recommended (Should-Have)

| # | Control | Category | Owner | Status |
|---|---------|----------|-------|--------|
| 19 | mTLS between Agent Orchestrator and MCP Server | Network | Platform | ☐ |
| 20 | Image signing with Notation (Notary v2) | Supply Chain | Dev | ☐ |
| 21 | Microsoft Sentinel integration with analytic rules | Monitoring | Security | ☐ |
| 22 | Customer-managed keys (CMK) for LAWS and audit storage | Encryption | Security | ☐ |
| 23 | NSG flow logs enabled and analyzed | Monitoring | Platform | ☐ |
| 24 | Azure Policy for ACA (enforce signed images, no public ingress) | Governance | Platform | ☐ |

### Optional (Nice-to-Have)

| # | Control | Category | Owner | Status |
|---|---------|----------|-------|--------|
| 25 | WAF (Azure Front Door) if any external gateway needed | Network | Platform | ☐ |
| 26 | Distroless container image | Container | Dev | ☐ |
| 27 | DAST scanning of MCP endpoints | Testing | Security | ☐ |
| 28 | Penetration testing on MCP server | Testing | Security | ☐ |

---

## Appendix A — Reference Implementation Snippets

### A.1 Entra ID Authentication Middleware

```python
"""auth_middleware.py — Entra ID token validation for MCP server."""

import os
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import jwt
from jwt import PyJWKClient

TENANT_ID = os.environ["AZURE_TENANT_ID"]
ALLOWED_CLIENT_IDS = set(os.environ.get("ALLOWED_CLIENT_IDS", "").split(","))
MCP_APP_CLIENT_ID = os.environ["MCP_APP_CLIENT_ID"]
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"

jwks_client = PyJWKClient(JWKS_URL, cache_keys=True)


class EntraIDAuthMiddleware(BaseHTTPMiddleware):
    """Validates Entra ID bearer tokens on every request."""

    SKIP_PATHS = {"/health", "/ready"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        token = self._extract_token(request)
        if not token:
            return JSONResponse({"error": "Missing Authorization header"}, status_code=401)

        claims = self._validate_token(token)
        if not claims:
            return JSONResponse({"error": "Invalid or expired token"}, status_code=403)

        request.state.caller_identity = claims.get("azp") or claims.get("appid")
        request.state.caller_oid = claims.get("oid")
        return await call_next(request)

    def _extract_token(self, request: Request) -> Optional[str]:
        auth = request.headers.get("Authorization", "")
        return auth[7:] if auth.startswith("Bearer ") else None

    def _validate_token(self, token: str) -> Optional[dict]:
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=ISSUER,
                audience=MCP_APP_CLIENT_ID,
                options={"require": ["exp", "iss", "aud", "oid"]},
            )
            caller_app = claims.get("azp") or claims.get("appid")
            if caller_app not in ALLOWED_CLIENT_IDS:
                return None
            return claims
        except (jwt.InvalidTokenError, Exception):
            return None
```

### A.2 Query Guard

```python
"""query_guard.py — Enterprise KQL safety validation."""

import re
import hashlib
from collections import defaultdict
from time import time

BLOCKED_PATTERNS = [
    r"\.drop\s", r"\.delete\s", r"\.purge\s",
    r"\.set\s", r"\.append\s", r"\.set-or-append",
    r"\.create\s", r"\.alter\s", r"\.rename\s",
    r"externaldata\s*\(", r"external_table\s*\(",
]
MAX_TIMESPAN_HOURS = 168
MAX_ROWS = 5000
RATE_LIMIT_PER_MINUTE = 30

_call_counts: dict[str, list[float]] = defaultdict(list)


def validate_query(kql: str, timespan_hours: int, caller_id: str) -> list[str]:
    violations = []
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, kql, re.IGNORECASE):
            violations.append(f"Blocked operation: {pattern}")
    if timespan_hours and timespan_hours > MAX_TIMESPAN_HOURS:
        violations.append(f"Timespan {timespan_hours}h exceeds max {MAX_TIMESPAN_HOURS}h")
    now = time()
    _call_counts[caller_id] = [t for t in _call_counts[caller_id] if now - t < 60]
    if len(_call_counts[caller_id]) >= RATE_LIMIT_PER_MINUTE:
        violations.append("Rate limit exceeded")
    else:
        _call_counts[caller_id].append(now)
    return violations


def hash_kql(kql: str) -> str:
    return hashlib.sha256(kql.encode()).hexdigest()
```

### A.3 Audit Logger

```python
"""audit_logger.py — Structured audit logging for compliance."""

import json
import logging
from datetime import datetime, timezone

audit_logger = logging.getLogger("mcp.audit")
audit_logger.setLevel(logging.INFO)


def log_tool_invocation(
    tool_name: str,
    caller_oid: str,
    caller_app: str,
    caller_ip: str,
    params: dict,
    result_rows: int,
    duration_ms: float,
    status: str,
    violations: list[str] | None = None,
):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "tool_invocation",
        "tool": tool_name,
        "caller_oid": caller_oid,
        "caller_app": caller_app,
        "caller_ip": caller_ip,
        "parameters": {k: v for k, v in params.items() if k != "kql"},
        "kql_hash": params.get("_kql_hash", ""),
        "result_rows": result_rows,
        "duration_ms": round(duration_ms, 2),
        "status": status,
        "query_guard_violations": violations or [],
    }
    audit_logger.info(json.dumps(record))
```

### A.4 Deployment Script — Enterprise Security Additions

```powershell
# === VNet-injected, internal-only deployment ===

# Create VNet and subnets
az network vnet create --name $VNET_NAME --resource-group $RG --location $LOCATION `
    --address-prefix "10.0.0.0/16"
az network vnet subnet create --name "subnet-aca-infra" --vnet-name $VNET_NAME `
    --resource-group $RG --address-prefixes "10.0.1.0/23"
az network vnet subnet create --name "subnet-private-eps" --vnet-name $VNET_NAME `
    --resource-group $RG --address-prefixes "10.0.3.0/24"

# Container Apps Environment with VNet injection
$INFRA_SUBNET_ID = az network vnet subnet show --name "subnet-aca-infra" `
    --vnet-name $VNET_NAME --resource-group $RG --query "id" -o tsv

az containerapp env create `
    --name $ACA_ENV_NAME --resource-group $RG --location $LOCATION `
    --infrastructure-subnet-resource-id $INFRA_SUBNET_ID `
    --internal-only true

# Container App with internal ingress only
az containerapp create `
    --name $ACA_APP_NAME --resource-group $RG --environment $ACA_ENV_NAME `
    --image $FULL_IMAGE --registry-server $ACR_LOGIN_SERVER `
    --registry-identity system --target-port 8000 `
    --ingress internal `          # NOT external
    --min-replicas 1 --max-replicas 5 `
    --cpu 1.0 --memory 2Gi `
    --system-assigned `
    --env-vars `
        "AZURE_KEYVAULT_URL=$KV_URL" `
        "MCP_APP_CLIENT_ID=$MCP_APP_ID" `
        "ALLOWED_CLIENT_IDS=$AGENT_ORCH_APP_ID" `
    --output none

# Private Endpoint for Log Analytics
az network private-endpoint create `
    --name "pe-laws-mcp" --resource-group $RG `
    --vnet-name $VNET_NAME --subnet "subnet-private-eps" `
    --private-connection-resource-id $LA_WORKSPACE_RESOURCE_ID `
    --group-ids "azuremonitor" --connection-name "mcp-to-laws"

# Key Vault with Private Endpoint
az keyvault create --name $KV_NAME --resource-group $RG --location $LOCATION `
    --enable-rbac-authorization true --public-network-access Disabled
az network private-endpoint create `
    --name "pe-kv-mcp" --resource-group $RG `
    --vnet-name $VNET_NAME --subnet "subnet-private-eps" `
    --private-connection-resource-id $KV_RESOURCE_ID `
    --group-ids "vault" --connection-name "mcp-to-kv"
```

---

*End of Document — Version 1.0 DRAFT*
