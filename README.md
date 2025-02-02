<div align="center">
  <h1>🎯 Serv00 & CT8 自动化保号脚本</h1>
  
  ![GitHub last commit](https://img.shields.io/github/last-commit/yourusername/Serv00_CT8_Auto_Login)
  ![GitHub issues](https://img.shields.io/github/issues/yourusername/Serv00_CT8_Auto_Login)
  ![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue)

  [![部署指南](https://img.shields.io/badge/部署指南-8A2BE2)](%23-🚀-快速部署指南)
  [![通知示例](https://img.shields.io/badge/通知示例-228B22)](%23-📨-通知示例)
  [![注意事项](https://img.shields.io/badge/注意事项-FF4500)](%23-⚠️-重要注意事项)

</div>

---

## 🚀 快速部署指南

### 1. Fork仓库
1. 访问[项目主页](https://github.com/yourusername/Serv00_CT8_Auto_Login)
2. 点击右上角 <kbd>Fork</kbd> 按钮
3. 选择目标账户/组织

### 2. 配置密钥
进入仓库 Settings → Secrets → Actions → New repository secret

| 密钥名称               | 示例值                                  | 获取方式                                |
|------------------------|---------------------------------------|----------------------------------------|
| `TELEGRAM_BOT_TOKEN`   | `123456:ABC-DEF1234ghIkl-zyx57W2v1u`  | 通过 @BotFather 创建机器人获取          |
| `TELEGRAM_CHAT_ID`     | `987654321`                           | 访问 `api.telegram.org/bot<TOKEN>/getUpdates` |
| `ACCOUNTS_JSON`        | 见下方格式                             | 按模板配置账户信息                      |

**账户配置模板**：
```json
[
  {
    "username": "serv00_user",
    "password": "your_strong_password",
    "panel": "panel11.serv00.com"
  },
  {
    "username": "ct8_user",
    "password": "another_strong_password",
    "panel": "panel.ct8.pl"
  }
]
```

### 3. 启用工作流
1. 进入仓库的 **Actions** 页面
2. 点击 **I understand my workflows, go ahead and enable them**
3. 工作流将根据预设计划自动运行（每3天UTC 00:00）

---

## 📨 通知示例
```markdown
📨 Serv00 & CT8 保号脚本运行报告
━━━━━━━━━━━━━━━━━━━━
🕘 北京时间: 2023-12-01 12:34:56
🌐 UTC时间: 2023-12-01 04:34:56
━━━━━━━━━━━━━━━━━━━━

📊 登录状态报告

🔹 服务商: CT8
👤 账号: user123
🕒 时间: 2023-12-01 12:34:56
✅ 状态: 登录成功
────────────────────
🔹 服务商: SERV00
👤 账号: example_user
🕒 时间: 2023-12-01 12:35:02
❌ 状态: 登录失败
────────────────────

🏁 所有账号操作已完成
```

---

## ⚠️ 重要注意事项
### 安全规范
- 🔐 禁止将Secrets提交到公开代码库
- 🔄 建议每90天轮换密码和API Token

### 运行配置
- ⏱ GitHub Actions免费版每月2000分钟
- ⚡ 推荐保持默认的3天执行周期
- 📆 UTC时间与本地时区转换需自行计算

### 故障排查
1. 检查Actions日志路径：
   ```
   https://github.com/[用户名]/[仓库名]/actions
   ```
2. 验证面板地址格式：
   - ✅ 正确格式：`panel11.serv00.com`
   - ❌ 错误格式：`http://panel11.serv00.com`

---

## 📜 协议声明
本项目采用 [MIT License](LICENSE)，禁止用于任何违法用途。服务商名称与logo是其所有者的商标。

> 遇到问题请提交 [Issue](https://github.com/yourusername/Serv00_CT8_Auto_Login/issues)
```
