# LocalMind-Data

LocalMind 应用的公开数据源，App 端从这里实时拉取：

| 文件 | 内容 | App 用途 |
| --- | --- | --- |
| `data/donors.json` | 捐献榜（名字/金额/base64 头像） | 关于页捐献榜 |
| `data/announcement.json` | 公告 | 启动弹窗 + 关于页展示 |
| `data/release.json` | 最新版本下发（versionCode/更新日志/是否强制） | 启动时更新检查 |

## 管理后台

**https://isnananya.github.io/LocalMind-Data/**

口令登录 + GitHub Fine-grained Token（只授权本仓库 Contents 读写，保存在浏览器 localStorage，不入库）。

后台功能：捐献榜增删改（头像上传自动压缩转 base64，不裁剪）、公告发布/下线、版本下发（可一键读取 LocalMind-Android 最新 Release 自动填充）。

## App 端读取地址

```
https://raw.githubusercontent.com/isnananya/LocalMind-Data/main/data/donors.json
https://raw.githubusercontent.com/isnananya/LocalMind-Data/main/data/announcement.json
https://raw.githubusercontent.com/isnananya/LocalMind-Data/main/data/release.json
```

## 注意事项

- 不要把任何 Token / 口令明文提交到本仓库
- 修改口令：后台 `docs/index.html` 里的 `GATE_HASH`（SHA-256）
