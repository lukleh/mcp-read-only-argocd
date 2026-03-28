#!/usr/bin/env python3
"""
Smoke test script for mcp-read-only-argocd.

Tests basic connectivity and API access using the configured connections.
Run this to verify your session tokens are working before using the MCP server.

Usage:
    python smoke_test.py
    python smoke_test.py --connection staging
    python smoke_test.py --print-paths
"""

import argparse
import asyncio
import sys

from mcp_read_only_argocd.argocd_connector import ArgoCDConnector
from mcp_read_only_argocd.config import ConfigParser
from mcp_read_only_argocd.runtime_paths import resolve_runtime_paths


async def test_connection(connector: ArgoCDConnector, connection_name: str) -> bool:
    """Test a single connection with various API calls."""
    print(f"\n{'='*60}")
    print(f"Testing connection: {connection_name}")
    print(f"URL: {connector.connection.url}")
    print(f"{'='*60}")

    success = True
    total_tests = 13

    apps = []
    projects = []
    clusters = []
    repos = []

    # Test 1: Version
    print(f"\n[1/{total_tests}] Getting Argo CD version...")
    try:
        version = await connector.get_version()
        print(f"  ✓ Version: {version.get('Version', 'unknown')}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        success = False

    # Test 2: Settings
    print(f"\n[2/{total_tests}] Getting Argo CD settings...")
    try:
        settings = await connector.get_settings()
        print(f"  ✓ URL: {settings.get('url', 'unknown')}")
        print(f"  ✓ Dex config present: {'dexConfig' in settings}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        success = False

    # Test 3: List applications
    print(f"\n[3/{total_tests}] Listing applications...")
    try:
        apps = await connector.list_applications()
        print(f"  ✓ Found {len(apps)} application(s)")
        if apps:
            # Show first 3 app names
            app_names = [app.get("metadata", {}).get("name", "?") for app in apps[:3]]
            print(f"  ✓ Sample apps: {', '.join(app_names)}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        success = False

    # Test 4: Get application details (sample)
    print(f"\n[4/{total_tests}] Getting application details (sample)...")
    app_name = apps[0].get("metadata", {}).get("name") if apps else None
    if not app_name:
        print("  - Skipped: No applications found")
    else:
        try:
            app = await connector.get_application(app_name)
            sync_status = (
                app.get("status", {}).get("sync", {}).get("status", "unknown")
                if isinstance(app, dict)
                else "unknown"
            )
            health_status = (
                app.get("status", {}).get("health", {}).get("status", "unknown")
                if isinstance(app, dict)
                else "unknown"
            )
            print(f"  ✓ App: {app_name}")
            print(f"  ✓ Sync: {sync_status} | Health: {health_status}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            success = False

    # Test 5: Get application resource tree (sample)
    print(f"\n[5/{total_tests}] Getting application resource tree (sample)...")
    if not app_name:
        print("  - Skipped: No applications found")
    else:
        try:
            tree = await connector.get_application_resource_tree(app_name)
            node_count = len(tree.get("nodes", [])) if isinstance(tree, dict) else None
            if node_count is not None:
                print(f"  ✓ Nodes: {node_count}")
            else:
                print("  ✓ Retrieved resource tree")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            success = False

    # Test 6: Get application managed resources (sample)
    print(f"\n[6/{total_tests}] Getting application managed resources (sample)...")
    if not app_name:
        print("  - Skipped: No applications found")
    else:
        try:
            resources = await connector.get_application_managed_resources(app_name)
            count = None
            if isinstance(resources, dict) and isinstance(resources.get("items"), list):
                count = len(resources["items"])
            if count is not None:
                print(f"  ✓ Managed resources: {count}")
            else:
                print("  ✓ Retrieved managed resources")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            success = False

    # Test 7: Get application logs (sample)
    print(f"\n[7/{total_tests}] Getting application logs (sample)...")
    if not app_name:
        print("  - Skipped: No applications found")
    else:
        try:
            logs = await connector.get_application_logs(app_name, tail_lines=10)
            lines = logs.get("lines") if isinstance(logs, dict) else None
            if isinstance(lines, list):
                print(f"  ✓ Retrieved {len(lines)} log line(s)")
                if lines:
                    print(f"  ✓ Last line: {lines[-1][:200]}")
            else:
                print("  ✓ Retrieved logs")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            success = False

    # Test 8: List projects
    print(f"\n[8/{total_tests}] Listing projects...")
    try:
        projects = await connector.list_projects()
        print(f"  ✓ Found {len(projects)} project(s)")
        if projects:
            project_names = [
                p.get("metadata", {}).get("name", "?") for p in projects[:3]
            ]
            print(f"  ✓ Sample projects: {', '.join(project_names)}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        success = False

    # Test 9: Get project details (sample)
    print(f"\n[9/{total_tests}] Getting project details (sample)...")
    project_name = projects[0].get("metadata", {}).get("name") if projects else None
    if not project_name:
        print("  - Skipped: No projects found")
    else:
        try:
            project = await connector.get_project(project_name)
            print(f"  ✓ Project: {project_name}")
            if isinstance(project, dict):
                dest_count = len(project.get("spec", {}).get("destinations", []) or [])
                repo_count = len(project.get("spec", {}).get("sourceRepos", []) or [])
                print(f"  ✓ Destinations: {dest_count} | Source repos: {repo_count}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            success = False

    # Test 10: List clusters
    print(f"\n[10/{total_tests}] Listing clusters...")
    try:
        clusters = await connector.list_clusters()
        print(f"  ✓ Found {len(clusters)} cluster(s)")
        if clusters:
            cluster_names = [c.get("name", c.get("server", "?")) for c in clusters[:3]]
            print(f"  ✓ Sample clusters: {', '.join(cluster_names)}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        success = False

    # Test 11: Get cluster details (sample)
    print(f"\n[11/{total_tests}] Getting cluster details (sample)...")
    cluster_server = None
    for c in clusters:
        if isinstance(c, dict) and c.get("server"):
            cluster_server = c["server"]
            break
    if not cluster_server:
        print("  - Skipped: No clusters found")
    else:
        try:
            cluster = await connector.get_cluster(cluster_server)
            print(f"  ✓ Cluster server: {cluster_server}")
            if isinstance(cluster, dict):
                name = cluster.get("name") or cluster.get("server", "unknown")
                print(f"  ✓ Name: {name}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            success = False

    # Test 12: List repositories
    print(f"\n[12/{total_tests}] Listing repositories...")
    try:
        repos = await connector.list_repositories()
        print(f"  ✓ Found {len(repos)} repo(s)")
        if repos:
            repo_names = [r.get("repo", r.get("url", "?")) for r in repos[:3]]
            print(f"  ✓ Sample repos: {', '.join(repo_names)}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        success = False

    # Test 13: Get repository details (sample)
    print(f"\n[13/{total_tests}] Getting repository details (sample)...")
    repo_url = None
    for r in repos:
        if isinstance(r, dict):
            repo_url = r.get("repo") or r.get("url")
            if isinstance(repo_url, str) and repo_url:
                break
    if not repo_url:
        print("  - Skipped: No repositories found")
    else:
        try:
            repo = await connector.get_repository(repo_url)
            print(f"  ✓ Repo: {repo_url}")
            if isinstance(repo, dict):
                repo_type = repo.get("type", "unknown")
                print(f"  ✓ Type: {repo_type}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            success = False

    return success


async def main(
    connection_filter: str | None = None,
    config_dir: str | None = None,
    state_dir: str | None = None,
    cache_dir: str | None = None,
    print_paths: bool = False,
):
    """Run smoke tests for all configured connections."""
    print("MCP Read-Only Argo CD - Smoke Test")
    print("=" * 60)

    runtime_paths = resolve_runtime_paths(
        config_dir=config_dir,
        state_dir=state_dir,
        cache_dir=cache_dir,
    )

    if print_paths:
        print(runtime_paths.render())
        return True

    if not runtime_paths.connections_file.exists():
        print(f"\n✗ Configuration file not found: {runtime_paths.connections_file}")
        print(
            "  Run `uvx mcp-read-only-argocd --write-sample-config` or create "
            "~/.config/lukleh/mcp-read-only-argocd/connections.yaml from "
            "connections.yaml.sample"
        )
        return False

    try:
        parser = ConfigParser(
            runtime_paths.connections_file,
            state_path=runtime_paths.state_file,
        )
        connections = parser.load_config()
    except Exception as e:
        print(f"\n✗ Failed to load configuration: {e}")
        return False

    if not connections:
        print("\n✗ No connections configured")
        return False

    # Filter connections if specified
    if connection_filter:
        connections = [c for c in connections if c.connection_name == connection_filter]
        if not connections:
            print(f"\n✗ Connection '{connection_filter}' not found")
            return False

    print(f"\nFound {len(connections)} connection(s) to test")

    # Test each connection
    all_success = True
    for conn in connections:
        connector = ArgoCDConnector(conn)
        try:
            success = await test_connection(connector, conn.connection_name)
            if not success:
                all_success = False
        finally:
            await connector.close()

    # Summary
    print(f"\n{'='*60}")
    if all_success:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed. Check your session token.")
    print(f"{'='*60}\n")

    return all_success


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(
        description="Smoke test for mcp-read-only-argocd"
    )
    arg_parser.add_argument(
        "--connection",
        "-c",
        help="Test only this connection (by name)",
        default=None,
    )
    arg_parser.add_argument(
        "--config-dir",
        help="Directory containing connections.yaml",
    )
    arg_parser.add_argument(
        "--state-dir",
        help="Directory containing session_tokens.json",
    )
    arg_parser.add_argument(
        "--cache-dir",
        help="Directory reserved for cache files",
    )
    arg_parser.add_argument(
        "--print-paths",
        action="store_true",
        help="Print resolved config/state/cache paths and exit",
    )
    args = arg_parser.parse_args()

    success = asyncio.run(
        main(
            args.connection,
            config_dir=args.config_dir,
            state_dir=args.state_dir,
            cache_dir=args.cache_dir,
            print_paths=args.print_paths,
        )
    )
    sys.exit(0 if success else 1)
