#!/usr/bin/env python3
"""
Seed data uploader for Agentic Filesystem.

Uploads sample files, waits for indexing, and runs demo searches
to verify the system is working end-to-end.
"""

import os
import sys
import time

import httpx

BASE_URL = os.environ.get("API_URL", "http://localhost:8000")
TENANT = "seed-tenant"
SEED_DIR = os.path.join(os.path.dirname(__file__), "files")


def upload_file(client: httpx.Client, filepath: str, namespace: str) -> dict:
    filename = os.path.basename(filepath)
    print(f"  Uploading {filename} to namespace '{namespace}'...", end=" ")

    with open(filepath, "rb") as f:
        response = client.post(
            f"/v1/{TENANT}/files",
            files={"file": (filename, f)},
            data={"namespace": namespace, "path": "", "tags": f"seed,{namespace}"},
            timeout=30.0,
        )
    response.raise_for_status()
    result = response.json()
    print(f"OK (file_id={result['file_id'][:8]}...)")
    return result


def wait_for_indexing(client: httpx.Client, file_id: str, timeout: int = 120) -> str:
    for i in range(timeout):
        response = client.get(f"/v1/{TENANT}/search/status/{file_id}", timeout=10.0)
        data = response.json()
        status = data["indexing_status"]
        if status == "indexed":
            return status
        if status == "failed":
            print(f"  FAILED: {data.get('indexing_error', 'unknown')}")
            return status
        time.sleep(1)
    return "timeout"


def run_search(client: httpx.Client, endpoint: str, body: dict) -> dict:
    response = client.post(f"/v1/{TENANT}/search/{endpoint}", json=body, timeout=30.0)
    response.raise_for_status()
    return response.json()


def main():
    client = httpx.Client(base_url=BASE_URL)

    # Check health
    print("Checking API health...")
    try:
        resp = client.get("/health", timeout=5.0)
        resp.raise_for_status()
        print(f"  API is healthy: {resp.json()}")
    except Exception as e:
        print(f"  API not available: {e}")
        print("  Make sure 'docker compose up' is running.")
        sys.exit(1)

    # Upload seed files
    print("\n--- Uploading Seed Files ---")
    uploaded = []

    for namespace in sorted(os.listdir(SEED_DIR)):
        ns_path = os.path.join(SEED_DIR, namespace)
        if not os.path.isdir(ns_path):
            continue
        for filename in sorted(os.listdir(ns_path)):
            filepath = os.path.join(ns_path, filename)
            if os.path.isfile(filepath):
                result = upload_file(client, filepath, namespace)
                uploaded.append(result)

    # Wait for indexing
    print(f"\n--- Waiting for Indexing ({len(uploaded)} files) ---")
    indexed_count = 0
    for item in uploaded:
        fid = item["file_id"]
        fname = item["filename"]
        print(f"  Waiting for {fname}...", end=" ", flush=True)
        status = wait_for_indexing(client, fid)
        print(f"[{status}]")
        if status == "indexed":
            indexed_count += 1

    print(f"\n  {indexed_count}/{len(uploaded)} files indexed successfully")

    # Run demo searches
    print("\n--- Demo: Semantic Search ---")
    result = run_search(client, "semantic", {"query": "system architecture components", "k": 5})
    print(f"  Query: 'system architecture components'")
    print(f"  Results: {result['total']}")
    for hit in result["results"][:3]:
        print(f"    [{hit['score']:.4f}] {hit['filename']}: {hit['chunk_text'][:80]}...")

    print("\n--- Demo: Hybrid Search ---")
    result = run_search(client, "hybrid", {"query": "sprint planning meeting decisions", "k": 5})
    print(f"  Query: 'sprint planning meeting decisions'")
    print(f"  Results: {result['total']}")
    for hit in result["results"][:3]:
        print(f"    [{hit['score']:.4f}] {hit['filename']}: {hit['chunk_text'][:80]}...")

    print("\n--- Demo: RAG Ask ---")
    result = run_search(client, "ask", {
        "query": "What embedding model is used and what are the chunk settings?",
        "k": 5,
    })
    print(f"  Question: 'What embedding model is used and what are the chunk settings?'")
    print(f"  Answer: {result['answer'][:300]}...")
    print(f"  Sources: {len(result['sources'])} chunks referenced")

    # Find similar
    if uploaded:
        print("\n--- Demo: Find Similar ---")
        first_id = uploaded[0]["file_id"]
        resp = client.get(f"/v1/{TENANT}/search/similar/{first_id}?k=3", timeout=30.0)
        if resp.status_code == 200:
            sim_result = resp.json()
            print(f"  Similar to: {uploaded[0]['filename']}")
            for hit in sim_result["results"][:3]:
                print(f"    [{hit['score']:.4f}] {hit['filename']}")

    # List directory
    print("\n--- Demo: Directory Listing ---")
    resp = client.get(f"/v1/{TENANT}/dirs/?namespace=docs", timeout=10.0)
    if resp.status_code == 200:
        dir_result = resp.json()
        print(f"  Namespace 'docs': {dir_result['total']} entries")
        for entry in dir_result["entries"]:
            print(f"    [{entry['type']}] {entry['name']}")

    print("\n--- Seed Complete ---")
    client.close()


if __name__ == "__main__":
    main()
