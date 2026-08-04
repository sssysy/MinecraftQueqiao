# MinecraftQueqiao

<p align="center">
  <a href="https://github.com/Genshin-bots/gsuid_core"><img src="https://i.mcmod.cn/class/cover/20250211/1739280504_2_VMph.jpg" height="128" alt="MinecraftQueqiao"></a>
</p>
<h1 align="center">MinecraftQueqiao 0.1.0</h1>
<h4 align="center">基于 gsuid_core 和鹊桥的 minecraft 连接插件</h4>
<div align="center">
  <a href="https://docs.sayu-bot.com/" target="_blank">安装文档 (gscore)</a> &nbsp; · &nbsp;
  <a href="https://queqiao-docs.pages.dev/deploy/" target="_blank">安装文档 (QueQiao)</a> &nbsp; · &nbsp;
  <a href="https://github.com/Genshin-bots/gsuid_core" target="_blank">gsuid_core</a>
</div>

## 丨注意

> [!CAUTION]
> 插件目前仅支持正向 Websocket 连接，请务必在服务端开放相应端口。

## 丨安装提醒

> **注意：该插件为 [早柚核心(gsuid_core)](https://github.com/Genshin-bots/gsuid_core) 的扩展，具体安装方式可参考上方安装文档**
>
> **运行环境要求 Python `3.12+`**
>
> 🚧 项目快速迭代中 🚧

## 丨绑定 / 使用教程
#### 1. 前往 [Modrinth](https://modrinth.com/plugin/queqiao) 或 [CurseForge](https://www.curseforge.com/minecraft/mc-mods/queqiao) 下载并安装服务端对应的 `插件/Mod`。
#### 2. 配置 `config.yml` 中的 `websocket_server`

    ```yaml
    websocket_server:
      enable: true          # 是否启用
      host: "0.0.0.0"     # WebSocket Server 地址
      port: 8080            # WebSocket Server 端口
    ```

- 插件端配置文件位于 ./plugin/QueQiao/config.yml。
- 模组端配置文件位于 ./config/QueQiao/config.yml。

#### 3. 启动服务器，等待开启 `Websocket Server`
#### 4. 在 Gscore 中安装本插件
- 方法一：从 Gscore 网页控制台安装：`网页控制台 -> 插件商城 -> 从 URL 安装`
- 方法二：手动安装：下载此`MinecraftQueqiao`文件夹，并放置在`gsuid_core/plugins/`目录下。

#### 5. 在网页控制台中绑定服务器
1. 访问 Gscore `网页控制台 -> 数据库管理 -> MinecraftQueqiao -> 鹊桥添加服务器 -> 新增`
2. 填入服务器相关信息
3. 重启 Gscore / 执行 `mc刷新ws连接` 命令

#### 6. 在网页控制台开启相关事件订阅
- 访问 Gscore `网页控制台 -> 插件配置 -> MinecraftQueqiao -> 订阅事件`


## 丨其他

- 本项目仅供学习使用，请勿用于商业用途
- [GPL-3.0 License](LICENSE)
- [QueQiao Wiki](https://queqiao-docs.pages.dev/)

## 致谢

- [Wuyi 无疑](https://github.com/KimigaiiWuyi)
- [gsuid_core](https://github.com/Genshin-bots/gsuid_core)
- [鹊桥](https://www.mcmod.cn/class/18274.html)
