# E2E 测试说明

## 截图目录

Playwright E2E 测试运行后，截图保存在：

```
/tmp/store-ontology-e2e/
```

## 截图命名规则

| 文件名 | 对应测试阶段 |
|--------|-------------|
| `t1_initial.png` | T1 页面初始加载 |
| `t2_scrolled.png` | T2 滚动到底部定位输入框 |
| `t2_debug.png` | T2 诊断（输入框未找到时）|
| `t3_filled_{query前8字}.png` | T3 填入 query 后截图 |
| `t3_submitted_{query前8字}.png` | T3 点击发送后截图 |
| `t4_ai_reply.png` | T4 AI 回复（含流式响应等待）|
| `error_final.png` | 异常时的最终页面状态 |
| `pw_final.png` | 脚本结束前最终截图 |

## 查看截图

```bash
# 测试后查看所有截图
ls -lh /tmp/store-ontology-e2e/

# 复制截图到项目目录（方便分享）
cp /tmp/store-ontology-e2e/*.png ./tests/e2e/screenshots/
```

## 运行前检查截图目录

```bash
# 确认目录存在
ls /tmp/store-ontology-e2e/

# 清理旧截图（重新运行前）
rm /tmp/store-ontology-e2e/*.png
```
