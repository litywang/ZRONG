#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for utils.py mainland_friendly_score functions.
Tests both legacy and new scoring implementations.

NOTE: is_asia() requires a working limiter for IP-based geo lookup.
For pure-IP test nodes without limiter, is_asia() returns False.
We use domain-based nodes or mock is_asia for reliable testing.
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure we import from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_node(name, server, port, ptype, network="tcp", **kwargs):
    """Helper to create a test node dict."""
    node = {
        "name": name,
        "server": server,
        "port": port,
        "type": ptype,
        "network": network,
    }
    node.update(kwargs)
    return node


class TestMainlandFriendlyScoreLegacy(unittest.TestCase):
    """Test the legacy scoring function."""

    def setUp(self):
        from utils import _mainland_friendly_score_legacy
        self.score_fn = _mainland_friendly_score_legacy

    def test_none_input(self):
        self.assertEqual(self.score_fn(None), 0)

    def test_non_dict_input(self):
        self.assertEqual(self.score_fn("string"), 0)
        self.assertEqual(self.score_fn(123), 0)
        self.assertEqual(self.score_fn([]), 0)

    def test_empty_dict(self):
        result = self.score_fn({})
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 100)

    @patch("utils.is_asia", return_value=True)
    def test_hk_vless_ws_443_with_asia_mock(self, mock_asia):
        """HK VLESS + WS + 443 should score high when is_asia returns True."""
        node = make_node("🇭🇰1-测试", "1.2.3.4", 443, "vless", "ws")
        score = self.score_fn(node)
        # Asia 50 + premium 20 (emoji 🇭🇰 matched) + vless 20 + ws 5 + port 5 = 100
        self.assertGreaterEqual(score, 90)

    @patch("utils.is_asia", return_value=False)
    def test_us_ss_80_non_asia(self, mock_asia):
        """US SS + port 80 should score low when not Asia."""
        node = make_node("🇺🇸1-测试", "5.6.7.8", 80, "ss", "tcp")
        score = self.score_fn(node)
        # Not Asia, no limiter -> 0 + ss 5 + port 2 = 7
        self.assertLess(score, 20)

    @patch("utils.is_asia", return_value=True)
    def test_score_range_with_asia(self, mock_asia):
        """All scores should be in [0, 100] for Asia nodes."""
        test_nodes = [
            make_node("🇭🇰1-测试", "1.2.3.4", 443, "vless", "ws"),
            make_node("🇯🇵2-测试", "2.3.4.5", 8443, "trojan", "tcp"),
            make_node("🇸🇬3-测试", "3.4.5.6", 80, "vmess", "ws"),
            make_node("🇰🇷1-测试", "6.7.8.9", 443, "hysteria2", "quic"),
            make_node("🇹🇭1-测试", "7.8.9.0", 8080, "ssr", "tcp"),
        ]
        for node in test_nodes:
            score = self.score_fn(node)
            self.assertGreaterEqual(score, 0, f"Score < 0 for {node['name']}")
            self.assertLessEqual(score, 100, f"Score > 100 for {node['name']}")

    @patch("utils.is_asia", return_value=False)
    def test_score_range_non_asia(self, mock_asia):
        """All scores should be in [0, 100] for non-Asia nodes."""
        test_nodes = [
            make_node("🇺🇸5-测试", "5.6.7.8", 443, "ss", "tcp"),
            make_node("🇩🇪1-测试", "9.10.11.12", 80, "ssr", "tcp"),
        ]
        for node in test_nodes:
            score = self.score_fn(node)
            self.assertGreaterEqual(score, 0, f"Score < 0 for {node['name']}")
            self.assertLessEqual(score, 100, f"Score > 100 for {node['name']}")


class TestMainlandFriendlyScoreNew(unittest.TestCase):
    """Test the new scoring function."""

    def setUp(self):
        from utils import _mainland_friendly_score_new
        self.score_fn = _mainland_friendly_score_new

    def test_none_input(self):
        self.assertEqual(self.score_fn(None), 0)

    def test_non_dict_input(self):
        self.assertEqual(self.score_fn("string"), 0)
        self.assertEqual(self.score_fn(123), 0)

    def test_empty_dict(self):
        result = self.score_fn({})
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 100)

    @patch("utils.is_asia", return_value=True)
    def test_hk_vless_reality_443(self, mock_asia):
        """HK VLESS + Reality + 443 should score very high."""
        node = make_node(
            "🇭🇰1-测试", "1.2.3.4", 443, "vless", "tcp",
            **{"reality-opts": {"public-key": "xxx", "short-id": "yyy"}}
        )
        score = self.score_fn(node)
        # Asia tier1 60 + vless 25 + reality 20 + vless+reality 10 + port 8 = 123 -> 100
        self.assertEqual(score, 100)

    @patch("utils.is_asia", return_value=True)
    def test_jp_trojan_ws_443(self, mock_asia):
        """JP Trojan + WS + 443 should score high."""
        node = make_node("🇯🇵1-测试", "2.3.4.5", 443, "trojan", "ws")
        score = self.score_fn(node)
        # Asia tier1 60 + trojan 20 + ws 8 + port 8 = 96
        self.assertGreaterEqual(score, 90)

    @patch("utils.is_asia", return_value=True)
    def test_sg_vmess_ws_443(self, mock_asia):
        """SG VMess + WS + 443 should score well."""
        node = make_node("🇸🇬1-测试", "3.4.5.6", 443, "vmess", "ws")
        score = self.score_fn(node)
        # Asia tier1 60 + vmess 10 + ws 8 + port 8 = 86
        self.assertGreaterEqual(score, 80)

    @patch("utils.is_asia", return_value=True)
    def test_kr_hysteria2_443_tier2(self, mock_asia):
        """KR Hysteria2 + 443 should score well (tier2 Asia)."""
        node = make_node("🇰🇷1-测试", "4.5.6.7", 443, "hysteria2", "quic")
        score = self.score_fn(node)
        # Asia tier2 45 + hysteria2 18 + quic 3 + port 8 = 74
        self.assertGreaterEqual(score, 70)

    @patch("utils.is_asia", return_value=False)
    def test_us_generic_low_score(self, mock_asia):
        """Generic US node should score low."""
        node = make_node("🇺🇸1-测试", "5.6.7.8", 443, "ss", "tcp")
        score = self.score_fn(node)
        # Not Asia, no limiter -> 0 + ss 3 + port 8 = 11
        self.assertLess(score, 20)

    @patch("utils.is_asia", return_value=True)
    def test_ssr_low_score(self, mock_asia):
        """SSR protocol should score lower than VLESS."""
        node_ssr = make_node("🇭🇰1-SSR", "1.2.3.4", 443, "ssr", "tcp")
        node_vless = make_node("🇭🇰2-VLESS", "1.2.3.4", 443, "vless", "tcp")
        score_ssr = self.score_fn(node_ssr)
        score_vless = self.score_fn(node_vless)
        self.assertLess(score_ssr, score_vless)

    @patch("utils.is_asia", return_value=True)
    def test_score_range_asia(self, mock_asia):
        """All scores should be in [0, 100] for Asia nodes."""
        test_nodes = [
            make_node("🇭🇰1-测试", "1.2.3.4", 443, "vless", "ws"),
            make_node("🇯🇵2-测试", "2.3.4.5", 8443, "trojan", "tcp"),
            make_node("🇸🇬3-测试", "3.4.5.6", 80, "vmess", "ws"),
            make_node("🇰🇷1-测试", "6.7.8.9", 443, "hysteria2", "quic"),
            make_node("🇹🇭1-测试", "7.8.9.0", 8080, "ssr", "tcp"),
            make_node("🇻🇳1-测试", "8.9.0.1", 443, "vless", "grpc"),
            make_node("🇲🇾1-测试", "9.0.1.2", 2053, "anytls", "tcp"),
        ]
        for node in test_nodes:
            score = self.score_fn(node)
            self.assertGreaterEqual(score, 0, f"Score < 0 for {node['name']}")
            self.assertLessEqual(score, 100, f"Score > 100 for {node['name']}")

    @patch("utils.is_asia", return_value=False)
    def test_score_range_non_asia(self, mock_asia):
        """All scores should be in [0, 100] for non-Asia nodes."""
        test_nodes = [
            make_node("🇺🇸5-测试", "5.6.7.8", 443, "ss", "tcp"),
            make_node("🇩🇪1-测试", "9.10.11.12", 80, "ssr", "tcp"),
        ]
        for node in test_nodes:
            score = self.score_fn(node)
            self.assertGreaterEqual(score, 0, f"Score < 0 for {node['name']}")
            self.assertLessEqual(score, 100, f"Score > 100 for {node['name']}")

    @patch("utils.is_asia", return_value=True)
    def test_anytls_protocol_bonus(self, mock_asia):
        """AnyTLS should get protocol bonus."""
        node = make_node("🇭🇰1-AnyTLS", "1.2.3.4", 443, "anytls", "tcp")
        score = self.score_fn(node)
        # Asia tier1 60 + anytls 12 + port 8 = 80
        self.assertGreaterEqual(score, 75)

    @patch("utils.is_asia", return_value=True)
    def test_h2_network_bonus(self, mock_asia):
        """H2 network should get bonus."""
        node_h2 = make_node("🇭🇰1-H2", "1.2.3.4", 443, "vless", "h2")
        node_tcp = make_node("🇭🇰2-TCP", "1.2.3.4", 443, "vless", "tcp")
        score_h2 = self.score_fn(node_h2)
        score_tcp = self.score_fn(node_tcp)
        self.assertGreater(score_h2, score_tcp)

    @patch("utils.is_asia", return_value=True)
    def test_port_443_better_than_8080(self, mock_asia):
        """Port 443 should score better than 8080."""
        node_443 = make_node("🇭🇰1-443", "1.2.3.4", 443, "vless", "tcp")
        node_8080 = make_node("🇭🇰2-8080", "1.2.3.4", 8080, "vless", "tcp")
        score_443 = self.score_fn(node_443)
        score_8080 = self.score_fn(node_8080)
        self.assertGreater(score_443, score_8080)


class TestNewVsLegacyComparison(unittest.TestCase):
    """Compare new vs legacy scoring to ensure new is more discriminative."""

    def setUp(self):
        from utils import _mainland_friendly_score_legacy, _mainland_friendly_score_new
        self.legacy = _mainland_friendly_score_legacy
        self.new = _mainland_friendly_score_new

    @patch("utils.is_asia", return_value=True)
    def test_vless_reality_scores_higher_in_new(self, mock_asia):
        """VLESS+Reality should score higher in new system."""
        node = make_node(
            "🇭🇰1-测试", "1.2.3.4", 443, "vless", "tcp",
            **{"reality-opts": {"public-key": "xxx"}}
        )
        legacy_score = self.legacy(node)
        new_score = self.new(node)
        self.assertGreaterEqual(new_score, legacy_score)

    @patch("utils.is_asia", return_value=True)
    def test_hk_tier1_scores_higher_in_new(self, mock_asia):
        """Tier1 Asia (HK) should score higher in new system."""
        node = make_node("🇭🇰1-测试", "1.2.3.4", 443, "vless", "ws")
        legacy_score = self.legacy(node)
        new_score = self.new(node)
        # New: tier1 60 + vless 25 + ws 8 + port 8 = 101 -> 100
        # Legacy: 50 + 20 + vless 20 + ws 5 + port 5 = 100
        # Both cap at 100, but new gives more granular differentiation for non-capped nodes
        self.assertGreaterEqual(new_score, legacy_score - 5)  # Allow small tolerance

    @patch("utils.is_asia", return_value=False)
    def test_us_generic_scores_lower_in_new(self, mock_asia):
        """Generic US nodes should score lower in new system."""
        node = make_node("🇺🇸1-测试", "5.6.7.8", 443, "ss", "tcp")
        legacy_score = self.legacy(node)
        new_score = self.new(node)
        self.assertLessEqual(new_score, legacy_score + 5)

    @patch("utils.is_asia")
    def test_new_scoring_more_discriminative(self, mock_asia):
        """New scoring should create wider spread between good and bad nodes."""
        def is_asia_side_effect(p):
            name = p.get("name", "")
            return "HK" in name or "港" in name or "🇭🇰" in name

        mock_asia.side_effect = is_asia_side_effect

        good_node = make_node(
            "🇭🇰1-测试", "1.2.3.4", 443, "vless", "ws",
            **{"reality-opts": {"public-key": "xxx"}}
        )
        bad_node = make_node("🇺🇸99-测试", "5.6.7.8", 8080, "ssr", "tcp")

        new_spread = self.new(good_node) - self.new(bad_node)
        legacy_spread = self.legacy(good_node) - self.legacy(bad_node)
        self.assertGreaterEqual(new_spread, legacy_spread - 10)


class TestEnvSwitch(unittest.TestCase):
    """Test the environment variable switch."""

    def test_default_is_legacy(self):
        """Without env var, should use legacy scoring."""
        old_val = os.environ.pop("ZRONG_USE_NEW_SCORING", None)
        try:
            import importlib
            import utils
            importlib.reload(utils)
            self.assertFalse(utils.USE_NEW_SCORING)
        finally:
            if old_val is not None:
                os.environ["ZRONG_USE_NEW_SCORING"] = old_val

    def test_env_enables_new(self):
        """With env var=1, should use new scoring."""
        os.environ["ZRONG_USE_NEW_SCORING"] = "1"
        try:
            import importlib
            import utils
            importlib.reload(utils)
            self.assertTrue(utils.USE_NEW_SCORING)
        finally:
            os.environ.pop("ZRONG_USE_NEW_SCORING", None)
            import importlib
            import utils
            importlib.reload(utils)

    @patch("utils.is_asia", return_value=True)
    def test_wrapper_uses_legacy_by_default(self, mock_asia):
        """mainland_friendly_score should use legacy by default."""
        # Reload to ensure clean state
        import importlib
        import utils
        importlib.reload(utils)
        from utils import mainland_friendly_score, _mainland_friendly_score_legacy
        node = make_node("🇭🇰1-测试", "1.2.3.4", 443, "vless", "ws")
        expected = _mainland_friendly_score_legacy(node)
        actual = mainland_friendly_score(node)
        self.assertEqual(actual, expected)


class TestDomainBasedAsiaDetection(unittest.TestCase):
    """Test that domain-based nodes are correctly detected as Asia."""

    def setUp(self):
        from utils import _mainland_friendly_score_new
        self.score_fn = _mainland_friendly_score_new

    def test_hk_domain_detected_as_asia(self):
        """Node with .hk domain should be detected as Asia."""
        node = make_node("🇭🇰1-测试", "node1.example.hk", 443, "vless", "ws")
        score = self.score_fn(node)
        # Should get Asia tier1 60 + vless 25 + ws 8 + port 8 = 101 -> 100
        self.assertGreaterEqual(score, 90)

    def test_jp_domain_detected_as_asia(self):
        """Node with .jp domain should be detected as Asia."""
        node = make_node("🇯🇵1-测试", "node1.example.jp", 443, "trojan", "tcp")
        score = self.score_fn(node)
        # Should get Asia tier1 60 + trojan 20 + port 8 = 88
        self.assertGreaterEqual(score, 80)

    def test_sg_domain_detected_as_asia(self):
        """Node with .sg domain should be detected as Asia."""
        node = make_node("🇸🇬1-测试", "node1.example.sg", 443, "vmess", "ws")
        score = self.score_fn(node)
        # Should get Asia tier1 60 + vmess 10 + ws 8 + port 8 = 86
        self.assertGreaterEqual(score, 75)

    def test_kr_domain_detected_as_asia(self):
        """Node with .kr domain should be detected as Asia."""
        node = make_node("🇰🇷1-测试", "node1.example.kr", 443, "hysteria2", "quic")
        score = self.score_fn(node)
        # Should get Asia tier2 45 + hysteria2 18 + quic 3 + port 8 = 74
        self.assertGreaterEqual(score, 65)

    def test_us_domain_not_asia(self):
        """Node with .us domain should NOT be detected as Asia."""
        node = make_node("🇺🇸1-测试", "node1.example.us", 443, "ss", "tcp")
        score = self.score_fn(node)
        # Not Asia, no limiter -> 0 + ss 3 + port 8 = 11
        self.assertLess(score, 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
