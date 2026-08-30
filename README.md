# MinecraftQueqiao

<p align="center">
  <a href="https://github.com/Genshin-bots/gsuid_core"><img src="ICON.png" height="250" alt="MinecraftQueqiao"></a>
</p>
<h1 align="center">MinecraftQueqiao</h1>
<h4 align="center">基于 gsuid_core 和鹊桥的反向 WebSocket 互通插件</h4>
<div align="center">
  <a href="https://docs.sayu-bot.com/" target="_blank">安装文档 (gscore)</a> &nbsp; · &nbsp;
  <a href="https://queqiao-docs.pages.dev/deploy/" target="_blank">安装文档 (QueQiao)</a> &nbsp; · &nbsp;
  <a href="https://github.com/Genshin-bots/gsuid_core" target="_blank">gsuid_core</a>
</div>

## 丨安装提醒

> **注意：该插件为 [早柚核心(gsuid_core)](https://github.com/Genshin-bots/gsuid_core) 的扩展，具体安装方式可参考上方安装文档**
>
> **运行环境要求 Python `3.12+`**
>
> 🚧 项目快速迭代中，如有 BUG 欢迎 PR 🚧

## 丨绑定 / 使用教程

#### 1. 安装鹊桥服务端
前往 [Modrinth](https://modrinth.com/plugin/queqiao) 或 [CurseForge](https://www.curseforge.com/minecraft/mc-mods/queqiao) 下载并安装服务端对应的 `插件/Mod`。
- 插件端配置文件位于 `./plugins/QueQiao/config.yml`。
- 模组端配置文件位于 `./config/QueQiao/config.yml`。

#### 2. 配置鹊桥 `config.yml`（反向 WebSocket 连接）
```yaml
server_name: "MyServer"        # 服务器名称（需与 Gscore 中配置的 ServerName 一致）
access_token: "your_token"     # 访问密钥（选填，与 Gscore 一致）

websocket_server:
  enable: false                # 关闭鹊桥本地服务端

websocket_client:
  enable: true                 # 开启反向客户端连接
  reconnect_interval: 5
  reconnect_max_times: 0
  url_list:
    - "ws://127.0.0.1:8765/minecraft/ws/MyServer"
    # MyServer未填写时默认使用 server_name 值
    # 127.0.0.1 应为 gscore 基础地址
```

#### 3. 启动 Minecraft 服务器

#### 4. 在 Gscore 中安装本插件
- **方法一**：从 Gscore 网页控制台安装：`网页控制台 -> 插件商城 -> 从 URL 安装`
- **方法二**：手动安装：下载本仓库并放置在 `gsuid_core/plugins/` 目录下。

#### 5. 在网页控制台中添加服务器
1. 访问 Gscore `网页控制台 -> 数据库管理 -> MinecraftQueqiao -> 绑定服务器 -> 新增`
2. 填入服务器相关信息：
   - `是否启用`: 是否启用该服务器连接
   - `ServerName`: 鹊桥配置中的 `server_name`（或连接 URL 路径后缀）
   - `服务器外显名`: 聊天转发与状态查询时展示的服务器名（留空默认使用 ServerName）
   - `access_token`: 鹊桥密钥（选填，若配置了则需与鹊桥一致）
   - `启用 ChatImage`: 若安装了 [ChatImage](https://www.mcmod.cn/class/9111.html) MOD 可开启聊天框图片预览

#### 6. 配置全局设置与事件订阅
访问 Gscore `网页控制台 -> 插件配置 -> MinecraftQueqiao`：
- **群聊显示服务器外显名**：消息转发到群聊时是否附带 `[服务器名]` 前缀。
- **订阅事件**：可自由勾选订阅 `玩家聊天`、`玩家加入`、`玩家退出`、`玩家死亡`、`玩家命令`、`玩家成就`。
- **RCON 超时时间(秒)**：WebSocket 执行命令等待超时秒数（默认 8 秒）。
- **群聊消息转发**：是否开启群聊消息转发到 MC 服务器。
- **群聊 -> MC 消息白名单**：转发到 MC 需要的前缀或正则表达式列表（默认 `["mcqq"]`）。
  - **普通前缀**：直接填写文本（如 `mcqq`），触发转发后会**自动去除该前缀**。
  - **正则表达式**：以 `r:` 开头（如 `r:^#.*`），匹配成功后会**保留原消息完整内容**（不剔除前缀）。
  - 支持配置多项，只要满足任意一项即可触发转发。
- **群聊 -> MC 消息黑名单**：屏蔽转发到 MC 的前缀或正则表达式列表（默认 `[]`）。**仅在白名单为空时生效**。命中任一规则的消息将不会被转发到 MC。
- **MC -> 群聊 消息白名单**：转发到群聊需要的前缀或正则表达式列表（默认 `[]`）。
  - 规则同上：普通前缀触发后自动去除，`r:` 开头的正则表达式匹配后保留原内容。
- **MC -> 群聊 消息黑名单**：屏蔽转发到群聊的前缀或正则表达式列表（默认 `[]`）。**仅在白名单为空时生效**。命中任一规则的消息将不会被转发到群聊。

---

## 丨指令列表

> **`[ ]` 表示选填，`< >` 表示必填**

| 指令 | 功能 | 权限 |
| :--- | :--- | :---: |
| `mc群服绑定 <服务器>` | 将当前群绑定到指定服务器 | 群员 |
| `mc群服解绑 <服务器>` | 解除当前群与指定服务器的绑定 | 群员 |
| `mc查看 [服务器]` | 查询当前群绑定的服务器在线状态 | 群员 |
| `mc连接状态` / `mcws状态` | 查看所有服务器的反向 WS 连接在线状态 | 管理员 |
| `mc广播 [服务器] <内容>` | 向服务器发送屏幕大标题 (Title) 广播 | 管理员 |
| `mc公告 [服务器] <内容>` | 向服务器聊天栏发布广播文字 | 管理员 |
| `mcrcon [服务器] <指令>` | 通过 WebSocket 向服务器执行控制台指令并返回回显 | 管理员 |
| `mc删除旧表` | 清理插件旧数据表并提示重启以重新初始化数据库结构 | 管理员 |

| 待填坑 |
|:----------:|
|mc私聊|
|mc定时公告|
|假人过滤|
|mc调用机器人指令|
|鹊桥版本分版本功能支持|
|mc动作栏|
|正向ws(待确认)|
|mc绑定服务器命令|
|mc绑定id(支持群服同id自动识别)|
|rcon白名单(增删)|
|playwright 渲染|
|非 ChatImage 模式下的链接点击交互 (ClickEvent)|
|转发指令过滤黑名单|
|死亡与成就消息本地化汉化|
|跨服聊天互通(服A <-> 服B)|
|传送点设置 / 传送(mc传送[point] / mc添加路径点[point])|
|等等......|

---

## 丨其他

- 本项目仅供学习使用，请勿用于商业用途
- [GPL-3.0 License](LICENSE)
- [QueQiao Wiki](https://queqiao-docs.pages.dev/)

## 致谢

- [Wuyi 无疑](https://github.com/KimigaiiWuyi)
- [gsuid_core](https://github.com/Genshin-bots/gsuid_core)
- [鹊桥 QueQiao](https://www.mcmod.cn/class/18274.html)
