# core/clash.py - ClashManager
# v28.41 Phase3 重构
import gzip
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import yaml

import requests
from network.geo import _geoip2_lookup, _GEOIP2_AVAILABLE
from core.config import (
    ensure_clash_dir,
    CLASH_PORT,
    CLASH_API_PORT,
    CLASH_VERSION,
    CLASH_PATH,
    CONFIG_FILE,
    LOG_FILE,
    TEST_URLS,
    TEST_URLS_BACKUP,
)
from utils import WORK_DIR

class ClashManager:
    def __init__(self):
        self.process = None
        self._geo_cache = {}  # v28.61: 缓存出口IP归属，避免重复调用ip-api.com
        self._exit_ip_cache = {}  # v28.98: 已废弃，保留避免属性引用错误
        ensure_clash_dir()

    def download_clash(self):
        if CLASH_PATH.exists():
            return True
        # ISSUE-3-03: 跨平台 Clash 二进制下载
        import platform
        sys = platform.system().lower()
        arch = platform.machine().lower()
        if sys == "windows":
            if "arm" in arch:
                clang_name = f"mihomo-windows-arm64-compatible-{CLASH_VERSION}.exe.gz"
            else:
                clang_name = f"mihomo-windows-amd64-compatible-{CLASH_VERSION}.exe.gz"
        elif sys == "darwin":
            if "arm" in arch:
                clang_name = f"mihomo-darwin-arm64-compatible-{CLASH_VERSION}.gz"
            else:
                clang_name = f"mihomo-darwin-amd64-compatible-{CLASH_VERSION}.gz"
        else:  # Linux
            if "arm" in arch:
                clang_name = f"mihomo-linux-arm64-compatible-{CLASH_VERSION}.gz"
            else:
                clang_name = f"mihomo-linux-amd64-compatible-{CLASH_VERSION}.gz"
        url = (
            f"https://github.com/MetaCubeX/mihomo/releases/download/{CLASH_VERSION}/"
            f"{clang_name}"
        )
        try:
            resp = requests.get(url, timeout=120, stream=True)
            if resp.status_code != 200:
                return False
            temp = WORK_DIR / "mihomo.gz"
            with open(temp, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            # v28.50: 使用独立变量确保文件句柄可关闭
            f_in = None
            f_out = None
            try:
                f_in = gzip.open(temp, "rb")
                f_out = open(CLASH_PATH, "wb")
                shutil.copyfileobj(f_in, f_out)
            finally:
                if f_in:
                    try:
                        f_in.close()
                    except OSError as e:
                        logging.debug(f"关闭输入文件失败: {e}", exc_info=True)
                if f_out:
                    try:
                        f_out.close()
                    except OSError as e:
                        logging.debug(f"关闭输出文件失败: {e}", exc_info=True)
            if os.name != 'nt':  # Windows 不支持 os.chmod 的 Unix 权限
                os.chmod(CLASH_PATH, 0o755)
            temp.unlink(missing_ok=True)
            return CLASH_PATH.exists()
        except (requests.RequestException, OSError, gzip.BadGzipFile):
            logging.debug("Exception occurred", exc_info=True)
            return False

    def _clean_proxy_for_clash(self, p):
        """清洗代理字典，移除内部字段和 Clash 不支持的字段"""
        # 白名单：Clash Meta 支持的字段
        CLASH_FIELDS = {
            'name','type','server','port','udp','tfo','mptcp',
            'skip-cert-verify','sni','servername','tls','alpn','ca','cert','key',
            'client-fingerprint','obfs','obfs-password',
            'network','ws-opts','grpc-opts','h2-opts','http-opts',
            'reality-opts','flow','pinned-sha256','dialer-proxy',
            'cipher','password','plugin','plugin-opts',
            'uuid','alterId','aid',
            'protocol','protocol-param','obfs','obfs-param',
            'auth-str','up','down',
            'congestion-controller',
            # hysteria2
            'password','obfs','obfs-password','sni',
            # anytls
            'password','client-fingerprint',
        }
        cleaned = {}
        for k, v in p.items():
            if k.startswith('_'):  # 内部字段（_src_weight 等）
                continue
            if k not in CLASH_FIELDS:
                logging.debug("Clash: 移除不支持字段 %s from %s", k, p.get('name','?'))
                continue
            # None 值保留（yaml.dump 会写成 null，Clash 可处理）
            cleaned[k] = v
        # BUGFIX v28.40: 校验并清理 REALITY short-id，防止 Clash 崩溃
        if cleaned.get('reality-opts'):
            ro = cleaned['reality-opts']
            if isinstance(ro, dict):
                sid = ro.get('short-id', '')
                # Clash Meta 要求 short-id 为 8/16/32 字符十六进制，或空字符串
                if sid and not re.fullmatch(r'[0-9a-fA-F]{8}|[0-9a-fA-F]{16}|[0-9a-fA-F]{32}', str(sid)):
                    logging.warning("Clash: 移除无效 REALITY short-id '%s' from %s", sid, cleaned.get('name', '?'))
                    del ro['short-id']
                    if not ro:
                        del cleaned['reality-opts']
        return cleaned

    def create_config(self, proxies):
        ensure_clash_dir()
        # BUGFIX v28.26: 过滤 Clash 不支持的协议（anytls 等）
        SUPPORTED_TYPES = {
            'ss', 'ssr', 'vmess', 'vless', 'trojan', 'socks5', 'http',
            'hysteria', 'hysteria2', 'tuic', 'snell', 'mieru', 'juicity'
        }
        filtered = []
        for p in proxies:
            if p.get('type', '').lower() not in SUPPORTED_TYPES:
                logging.debug("Clash: 跳过不支持的协议类型 %s from %s", p.get('type'), p.get('name','?'))
                continue
            filtered.append(p)
        if not filtered:
            logging.info("[CLASH] 所有节点协议均不支持，无法生成配置")
            return False
        # BUGFIX: 移除内部双重截断，调用方已用 batch_size 限制了 proxies 数量
        # 原代码 proxies[:MAX_PROXY_TEST_NODES] 出现两次，与外层 batch_size 职责重叠
        names = []
        seen = set()
        cleaned_proxies = [self._clean_proxy_for_clash(p) for p in filtered]

        # BUG[4-02] 修复：必填字段验证
        required_fields = {"name", "type", "server", "port"}
        valid_proxies = []
        for p in cleaned_proxies:
            missing = required_fields - set(p.keys())
            if missing:
                logging.warning("Clash: 跳过缺少必填字段 %s 的节点 %s", missing, p.get("name", "?"))
                continue
            # port 必须是有效数字
            try:
                port = int(p["port"])
                if not (1 <= port <= 65535):
                    raise ValueError
            except (ValueError, TypeError):
                logging.warning("Clash: 跳过端口无效 %s 的节点 %s", p.get("port"), p.get("name", "?"))
                continue
            valid_proxies.append(p)

        if not valid_proxies:
            logging.info("[CLASH] 所有节点缺少必填字段或端口无效，无法生成配置")
            return False

        for i, p in enumerate(valid_proxies):
            name = p["name"]
            if name in seen:
                name = f"{name}-{i}"
            seen.add(name)
            names.append(name)
            p["name"] = name
                # v30.0: 简化Clash配置——移除rule-providers/DNS fake-ip（下载耗时不稳定）
        # 测速环境只需：所有流量走TEST代理组，无需路由规则和DNS提供者
        rules = ["MATCH,TEST"]

        config = {
            "port": CLASH_PORT, "socks-port": CLASH_PORT + 1, "allow-lan": False, "mode": "global",
            "log-level": "error", "external-controller": f"127.0.0.1:{CLASH_API_PORT}",
            "secret": "",
            "ipv6": False, "unified-delay": True, "tcp-concurrent": True,
            # v30.0: 简化DNS——仅用公共DNS，无需fake-ip和规则提供者
            "dns": {
                "enable": True,
                "listen": "0.0.0.0:1053",
                "enhanced-mode": "normal",
                "nameserver": [
                    "8.8.8.8",
                    "1.1.1.1",
                ],
            },
            "proxies": valid_proxies,
            "proxy-groups": [{"name": "TEST", "type": "select", "proxies": names}],
            "rules": rules
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, Dumper=yaml.SafeDumper)
        return True

    def start(self):
        ensure_clash_dir()
        if not CLASH_PATH.exists() and not self.download_clash():
            logging.info("[CLASH] mihomo 二进制文件不存在且下载失败")
            return False
        LOG_FILE.touch()
        try:
            cmd = [str(CLASH_PATH.absolute()), "-d", str(WORK_DIR.absolute()), "-f", str(CONFIG_FILE.absolute())]
            # BUGFIX v28.15: preexec_fn=os.setsid 仅 Linux 可用，Windows 不支持
            popen_kwargs = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "cwd": str(
                    WORK_DIR.absolute())}
            if os.name != "nt":
                # pylint: disable=no-member
                popen_kwargs["preexec_fn"] = os.setsid  # type: ignore[attr-defined]
            self.process = subprocess.Popen(cmd, **popen_kwargs)
            # v28.39: 初始化 out 避免未定义
            out = ""
            # v28.50: 确保进程管道正确关闭
            api_ready = False
            try:
                for i in range(30):
                    time.sleep(1)
                    if self.process.poll() is not None:
                        try:
                            out, _ = self.process.communicate(timeout=5)
                            out_short = out[:500] + "\n...\n" + out[-500:] if len(out) > 1000 else out
                            logging.info(f"[CLASH] 进程崩溃，输出:\n{out_short}")
                        except (subprocess.TimeoutExpired, OSError):
                            logging.info("[CLASH] 进程崩溃，无法读取输出")
                        return False
                    try:
                        if requests.get(f"http://127.0.0.1:{CLASH_API_PORT}/version", timeout=2).status_code == 200:
                            logging.info("[CLASH] API 就绪")
                            api_ready = True
                            break
                    except requests.RequestException:
                        if i < 3:
                            logging.info(f"[CLASH] API 未就绪，等待中... ({i+1}/30)")
                if not api_ready:
                    logging.info("[CLASH] 启动超时（30秒）")
                    return False
            except (OSError, subprocess.SubprocessError) as e:
                logging.info(f"[CLASH] 启动异常：{e}")
                return False
            return True
        except (OSError, subprocess.SubprocessError) as e:
            logging.info(f"[CLASH] Popen 异常：{e}")
            return False

    def stop(self):
        if self.process:
            try:
                # BUGFIX v28.15: os.killpg/signal.SIGTERM 仅 Linux 可用
                if os.name != "nt":
                    # pylint: disable=no-member
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)  # type: ignore[attr-defined]
                else:
                    self.process.terminate()
                self.process.wait(timeout=5)
            except (OSError, subprocess.SubprocessError):
                logging.debug("Clash stop failed")
            self.process = None

    def test_proxy(self, name, server=None, port=None, retry=False):
        """v30.1: 双层验证——1)代理能连上 2)能访问国内网站(说明代理通了)"""
        result = {"success": False, "latency": 9999.0, "speed": 0.0, "error": "", "mainland_reachable": False}
        try:
            requests.put(f"http://127.0.0.1:{CLASH_API_PORT}/proxies/GLOBAL", json={"name": name}, timeout=2)
            time.sleep(0.03)
            px = {"http": f"http://127.0.0.1:{CLASH_PORT}", "https": f"http://127.0.0.1:{CLASH_PORT}"}

            # 第一层：测试代理是否能连上（SSL握手）
            connected = False
            for url in TEST_URLS:
                try:
                    start = time.time()
                    resp = requests.get(url, proxies=px, timeout=(5, 8), allow_redirects=True)
                    elapsed = (time.time() - start) * 1000
                    if resp.status_code == 200:
                        connected = True
                        result["latency"] = round(elapsed, 1)
                        result["speed"] = len(resp.content) / 1024 / max(elapsed / 1000, 0.01)
                        break
                except requests.ConnectTimeout:
                    break
                except requests.ReadTimeout:
                    break
                except requests.RequestException:
                    continue

            if not connected:
                # 备用池
                for url in TEST_URLS_BACKUP:
                    try:
                        start = time.time()
                        resp = requests.get(url, proxies=px, timeout=(3, 5), allow_redirects=True)
                        elapsed = (time.time() - start) * 1000
                        if resp.status_code in (200, 204):
                            connected = True
                            result["latency"] = round(elapsed, 1)
                            result["speed"] = 1.0
                            break
                    except requests.RequestException:
                        continue

            if not connected:
                result["error"] = "Connection failed"
                return result

            # 第二层：验证代理能访问国内网站（关键！）
            # 如果连不上百度，说明代理没真正通（可能是 false positive）
            mainland_ok = False
            for url in ["http://www.baidu.com", "http://www.qq.com"]:
                try:
                    resp = requests.get(url, proxies=px, timeout=(5, 10))
                    if resp.status_code == 200:
                        mainland_ok = True
                        result["mainland_reachable"] = True
                        break
                except requests.RequestException:
                    continue

            # v30.1: 只有能访问国内网站，才算真正通过
            if mainland_ok:
                result["success"] = True
            else:
                result["success"] = False
                result["error"] = "Cannot access mainland sites"

        except requests.RequestException as e:
            result["error"] = str(e)[:60]

        if retry and not result["success"]:
            time.sleep(0.3)
            return self.test_proxy(name, server=server, port=port, retry=False)
        return result