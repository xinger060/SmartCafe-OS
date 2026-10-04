#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实测 run.sh 里那段 node 合并脚本（不是重写一份，是从 run.sh 里抠出来跑）。

覆盖三种场景：
  A. 选项里的令牌是空的 → 不能把 config.json 里已有的令牌抹掉
  B. 选项里设了令牌       → 要覆盖进去
  C. config.json 不存在   → 要能新建，且端口必须是 8766（否则 ingress 打不开）
外加 D. 非选项字段（password_hash 等）必须原样保留
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RUN_SH = os.path.join("smartcafe_server", "run.sh")
TOKEN_OLD = "eyJOLD-" + "x" * 160
TOKEN_NEW = "eyJNEW-" + "y" * 160

src = open(RUN_SH, encoding="utf-8").read()

# 抠出 node -e ' ... ' 之间的内容
m = re.search(r"node -e '\n(.*?)\n'", src, re.S)
if not m:
    print("❌ 没能从 run.sh 里抠出 node 脚本")
    sys.exit(1)
script = m.group(1)
print("从 run.sh 抠出 node 脚本 %d 行" % len(script.splitlines()))
print()


def run_case(name, initial, env_token, expect):
    tmpdir = tempfile.mkdtemp()
    cfg_path = os.path.join(tmpdir, "config.json")
    if initial is not None:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(initial, f, ensure_ascii=False, indent=2)

    s = script.replace("/data/smartcafe-server/config.json", cfg_path.replace("\\", "/"))
    js = os.path.join(tmpdir, "merge.js")
    with open(js, "w", encoding="utf-8") as f:
        f.write(s)

    env = dict(os.environ)
    env.update({
        # ⚠️ 这里是【假值】。这个文件会跟着 smartcafe_server/ 一起进公开仓库，
        #    绝对不能写真实的 HA 地址/账号/密码/令牌。
        #    （踩过：曾经把真实的 HA 密码写在这里，结果泄露到公开仓库。）
        "HA_BASE_URL": "http://192.168.1.100",
        "HA_USERNAME": "testuser",
        "HA_PASSWORD": "test-password-not-real",
        "HA_TOKEN_REFRESH_TIME": "",
        "HA_LONG_LIVED_TOKEN": env_token,
    })
    p = subprocess.run(["node", js], capture_output=True, text=True,
                       env=env, errors="replace")
    if p.returncode != 0:
        print("  ❌ %s：node 执行失败\n%s" % (name, p.stderr[:400]))
        return False
    if not os.path.exists(cfg_path):
        print("  ❌ %s：config.json 没生成" % name)
        return False
    got = json.load(open(cfg_path, encoding="utf-8"))

    ok = True
    for k, v in expect.items():
        if callable(v):
            if not v(got):
                print("  ❌ %s：%s 不符合预期（实际 %r）" % (name, k, got.get(k)))
                ok = False
        elif got.get(k) != v:
            print("  ❌ %s：%s 期望 %r，实际 %r" % (name, k, v, got.get(k)))
            ok = False
    print("  %s %s" % ("✅" if ok else "❌", name))
    return ok


allok = True

allok &= run_case(
    "A. 选项令牌为空 → 保留 config.json 里已有的令牌",
    {"ha_base_url": "http://old", "ha_long_lived_token": TOKEN_OLD,
     "password_hash": "abc", "password_salt": "def", "port": 8766},
    "",
    {"ha_long_lived_token": TOKEN_OLD, "port": 8766,
     "password_hash": "abc", "password_salt": "def",
     "ha_base_url": "http://192.168.1.100"},
)

allok &= run_case(
    "B. 选项里设了令牌 → 覆盖进去",
    {"ha_base_url": "http://old", "ha_long_lived_token": TOKEN_OLD, "port": 8766},
    TOKEN_NEW,
    {"ha_long_lived_token": TOKEN_NEW, "port": 8766},
)

allok &= run_case(
    "C. config.json 不存在 → 新建，端口必须是 8766",
    None,
    TOKEN_NEW,
    {"ha_long_lived_token": TOKEN_NEW, "port": 8766,
     "ha_base_url": "http://192.168.1.100", "ha_username": "testuser",
     "token_refresh_time": "", "password_hash": "", "password_salt": ""},
)

allok &= run_case(
    "D. 自定义字段不能被丢掉",
    {"ha_base_url": "http://old", "port": 8766,
     "我自己的字段": "要保留", "password_hash": "h", "password_salt": "s"},
    "",
    {"我自己的字段": "要保留", "password_hash": "h", "password_salt": "s", "port": 8766},
)

print()
print("=== %s ===" % ("全部通过 ✅" if allok else "有失败 ❌"))
sys.exit(0 if allok else 1)
