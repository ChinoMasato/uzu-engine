import hashlib
import os
import sys
import tempfile
import unittest

AI_LOOP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if AI_LOOP_DIR not in sys.path:
    sys.path.insert(0, AI_LOOP_DIR)

import mcp_server


class TestMcpSkills(unittest.TestCase):
    def setUp(self):
        self._orig_skills_dir = mcp_server.SKILLS_DIR
        self._tmpdir = tempfile.TemporaryDirectory()
        self.skills_root = self._tmpdir.name
        mcp_server.SKILLS_DIR = self.skills_root

        self.alpha_dir = os.path.join(self.skills_root, "alpha")
        self.beta_dir = os.path.join(self.skills_root, "beta")
        os.makedirs(self.alpha_dir)
        os.makedirs(self.beta_dir)

        self.alpha_md = (
            "---\n"
            "name: alpha\n"
            "description: Alpha skill description.\n"
            "---\n\n"
            "# Alpha\n\nAlpha body.\n"
        )
        self.alpha_extra = "alpha extra resource\n"
        self.beta_md = (
            "---\n"
            "name: beta\n"
            "description: Beta skill description.\n"
            "---\n\n"
            "# Beta\n\nBeta body.\n"
        )

        with open(os.path.join(self.alpha_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(self.alpha_md)
        with open(os.path.join(self.alpha_dir, "notes.txt"), "w", encoding="utf-8") as f:
            f.write(self.alpha_extra)
        with open(os.path.join(self.beta_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(self.beta_md)

    def tearDown(self):
        mcp_server.SKILLS_DIR = self._orig_skills_dir
        self._tmpdir.cleanup()

    def test_initialize_capabilities_include_skills_extension(self):
        resp = mcp_server.handle(".", {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": mcp_server.PROTOCOL_VERSION, "capabilities": {}},
        })
        caps = resp["result"]["capabilities"]
        self.assertIn("tools", caps)
        self.assertIn("resources", caps)
        self.assertIn("extensions", caps)
        self.assertIn("io.modelcontextprotocol/skills", caps["extensions"])

    def test_server_discover_returns_2026_07_28_and_same_capabilities(self):
        init_resp = mcp_server.handle(".", {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        disc_resp = mcp_server.handle(".", {"jsonrpc": "2.0", "id": 2, "method": "server/discover"})
        self.assertEqual(disc_resp["result"]["protocolVersion"], "2026-07-28")
        self.assertEqual(disc_resp["result"]["capabilities"], init_resp["result"]["capabilities"])
        self.assertEqual(disc_resp["result"]["serverInfo"], init_resp["result"]["serverInfo"])

    def test_skills_list_contains_two_skills_and_matching_sha256_digests(self):
        resp = mcp_server.handle(".", {"jsonrpc": "2.0", "id": 3, "method": "skills/list"})
        result = resp["result"]
        self.assertEqual(result["ttlMs"], 60000)
        self.assertEqual(result["cacheScope"], "private")

        skills = result["skills"]
        self.assertEqual(len(skills), 2)
        by_uri = {s["uri"]: s for s in skills}
        self.assertIn("skill://alpha/SKILL.md", by_uri)
        self.assertIn("skill://beta/SKILL.md", by_uri)

        alpha_entry = by_uri["skill://alpha/SKILL.md"]
        self.assertEqual(alpha_entry["frontmatter"]["name"], "alpha")
        self.assertEqual(alpha_entry["frontmatter"]["description"], "Alpha skill description.")
        alpha_res = {r["uri"]: r for r in alpha_entry["resources"]}
        expected_alpha_digest = "sha256:" + hashlib.sha256(self.alpha_md.encode("utf-8")).hexdigest()
        self.assertEqual(alpha_res["skill://alpha/SKILL.md"]["digest"], expected_alpha_digest)
        self.assertEqual(alpha_res["skill://alpha/SKILL.md"]["size"], len(self.alpha_md.encode("utf-8")))

        beta_entry = by_uri["skill://beta/SKILL.md"]
        self.assertEqual(beta_entry["frontmatter"]["name"], "beta")
        beta_res = {r["uri"]: r for r in beta_entry["resources"]}
        expected_beta_digest = "sha256:" + hashlib.sha256(self.beta_md.encode("utf-8")).hexdigest()
        self.assertEqual(beta_res["skill://beta/SKILL.md"]["digest"], expected_beta_digest)

    def test_skills_get_known_and_unknown(self):
        ok_resp = mcp_server.handle(".", {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "skills/get",
            "params": {"uri": "skill://alpha/SKILL.md"},
        })
        self.assertEqual(ok_resp["result"]["skill"]["uri"], "skill://alpha/SKILL.md")
        self.assertEqual(ok_resp["result"]["skill"]["frontmatter"]["name"], "alpha")

        err_resp = mcp_server.handle(".", {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "skills/get",
            "params": {"uri": "skill://missing/SKILL.md"},
        })
        self.assertEqual(err_resp["error"]["code"], -32602)

    def test_resources_list_includes_skill_md_and_extra_file(self):
        resp = mcp_server.handle(".", {"jsonrpc": "2.0", "id": 6, "method": "resources/list"})
        resources = resp["result"]["resources"]
        by_uri = {r["uri"]: r for r in resources}
        self.assertIn("skill://alpha/SKILL.md", by_uri)
        self.assertIn("skill://alpha/notes.txt", by_uri)
        self.assertIn("skill://beta/SKILL.md", by_uri)
        self.assertEqual(by_uri["skill://alpha/SKILL.md"]["mimeType"], "text/markdown")
        self.assertEqual(by_uri["skill://alpha/notes.txt"]["mimeType"], "text/plain")

    def test_resources_read_known_and_unknown(self):
        ok_resp = mcp_server.handle(".", {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "resources/read",
            "params": {"uri": "skill://alpha/SKILL.md"},
        })
        contents = ok_resp["result"]["contents"]
        self.assertEqual(len(contents), 1)
        self.assertEqual(contents[0]["uri"], "skill://alpha/SKILL.md")
        self.assertEqual(contents[0]["mimeType"], "text/markdown")
        self.assertEqual(contents[0]["text"], self.alpha_md)

        extra_resp = mcp_server.handle(".", {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "resources/read",
            "params": {"uri": "skill://alpha/notes.txt"},
        })
        self.assertEqual(extra_resp["result"]["contents"][0]["text"], self.alpha_extra)

        err_resp = mcp_server.handle(".", {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "resources/read",
            "params": {"uri": "skill://alpha/nonexistent.md"},
        })
        self.assertEqual(err_resp["error"]["code"], -32602)

    def test_tools_list_unchanged(self):
        resp = mcp_server.handle(".", {"jsonrpc": "2.0", "id": 10, "method": "tools/list"})
        tools = resp["result"]["tools"]
        self.assertEqual(len(tools), len(mcp_server.TOOLS))


if __name__ == "__main__":
    unittest.main()

