"""Grant the AI Foundry resource's managed identity permission to call the
Entra-protected MCP container app.

This creates an app role assignment so the Foundry service can authenticate
to the container app without needing to pass tokens in the MCP tool config.

Steps:
  1. Creates an 'MCP.Call' app role on the container app's Entra app registration
  2. Assigns the Foundry managed identity to that role
  3. This allows Foundry to get tokens for the container app's audience
"""
import json
import subprocess
import sys


# ── Configuration ─────────────────────────────────────────────────────────────
CONTAINER_APP_CLIENT_ID = "c113e212-b251-4101-a4f1-373bf14ff051"  # Container app Entra app
FOUNDRY_PRINCIPAL_ID    = "40089cd2-f290-4d81-806f-665ae305eeca"  # Foundry managed identity
TENANT_ID               = "72f988bf-86f1-41af-91ab-2d7cd011db47"


def az(cmd: str) -> str:
    """Run an az CLI command and return stdout."""
    result = subprocess.run(
        f"az {cmd}",
        capture_output=True, text=True, shell=True
    )
    if result.returncode != 0:
        print(f"  Error: {result.stderr.strip()}")
    return result.stdout.strip()


def main() -> None:
    print("Step 1: Get the container app's Entra app registration object ID")
    app_info = az(f"ad app show --id {CONTAINER_APP_CLIENT_ID} --query id -o tsv")
    print(f"  App object ID: {app_info}")

    print("\nStep 2: Get the service principal object ID for the container app")
    sp_id = az(f"ad sp show --id {CONTAINER_APP_CLIENT_ID} --query id -o tsv")
    print(f"  Service principal ID: {sp_id}")

    print("\nStep 3: Check if app role 'MCP.Call' already exists")
    roles_json = az(f"ad app show --id {CONTAINER_APP_CLIENT_ID} --query appRoles -o json")
    roles = json.loads(roles_json) if roles_json else []
    mcp_role = next((r for r in roles if r.get("value") == "MCP.Call"), None)

    if not mcp_role:
        print("  No MCP.Call role found. Creating one...")
        import uuid
        role_id = str(uuid.uuid4())
        role_def = json.dumps([{
            "id": role_id,
            "allowedMemberTypes": ["Application"],
            "displayName": "MCP Call",
            "description": "Allows calling the MCP server",
            "value": "MCP.Call",
            "isEnabled": True,
        }] + roles)

        # Write role definition to temp file (az cli limitation with complex JSON)
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(role_def)
            role_file = f.name

        result = subprocess.run(
            ["az", "ad", "app", "update", "--id", CONTAINER_APP_CLIENT_ID,
             "--app-roles", f"@{role_file}"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  Error creating role: {result.stderr}")
            # Continue anyway — try without app role
        else:
            print(f"  Created MCP.Call role (ID: {role_id})")
        mcp_role_id = role_id
    else:
        mcp_role_id = mcp_role["id"]
        print(f"  MCP.Call role exists (ID: {mcp_role_id})")

    print("\nStep 4: Assign the Foundry managed identity to the app role")
    # Create app role assignment for the Foundry managed identity
    assignment_body = json.dumps({
        "principalId": FOUNDRY_PRINCIPAL_ID,
        "resourceId": sp_id,
        "appRoleId": mcp_role_id,
    })

    result = subprocess.run(
        ["az", "rest", "--method", "POST",
         "--uri", f"https://graph.microsoft.com/v1.0/servicePrincipals/{sp_id}/appRoleAssignedTo",
         "--headers", "Content-Type=application/json",
         "--body", assignment_body],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        print("  App role assignment created successfully!")
        print(f"\n  The Foundry resource (principal: {FOUNDRY_PRINCIPAL_ID})")
        print(f"  can now authenticate to the container app ({CONTAINER_APP_CLIENT_ID})")
    elif "Permission being assigned already exists" in result.stderr or "already exists" in result.stdout:
        print("  Assignment already exists — Foundry identity is already authorized.")
    else:
        print(f"  Error: {result.stderr}")
        print(f"  Output: {result.stdout}")

    print("\nStep 5: Verify the Foundry identity can get a token")
    print("  (The Foundry agent service should now be able to call the MCP server)")
    print("  Try the agent in the playground again.")


if __name__ == "__main__":
    main()
