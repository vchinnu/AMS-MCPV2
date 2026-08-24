"""Generate the Security HLD Word document for the SAP RCA MCP Server."""

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import os

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "SAP_RCA_MCP_Server_Security_HLD.docx")

# ── Colour palette ──────────────────────────────────────────────────────────
BLUE_DARK  = RGBColor(0x00, 0x33, 0x66)
BLUE_MED   = RGBColor(0x00, 0x70, 0xC0)
BLUE_LIGHT = RGBColor(0xD6, 0xE4, 0xF0)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
BLACK      = RGBColor(0x00, 0x00, 0x00)
GREY_LIGHT = RGBColor(0xF2, 0xF2, 0xF2)
RED        = RGBColor(0xC0, 0x00, 0x00)
GREEN      = RGBColor(0x00, 0x70, 0x00)

doc = Document()

# ── Page setup ──────────────────────────────────────────────────────────────
for section in doc.sections:
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

# ── Style helpers ───────────────────────────────────────────────────────────
style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(10.5)
style.paragraph_format.space_after = Pt(6)

for level in range(1, 5):
    hs = doc.styles[f"Heading {level}"]
    hs.font.name = "Calibri"
    hs.font.color.rgb = BLUE_DARK
    if level == 1:
        hs.font.size = Pt(18)
        hs.font.bold = True
    elif level == 2:
        hs.font.size = Pt(14)
        hs.font.bold = True
    elif level == 3:
        hs.font.size = Pt(12)
        hs.font.bold = True
    else:
        hs.font.size = Pt(11)
        hs.font.bold = True


def add_table(headers, rows, col_widths=None, header_color="003366"):
    """Add a formatted table."""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"

    # Header row
    hdr = table.rows[0]
    for i, h in enumerate(headers):
        cell = hdr.cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(h)
        run.bold = True
        run.font.color.rgb = WHITE
        run.font.size = Pt(10)
        run.font.name = "Calibri"
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{header_color}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

    # Data rows
    for r_idx, row_data in enumerate(rows):
        row = table.rows[r_idx + 1]
        bg = "F2F2F2" if r_idx % 2 == 0 else "FFFFFF"
        for c_idx, val in enumerate(row_data):
            cell = row.cells[c_idx]
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(str(val))
            run.font.size = Pt(9.5)
            run.font.name = "Calibri"
            shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg}"/>')
            cell._tc.get_or_add_tcPr().append(shading)

    # Column widths
    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Cm(w)

    doc.add_paragraph("")  # spacer
    return table


def add_code_block(code_text):
    """Add a formatted code block."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.left_indent = Cm(0.5)
    run = p.add_run(code_text)
    run.font.name = "Consolas"
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(0x1E, 0x1E, 0x1E)
    # Light grey background via shading on the paragraph
    pPr = p._p.get_or_add_pPr()
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F5F5F5" w:val="clear"/>')
    pPr.append(shading)


def add_bullet(text, bold_prefix=""):
    """Add a bullet point."""
    p = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        run_b = p.add_run(bold_prefix)
        run_b.bold = True
        run_b.font.size = Pt(10.5)
        run_b.font.name = "Calibri"
        p.add_run(text)
    else:
        p.text = text


def add_note(text, label="Note"):
    """Add a highlighted note."""
    p = doc.add_paragraph()
    run_label = p.add_run(f"{label}: ")
    run_label.bold = True
    run_label.font.color.rgb = BLUE_MED
    run_label.font.size = Pt(10)
    run_label.font.name = "Calibri"
    run_text = p.add_run(text)
    run_text.font.size = Pt(10)
    run_text.font.name = "Calibri"


# ═══════════════════════════════════════════════════════════════════════════
#  TITLE PAGE
# ═══════════════════════════════════════════════════════════════════════════
doc.add_paragraph("\n\n\n")

title_p = doc.add_paragraph()
title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title_p.add_run("SAP RCA MCP Server")
run.bold = True
run.font.size = Pt(28)
run.font.color.rgb = BLUE_DARK
run.font.name = "Calibri"

subtitle_p = doc.add_paragraph()
subtitle_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = subtitle_p.add_run("Security High-Level Design (HLD)")
run.font.size = Pt(20)
run.font.color.rgb = BLUE_MED
run.font.name = "Calibri"

doc.add_paragraph("")

add_table(
    ["Property", "Value"],
    [
        ["Document Type", "Security High-Level Design"],
        ["Version", "1.0"],
        ["Date", "July 2026"],
        ["Status", "DRAFT — For Team Review"],
        ["Component", "AMS SAP MCP Server (Managed MCP Server)"],
        ["Classification", "Internal — Microsoft Confidential"],
    ],
    col_widths=[6, 10],
)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
#  TABLE OF CONTENTS (placeholder)
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("Table of Contents", level=1)
toc_items = [
    "1.  Executive Summary",
    "2.  Architecture Overview",
    "3.  Threat Model (STRIDE Analysis)",
    "4.  Network Security",
    "5.  Identity & Authentication",
    "6.  Authorization & Access Control",
    "7.  Secrets Management",
    "8.  Data Protection",
    "9.  Query Safety & Input Validation",
    "10. Audit, Logging & Monitoring",
    "11. Container & Supply Chain Security",
    "12. Cross-Tenant Access Model",
    "13. Deployment Security Controls",
    "14. Compliance Alignment",
    "15. Security Checklist",
    "Appendix A — Reference Implementation Snippets",
]
for item in toc_items:
    p = doc.add_paragraph(item)
    p.paragraph_format.space_after = Pt(2)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
#  1. EXECUTIVE SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("1. Executive Summary", level=1)

doc.add_paragraph(
    "The SAP RCA MCP Server is an enterprise-grade Model Context Protocol (MCP) server "
    "that provides SAP observability and root-cause-analysis capabilities to AI agents. "
    "It is deployed within the customer's Azure tenant and VNet boundaries, connecting to "
    "customer-owned data sources (Azure Log Analytics Workspaces) and invoked by agent "
    "orchestrators running inside the same network perimeter."
)

doc.add_paragraph("This document defines the security controls required for enterprise deployment, ensuring:")
add_bullet("Zero public internet exposure — all traffic stays within the customer's VNet")
add_bullet("Entra ID–based authentication — every request is validated against the customer's identity provider")
add_bullet("Managed Identity for backend access — no stored credentials for data-source connectivity")
add_bullet("Read-only data access — the server can never modify, delete, or exfiltrate customer data")
add_bullet("Full audit trail — every tool invocation is logged for compliance and forensics")

doc.add_heading("1.1 Scope", level=2)
add_table(
    ["In Scope", "Out of Scope"],
    [
        ["MCP Server (Container App)", "Agent Orchestrator internals"],
        ["Network perimeter (VNet, Private Endpoints)", "LLM model security"],
        ["Authentication & authorization middleware", "Agent Platform Control Plane (Microsoft Tenant)"],
        ["Data-source connectivity (LAWS)", "Customer application layer"],
        ["Audit logging pipeline", "SOC/SIEM operations"],
    ],
    col_widths=[8, 8],
)

# ═══════════════════════════════════════════════════════════════════════════
#  2. ARCHITECTURE OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("2. Architecture Overview", level=1)

doc.add_heading("2.1 Deployment Context", level=2)
doc.add_paragraph(
    "The MCP server is deployed as an Azure Container App within the customer's VNet. "
    "All communication occurs over private network paths using Private Endpoints. "
    "The following diagram shows the deployment topology:"
)

arch_diagram = """
┌──────────────────────────── Customer Tenant ─────────────────────────────┐
│                                                                          │
│   ┌────────────────────────── Customer VNet ──────────────────────────┐  │
│   │                                                                   │  │
│   │   User ──► Agent Client ──► Agent Orchestrator                   │  │
│   │                                    │                              │  │
│   │                                    ▼ (Entra ID token)            │  │
│   │            ┌─────── MCP Servers ────────────────────────┐        │  │
│   │            │  ┌─────────────────┐  ┌────────────────┐  │        │  │
│   │            │  │ AMS SAP MCP     │  │ Other MCP      │  │        │  │
│   │            │  │ [Auth Middleware]│  │ Servers        │  │        │  │
│   │            │  │ [Query Guard]   │  │                │  │        │  │
│   │            │  │ [MCP Tools]     │  │                │  │        │  │
│   │            │  │ [Audit Logger]  │  │                │  │        │  │
│   │            │  └────────┬────────┘  └────────────────┘  │        │  │
│   │            └───────────┼───────────────────────────────┘        │  │
│   │                        │ Private Endpoint                       │  │
│   │                        ▼                                        │  │
│   │   ┌─────────────────────────────────────────────────────────┐   │  │
│   │   │ Data Sources: AMS LAWS │ Key Vault │ Container Registry │   │  │
│   │   └─────────────────────────────────────────────────────────┘   │  │
│   └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│   ┌─── Telemetry ────┐    ┌──── Knowledge Base ────┐                 │
│   │ Audit / Sentinel  │    │ Domain Knowledge DB    │                 │
│   └──────────────────┘    └────────────────────────┘                 │
└───────────────────────────────────────────────────────────────────────┘
          ▲ Cross-Tenant (Entra ID multi-tenant app)
┌─────────┴─────────── Microsoft Tenant ────────────────────────────────┐
│   Agent Platform Control Plane  │  Managed LLM (Azure OpenAI)         │
└───────────────────────────────────────────────────────────────────────┘
"""
add_code_block(arch_diagram.strip())

doc.add_heading("2.2 Data Flow Summary", level=2)
add_table(
    ["Step", "From", "To", "Protocol", "Auth Mechanism"],
    [
        ["1.a", "User", "Agent Client Layer", "HTTPS", "User identity (Entra ID SSO)"],
        ["2.a", "Agent Client", "Agent Orchestrator", "HTTPS", "Entra ID token (delegated)"],
        ["3.a", "Orchestrator", "SAP Agent", "Internal", "Agent runtime session"],
        ["4.a", "SAP Agent", "AMS SAP MCP Server", "HTTPS (internal)", "Entra ID app token (client_credentials)"],
        ["5", "MCP Server", "AMS LAWS", "HTTPS (PE)", "Managed Identity"],
        ["5", "MCP Server", "Key Vault", "HTTPS (PE)", "Managed Identity"],
    ],
    col_widths=[1.5, 3, 3.5, 3, 5],
)

# ═══════════════════════════════════════════════════════════════════════════
#  3. THREAT MODEL
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("3. Threat Model", level=1)

doc.add_heading("3.1 STRIDE Analysis", level=2)
doc.add_paragraph(
    "The following STRIDE analysis identifies the key threats to the MCP server "
    "and the corresponding mitigations:"
)

add_table(
    ["Threat", "STRIDE Category", "Risk", "Mitigation"],
    [
        ["Unauthorized agent invokes MCP tools", "Spoofing", "High",
         "Entra ID token validation; allow-listed client app IDs only"],
        ["Attacker crafts malicious KQL to delete data", "Tampering", "Critical",
         "Query guard blocks all write/delete/purge operations"],
        ["Agent sends KQL to exfiltrate data via externaldata()", "Information Disclosure", "High",
         "Block externaldata operator; VNet-only egress"],
        ["MCP server overwhelmed by excessive queries", "Denial of Service", "Medium",
         "Rate limiting per caller identity; row caps; timeout enforcement"],
        ["Tool invocations not logged", "Repudiation", "Medium",
         "Structured audit logging to immutable storage"],
        ["Man-in-the-middle intercepts agent-to-MCP traffic", "Information Disclosure", "Medium",
         "TLS 1.2+ enforced; VNet-internal traffic; optional mTLS"],
        ["Container image contains vulnerable packages", "Elevation of Privilege", "Medium",
         "Defender for Containers; base image scanning; non-root runtime"],
    ],
    col_widths=[4.5, 2.5, 1.5, 7.5],
)

doc.add_heading("3.2 Trust Boundaries", level=2)
doc.add_paragraph("Validation occurs at every boundary crossing:")
add_bullet("Boundary 1 (Customer VNet) → NSG rules, Private Endpoints", bold_prefix="Network: ")
add_bullet("Boundary 2 (Container Apps Environment) → Entra ID token validation in auth middleware", bold_prefix="Identity: ")
add_bullet("Boundary 3 (MCP Server Container) → KQL query safety validation, rate limiting, audit logging", bold_prefix="Application: ")

trust_diagram = """Trust Boundaries:

 ┌──────────────────────────────────────────────────────────┐
 │  Boundary 1: Customer VNet                               │
 │   ┌──────────────────────────────────────────────────┐   │
 │   │  Boundary 2: Container Apps Environment           │   │
 │   │   ┌──────────────────────────────────────────┐   │   │
 │   │   │  Boundary 3: MCP Server Container         │   │   │
 │   │   │   ┌──────────────────────────────────┐   │   │   │
 │   │   │   │  Auth Middleware (validates tokens) │   │   │   │
 │   │   │   ├──────────────────────────────────┤   │   │   │
 │   │   │   │  Query Guard (validates KQL)      │   │   │   │
 │   │   │   ├──────────────────────────────────┤   │   │   │
 │   │   │   │  MCP Tools (business logic)       │   │   │   │
 │   │   │   └──────────────────────────────────┘   │   │   │
 │   │   └──────────────────────────────────────────┘   │   │
 │   └──────────────────────────────────────────────────┘   │
 └──────────────────────────────────────────────────────────┘"""
add_code_block(trust_diagram)

# ═══════════════════════════════════════════════════════════════════════════
#  4. NETWORK SECURITY
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("4. Network Security", level=1)

doc.add_heading("4.1 VNet Integration (Mandatory)", level=2)
doc.add_paragraph(
    "The Container Apps Environment must be deployed with VNet injection and internal-only "
    "ingress. No public IP address is assigned. All backend services are accessed exclusively "
    "via Private Endpoints."
)

subnet_diagram = """Customer VNet (e.g. 10.0.0.0/16)
 ├── subnet-aca-infra     (10.0.1.0/23)  — Container Apps Environment (delegated)
 ├── subnet-private-eps   (10.0.3.0/24)  — Private Endpoints (LAWS, Key Vault, ACR)
 └── subnet-agents        (10.0.4.0/24)  — Agent Orchestrator / compute"""
add_code_block(subnet_diagram)

add_table(
    ["Setting", "Value", "Rationale"],
    [
        ["Container Apps ingress", "internal", "No public internet access"],
        ["VNet injection", "Required", "All traffic stays within VNet"],
        ["ACA infrastructure subnet", "/23 minimum", "Azure requirement for ACA"],
        ["Private Endpoints", "LAWS, Key Vault, ACR", "All backend access over private network"],
    ],
    col_widths=[4, 4, 8],
)

doc.add_heading("4.2 Network Security Groups (NSGs)", level=2)
doc.add_paragraph("The following NSG rules must be applied to control traffic flow:")

add_table(
    ["Rule", "Direction", "Source", "Destination", "Port", "Action"],
    [
        ["Allow Agent → MCP", "Inbound", "subnet-agents", "subnet-aca-infra", "443", "Allow"],
        ["Allow MCP → LAWS PE", "Outbound", "subnet-aca-infra", "subnet-private-eps", "443", "Allow"],
        ["Allow MCP → KV PE", "Outbound", "subnet-aca-infra", "subnet-private-eps", "443", "Allow"],
        ["Allow MCP → Entra ID", "Outbound", "subnet-aca-infra", "AzureActiveDirectory", "443", "Allow"],
        ["Deny all other inbound", "Inbound", "*", "subnet-aca-infra", "*", "DENY"],
        ["Deny all other outbound", "Outbound", "subnet-aca-infra", "Internet", "*", "DENY"],
    ],
    col_widths=[3.5, 1.8, 3, 3, 1, 1.2],
)

doc.add_heading("4.3 DNS Configuration", level=2)
add_table(
    ["Private DNS Zone", "Purpose"],
    [
        ["privatelink.oms.opinsights.azure.com", "Log Analytics Private Link"],
        ["privatelink.vaultcore.azure.net", "Key Vault Private Link"],
        ["privatelink.azurecr.io", "Container Registry Private Link"],
        ["Custom Private DNS Zone", "Internal ACA endpoint resolution"],
    ],
    col_widths=[8, 8],
)

doc.add_heading("4.4 Egress Lockdown", level=2)
doc.add_paragraph("All outbound traffic from the MCP server is restricted to:")
add_bullet("Private Endpoints (LAWS, Key Vault, ACR) — via VNet routing")
add_bullet("Entra ID endpoints (login.microsoftonline.com) — via Service Tag")
add_bullet("No general internet egress — prevents data exfiltration", bold_prefix="Critical: ")

# ═══════════════════════════════════════════════════════════════════════════
#  5. IDENTITY & AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("5. Identity & Authentication", level=1)

doc.add_heading("5.1 Authentication Layers", level=2)
doc.add_paragraph(
    "The MCP server uses a multi-layer authentication model. Inbound requests are "
    "authenticated via Entra ID bearer tokens. Outbound connections to backend services "
    "use Managed Identity — no credentials are stored."
)

auth_diagram = """
                     Entra ID (Customer Tenant)
                     App Registration: "AMS-SAP-MCP-Server"
                     ┌─────────────────────────────────┐
                     │  App Roles:                      │
                     │    MCP.Tools.Invoke              │
                     │    MCP.Schema.Read               │
                     │    MCP.Admin                     │
                     └──────────┬──────────┬────────────┘
                                │          │
                 ┌──────────────┘          └──────────────┐
                 ▼                                         ▼
      Agent Orchestrator (SP)              SRE Automation Scripts (SP)
      client_credentials grant             client_credentials grant
      → Bearer token                       → Bearer token
"""
add_code_block(auth_diagram.strip())

doc.add_heading("5.2 Token Validation (Server-Side Middleware)", level=2)
doc.add_paragraph(
    "Every request to the MCP server must include a valid Entra ID bearer token. "
    "The middleware validates the following claims:"
)

add_table(
    ["Check", "Description", "Failure Action"],
    [
        ["Token presence", "Authorization: Bearer <token> header required", "401 Unauthorized"],
        ["Signature", "Validated against Entra ID JWKS endpoint", "403 Forbidden"],
        ["Issuer (iss)", "Must match customer tenant: https://login.microsoftonline.com/{tenant-id}/v2.0", "403 Forbidden"],
        ["Audience (aud)", "Must match MCP server's app registration client ID", "403 Forbidden"],
        ["Expiry (exp)", "Token must not be expired", "401 Unauthorized"],
        ["App ID (azp/appid)", "Must be in the server's allow list of approved client app IDs", "403 Forbidden"],
        ["App Role", "Caller must have MCP.Tools.Invoke role assigned", "403 Forbidden"],
    ],
    col_widths=[3, 8, 3],
)

doc.add_heading("5.3 Managed Identity (Outbound)", level=2)
doc.add_paragraph(
    "The MCP server uses a system-assigned Managed Identity to authenticate to all "
    "backend services. No credentials are stored anywhere."
)

add_table(
    ["Target Service", "Role Assignment", "Scope"],
    [
        ["Log Analytics Workspace", "Log Analytics Reader", "LAWS resource"],
        ["Azure Key Vault", "Key Vault Secrets User", "Key Vault resource"],
        ["Azure Container Registry", "AcrPull", "ACR resource"],
    ],
    col_widths=[5, 5, 5],
)

doc.add_heading("5.4 Health Endpoint Exception", level=2)
doc.add_paragraph(
    "The /health and /ready endpoints are excluded from authentication to support "
    "Azure Container Apps liveness/readiness probes and load balancer health checks. "
    "These endpoints return only a status code and a static JSON body — no data is exposed."
)

# ═══════════════════════════════════════════════════════════════════════════
#  6. AUTHORIZATION & ACCESS CONTROL
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("6. Authorization & Access Control", level=1)

doc.add_heading("6.1 RBAC Model", level=2)
doc.add_paragraph(
    "The MCP server's Entra ID app registration defines granular app roles "
    "that control what each caller can do:"
)

add_table(
    ["App Role", "Permissions", "Intended For"],
    [
        ["MCP.Tools.Invoke", "Can invoke execute_query, deeper_rca_analysis, run_full_rca", "Agent Orchestrator, SRE Automation"],
        ["MCP.Schema.Read", "Can invoke get_schema only", "Monitoring dashboards"],
        ["MCP.Admin", "Full access + configuration endpoints", "Platform administrators"],
    ],
    col_widths=[3.5, 7, 5],
)

doc.add_heading("6.2 Role Assignments", level=2)
add_table(
    ["Principal", "Type", "Assigned Role", "Justification"],
    [
        ["Agent Orchestrator SP", "Application", "MCP.Tools.Invoke", "Needs to run queries and RCA"],
        ["SRE Automation SP", "Application", "MCP.Tools.Invoke", "Automated incident response"],
        ["Monitoring Dashboard SP", "Application", "MCP.Schema.Read", "Only needs schema metadata"],
        ["Platform Admin Group", "User/Group", "MCP.Admin", "Configuration and management"],
    ],
    col_widths=[4, 2.5, 3, 5],
)

doc.add_heading("6.3 Principle of Least Privilege", level=2)
add_bullet("The MCP server's Managed Identity has read-only access to Log Analytics — it cannot write, delete, or purge data")
add_bullet("Each caller is restricted to the minimum role needed")
add_bullet("No wildcard permissions — all roles are explicitly scoped to specific resources")

# ═══════════════════════════════════════════════════════════════════════════
#  7. SECRETS MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("7. Secrets Management", level=1)

doc.add_heading("7.1 Secret Storage Strategy", level=2)
add_table(
    ["Secret", "Storage Location", "Access Method"],
    [
        ["LAWS Workspace ID", "Azure Key Vault", "Managed Identity → Key Vault Secrets User"],
        ["Tenant ID", "Azure Key Vault", "Managed Identity → Key Vault Secrets User"],
        ["MCP App Client ID", "Container App env var (non-secret)", "Direct"],
        ["Allowed Client IDs list", "Container App env var (non-secret)", "Direct"],
        ["Service Principal credentials", "NOT USED", "Managed Identity replaces SP auth"],
    ],
    col_widths=[4, 5, 6],
)

doc.add_heading("7.2 Key Vault Configuration", level=2)
add_table(
    ["Setting", "Value", "Rationale"],
    [
        ["RBAC authorization", "Enabled", "No access policies — Entra ID RBAC only"],
        ["Public network access", "Disabled", "Private Endpoint only"],
        ["Soft delete", "Enabled (90 days)", "Accidental deletion recovery"],
        ["Purge protection", "Enabled", "Prevent permanent secret loss"],
        ["Diagnostic logging", "Enabled → LAWS", "Audit all secret access"],
    ],
    col_widths=[4, 4, 7],
)

doc.add_heading("7.3 Secret Rotation", level=2)
add_table(
    ["Secret", "Rotation Frequency", "Mechanism"],
    [
        ["Managed Identity", "Automatic", "Azure-managed, no human intervention"],
        ["Key Vault secrets", "90 days", "Azure Key Vault auto-rotation policy"],
        ["App Registration certs", "12 months", "Entra ID certificate rotation"],
    ],
    col_widths=[4, 4, 7],
)

# ═══════════════════════════════════════════════════════════════════════════
#  8. DATA PROTECTION
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("8. Data Protection", level=1)

doc.add_heading("8.1 Encryption", level=2)
add_table(
    ["Layer", "Mechanism", "Standard"],
    [
        ["In transit (Agent → MCP)", "TLS 1.2+", "Enforced by Container Apps"],
        ["In transit (MCP → LAWS)", "TLS 1.2+", "Enforced by Private Endpoint"],
        ["At rest (LAWS data)", "Azure-managed keys or CMK", "AES-256"],
        ["At rest (Key Vault)", "HSM-backed encryption", "FIPS 140-2 Level 2"],
        ["At rest (Audit logs)", "Azure-managed keys or CMK", "AES-256"],
    ],
    col_widths=[5, 5, 5],
)

doc.add_heading("8.2 Data Residency", level=2)
add_bullet("All data stays within the customer's Azure tenant")
add_bullet("The MCP server does not store any query results — data flows through and is returned to the caller")
add_bullet("Audit logs are written to the customer's own Log Analytics workspace or storage account")
add_bullet("No data is transmitted to Microsoft's tenant — the LLM receives only structured findings, not raw LAWS data")

doc.add_heading("8.3 Data Classification", level=2)
add_table(
    ["Data Type", "Classification", "Handling"],
    [
        ["KQL queries", "Internal", "Logged (hash only in audit)"],
        ["Query results (SAP metrics)", "Confidential", "Not persisted; returned to caller"],
        ["Schema metadata", "Internal", "Cached in memory; no PII"],
        ["Audit logs", "Internal", "Immutable storage, 90-day retention"],
        ["Authentication tokens", "Restricted", "Validated in memory; never logged"],
    ],
    col_widths=[4.5, 3, 7],
)

# ═══════════════════════════════════════════════════════════════════════════
#  9. QUERY SAFETY & INPUT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("9. Query Safety & Input Validation", level=1)

doc.add_heading("9.1 KQL Query Guard", level=2)
doc.add_paragraph(
    "Every KQL query submitted to the MCP server is validated before execution. "
    "The following patterns are blocked:"
)

add_table(
    ["Rule", "Patterns Blocked", "Risk Mitigated"],
    [
        ["No destructive operations", ".drop, .delete, .purge", "Data loss"],
        ["No write operations", ".set, .append, .set-or-append", "Data tampering"],
        ["No external data access", "externaldata(), external_table()", "Data exfiltration"],
        ["No resource exhaustion", "Unbounded materialize()", "Denial of Service"],
        ["Row cap enforcement", "Auto-inject 'take' if missing", "Resource abuse"],
        ["Time window limit", "Max 168 hours (7 days)", "Excessive data scan"],
    ],
    col_widths=[4.5, 5, 5],
)

doc.add_heading("9.2 Rate Limiting", level=2)
add_table(
    ["Limit", "Value", "Scope"],
    [
        ["Requests per minute", "30", "Per caller identity (appid)"],
        ["Concurrent queries", "5", "Per caller identity"],
        ["Max rows per query", "5,000", "Global"],
        ["Query timeout", "90 seconds", "Per query"],
    ],
    col_widths=[5, 3, 7],
)

doc.add_heading("9.3 Input Sanitization", level=2)
add_bullet("KQL strings are passed directly to the Azure Monitor Query SDK — no string interpolation or concatenation with user inputs")
add_bullet("SID parameter is validated against alphanumeric pattern: ^[A-Z0-9]{2,5}$")
add_bullet("Workspace ID is validated as GUID format or ARM resource ID pattern")
add_bullet("analysis_type is validated against a fixed enum of allowed values")

# ═══════════════════════════════════════════════════════════════════════════
#  10. AUDIT, LOGGING & MONITORING
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("10. Audit, Logging & Monitoring", level=1)

doc.add_heading("10.1 Audit Log Schema", level=2)
doc.add_paragraph("Every MCP tool invocation generates a structured audit record:")

audit_schema = """{
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
}"""
add_code_block(audit_schema)

doc.add_heading("10.2 Log Destinations", level=2)
add_table(
    ["Log Type", "Destination", "Retention"],
    [
        ["Audit logs (tool invocations)", "Customer LAWS / Sentinel", "90 days (configurable)"],
        ["Authentication failures", "Customer LAWS / Sentinel", "90 days"],
        ["Query guard violations", "Customer LAWS / Sentinel + Alert", "90 days"],
        ["Container stdout/stderr", "ACA-managed LAWS", "30 days"],
        ["Key Vault access logs", "Customer LAWS", "90 days"],
        ["NSG flow logs", "Customer Storage Account", "30 days"],
    ],
    col_widths=[5, 5, 4],
)

doc.add_heading("10.3 Alerting Rules", level=2)
add_table(
    ["Alert", "Condition", "Severity", "Action"],
    [
        ["Auth failure spike", "> 10 failed auth attempts in 5 min", "High", "Notify SOC"],
        ["Query guard violation", "Any blocked query detected", "Medium", "Notify SOC + log caller"],
        ["Rate limit exceeded", "Caller hits rate limit", "Low", "Log + throttle"],
        ["MCP server unhealthy", "Health probe fails for > 2 min", "Critical", "Auto-restart + notify"],
        ["Unusual query volume", "> 3x baseline in 15 min", "Medium", "Notify ops"],
    ],
    col_widths=[3.5, 4.5, 2, 4],
)

doc.add_heading("10.4 Microsoft Sentinel Integration", level=2)
doc.add_paragraph("For customers using Microsoft Sentinel, audit logs can be ingested via:")
add_bullet("Diagnostic Settings on the Container App → LAWS")
add_bullet("Custom log table (MCPAudit_CL) for structured tool invocation records")
add_bullet("Analytic Rules for detecting suspicious patterns (e.g., repeated query guard violations)")

# ═══════════════════════════════════════════════════════════════════════════
#  11. CONTAINER & SUPPLY CHAIN SECURITY
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("11. Container & Supply Chain Security", level=1)

doc.add_heading("11.1 Container Hardening", level=2)
add_table(
    ["Control", "Implementation", "Rationale"],
    [
        ["Non-root execution", "USER mcpuser in Dockerfile", "Prevent container escape privilege escalation"],
        ["Read-only filesystem", "--read-only + tmpfs for /tmp", "Prevent runtime binary modification"],
        ["No capabilities", "Drop all Linux capabilities", "Minimize attack surface"],
        ["Minimal base image", "python:3.11-slim", "Reduce CVE surface"],
        ["No shell (optional)", "Distroless variant for production", "Prevent interactive exploitation"],
    ],
    col_widths=[3.5, 5, 6],
)

doc.add_heading("11.2 Image Security Pipeline", level=2)
add_table(
    ["Control", "Tool", "Frequency"],
    [
        ["Vulnerability scanning", "Microsoft Defender for Containers", "Every push + daily"],
        ["Base image updates", "Dependabot / Renovate", "Weekly"],
        ["Dependency pinning", "requirements-lock.txt with hashes", "Every build"],
        ["Image signing", "Notation (Notary v2)", "Every push"],
        ["Admission control", "Azure Policy on ACA", "Every deployment"],
    ],
    col_widths=[4, 5, 4],
)

doc.add_heading("11.3 Secure Dockerfile", level=2)
secure_dockerfile = """FROM python:3.11-slim AS base

# Non-root user
RUN groupadd -r mcpuser && useradd --no-log-init -r -g mcpuser mcpuser

WORKDIR /app

# Pin dependencies with hashes
COPY requirements-lock.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements-lock.txt

COPY --chown=mcpuser:mcpuser . .

USER mcpuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \\
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

CMD ["python", "run_server.py"]"""
add_code_block(secure_dockerfile)

# ═══════════════════════════════════════════════════════════════════════════
#  12. CROSS-TENANT ACCESS MODEL
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("12. Cross-Tenant Access Model", level=1)

doc.add_heading("12.1 Microsoft Tenant → Customer Tenant", level=2)
doc.add_paragraph(
    "The Agent Platform Control Plane in Microsoft's tenant manages deployments but "
    "does not access customer data. Access is controlled via cross-tenant app registration."
)

cross_tenant_diagram = """
┌──── Microsoft Tenant ─────────────┐      ┌────── Customer Tenant ──────────────┐
│                                    │      │                                     │
│  Platform Control Plane            │      │  Cross-Tenant Access Policy          │
│  (Multi-tenant App Registration)   │─────►│  ┌────────────────────────────────┐ │
│                                    │      │  │ Allowed: Microsoft Platform App │ │
│  Actions:                          │      │  │ Scope:   Deployment only        │ │
│  - Deploy/update MCP container     │      │  │ No data-plane access            │ │
│  - Push agent configurations       │      │  └────────────────────────────────┘ │
│  - Read health/readiness status    │      │                                     │
│                                    │      │  MCP Server App Registration         │
│  Cannot:                           │      │  (Single-tenant: AzureADMyOrg)      │
│  - Invoke MCP tools                │      │  Only customer tenant identities     │
│  - Read query results              │      │  can invoke tools                    │
│  - Access LAWS data                │      │                                     │
└────────────────────────────────────┘      └─────────────────────────────────────┘"""
add_code_block(cross_tenant_diagram)

doc.add_heading("12.2 App Registration Settings", level=2)
add_table(
    ["Setting", "Value", "Rationale"],
    [
        ["Supported account types", "Accounts in this organizational directory only (AzureADMyOrg)", "No external tenant can invoke tools"],
        ["App roles", "MCP.Tools.Invoke, MCP.Schema.Read, MCP.Admin", "Granular authorization"],
        ["API permissions", "None (server-side only)", "MCP server doesn't call external APIs"],
        ["Token version", "v2.0", "Modern Entra ID token format"],
    ],
    col_widths=[4, 6, 5],
)

# ═══════════════════════════════════════════════════════════════════════════
#  13. DEPLOYMENT SECURITY CONTROLS
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("13. Deployment Security Controls", level=1)

doc.add_heading("13.1 Infrastructure-as-Code Security", level=2)
add_table(
    ["Control", "Implementation"],
    [
        ["No secrets in IaC scripts", "All secrets in Key Vault; deployment scripts reference Key Vault"],
        ["Parameterized deployments", "Subscription, resource group, names are parameters"],
        ["RBAC for deployment", "Only platform admins can run deployment scripts"],
        ["State protection", "ACA manages state; no Terraform state file exposure"],
    ],
    col_widths=[5, 10],
)

doc.add_heading("13.2 CI/CD Pipeline Security", level=2)
add_table(
    ["Stage", "Security Control"],
    [
        ["Source", "Branch protection; signed commits; PR reviews"],
        ["Build", "Pinned dependencies with hash verification"],
        ["Scan", "Defender for Containers image scan; SAST (CodeQL/Semgrep)"],
        ["Sign", "Image signed with Notation before push to ACR"],
        ["Deploy", "ACR → ACA via Managed Identity (AcrPull); no admin credentials"],
        ["Verify", "Post-deploy health check; smoke test against /health"],
    ],
    col_widths=[3, 12],
)

doc.add_heading("13.3 Environment Separation", level=2)
add_table(
    ["Environment", "Purpose", "Network", "Auth"],
    [
        ["Dev", "Development & testing", "Separate VNet or peered subnet", "Dev Entra ID app"],
        ["Staging", "Pre-production validation", "Customer VNet (isolated subnet)", "Staging Entra ID app"],
        ["Production", "Live customer deployment", "Customer VNet (production subnet)", "Production Entra ID app"],
    ],
    col_widths=[3, 4, 5, 4],
)

# ═══════════════════════════════════════════════════════════════════════════
#  14. COMPLIANCE ALIGNMENT
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("14. Compliance Alignment", level=1)

doc.add_paragraph(
    "The following table maps each security control to relevant compliance frameworks:"
)

add_table(
    ["Security Control", "SOC 2", "ISO 27001", "NIST 800-53", "CIS"],
    [
        ["Entra ID authentication", "CC6.1", "A.9.4.1", "IA-2, IA-8", "16.2"],
        ["RBAC authorization", "CC6.3", "A.9.4.1", "AC-3, AC-6", "16.7"],
        ["VNet isolation", "CC6.6", "A.13.1.1", "SC-7", "12.1"],
        ["TLS encryption", "CC6.7", "A.10.1.1", "SC-8, SC-13", "14.4"],
        ["Audit logging", "CC7.2", "A.12.4.1", "AU-2, AU-3", "8.2"],
        ["Key Vault secrets", "CC6.7", "A.10.1.2", "SC-12, SC-28", "14.8"],
        ["Query safety validation", "CC6.1", "A.14.2.5", "SI-10", "16.5"],
        ["Container hardening", "CC6.8", "A.12.6.1", "CM-7, SI-3", "5.1"],
    ],
    col_widths=[4, 2, 2.5, 3, 2],
)

# ═══════════════════════════════════════════════════════════════════════════
#  15. SECURITY CHECKLIST
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("15. Security Checklist", level=1)

doc.add_heading("15.1 Mandatory Controls (Must-Have for Production)", level=2)
add_table(
    ["#", "Control", "Category", "Owner", "Status"],
    [
        ["1", "VNet-injected Container Apps with --internal-only ingress", "Network", "Platform", "☐"],
        ["2", "Private Endpoints for LAWS, Key Vault, ACR", "Network", "Platform", "☐"],
        ["3", "NSG rules restricting inbound to agent subnet only", "Network", "Platform", "☐"],
        ["4", "Internet egress blocked (except Entra ID service tag)", "Network", "Platform", "☐"],
        ["5", "Entra ID app registration (single-tenant, AzureADMyOrg)", "Identity", "Security", "☐"],
        ["6", "OAuth2 bearer token validation middleware", "Identity", "Dev", "☐"],
        ["7", "App Role enforcement (MCP.Tools.Invoke)", "AuthZ", "Dev", "☐"],
        ["8", "Allowed client app ID allow-list", "AuthZ", "Security", "☐"],
        ["9", "System-assigned Managed Identity for LAWS, KV, ACR", "Identity", "Platform", "☐"],
        ["10", "Key Vault for all secrets (RBAC mode, private endpoint)", "Secrets", "Platform", "☐"],
        ["11", "KQL query guard (block write/delete/externaldata)", "Data", "Dev", "☐"],
        ["12", "Row cap and time window enforcement", "Data", "Dev", "☐"],
        ["13", "Rate limiting per caller identity", "Data", "Dev", "☐"],
        ["14", "Structured audit logging (every tool invocation)", "Audit", "Dev", "☐"],
        ["15", "TLS 1.2+ enforced on all connections", "Encryption", "Platform", "☐"],
        ["16", "Non-root container execution", "Container", "Dev", "☐"],
        ["17", "Pinned dependencies with hash verification", "Supply Chain", "Dev", "☐"],
        ["18", "Defender for Containers enabled", "Container", "Security", "☐"],
    ],
    col_widths=[0.8, 7.5, 2, 2, 1.2],
)

doc.add_heading("15.2 Recommended Controls (Should-Have)", level=2)
add_table(
    ["#", "Control", "Category", "Owner", "Status"],
    [
        ["19", "mTLS between Agent Orchestrator and MCP Server", "Network", "Platform", "☐"],
        ["20", "Image signing with Notation (Notary v2)", "Supply Chain", "Dev", "☐"],
        ["21", "Microsoft Sentinel integration with analytic rules", "Monitoring", "Security", "☐"],
        ["22", "Customer-managed keys (CMK) for LAWS and audit storage", "Encryption", "Security", "☐"],
        ["23", "NSG flow logs enabled and analyzed", "Monitoring", "Platform", "☐"],
        ["24", "Azure Policy (enforce signed images, no public ingress)", "Governance", "Platform", "☐"],
    ],
    col_widths=[0.8, 7.5, 2, 2, 1.2],
)

doc.add_heading("15.3 Optional Controls (Nice-to-Have)", level=2)
add_table(
    ["#", "Control", "Category", "Owner", "Status"],
    [
        ["25", "WAF (Azure Front Door) if any external gateway needed", "Network", "Platform", "☐"],
        ["26", "Distroless container image", "Container", "Dev", "☐"],
        ["27", "DAST scanning of MCP endpoints", "Testing", "Security", "☐"],
        ["28", "Penetration testing on MCP server", "Testing", "Security", "☐"],
    ],
    col_widths=[0.8, 7.5, 2, 2, 1.2],
)

# ═══════════════════════════════════════════════════════════════════════════
#  APPENDIX A — REFERENCE IMPLEMENTATION SNIPPETS
# ═══════════════════════════════════════════════════════════════════════════
doc.add_page_break()
doc.add_heading("Appendix A — Reference Implementation Snippets", level=1)

doc.add_heading("A.1 Entra ID Authentication Middleware (Python)", level=2)
auth_code = '''"""auth_middleware.py — Entra ID token validation for MCP server."""

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
            return JSONResponse(
                {"error": "Missing Authorization header"}, status_code=401
            )

        claims = self._validate_token(token)
        if not claims:
            return JSONResponse(
                {"error": "Invalid or expired token"}, status_code=403
            )

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
            return None'''
add_code_block(auth_code)

doc.add_heading("A.2 Query Guard (Python)", level=2)
guard_code = '''"""query_guard.py — Enterprise KQL safety validation."""

import re
import hashlib
from collections import defaultdict
from time import time

BLOCKED_PATTERNS = [
    r"\\.drop\\s", r"\\.delete\\s", r"\\.purge\\s",
    r"\\.set\\s", r"\\.append\\s", r"\\.set-or-append",
    r"\\.create\\s", r"\\.alter\\s", r"\\.rename\\s",
    r"externaldata\\s*\\(", r"external_table\\s*\\(",
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
        violations.append(f"Timespan {timespan_hours}h exceeds max")
    now = time()
    _call_counts[caller_id] = [t for t in _call_counts[caller_id] if now - t < 60]
    if len(_call_counts[caller_id]) >= RATE_LIMIT_PER_MINUTE:
        violations.append("Rate limit exceeded")
    else:
        _call_counts[caller_id].append(now)
    return violations'''
add_code_block(guard_code)

doc.add_heading("A.3 Audit Logger (Python)", level=2)
audit_code = '''"""audit_logger.py — Structured audit logging for compliance."""

import json
import logging
import hashlib
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
        "kql_hash": hashlib.sha256(
            params.get("kql", "").encode()
        ).hexdigest(),
        "result_rows": result_rows,
        "duration_ms": round(duration_ms, 2),
        "status": status,
        "query_guard_violations": violations or [],
    }
    audit_logger.info(json.dumps(record))'''
add_code_block(audit_code)

doc.add_heading("A.4 Enterprise Deployment Script (PowerShell)", level=2)
deploy_code = """# === VNet-injected, internal-only deployment ===

# Create VNet and subnets
az network vnet create --name $VNET_NAME --resource-group $RG `
    --location $LOCATION --address-prefix "10.0.0.0/16"
az network vnet subnet create --name "subnet-aca-infra" `
    --vnet-name $VNET_NAME --resource-group $RG `
    --address-prefixes "10.0.1.0/23"
az network vnet subnet create --name "subnet-private-eps" `
    --vnet-name $VNET_NAME --resource-group $RG `
    --address-prefixes "10.0.3.0/24"

# Container Apps Environment with VNet injection
$INFRA_SUBNET_ID = az network vnet subnet show `
    --name "subnet-aca-infra" --vnet-name $VNET_NAME `
    --resource-group $RG --query "id" -o tsv

az containerapp env create `
    --name $ACA_ENV_NAME --resource-group $RG `
    --location $LOCATION `
    --infrastructure-subnet-resource-id $INFRA_SUBNET_ID `
    --internal-only true

# Container App with internal ingress
az containerapp create `
    --name $ACA_APP_NAME --resource-group $RG `
    --environment $ACA_ENV_NAME `
    --image $FULL_IMAGE `
    --registry-server $ACR_LOGIN_SERVER `
    --registry-identity system `
    --target-port 8000 `
    --ingress internal `
    --min-replicas 1 --max-replicas 5 `
    --cpu 1.0 --memory 2Gi `
    --system-assigned `
    --env-vars `
        "AZURE_KEYVAULT_URL=$KV_URL" `
        "MCP_APP_CLIENT_ID=$MCP_APP_ID" `
        "ALLOWED_CLIENT_IDS=$AGENT_ORCH_APP_ID"

# Private Endpoint for Log Analytics
az network private-endpoint create `
    --name "pe-laws-mcp" --resource-group $RG `
    --vnet-name $VNET_NAME --subnet "subnet-private-eps" `
    --private-connection-resource-id $LA_RESOURCE_ID `
    --group-ids "azuremonitor" `
    --connection-name "mcp-to-laws"

# Key Vault with Private Endpoint
az keyvault create --name $KV_NAME --resource-group $RG `
    --location $LOCATION `
    --enable-rbac-authorization true `
    --public-network-access Disabled
az network private-endpoint create `
    --name "pe-kv-mcp" --resource-group $RG `
    --vnet-name $VNET_NAME --subnet "subnet-private-eps" `
    --private-connection-resource-id $KV_RESOURCE_ID `
    --group-ids "vault" `
    --connection-name "mcp-to-kv"
"""
add_code_block(deploy_code)

# ═══════════════════════════════════════════════════════════════════════════
#  FOOTER / END OF DOC
# ═══════════════════════════════════════════════════════════════════════════
doc.add_paragraph("")
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("— End of Document — Version 1.0 DRAFT —")
run.font.size = Pt(10)
run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
run.italic = True

# ── Save ─────────────────────────────────────────────────────────────────
doc.save(OUTPUT_PATH)
print(f"Document saved to: {OUTPUT_PATH}")
