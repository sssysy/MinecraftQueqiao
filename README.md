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

#### 5. 添加服务器
##### （1）通过指令绑定服务器（推荐）
- 输入指令 `mc添加服务器` ，之后根据提示进行操作即可。
##### （2）通过网页控制台添加服务器
1. 访问 Gscore `网页控制台 -> 数据库管理 -> MinecraftQueqiao -> 绑定服务器 -> 新增`
2. 填入服务器相关信息：

| 配置项 | 说明 |
| :--- | :--- |
| **是否启用** | 是否启用该服务器连接 |
| **ServerName** | 鹊桥配置中的 `server_name` |
| **服务器外显名** | 聊天转发与状态查询时展示的服务器名 (可空) |
| **服务器地址** | Minecraft 服务器直连地址 |
| **access_token** | 鹊桥 access_token |
| **启用 ChatImage** | 若安装了 [ChatImage](https://www.mcmod.cn/class/9111.html) MOD 可开启聊天框图片预览 |


#### 6. 插件配置说明
访问 Gscore `网页控制台 -> 插件配置 -> MinecraftQueqiao`：
| 配置项 | 说明 |
| :--- | :--- |
| **群聊显示服务器外显名** | 如：`[外显名] <sssysy> 你好` |
| **订阅事件** | 对应事件需要鹊桥服务端开启事件上报插件才能接收到，单独开启插件端订阅事件无效 |
| **RCON 超时时间(秒)** | 默认8秒 |
| **群聊消息转发** | 群聊消息转发到 MC 服务器的总开关 |
| **群聊 -> MC 消息白名单** | 触发转发到 MC 需要的前缀或正则表达式列表<br>• **普通前缀**：直接填写文本（如 `mcqq`），触发后**自动去除该前缀**<br>• **正则表达式**：以 `r:` 开头（如 `r:^#.*`），匹配后**保留原消息完整内容** |
| **群聊 -> MC 消息黑名单** | 屏蔽转发到 MC 的前缀或正则表达式列表<br>• **仅在白名单为空时生效**，命中任一规则的消息将不会被转发到 MC<br>• 支持普通前缀与以 `r:` 开头的正则表达式 |
| **MC -> 群聊 消息白名单** | 触发转发到群聊需要的前缀或正则表达式列表<br>• **普通前缀**：直接填写文本（如 `mcqq`），触发后**自动去除该前缀**<br>• **正则表达式**：以 `r:` 开头（如 `r:^#.*`），匹配后**保留原消息完整内容** |
| **MC -> 群聊 消息黑名单** | 屏蔽转发到群聊的前缀或正则表达式列表<br>• **仅在白名单为空时生效**，命中任一规则的消息将不会被转发到群聊<br>• 支持普通前缀与以 `r:` 开头的正则表达式 |
| **假人过滤列表** | 过滤假人/Bot的玩家名或正则表达式列表<br>• **普通名称**：直接填写游戏角色名（如 `bot_miner`）<br>• **正则表达式**：以 `r:` 开头（如 `r:^bot_.*` 或 `r:.*_fake$`） |

## 功能使用教程
### 设置定时公告
1. 访问 Gscore `网页控制台 -> 数据库管理 -> MinecraftQueqiao -> 定时公告 -> 新增`
2. 填入公告相关信息：
   - `是否启用`: 是否开启该定时公告
   - `ServerName`: 目标服务器名称（需与绑定的服务器 ServerName 一致；留空则全服广播）
   - `公告内容`: 推送到 Minecraft 聊天栏的公告文本（支持文本和Minecraft Raw JSON）
   - `推送时间/间隔(cron或时间戳)`:
     - **Cron 循环推送**：可通过网站换算
     - **Unix 时间戳定时推送**：可通过网站换算
     - **留空 / 0**：默认不推送
3. **刷新生效**：在网页后台添加或修改数据后，在群聊中发送 `mc刷新定时公告` 指令即可立即重新加载并注册定时任务。

---

## 丨指令列表

> **`[ ]` 表示选填，`< >` 表示必填**

| 指令 | 功能 | 权限 |
| :--- | :--- | :---: |
| `mc绑定 <游戏ID>` / `mc绑定 [@用户/QQ] <游戏ID>` | 绑定自身账号或代他人绑定 MC 游戏角色名 | 群员 / 管理员 |
| `mc解绑` / `mc解绑 [@用户/QQ]` | 解除绑定的 MC 游戏角色名 | 群员 / 管理员 |
| `mc我的绑定` / `mc查看绑定 [@用户/QQ]` | 查看自身或他人绑定的 MC 游戏角色名 | 群员 |
| `mc私聊 <@用户/QQ/游戏ID> <内容>` | 向绑定的玩家或指定游戏ID发送游戏内私聊 (tellraw) | 群员 |
| `mc群服绑定 <服务器>` | 将当前群绑定到指定服务器 | 群员 |
| `mc群服解绑 <服务器>` | 解除当前群与指定服务器的绑定 | 群员 |
| `mc查看 [服务器]` | 查看服务器的详细配置与运行信息 | 群员 |
| `mc连接状态` / `mcws状态` | 查看所有服务器的反向 WS 连接在线状态 | 管理员 |
| `mc广播 [服务器] <内容>` | 向服务器发送屏幕大标题 (Title) 广播 | 管理员 |
| `mc公告 [服务器] <内容>` | 向服务器聊天栏发布广播文字 | 管理员 |
| `mc刷新定时公告` | 重新读取数据库并智能解析注册定时公告任务 | 管理员 |
| `mcrcon [服务器] <指令>` | 通过 WebSocket 向服务器执行控制台指令并返回回显 | RCON管理员 |
| `mc增加rcon管理员 [服务器] <QQ/@用户>` | 添加服务器 RCON 白名单管理员 | 管理员 |
| `mc删除rcon管理员 [服务器] <QQ/@用户>` | 移除服务器 RCON 白名单管理员 | 管理员 |
| `mc查看rcon管理员 [服务器]` | 查看服务器 RCON 白名单管理员列表 | 管理员 |
| `mc添加服务器` | 私聊多步会话添加/配置 MC 服务器 | 管理员 |
| `mc删除服务器 <服务器>` | 删除指定 MC 服务器配置及关联群绑定 | 管理员 |
| `mc删除旧表` | 清理插件旧数据表并提示重启以重新初始化数据库结构 | 管理员 |

| 待填坑 |
|:----------:|
|mc调用机器人指令|
|mc动作栏|
|playwright 渲染|
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
