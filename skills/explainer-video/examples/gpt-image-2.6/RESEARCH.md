# GPT Image 2.6 资料汇总（核实于 2026-11-06）

## 结论
- 已正式发布：**2026-11-04**。官方产品名是 **ChatGPT Images 2.6**。API 里没有单独的 `gpt-image-2.6`，只有两个模型：
  - `gpt-image-2.6-flare`：主打速度，适合海报、商品图等专业版式；quality=low 时**最快约 6 秒**出图（官方说的是最佳情况，不是常态）
  - `gpt-image-2.6-sunburst`：主打细节，在 medium/high 质量下**多次编辑之间的一致性更好**
- 官方称比 GPT-Image-2.5 **快 50%**（没有说明测试条件）。
- 覆盖范围：ChatGPT 和 Codex 的全部订阅档位（网页、桌面、移动端），API 同日上线。社区有人反馈 Codex 当时还没部署。

## 新功能
| 功能 | 在哪用 | 要点 |
|---|---|---|
| 动图 GIF | ChatGPT + API | 可从文字或图片生成，能调速度、逐帧修改。API 参数：`output_format:"gif"`，`frame_count` 2–16（默认 9），`frame_duration_ms` 20–2000（默认 200）。默认时长 9×200ms=1.8 秒 |
| 参考图保存复用 | ChatGPT | 存下自己、宠物、角色的参考图，下次直接复用，不用重新上传 |
| 标注编辑 Markup | ChatGPT + API | 在图上圈出要改的地方。API：`/v1/images/edits` 的 `markup` 字段，需要与原图同尺寸的透明 PNG，不能和 `mask` 同时用。不额外收费 |
| SVG 导出 | API | `output_format:"svg"`，必须 `n:1`，不支持流式输出，也不支持编辑。只输出静态矢量图 |
| 复杂度 complexity | API | 取值 `low/medium/high`，默认 high。低：适合简单修改；高：适合密集文字和复杂版式。不额外收费，但值越高越慢，也更容易改到不想改的地方 |

## 参数与价格
- quality：`low / medium / high / xhigh / max`
- 尺寸：宽高必须是 16 的倍数，长宽比在 1:3 到 3:1 之间，单边不超过 3840。超过 2560×1440 的分辨率属于实验性。
- 价格（每 1M token）：文本输入 $5，图像输入 $8，**图像输出 $30**。flare 和 sunburst 价格相同，和 2.5 也相同。
- 社区实测（开发者论坛，单个用户的测试）：同一提示词在 medium 质量下，输出 token 从 344（2.5）涨到 1136（2.6），所以实际单张成本可能更高。

## 榜单（第三方，均为初步数据，不同榜单分数不能直接比较）
- Arena 文生图（Medium 档）：Sunburst 2.6 得分 1409，排第 2；Flare 2.6 得分 1384，排第 4
- Arena 单图编辑：Sunburst 2.6 得分 1476，排第 3
- Rapidata 人类偏好：Sunburst 2.6 得分 1316，2.5 Sunburst 为 1221，Nano Banana 2.1 为 1123

## 示例代码（官方文档，标注编辑）
```python
result = client.images.edit(
    model="gpt-image-2.6-flare",
    image=("kitchen.webp", image, "image/webp"),
    markup=(overlay.name, markup, "image/png"),
    quality="medium",
    prompt="Recolor the striped vase inside the red circle to solid cobalt blue ...",
)
```

## 已知限制
复杂提示词可能需要约 2 分钟；文字位置仍可能不准；角色一致性仍会漂移；使用前需完成组织验证。

## 来源
- OpenAI 官网发布页 https://openai.com/index/introducing-images-2-6/（返回 403，内容经转载交叉核对）
- OpenAI API 更新日志 https://developers.openai.com/api/docs/changelog
- 图像生成指南 https://developers.openai.com/api/docs/guides/image-generation
- 价格页 https://developers.openai.com/api/docs/pricing
- 官方社区公告帖 https://community.openai.com/t/images-upgraded-introducing-chatgpt-images-2-6/1412901
- OpenAI 在 X 上的公告 https://x.com/OpenAI/status/2118124944928432327
- TestingCatalog https://www.testingcatalog.com/openai-launches-images-2-6-with-gifs-and-image-reference/
- Kingy AI（榜单汇总）https://kingy.ai/blog/gpt-image-2-6-sunburst-flare/
