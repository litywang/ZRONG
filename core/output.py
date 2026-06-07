# core/output.py - format_proxy_to_link
# v28.41 Phase3 重构

def format_proxy_to_link(p):
    """将代理对象转换为协议链接"""
    try:
        ptype = p.get("type", "")
        name_enc = urllib.parse.quote(p.get("name", "node"), safe="")

        if ptype == "vmess":
            # v28.19: 修复host来源，优先从ws-opts获取
            ws_opts = p.get("ws-opts", {})
            host = ws_opts.get("headers", {}).get("Host", "")
            if not host:
                host = p.get("sni", "")
            data = {"v": "2", "ps": p["name"], "add": p["server"], "port": p["port"],
                    "id": p["uuid"], "aid": p.get("alterId", 0), "net": p.get("network", "tcp"),
                    "type": "none", "host": host, "path": ws_opts.get("path", ""),
                    "tls": "tls" if p.get("tls") else ""}
            # BUGFIX v28.20: 补充 alpn 字段
            if p.get("alpn"):
                data["alpn"] = ",".join(p["alpn"]) if isinstance(p["alpn"], list) else p["alpn"]
            # BUGFIX v28.20: h2 传输层信息
            if p.get("network") == "h2" and p.get("h2-opts"):
                h2o = p["h2-opts"]
                data["path"] = h2o.get("path", data["path"])
                h2_host = h2o.get("host", [])
                if isinstance(h2_host, list) and h2_host:
                    data["host"] = h2_host[0]
                elif isinstance(h2_host, str) and h2_host:
                    data["host"] = h2_host
            # BUGFIX: grpc 传输层信息
            if p.get("grpc-opts"):
                data["path"] = p["grpc-opts"].get("grpc-service-name", "")
                data["host"] = ""
                data["type"] = "gun"
            return "vmess://" + base64.b64encode(json.dumps(data, separators=(',', ':')).encode()).decode()

        elif ptype == "trojan":
            pwd_enc = urllib.parse.quote(p.get('password', ''), safe='')
            sni = p.get('sni', p.get('server', ''))
            # BUGFIX v28.20: 添加传输层类型和参数
            ttype = p.get('network', 'tcp')
            params = f"sni={urllib.parse.quote(str(sni), safe='')}&type={ttype}&allowInsecure=1"
            # WS 传输参数
            if ttype == 'ws':
                ws_opts = p.get('ws-opts', {})
                if ws_opts.get('path'):
                    params += f"&path={urllib.parse.quote(ws_opts['path'], safe='')}"
                ws_host = ws_opts.get('headers', {}).get('Host', '')
                if ws_host:
                    params += f"&host={urllib.parse.quote(ws_host, safe='')}"
            # GRPC 传输参数
            if ttype == 'grpc' and p.get('grpc-opts'):
                svc = p['grpc-opts'].get('grpc-service-name', '')
                if svc:
                    params += f"&serviceName={urllib.parse.quote(svc, safe='')}"
            # alpn/fingerprint
            # v28.23: alpn 类型容错（YAML直接加载时可能是字符串）
            if p.get('alpn'):
                alpn_val = p['alpn']
                if isinstance(alpn_val, str):
                    alpn_list = [a.strip() for a in alpn_val.split(',') if a.strip()]
                elif isinstance(alpn_val, list):
                    alpn_list = alpn_val
                else:
                    alpn_list = []
                if alpn_list:
                    params += f"&alpn={','.join(alpn_list)}"
            if p.get('client-fingerprint'):
                params += f"&fp={p['client-fingerprint']}"
            return f"trojan://{pwd_enc}@{p['server']}:{p['port']}?{params}#{name_enc}"

        elif ptype == "vless":
            uuid = p.get('uuid', '')
            # v28.19: 修复reality参数丢失
            has_reality = bool(p.get('reality-opts'))
            security = "reality" if has_reality else ("tls" if p.get('tls') else "none")
            flow = p.get('flow', '')
            params = f"encryption=none&type={p.get('network', 'tcp')}&security={security}"
            # BUGFIX v28.20: vless WS 传输层参数（path/host）
            if p.get('network') == 'ws':
                ws_opts = p.get('ws-opts', {})
                if ws_opts.get('path'):
                    params += f"&path={urllib.parse.quote(ws_opts['path'], safe='')}"
                ws_host = ws_opts.get('headers', {}).get('Host', '')
                if ws_host:
                    params += f"&host={urllib.parse.quote(ws_host, safe='')}"
            # BUGFIX: grpc 传输层信息
            if p.get('network') == 'grpc' and p.get('grpc-opts'):
                svc = p['grpc-opts'].get('grpc-service-name', '')
                if svc:
                    params += f"&serviceName={svc}"
            if flow:
                params += f"&flow={flow}"
            if p.get('sni'):
                params += f"&sni={urllib.parse.quote(str(p['sni']), safe='')}"
            # v28.19: 添加reality必要参数
            if has_reality:
                ro = p['reality-opts']
                params += f"&pbk={ro.get('public-key', '')}&sid={ro.get('short-id', '')}"
                fp = p.get('client-fingerprint', 'chrome')
                params += f"&fp={fp}"
            return f"vless://{uuid}@{p['server']}:{p['port']}?{params}#{name_enc}"

        elif ptype == "ss":
            auth = f"{p['cipher']}:{p['password']}"
            auth_enc = base64.b64encode(auth.encode()).decode()
            return f"ss://{auth_enc}@{p['server']}:{p['port']}#{name_enc}"

        elif ptype == "ssr":
            # BUGFIX v28.20: 输出合法 SSR 链接（而非注释）
            # SSR 格式: ssr://base64(server:port:protocol:method:obfs:base64pass/?params)
            try:
                server = p.get('server', '')
                port = p.get('port', 0)
                protocol = p.get('protocol', 'origin')
                method = p.get('method') or p.get('cipher', 'aes-256-cfb')
                obfs = p.get('obfs', 'plain')
                password = p.get('password', '')
                b64_pwd = base64.b64encode(password.encode()).decode().rstrip('=')
                main_part = f"{server}:{port}:{protocol}:{method}:{obfs}:{b64_pwd}"
                params_parts = []
                obfs_param = p.get('obfs-param', '')
                if obfs_param:
                    b64_op = base64.b64encode(obfs_param.encode()).decode().rstrip('=')
                    params_parts.append(f"obfsparam={b64_op}")
                proto_param = p.get('protocol-param', '')
                if proto_param:
                    b64_pp = base64.b64encode(proto_param.encode()).decode().rstrip('=')
                    params_parts.append(f"protoparam={b64_pp}")
                remarks = p.get('name', '')
                if remarks:
                    b64_name = base64.b64encode(remarks.encode()).decode().rstrip('=')
                    params_parts.append(f"remarks={b64_name}")
                params_str = '/?' + '&'.join(params_parts) if params_parts else ''
                full = main_part + params_str
                b64_full = base64.b64encode(full.encode()).decode()
                return f"ssr://{b64_full}"
            except (KeyError, ValueError, TypeError):
                logging.debug("Exception occurred", exc_info=True)
                return None  # v28.22: SSR 序列化失败时返回 None 而非注释行，避免客户端解析错误

        elif ptype == "hysteria2":
            pwd = urllib.parse.quote(p.get('password', ''), safe='')
            params = "insecure=1"
            if p.get('sni'):
                params += f"&sni={urllib.parse.quote(str(p['sni']), safe='')}"
            # BUGFIX v28.20: 补充 obfs/obfs-password/fp 参数
            if p.get('obfs'):
                params += f"&obfs={urllib.parse.quote(p['obfs'], safe='')}"
            if p.get('obfs-password'):
                params += f"&obfs-password={urllib.parse.quote(p['obfs-password'], safe='')}"
            if p.get('client-fingerprint'):
                params += f"&fp={p['client-fingerprint']}"
            return f"hysteria2://{pwd}@{p['server']}:{p['port']}?{params}#{name_enc}"

        elif ptype == "hysteria":
            pwd = urllib.parse.quote(p.get('password', ''), safe='')
            return f"hysteria://{pwd}@{p['server']}:{p['port']}#{name_enc}"

        elif ptype == "tuic":
            uuid_val = p.get('uuid', '')
            # BUGFIX v28.20: tuic password 和 uuid 可能不同
            password = p.get('password', uuid_val)
            params = "congestion_control=cubic"
            if p.get('sni'):
                params += f"&sni={urllib.parse.quote(str(p['sni']), safe='')}"
            if p.get('alpn'):
                # v28.23: alpn 类型容错
                _alpn_v = p['alpn']
                if isinstance(_alpn_v, str):
                    _alpn_v = [a.strip() for a in _alpn_v.split(',') if a.strip()]
                if isinstance(_alpn_v, list) and _alpn_v:
                    params += f"&alpn={','.join(_alpn_v)}"
            if p.get('client-fingerprint'):
                params += f"&fp={p['client-fingerprint']}"
            return f"tuic://{uuid_val}:{password}@{p['server']}:{p['port']}?{params}#{name_enc}"

        elif ptype == "snell":
            pwd = urllib.parse.quote(p.get('psk', ''), safe='')
            return f"snell://{pwd}@{p['server']}:{p['port']}#{name_enc}"

        elif ptype == "socks5":
            auth = ""
            if p.get('username') and p.get('password'):
                auth = f"{urllib.parse.quote(p['username'])}:{urllib.parse.quote(p['password'])}@"
            return f"socks5://{auth}{p['server']}:{p['port']}#{name_enc}"

        elif ptype == "http":
            auth = ""
            if p.get('username') and p.get('password'):
                auth = f"{urllib.parse.quote(p['username'])}:{urllib.parse.quote(p['password'])}@"
            scheme = "https" if p.get('tls') else "http"
            return f"{scheme}://{auth}{p['server']}:{p['port']}#{name_enc}"

        return None  # v28.22: 未知协议返回None而非注释行，避免客户端解析错误
    except (KeyError, ValueError, TypeError):
        logging.debug("Exception occurred", exc_info=True)
        return None  # v28.22: 异常时返回None而非注释行
